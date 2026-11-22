from checks import (answer_figures, check_run, chunk_supports, consistency, derived, first_rank, refusal_language,
                    stated, strip_citations)
from numparse import parse_figures

MSFT, CSV = "0001193125-26-436133", "0001016281-26-000070"


def chunk(rank, accession, text, chunk_id=None):
    return {"rank": rank, "chunk_id": chunk_id or rank, "filing": {"accession": accession}, "text": text}


def claim(text):
    (figure,) = answer_figures(text)
    return figure


def target(value, quantum, as_filed, accession=MSFT, line="", **extra):
    sources = [{"accession": accession, "line": line}] if accession else []
    return {"label": as_filed, "value": value, "quantum": quantum, "unit": "USD", "as_filed": as_filed,
            "sources": sources, **extra}


def test_a_citation_marker_does_not_split_a_number_from_its_scale():
    assert strip_citations("net sales of $201,944 [5] million, up 12% [3][5].") == "net sales of $201,944 million, up 12%."
    assert [f.value for f in answer_figures("$201,944 [5] million")] == [201944e6]


def test_refusal_language_is_read_from_the_opening():
    assert refusal_language("**The search results don't include Microsoft's revenue for Q3 2026.**")
    assert refusal_language("The excerpts do not contain NVIDIA's revenue.")
    assert refusal_language("**The filings don't say how much OpenAI lost last quarter.** OpenAI is private.")
    assert not refusal_language("Amazon's operating income was $28.1 billion in Q3 2026 [1].")


def test_a_table_cell_supports_a_rounded_claim_in_the_filing_unit():
    income = chunk(1, MSFT, "(In millions)\nTotal revenue | 92,279 | 77,673")
    assert chunk_supports(claim("$92.3 billion"), income)
    assert chunk_supports(claim("$92,279 million"), income)
    assert not chunk_supports(claim("$92.3 million"), income)
    assert not chunk_supports(claim("$93.2 billion"), income)


def test_a_thousands_filer_is_not_read_in_millions():
    income = chunk(1, CSV, "Total revenue | 100,256 | 102,742")
    assert chunk_supports(claim("$100.3 million"), income)
    assert not chunk_supports(claim("$100.3 billion"), income)


def test_first_rank_can_be_limited_to_the_right_filing():
    chunks = [chunk(1, CSV, "Other | 92,279"), chunk(2, MSFT, "prose only"), chunk(3, MSFT, "Total revenue | 92,279")]
    assert first_rank(claim("$92,279 million"), chunks, {MSFT}) == 3
    assert first_rank(claim("$92,279 million"), [chunks[1]]) is None


def test_derived_figures_are_differences_sums_and_percentage_changes():
    now, change, percent, before = answer_figures("Revenue was $100.3 million, down $2.4 million, or 2.3%, from "
                                                  "$102.7 million.")
    assert derived(change, [now, before])
    assert derived(percent, [now, before])
    assert not derived(change, [now])
    assert not derived(claim("$5.0 million"), [now, before])


def test_an_unsupported_figure_is_not_excused_by_its_own_difference():
    row = check_run(run("Revenue was $82.9 billion, $9.4 billion below the $92.3 billion [2] reported now.", CHUNKS, [2]),
                    EXPECTED)
    assert row["ungrounded"] == ["$82.9 billion", "$9.4 billion"] and row["grounded"] == "no"


def test_derived_reads_a_quoted_table_row_in_the_table_unit():
    figures = answer_figures("Total revenue | 100,256 | 102,742 (in thousands). That is a decline of about $2.5 million.")
    assert derived(figures[-1], figures, 1e3)
    assert not derived(figures[-1], figures)


def test_stated_tells_a_scaled_figure_from_a_quoted_table_cell():
    revenue = target(100256e3, 1e3, "100,256", CSV)
    assert stated(revenue, answer_figures("about $100.3 million"), 1e3) == "scaled"
    assert stated(revenue, answer_figures("$100,256 thousand"), 1e3) == "scaled"
    assert stated(revenue, answer_figures("Total revenue | 100,256 | 102,742"), 1e3) == "bare"
    assert stated(revenue, answer_figures("about $102.7 million"), 1e3) is None


def test_a_units_misread_needs_a_stated_unit():
    as_millions = target(100256e6, 1e6, "100,256", None, misread="units")
    as_dollars = target(100256, 1, "100,256", None, misread="units")
    quoted = answer_figures("Total revenue | 100,256 | 102,742, about $100.3 million")
    assert stated(as_millions, quoted, 1e3) is None and stated(as_dollars, quoted, 1e3) is None
    assert stated(as_millions, answer_figures("revenue of $100,256 million"), 1e3) == "scaled"
    assert stated(as_millions, answer_figures("revenue of $100.3 billion"), 1e3) == "scaled"
    assert stated(as_dollars, answer_figures("revenue of $100,256"), 1e3) == "scaled"


def test_per_share_amounts_match_without_a_scale():
    eps = {"label": "diluted EPS", "value": 4.92, "quantum": 0.01, "unit": "USD/share", "as_filed": "$4.92", "sources": []}
    assert stated(eps, answer_figures("diluted EPS of $4.92"), 1e6) == "scaled"
    assert stated(eps, answer_figures("basic EPS of $4.93"), 1e6) is None


def run(answer, chunks, cited):
    return {"run": 1, "answer": answer, "retrieved_chunks": chunks, "cited_sources": [{"chunk_id": c} for c in cited]}


EXPECTED = {"id": "q", "expected": [target(92279e6, 1e6, "92,279", MSFT, "Total revenue | 92,279 | 77,673")],
            "distractors": [target(77673e6, 1e6, "77,673", None, what="prior year", misread="column")]}
CHUNKS = [chunk(1, MSFT, "Microsoft Cloud revenue increased 30% to $63.9 billion."),
          chunk(2, MSFT, "(In millions)\nTotal revenue | 92,279 | 77,673")]


def test_check_run_reports_recall_rank_and_grounding():
    row = check_run(run("Revenue was $92.3 billion [2], up from $77.7 billion [2].", CHUNKS, [2]), EXPECTED)
    assert row["recall"] == "all" and row["expected"][0]["figure_rank"] == 2 and row["expected"][0]["line_rank"] == 2
    assert row["expected"][0]["cited"] and row["expected_stated"] and row["grounded"] == "yes"
    assert [d["misread"] for d in row["distractors_stated"]] == ["column"]


def test_a_figure_in_an_uncited_chunk_is_uncited_and_one_in_no_chunk_is_ungrounded():
    uncited = check_run(run("Revenue was $92.3 billion [1].", CHUNKS, [1]), EXPECTED)
    assert uncited["grounded"] == "uncited" and uncited["ungrounded"] == ["$92.3 billion"]
    memory = check_run(run("Revenue was $82.9 billion [2].", CHUNKS, [2]), EXPECTED)
    assert memory["grounded"] == "no" and not memory["expected_stated"]


def test_a_retrieval_miss_and_an_answer_without_figures():
    row = check_run(run("The excerpts do not include total revenue.", CHUNKS[:1], []), EXPECTED)
    assert row["recall"] == "none" and row["grounded"] == "no_figures" and row["refusal_language"]


def test_consistency_compares_lead_figures_whatever_their_scale():
    def row(answer):
        return check_run(run(answer, CHUNKS, [2]), EXPECTED)
    same = consistency("q", [row("Total revenue | 92,279 [2]"), row("$92.3 billion [2]"), row("$92,279 million [2]")])
    assert same["consistent"] and same["same_lead_figure"]
    mixed = consistency("q", [row("$92.3 billion [2]"), row("$77.7 billion [2]"), row("$92.3 billion [2]")])
    assert not mixed["consistent"] and mixed["expected_stated"] == [True, False, True]


def test_a_unit_note_after_a_year_is_not_an_amount():
    assert parse_figures("Operating income for Q3 2025 (in millions) was $17,422.")[0].value == 17422


# --- round 2: percentages, computed answers, text answers ----------------------------------------------------

AMZN = "0001018724-26-000040"
SALES = target(201944e6, 1e6, "201,944", AMZN, "Total net sales | 180,169 | 201,944")
INCOME = target(28076e6, 1e6, "28,076", AMZN, "Operating income | 17,422 | 28,076")
MARGIN = {"id": "m", "expected": [{"label": "operating margin", "value": 13.903, "quantum": 0.001, "unit": "percent",
                                   "kind": "percent", "as_filed": "13.9%, computed", "sources": []}],
          "inputs": [INCOME, SALES],
          "distractors": [{"value": 9.67, "quantum": 0.01, "unit": "percent", "kind": "percent", "as_filed": "9.7%",
                           "what": "prior year", "misread": "column"}]}
STATEMENT = chunk(1, AMZN, "(in millions)\nTotal net sales | 180,169 | 201,944\nOperating income | 17,422 | 28,076")


def test_a_percentage_target_is_matched_against_percentages_only():
    margin = MARGIN["expected"][0]
    assert stated(margin, answer_figures("an operating margin of about 13.9%"), 1e6) == "scaled"
    assert stated(margin, answer_figures("roughly 14%"), 1e6) == "scaled"
    assert stated(margin, answer_figures("$13.9 billion, up 9.7%"), 1e6) is None


def test_a_computed_answer_is_grounded_and_recall_is_judged_on_its_inputs():
    row = check_run(run("Operating income of $28,076 million [1] on net sales of $201,944 million [1] is 13.9%.",
                        [STATEMENT], [1]), MARGIN)
    assert row["recall"] == "all" and [r["figure_rank"] for r in row["inputs"]] == [1, 1]
    assert row["expected_stated"] and row["grounded"] == "yes" and row["lead_figure"] == "13.9%"
    miss = check_run(run("The margin was 9.7%.", [chunk(1, AMZN, "Total net sales | 180,169 | 201,944")], [1]), MARGIN)
    assert miss["recall"] == "some" and not miss["expected_stated"] and miss["grounded"] == "no"
    assert [d["misread"] for d in miss["distractors_stated"]] == ["column"]


def test_derived_figures_can_combine_three_inputs():
    ocf, capex, proceeds, fcf = answer_figures("$42,422 million less $77,259 million plus $1,381 million is "
                                               "-$33,456 million")
    assert derived(fcf, [ocf, capex, proceeds])
    assert not derived(fcf, [ocf, proceeds])


def test_any_one_expected_figure_is_enough_when_the_record_says_so():
    record = {"id": "c", "expected_match": "any", "expected": [
        target(582e3, 1e3, "582, computed", None),
        {"label": "percent", "value": 14.12, "quantum": 0.01, "unit": "percent", "kind": "percent",
         "as_filed": "14.1%", "sources": []}]}
    assert check_run(run("Net income rose about 14%.", [], []), record)["expected_stated"]
    assert not check_run(run("Net income fell 53%.", [], []), record)["expected_stated"]
    del record["expected_match"]
    assert not check_run(run("Net income rose about 14%.", [], []), record)["expected_stated"]


def test_a_text_target_is_found_in_the_answer_and_in_a_chunk():
    signer = {"label": "signer", "kind": "text", "text": "John Enwright", "unit": "text", "as_filed": "John Enwright",
              "sources": [{"accession": CSV, "line": "Date: | November 5, 2026 | /s/ John Enwright"}]}
    record = {"id": "s", "expected": [signer],
              "distractors": [{"kind": "text", "text": "Metzger", "unit": "text", "as_filed": "Steven D. Metzger",
                               "what": "COO", "misread": "basis"}]}
    block = chunk(3, CSV, "SIGNATURES\nDate: | November 5, 2026 | /s/ John Enwright\n(Principal Financial Officer)")
    row = check_run(run("It was signed by John Enwright [3], not Steven D. Metzger.", [block], [3]), record)
    assert row["expected"][0]["stated"] == "text" and row["expected"][0]["figure_rank"] == 3 and row["recall"] == "all"
    assert row["expected"][0]["cited"] and [d["what"] for d in row["distractors_stated"]] == ["COO"]
    assert check_run(run("The excerpts do not show a signature.", [], []), record)["recall"] == "none"


def test_a_question_with_no_expected_figure_has_no_recall_and_states_nothing():
    row = check_run(run("The excerpts do not state a purchase price.", [STATEMENT], []), {"id": "r", "expected": []})
    assert row["recall"] == "n/a" and not row["expected_stated"] and row["grounded"] == "no_figures"
