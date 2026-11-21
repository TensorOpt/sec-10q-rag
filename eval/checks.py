"""Mechanical checks on the probe runs: context recall, groundedness and consistency.

    uv run python eval/checks.py            # writes eval/checks.jsonl and eval/consistency.jsonl

These are signals for the labeller, not labels. They read figures only: they cannot tell whether a figure
is offered as the answer or as context, or whether its period label is right.
"""

import json
import re
import sys
from itertools import permutations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from numparse import Figure, matches, parse_figures  # noqa: E402

ROOT = Path(__file__).parent.parent
# Unit of each ingested filing's tables (probes/README.md). Bare table cells are read in this unit.
TABLE_UNIT = {
    "0001193125-26-436133": 1e6,  # MSFT
    "0001018724-26-000040": 1e6,  # AMZN
    "0001628280-26-069523": 1e6,  # JPM
    "0001016281-26-000070": 1e3,  # CSV
    "0001437749-26-034887": 1e3,  # NRC
}
_CITATION = re.compile(r"\s?(?:\[\d+\])+")
_REFUSAL = re.compile(
    r"\b(?:don[’']t|do not|doesn[’']t|does not|isn[’']t|is not|aren[’']t|are not|cannot|can[’']t|not|no)\b"
    r"[^.\n]{0,80}\b(?:includ|contain|provid|available|shown|cover|report|disclos|state|give|answer|determin|say|mention)",
    re.IGNORECASE,
)


def strip_citations(answer: str) -> str:
    """Drop the "[n]" markers the CLI inserts, which can split a number from its scale ("$201,944 [5] million")."""
    return _CITATION.sub("", answer)


def answer_figures(answer: str) -> list[Figure]:
    return parse_figures(strip_citations(answer))


def refusal_language(answer: str) -> bool:
    """True when the opening of the answer says the excerpts lack something."""
    return bool(_REFUSAL.search(strip_citations(answer)[:400]))


def chunk_supports(claim: Figure, chunk: dict) -> bool:
    scale = TABLE_UNIT.get(chunk["filing"]["accession"], 1)
    return any(matches(claim, source, scale) for source in parse_figures(chunk["text"], table=True))


def first_rank(claim: Figure, chunks: list[dict], accessions: set[str] | None = None) -> int | None:
    """Rank of the first chunk that contains the figure, optionally only chunks of the given filings."""
    for chunk in sorted(chunks, key=lambda c: c["rank"]):
        if accessions and chunk["filing"]["accession"] not in accessions:
            continue
        if chunk_supports(claim, chunk):
            return chunk["rank"]
    return None


def _close(claim: Figure, value: float) -> bool:
    return abs(abs(claim.value) - abs(value)) <= claim.quantum / 2 * (1 + 1e-9)


def derived(claim: Figure, others: list[Figure], table_unit: float = 1) -> bool:
    """True when the figure is the difference, sum, ratio or percentage change of two of the other figures.

    The caller passes the figures that are supported by a cited chunk, so a figure is not excused by its own
    difference from another unsupported one.
    An unscaled figure quoted from a table ("100,256") is also tried in the table's unit.
    """
    values = []
    for o in others:
        if o is claim or o.kind == "percent":
            continue
        values.append((o, o.value))
        if not o.scaled and table_unit != 1:
            values.append((o, o.value * table_unit))
    for (fa, a), (fb, b) in permutations(values, 2):
        if fa is fb:
            continue
        if claim.kind == "percent":
            if b and (_close(claim, (a - b) / b * 100) or _close(claim, a / b * 100)):
                return True
        elif _close(claim, a - b) or _close(claim, a + b):
            return True
        elif b and claim.kind == "number" and _close(claim, a / b):
            return True
    return False


def as_figure(expected: dict) -> Figure:
    return Figure(expected["value"], expected["quantum"], "money", True, expected["as_filed"])


def stated(target: dict, figures: list[Figure], table_unit: float) -> str | None:
    """How the answer states a target figure: "scaled" (with a scale word, or as an exact dollar or per-share
    amount), "bare" (an unscaled number equal to the table cell, as when the answer quotes a table row) or None."""
    source = as_figure(target)
    amounts = [f for f in figures if f.kind != "percent"]
    if target["unit"] != "USD":  # per-share amounts carry no scale
        return "scaled" if any(matches(f, source) for f in amounts) else None
    if any(matches(f, source) for f in amounts if f.scaled or f.kind == "money" and f.value == target["value"]):
        return "scaled"
    if target.get("misread") == "units" or table_unit == 1:
        return None  # a units misread only shows in a figure that states its unit
    cell = Figure(target["value"] / table_unit, target["quantum"] / table_unit, "money", True, target["as_filed"])
    return "bare" if any(matches(f, cell) for f in amounts if not f.scaled) else None


def target_unit(target: dict) -> float:
    accessions = {s["accession"] for s in target.get("sources", [])}
    units = {TABLE_UNIT[a] for a in accessions if a in TABLE_UNIT}
    return units.pop() if len(units) == 1 else 1e6


def check_run(run: dict, expected: dict) -> dict:
    figures = answer_figures(run["answer"])
    chunks = run["retrieved_chunks"]
    cited_ids = {c["chunk_id"] for c in run["cited_sources"]}
    cited = [c for c in chunks if c["chunk_id"] in cited_ids]
    unit = next((target_unit(t) for t in expected["expected"] if t["sources"]), 1e6)  # the question's filing unit

    # Groundedness: does each figure in the answer appear in a cited chunk?
    in_cited = [any(chunk_supports(f, c) for c in cited) for f in figures]
    supported = [f for f, ok in zip(figures, in_cited) if ok]  # only these can be the inputs of a derived figure
    figure_rows = []
    for f, ok in zip(figures, in_cited):
        figure_rows.append({
            "raw": f.raw, "value": f.value, "kind": f.kind, "in_cited": ok,
            "retrieved_rank": first_rank(f, chunks),
            "derived": not ok and derived(f, supported, unit),
        })
    ungrounded = [r for r in figure_rows if not r["in_cited"] and not r["derived"]]
    # "uncited": every unsupported figure is in a retrieved chunk the answer did not cite.
    grounded = ("no_figures" if not figures else "yes" if not ungrounded
                else "uncited" if all(r["retrieved_rank"] for r in ungrounded) else "no")

    # Context recall: does a retrieved chunk contain the expected figure, and at what rank?
    expected_rows = []
    for target in expected["expected"]:
        accessions = {s["accession"] for s in target["sources"]}
        lines = [s["line"].strip("… ") for s in target["sources"]]
        line_ranks = [c["rank"] for c in chunks if any(line in c["text"] for line in lines)]
        figure_rank = first_rank(as_figure(target), chunks, accessions) if accessions else None
        holders = {c["chunk_id"] for c in chunks if c["filing"]["accession"] in accessions
                   and chunk_supports(as_figure(target), c)}
        expected_rows.append({
            "label": target["label"], "in_corpus": bool(target["sources"]),
            "figure_rank": figure_rank, "line_rank": min(line_ranks, default=None),
            "cited": bool(holders & cited_ids),
            "stated": stated(target, figures, target_unit(target)),
        })
    in_corpus = [r for r in expected_rows if r["in_corpus"]]
    found = [r for r in in_corpus if r["figure_rank"]]
    recall = "n/a" if not in_corpus else "all" if len(found) == len(in_corpus) else "some" if found else "none"

    def hits(key):
        out = []
        for target in expected.get(key, []):
            mode = stated(target, figures, target_unit(target) if target.get("sources") else unit)
            if mode:
                out.append({"what": target.get("label") or target["what"], "as_filed": target["as_filed"],
                            "mode": mode, **({"misread": target["misread"]} if "misread" in target else {})})
        return out

    lead = next((f for f in figures if f.kind != "percent"), None)
    return {
        "id": expected["id"], "run": run["run"],
        "refusal_language": refusal_language(run["answer"]),
        "recall": recall, "expected": expected_rows,
        "expected_stated": bool(expected_rows) and all(r["stated"] for r in expected_rows),
        "acceptable_stated": hits("acceptable_if_labelled"), "distractors_stated": hits("distractors"),
        "grounded": grounded, "n_figures": len(figures), "ungrounded": [r["raw"] for r in ungrounded],
        "lead_figure": lead.raw if lead else None, "lead_value": lead.value if lead else None,
        "figures": figure_rows,
    }


def _digits(value: float) -> str:
    """Three significant digits without the magnitude, so "$17,422" (a table cell) and "$17.4 billion" agree."""
    return f"{abs(value):.2e}".split("e")[0]


def consistency(question_id: str, runs: list[dict]) -> dict:
    """Same figure across the runs? Compares which expected figures each run states, the lead figure, and how
    many of the amounts in the answers appear in every run."""
    leads = [r["lead_value"] for r in runs]
    same_lead = len({None if v is None else _digits(v) for v in leads}) == 1
    patterns = [tuple(e["stated"] is not None for e in r["expected"]) for r in runs]
    sets = [{_digits(f["value"]) for f in r["figures"] if f["kind"] != "percent"} for r in runs]
    union, common = set.union(*sets), set.intersection(*sets)
    return {
        "id": question_id, "runs": len(runs),
        "same_expected_stated": len(set(patterns)) == 1, "expected_stated": [r["expected_stated"] for r in runs],
        "same_lead_figure": same_lead, "lead_figures": [r["lead_figure"] for r in runs],
        "amounts_in_every_run": len(common), "amounts_in_any_run": len(union),
        "same_refusal_language": len({r["refusal_language"] for r in runs}) == 1,
        "same_grounded": len({r["grounded"] for r in runs}) == 1,
        "consistent": same_lead and len(set(patterns)) == 1,
    }


def main() -> None:
    expected = {}
    for line in (ROOT / "eval" / "expected.jsonl").read_text().splitlines():
        row = json.loads(line)
        expected[row["question"]] = row
    rows = []
    for line in (ROOT / "probes" / "results.jsonl").read_text().splitlines():
        run = json.loads(line)
        rows.append(check_run(run, expected[run["question"]]))
    by_question: dict[str, list[dict]] = {}
    for row in rows:
        by_question.setdefault(row["id"], []).append(row)
    summary = [consistency(qid, runs) for qid, runs in by_question.items()]

    (ROOT / "eval" / "checks.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    (ROOT / "eval" / "consistency.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in summary))

    print("id   run recall figure_rank line_rank cited stated grounded refusal lead")
    for r in rows:
        e = r["expected"]
        print(f"{r['id']}  {r['run']}   {r['recall']:<5} {str([x['figure_rank'] for x in e]):<12} "
              f"{str([x['line_rank'] for x in e]):<12} {str([int(x['cited']) for x in e]):<9} "
              f"{str([x['stated'] or '-' for x in e]):<28} {r['grounded']:<10} {str(r['refusal_language']):<5} "
              f"{r['lead_figure']}")
    print("\nid   consistent same_lead same_expected amounts(all/any) lead_figures")
    for s in summary:
        print(f"{s['id']}  {str(s['consistent']):<10} {str(s['same_lead_figure']):<9} "
              f"{str(s['same_expected_stated']):<13} {s['amounts_in_every_run']:>3}/{s['amounts_in_any_run']:<11} "
              f"{s['lead_figures']}")


if __name__ == "__main__":
    main()
