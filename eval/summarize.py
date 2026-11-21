"""Join the labels with the mechanical checks, roll runs up to questions and list what needs human review.

    uv run python eval/summarize.py         # prints the tables used in EVAL.md, writes eval/review.jsonl
"""

import json
from collections import Counter
from pathlib import Path

EVAL = Path(__file__).parent
WORST_FIRST = ["confident_wrong", "false_refusal", "hedged_not_ok", "hedged_ok", "correct", "correct_refusal"]
ANSWERED = {"correct", "confident_wrong"}
REFUSED = {"correct_refusal", "false_refusal"}


def load(name: str) -> list[dict]:
    return [json.loads(line) for line in (EVAL / name).read_text().splitlines()]


def disagreements(label: dict, check: dict) -> list[str]:
    """Ways a label and the mechanical checks for the same run contradict each other."""
    outcome, causes = label["outcome"], label["cause"]
    out = []
    if outcome == "correct" and not check["expected_stated"]:
        out.append("labelled correct, but the answer does not state every expected figure")
    if outcome in ("confident_wrong", "false_refusal") and check["expected_stated"]:
        out.append(f"labelled {outcome}, but the answer states the expected figure(s)")
    if outcome == "correct_refusal" and check["expected_stated"]:
        out.append("labelled correct_refusal, but the answer states the out-of-corpus figure")
    if outcome in REFUSED and not check["refusal_language"]:
        out.append(f"labelled {outcome}, but the answer does not open with refusal language")
    if outcome in ANSWERED and check["refusal_language"]:
        out.append(f"labelled {outcome}, but the answer opens with refusal language")
    if "retrieval_miss" in causes and check["recall"] == "all":
        out.append("cause retrieval_miss, but every expected figure is in a retrieved chunk")
    if outcome in ("false_refusal", "hedged_ok") and "retrieval_miss" not in causes and check["recall"] != "all":
        out.append(f"labelled {outcome} without retrieval_miss, but an expected figure was not retrieved")
    if outcome == "correct" and check["recall"] not in ("all", "n/a"):
        out.append("labelled correct, but an expected figure is in no retrieved chunk")
    if outcome == "correct" and check["grounded"] in ("no", "uncited"):
        where = "no retrieved chunk" if check["grounded"] == "no" else "retrieved chunks that were not cited"
        out.append(f"labelled correct, but {len(check['ungrounded'])} figure(s) are supported only by {where}: "
                   + ", ".join(check["ungrounded"]))
    if "memory" in causes and check["grounded"] == "yes":
        out.append("cause memory, but every figure is in a cited chunk")
    return out


def question_outcome(outcomes: list[str]) -> tuple[str, int]:
    worst = min(outcomes, key=WORST_FIRST.index)
    return worst, outcomes.count(worst)


def main() -> None:
    expected = {r["id"]: r for r in load("expected.jsonl")}
    checks = {(r["id"], r["run"]): r for r in load("checks.jsonl")}
    consistent = {r["id"]: r for r in load("consistency.jsonl")}
    labels = load("labels.jsonl")
    by_question: dict[str, list[dict]] = {}
    for label in labels:
        by_question.setdefault(label["id"], []).append(label)

    review = []
    for label in labels:
        check = checks[(label["id"], label["run"])]
        reasons = disagreements(label, check)
        if label["outcome"] == "confident_wrong":
            reasons.insert(0, "confident_wrong")
        if "context_issue" in label:
            reasons.append("wrong supporting context: " + label["context_issue"])
        if reasons:
            review.append({"id": label["id"], "run": label["run"], "question": expected[label["id"]]["question"],
                           "outcome": label["outcome"], "reasons": reasons, "evidence": label["evidence"]})
    (EVAL / "review.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in review))

    print("## Per question\n")
    print("| # | Category | Question | Expected | In corpus | Recall (rank) | Runs 1, 2, 3 | Question outcome | Grounded | Same expected figure | Same lead figure |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    question_outcomes = {}
    for qid, runs in by_question.items():
        e = expected[qid]
        cs = [checks[(qid, r["run"])] for r in runs]
        outcome, n = question_outcome([r["outcome"] for r in runs])
        question_outcomes[qid] = outcome
        figures = "; ".join(f["as_filed"] for f in e["expected"]) or "none"
        ranks = sorted({", ".join(str(x["figure_rank"] or "miss") for x in c["expected"]) for c in cs})
        recall = "n/a" if cs[0]["recall"] == "n/a" else f"{cs[0]['recall']} ({' / '.join(ranks)})"
        in_corpus = {True: "yes", False: "no"}.get(e["in_corpus"], str(e["in_corpus"]))
        print(f"| {qid} | {e['category']} | {e['question']} | {figures} | {in_corpus} | {recall} | "
              f"{', '.join(r['outcome'] for r in runs)} | {outcome} {n}/3 | {', '.join(c['grounded'] for c in cs)} | "
              f"{'yes' if consistent[qid]['same_expected_stated'] else 'no'} | "
              f"{'yes' if consistent[qid]['same_lead_figure'] else 'no'} |")

    print("\n## Outcome counts (questions)\n")
    counts = Counter(question_outcomes.values())
    print("| Outcome | Questions | Which |")
    print("|---|---|---|")
    for outcome in WORST_FIRST:
        ids = [q for q, o in question_outcomes.items() if o == outcome]
        print(f"| {outcome} | {counts[outcome]} | {', '.join(ids)} |")
    print(f"| total | {sum(counts.values())} | |")
    print("\nRuns:", dict(Counter(r["outcome"] for r in labels)))
    print("Causes (runs):", dict(Counter(c for r in labels for c in r["cause"])))

    print("\n## Grounded x outcome (questions)\n")
    def grounded_of(qid):
        states = {checks[(qid, r["run"])]["grounded"] for r in by_question[qid]}
        for state in ("no", "uncited", "yes", "no_figures"):
            if state in states:
                return state
    rows = ["yes", "uncited", "no", "no_figures"]
    cols = [o for o in WORST_FIRST if counts[o]]
    table = Counter((grounded_of(q), o) for q, o in question_outcomes.items())
    print("| Grounded (worst run) | " + " | ".join(cols) + " | total |")
    print("|---|" + "---|" * (len(cols) + 1))
    for g in rows:
        print(f"| {g} | " + " | ".join(str(table[(g, o)]) for o in cols) + f" | {sum(table[(g, o)] for o in cols)} |")
    print("| total | " + " | ".join(str(counts[o]) for o in cols) + f" | {sum(counts.values())} |")

    print("\n## Grounded x outcome (runs)\n")
    table = Counter((checks[(r["id"], r["run"])]["grounded"], r["outcome"]) for r in labels)
    run_counts = Counter(r["outcome"] for r in labels)
    print("| Grounded | " + " | ".join(cols) + " | total |")
    print("|---|" + "---|" * (len(cols) + 1))
    for g in rows:
        print(f"| {g} | " + " | ".join(str(table[(g, o)]) for o in cols) + f" | {sum(table[(g, o)] for o in cols)} |")
    print("| total | " + " | ".join(str(run_counts[o]) for o in cols) + f" | {len(labels)} |")

    print("\n## Consistency\n")
    for qid, c in consistent.items():
        if not c["consistent"] or not c["same_grounded"]:
            print(f"- {qid}: lead figures {c['lead_figures']}, expected stated {c['expected_stated']}, "
                  f"same grounded {c['same_grounded']}")

    print("\n## Needs human review\n")
    for r in review:
        print(f"- {r['id']} run {r['run']} ({r['outcome']}): " + "; ".join(r["reasons"]))


if __name__ == "__main__":
    main()
