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


def disagreements(label: dict, check: dict, expected: dict) -> list[str]:
    """Ways a label and the mechanical checks for the same run contradict each other."""
    outcome, causes = label["outcome"], label["cause"]
    # An answer that rejects a false premise opens with "did not", which the refusal check cannot tell apart.
    rejects_premise = (expected.get("must_flag") or "").startswith("The premise")
    out = []
    if outcome == "correct" and not check["expected_stated"]:
        out.append("labelled correct, but the answer does not state every expected figure")
    if outcome in ("confident_wrong", "false_refusal") and check["expected_stated"]:
        out.append(f"labelled {outcome}, but the answer states the expected figure(s)")
    if outcome == "correct_refusal" and check["expected_stated"]:
        out.append("labelled correct_refusal, but the answer states the out-of-corpus figure")
    if outcome in REFUSED and not check["refusal_language"]:
        out.append(f"labelled {outcome}, but the answer does not open with refusal language")
    if outcome in ANSWERED and check["refusal_language"] and not rejects_premise:
        out.append(f"labelled {outcome}, but the answer opens with refusal language")
    if "retrieval_miss" in causes and check["recall"] == "all":
        out.append("cause retrieval_miss, but every expected figure is in a retrieved chunk")
    if outcome in ("false_refusal", "hedged_ok") and "retrieval_miss" not in causes and check["recall"] != "all":
        out.append(f"labelled {outcome} without retrieval_miss, but an expected figure was not retrieved")
    if outcome == "correct" and check["recall"] not in ("all", "n/a"):
        out.append("labelled correct, but an expected figure (or an input of a computed one) is in no retrieved chunk")
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


def table(header: list[str], rows: list[list]) -> None:
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))
    for row in rows:
        print("| " + " | ".join(str(cell) for cell in row) + " |")


def main() -> None:
    expected = {r["id"]: r for r in load("expected.jsonl")}
    checks = {(r["id"], r["run"]): r for r in load("checks.jsonl")}
    consistent = {r["id"]: r for r in load("consistency.jsonl")}
    labels = load("labels.jsonl")
    by_question: dict[str, list[dict]] = {}
    for label in labels:
        assert label["round"] == expected[label["id"]]["round"] == checks[(label["id"], label["run"])]["round"]
        by_question.setdefault(label["id"], []).append(label)
    rounds = sorted({e["round"] for e in expected.values()})
    scopes = [(f"round {n}", [q for q in by_question if expected[q]["round"] == n]) for n in rounds]
    scopes.append(("both rounds", list(by_question)))

    review = []
    for label in labels:
        check = checks[(label["id"], label["run"])]
        reasons = disagreements(label, check, expected[label["id"]])
        if label["outcome"] == "confident_wrong":
            reasons.insert(0, "confident_wrong")
        if "context_issue" in label:
            reasons.append("wrong supporting context: " + label["context_issue"])
        if "judgment" in label:
            reasons.append("labeller's judgment call: " + label["judgment"])
        if reasons:
            review.append({"id": label["id"], "round": label["round"], "run": label["run"],
                           "question": expected[label["id"]]["question"], "outcome": label["outcome"],
                           "reasons": reasons, "evidence": label["evidence"]})
    (EVAL / "review.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in review))

    question_outcomes = {q: question_outcome([r["outcome"] for r in runs])[0] for q, runs in by_question.items()}

    def grounded_of(qid):
        states = {checks[(qid, r["run"])]["grounded"] for r in by_question[qid]}
        return next(state for state in ("no", "uncited", "yes", "no_figures") if state in states)

    for name, ids in scopes[:-1]:
        print(f"\n## Per question, {name}\n")
        rows = []
        for qid in ids:
            e, runs = expected[qid], by_question[qid]
            cs = [checks[(qid, r["run"])] for r in runs]
            outcome, n = question_outcome([r["outcome"] for r in runs])
            figures = "; ".join(f["as_filed"] for f in e["expected"]) or "none"
            if e.get("expected_match") == "any":
                figures = figures.replace("; ", " or ")
            ranks = sorted({", ".join(str(x or "miss") for x in c["recall_ranks"]) for c in cs})
            recall = "n/a" if cs[0]["recall"] == "n/a" else f"{cs[0]['recall']} ({' / '.join(ranks)})"
            in_corpus = {True: "yes", False: "no"}.get(e["in_corpus"], str(e["in_corpus"]))
            rows.append([qid, e["category"], e["question"], figures, in_corpus, recall,
                         ", ".join(r["outcome"] for r in runs), f"{outcome} {n}/3",
                         ", ".join(c["grounded"] for c in cs),
                         "yes" if consistent[qid]["same_expected_stated"] else "no",
                         "yes" if consistent[qid]["same_lead_figure"] else "no"])
        table(["#", "Category", "Question", "Expected", "In corpus", "Recall (rank)", "Runs 1, 2, 3",
               "Question outcome", "Grounded", "Same expected figure", "Same lead figure"], rows)

    print("\n## Outcome counts (questions)\n")
    table(["Outcome"] + [name for name, _ in scopes] + ["Which"],
          [[o] + [sum(question_outcomes[q] == o for q in ids) for _, ids in scopes]
           + [", ".join(q for q in by_question if question_outcomes[q] == o)] for o in WORST_FIRST]
          + [["total"] + [len(ids) for _, ids in scopes] + [""]])

    print("\n## Outcome counts (runs)\n")
    table(["Outcome"] + [name for name, _ in scopes],
          [[o] + [sum(r["outcome"] == o for q in ids for r in by_question[q]) for _, ids in scopes] for o in WORST_FIRST]
          + [["total"] + [sum(len(by_question[q]) for q in ids) for _, ids in scopes]])
    print("\n## Causes (runs)\n")
    causes = sorted({c for r in labels for c in r["cause"]})
    table(["Cause"] + [name for name, _ in scopes],
          [[c] + [sum(c in r["cause"] for q in ids for r in by_question[q]) for _, ids in scopes] for c in causes])

    states = ["yes", "uncited", "no", "no_figures"]
    for name, ids in scopes:
        cols = [o for o in WORST_FIRST if any(question_outcomes[q] == o for q in ids)]
        print(f"\n## Grounded x outcome (questions), {name}\n")
        cross = Counter((grounded_of(q), question_outcomes[q]) for q in ids)
        table(["Grounded (worst run)"] + cols + ["total"],
              [[g] + [cross[(g, o)] for o in cols] + [sum(cross[(g, o)] for o in cols)] for g in states]
              + [["total"] + [sum(cross[(g, o)] for g in states) for o in cols] + [len(ids)]])
        print(f"\n## Grounded x outcome (runs), {name}\n")
        runs = [r for q in ids for r in by_question[q]]
        cross = Counter((checks[(r["id"], r["run"])]["grounded"], r["outcome"]) for r in runs)
        table(["Grounded"] + cols + ["total"],
              [[g] + [cross[(g, o)] for o in cols] + [sum(cross[(g, o)] for o in cols)] for g in states]
              + [["total"] + [sum(cross[(g, o)] for g in states) for o in cols] + [len(runs)]])

    print("\n## Consistency\n")
    for qid, c in consistent.items():
        if not c["consistent"] or not c["same_grounded"]:
            print(f"- {qid} (round {c['round']}): lead figures {c['lead_figures']}, expected stated "
                  f"{c['expected_stated']}, same grounded {c['same_grounded']}")

    print("\n## Needs human review\n")
    for r in review:
        print(f"- {r['id']} run {r['run']} (round {r['round']}, {r['outcome']}): " + "; ".join(r["reasons"]))


if __name__ == "__main__":
    main()
