# Probe evaluation (TO-164)

Labels the failure-mode probe run in `probes/results.jsonl` (build `naive-v1`).
The prompt is in [PROMPTS.md](../PROMPTS.md#probe-evaluation-prompt). Findings are in [EVAL.md](../EVAL.md).

## Files

| File | What it is |
|---|---|
| `expected.jsonl` | Expected answer and acceptance rule per question. Written and committed before any answer, citation or retrieved chunk in `probes/results.jsonl` was opened. |
| `fetch_sources.sh` | Downloads the EDGAR documents the expected answers come from. Needs `SEC_USER_AGENT`. |
| `numparse.py`, `test_numparse.py` | Figure parser used by the mechanical checks, with its tests (`uv run pytest eval`). |

## How `expected.jsonl` was built

Only three fields of `probes/results.jsonl` were read: `question`, `category` and `xbrl_reference` (plus `xbrl_note`),
and the run metadata (`timestamp`, `model`, `k`). Run date: 2026-11-21.

1. The five ingested 10-Qs were downloaded from EDGAR and converted with the project's own `html_to_text` and
   `chunk_text`. The chunk counts (59, 61, 185, 40, 22) match `probes/README.md`, so the text is the corpus text.
2. Each expected figure was read from the filing text. Every `sources[].line` is copied verbatim from that text by a
   script that fails if the line does not contain the figure. `chunk_index` is the 0-based position of the chunk(s)
   holding that line within the filing.
3. Tagged figures were checked against `data.sec.gov` companyfacts. All 19 XBRL references in `results.jsonl` match
   companyfacts on value, period and accession. One is stale for its question (q15, NVIDIA); see that record.
4. Figures with no companyfacts concept (Microsoft Cloud, segment figures, managed basis, non-GAAP EPS) come from the
   filing HTML only. Out-of-corpus references come from Microsoft's FY2026 10-K and Q3 FY2026 10-Q (companyfacts),
   Alphabet's 10-Q and NVIDIA's 8-K of 2026-11-17.

## Record fields

- `expected_kind`: `answer`, `answer_with_flag` (a correct answer must flag an ambiguity) or `refusal`
  (the answer is not in the corpus, so the only correct response is to say so).
- `in_corpus`: whether the expected figure is in an ingested filing.
- `expected`: the figure(s). `value` is in dollars (or dollars per share), `quantum` is the precision of the filed
  figure, `as_filed` is the text in the filing.
- `acceptable_if_labelled`: figures that are right only with the stated label (for example managed basis).
- `distractors`: wrong figures a misreading would produce, each with the kind of misread it would show.
- `must_flag`: what a correct answer has to make explicit, or null.
- `acceptance_rule`: what counts as correct for this question.
- `xbrl_reference_check`: result of checking the reference in `results.jsonl`.

## Rules that apply to every question

- A stated figure matches an expected one when the expected value rounds to it at the precision stated
  (`numparse.matches`): "$92.3 billion" matches 92,279 in a table in millions.
- Any period, unit or basis the answer attaches to a figure must be right. A right number with a wrong label is wrong.
- "Last quarter" is read as of the run date. For all five filers that is the quarter ended 2026-09-30.
- The outcome is judged on the figure the question asks for. A wrong figure in supporting context (a prior-year
  comparison, a growth rate) is quoted in the evidence and sent to human review, without changing the outcome.

## Outcome labels (per run)

| Label | Meaning |
|---|---|
| `correct` | Commits to the expected figure(s) with the right period, unit and basis, and meets `must_flag`. A warranted caveat does not change this. |
| `confident_wrong` | Commits to a figure, period, unit, basis or ranking that fails the rule, without saying it may not be what was asked. Includes a figure given as the answer to a question the corpus cannot answer. |
| `correct_refusal` | The expected answer is not in the corpus, the answer says so, and gives no figure as the answer. |
| `false_refusal` | The expected answer is in the corpus, and the answer says it is not available and gives no acceptable figure. |
| `hedged_ok` | Does not fully answer, but everything stated is accurate and correctly labelled, and the reason given for not answering fully is true of the retrieved chunks. |
| `hedged_not_ok` | Hedges where the expected figure was in the retrieved chunks, or hedges around a wrong figure, or lists candidates without identifying the expected one. |

## Cause labels (for every run that is not `correct` or `correct_refusal`)

- `retrieval_miss`: no retrieved chunk contains the expected figure.
- `misread`: the stated figure is in a retrieved chunk but is the wrong cell. One of `column`, `period`, `segment`,
  `basis`, `units`.
- `memory`: the stated figure is in no retrieved chunk.

A run can have two causes (a retrieval miss followed by a misread of what was retrieved).

## From runs to questions

The question is the unit. A question's outcome is its worst run, in this order:
`confident_wrong`, `false_refusal`, `hedged_not_ok`, `hedged_ok`, then `correct` or `correct_refusal`.
The number of runs showing that outcome (1/3, 2/3, 3/3) is reported next to it.
