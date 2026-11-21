"""Pull figures out of answers and filing text, and decide when two figures are the same number."""

import re
from dataclasses import dataclass

SCALES = {
    "trillion": 1e12, "billion": 1e9, "bn": 1e9, "b": 1e9,
    "million": 1e6, "mm": 1e6, "m": 1e6,
    "thousand": 1e3, "k": 1e3,
}

_NUMBER = re.compile(
    r"(?<![\w.,/\[-])"                                      # not inside a word, number, date or citation
    r"(?P<prefix>(?:[($\-−]\s?){0,3})"
    r"(?P<digits>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<close>\))?"
)
_SCALE = re.compile(
    r"[\s-]?(?:(?P<word>trillion|billion|million|thousand|bn|mm)\b|(?P<letter>[BMK])\b"
    r"|\s?\(?in (?P<unit>thousand|million|billion)s\b\)?)",
    re.IGNORECASE,
)
_PERCENT = re.compile(r"\s?(?:%|percent\b)", re.IGNORECASE)
_MONTH = re.compile(r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s$", re.IGNORECASE)
_YEAR = re.compile(r"(?:19|20)\d\d$")


@dataclass(frozen=True)
class Figure:
    value: float    # signed, in base units once any stated scale is applied
    quantum: float  # size of the last stated digit, in the same units
    kind: str       # "money", "percent" or "number"
    scaled: bool    # True when the text states the scale (million, billion, ...)
    raw: str


def parse_figures(text: str, table: bool = False) -> list[Figure]:
    """Figures stated in text. Dates, years, form names and citations are skipped.

    Bare integers ("282", "9") are skipped in prose and kept when table is True, because a filing's
    table cells carry neither a currency sign nor a scale.
    """
    figures = []
    for m in _NUMBER.finditer(text):
        prefix, digits = m["prefix"], m["digits"]
        end = m.end()
        value = float(digits.replace(",", ""))
        decimals = len(digits.partition(".")[2])
        quantum = 10.0 ** -decimals
        has_currency = "$" in prefix

        scale = _SCALE.match(text, end) if not m["close"] else None
        percent = None if scale else _PERCENT.match(text, end)
        if scale:
            factor = SCALES[(scale["word"] or scale["letter"] or scale["unit"]).lower()]
            # A lone letter only counts as a scale after a currency amount ("$92.3B", not "3 B shares").
            if scale["letter"] and not has_currency:
                scale = None
            else:
                value, quantum, end = value * factor, quantum * factor, scale.end()
        if not scale and not percent and re.match(r"-?[A-Za-z]", text[end:end + 2]):
            continue  # "10-Q", "8-K", "3D"
        plain = not (has_currency or scale or percent)
        if plain and "," not in digits and "." not in digits:
            is_date = _YEAR.match(digits) or _MONTH.search(text[max(0, m.start() - 12):m.start()])
            if not table or is_date:
                continue  # years, days of the month, counts
        if prefix.count("(") and m["close"] or "-" in prefix or "−" in prefix:
            value = -value

        kind = "percent" if percent else "number" if plain else "money"
        raw_end = percent.end() if percent else end
        figures.append(Figure(value, quantum, kind, bool(scale), text[m.start():raw_end].strip()))
    return figures


def _readings(figure: Figure, bare_scale: float):
    """A source figure as stated, and (for an unscaled table cell) in the filing's unit."""
    yield figure.value, figure.quantum
    if not figure.scaled and figure.kind != "percent" and bare_scale != 1:
        yield figure.value * bare_scale, figure.quantum * bare_scale


def matches(claim: Figure, source: Figure, bare_scale: float = 1) -> bool:
    """True when source, read at least as precisely as claim, rounds to claim. Sign is ignored.

    bare_scale is the unit of the filing's tables (1e6 for "in millions"), tried for source figures
    that carry no scale of their own.
    """
    if (claim.kind == "percent") != (source.kind == "percent"):
        return False
    for value, quantum in _readings(source, bare_scale):
        if quantum > claim.quantum * (1 + 1e-9):
            continue
        if abs(abs(claim.value) - abs(value)) <= claim.quantum / 2 * (1 + 1e-9):
            return True
    return False
