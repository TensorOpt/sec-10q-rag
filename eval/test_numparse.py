"""Tests for the figure parser used by the mechanical probe checks."""

import pytest

from numparse import matches, parse_figures


def values(text, table=False):
    return [f.value for f in parse_figures(text, table)]


def one(text):
    (figure,) = parse_figures(text)
    return figure


# --- commas -----------------------------------------------------------------

def test_commas_are_thousands_separators():
    assert values("Total revenue | $92,279 | $77,673") == [92279, 77673]
    assert values("net sales of $584,069 million") == [584_069e6]
    assert values("$1,234,567.89") == [1234567.89]


def test_a_comma_followed_by_a_space_does_not_join_numbers():
    assert values("were $1,234, $5,678 and $91.5") == [1234, 5678, 91.5]


# --- parentheses and signs --------------------------------------------------

def test_accounting_parentheses_are_negative():
    assert values("Other income (expense), net | (4,923) | 282", table=True) == [-4923, 282]
    assert values("$(1,234)") == [-1234]
    assert values("($1,234)") == [-1234]


def test_minus_signs_are_negative():
    assert values("-1,234.5 and −2,345.5") == [-1234.5, -2345.5]


def test_a_parenthetical_restatement_is_not_negative():
    assert values("revenue of $92.3 billion ($92,279 million)") == [92.3e9, 92_279e6]


# --- millions vs billions ---------------------------------------------------

@pytest.mark.parametrize("text, value", [
    ("$92.3 billion", 92.3e9),
    ("$92,279 million", 92_279e6),
    ("$100,256 thousand", 100_256e3),
    ("$1.2 trillion", 1.2e12),
    ("$92.3B", 92.3e9),
    ("$92.3 bn", 92.3e9),
    ("$38.4M", 38.4e6),
    ("$250K", 250e3),
    ("92.3-billion-dollar", 92.3e9),
    ("$100,256 (in thousands)", 100_256e3),
    ("$92,279 (in millions)", 92_279e6),
])
def test_scale_words(text, value):
    figure = one(text)
    assert figure.value == pytest.approx(value)
    assert figure.scaled and figure.kind == "money"


def test_millions_and_billions_are_not_confused():
    million, billion = parse_figures("$201,944 million versus $201,944 billion")
    assert billion.value == pytest.approx(1000 * million.value)
    assert not matches(billion, million)


def test_bare_table_numbers_take_the_filing_unit_only_when_matching():
    claim = one("$92.3 billion")
    cell = one("92,279")
    assert cell.value == 92279 and not cell.scaled
    assert matches(claim, cell, bare_scale=1e6)
    assert not matches(claim, cell, bare_scale=1e3)
    assert not matches(claim, cell)


def test_thousands_filer_read_as_millions_does_not_match():
    cell = one("Total revenue | $100,256")
    assert matches(one("$100.3 million"), cell, bare_scale=1e3)
    assert matches(one("$100,256 thousand"), cell, bare_scale=1e3)
    assert not matches(one("$100,256 million"), cell, bare_scale=1e3)
    assert not matches(one("$100.3 billion"), cell, bare_scale=1e3)


def test_bare_numbers_also_match_unscaled_for_per_share_amounts():
    assert matches(one("$4.92 per diluted share"), one("Diluted | $4.92"), bare_scale=1e6)


# --- rounding ---------------------------------------------------------------

@pytest.mark.parametrize("claim, ok", [
    ("$92.3 billion", True),
    ("$92.28 billion", True),
    ("$92.279 billion", True),
    ("$92 billion", True),
    ("$92.2 billion", False),
    ("$92.4 billion", False),
    ("$92.27 billion", False),
    ("$93 billion", False),
])
def test_a_claim_matches_a_source_that_rounds_to_it(claim, ok):
    assert matches(one(claim), one("$92,279"), bare_scale=1e6) is ok


def test_half_way_values_round_either_way():
    source = one("$1,250 million")
    assert matches(one("$1.2 billion"), source)
    assert matches(one("$1.3 billion"), source)


def test_a_coarser_source_does_not_support_a_more_precise_claim():
    assert not matches(one("$92,279 million"), one("$92.3 billion"))
    assert matches(one("$92.3 billion"), one("$92.3 billion"))


def test_quantum_is_the_last_stated_digit():
    assert one("$92.3 billion").quantum == pytest.approx(0.1e9)
    assert one("$92,279 million").quantum == pytest.approx(1e6)
    assert one("$4.92").quantum == pytest.approx(0.01)


def test_matching_ignores_sign():
    assert matches(one("a net loss of $1.2 billion"), one("(1,234)"), bare_scale=1e6)


# --- percent ----------------------------------------------------------------

def test_percentages():
    up, down = parse_figures("up 19% from 2025, margin 13.9 percent")
    assert (up.value, up.kind) == (19, "percent")
    assert (down.value, down.kind) == (13.9, "percent")
    assert not matches(one("$19 million"), up)


# --- things that are not figures --------------------------------------------

@pytest.mark.parametrize("text", [
    "the quarter ended September 30, 2026",
    "fiscal year 2026 and FY2026",
    "Form 10-Q and 8-K",
    "Q3 2026 [1][2]",
    "the first 9 months, 3 segments",
    "Note 13",
])
def test_dates_years_form_names_and_citations_are_skipped(text):
    assert parse_figures(text) == []


def test_table_cells_keep_bare_integers_but_not_dates():
    text = "Three Months Ended September 30, | 2026 | 2025\nInterest expense | 282 | 9"
    assert values(text) == []
    assert values(text, table=True) == [282, 9]


def test_a_year_with_a_currency_sign_or_scale_is_a_figure():
    assert values("$2,026 million and $2026") == [2026e6, 2026]


def test_raw_text_is_kept_for_evidence():
    assert one("revenue was $92.3 billion [1]").raw == "$92.3 billion"
