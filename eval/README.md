# Probe evaluation (TO-164)

Labels the failure-mode probe run in `probes/results.jsonl` (build `naive-v1`).
The prompt is in [PROMPTS.md](../PROMPTS.md#probe-evaluation-prompt). Findings are in [EVAL.md](../EVAL.md).

## Files

| File | What it is |
|---|---|
| `expected.jsonl` | Expected answer and acceptance rule per question. Written and committed before any answer, citation or retrieved chunk in `probes/results.jsonl` was opened. |
| `fetch_sources.sh` | Downloads the EDGAR documents the expected answers come from. Needs `SEC_USER_AGENT`. |
| `numparse.py`, `test_numparse.py` | Figure parser used by the mechanical checks, with its tests (`uv run pytest eval`). |
| `checks.py`, `test_checks.py` | Mechanical checks (context recall, groundedness, consistency) and their tests. `uv run python eval/checks.py` rewrites the two files below. |
| `checks.jsonl` | One row per run (63). |
| `consistency.jsonl` | One row per question (21). |
| `labels.jsonl` | Outcome, cause and one line of evidence per run (63), written by the labeller (a Claude model). |
| `summarize.py` | Joins labels and checks, rolls runs up to questions, prints the tables in `EVAL.md` and writes `review.jsonl`. |
| `review.jsonl` | Runs that need human review: every `confident_wrong`, every run where label and mechanical checks disagree, every run with a wrong figure or label in supporting context. |

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

## Mechanical checks

These read figures only. They cannot tell whether a figure is offered as the answer or as context, or whether its
period label is right. They are evidence for the labeller and a cross-check on the labels, not labels.

Figures are parsed with `numparse.py` after the CLI's `[n]` citation markers are removed (a marker can sit between
a number and its scale, as in "$201,944 [5] million"). A bare table cell is read in the filing's unit (millions for
MSFT, AMZN and JPM, thousands for CSV and NRC).

`checks.jsonl`, per run:

- `recall`: `all`, `some` or `none` of the expected in-corpus figures are in a retrieved chunk of the right filing;
  `n/a` when the expected answer is not in the corpus.
- `expected[].figure_rank`: rank of the first retrieved chunk of the right filing that contains the figure.
  `line_rank`: rank of the first chunk that contains one of the verbatim source lines in `expected.jsonl` (stricter).
  `cited`: whether a chunk holding the figure was cited.
  `stated`: `scaled` if the answer gives the figure with a scale word or as an exact dollar or per-share amount,
  `bare` if it only quotes the unscaled table cell, null if it does not give it.
- `acceptable_stated`, `distractors_stated`: the labelled-only figures and the known wrong figures that the answer
  mentions. A distractor mentioned as context (a prior-year comparison) still shows up here.
- `grounded`: `yes` if every figure in the answer is in a cited chunk or is derived (a difference, sum, ratio or
  percentage change of two figures that are); `uncited` if the unsupported figures are all in retrieved chunks the
  answer did not cite; `no` if some figure is in no retrieved chunk; `no_figures` if the answer states none.
  `ungrounded` lists the unsupported figures.
- `refusal_language`: the opening of the answer says the excerpts lack something.

`consistency.jsonl`, per question: whether the three runs state the same expected figures (`same_expected_stated`),
open with the same figure (`same_lead_figure`, compared on three significant digits whatever the scale), and how many
of the amounts mentioned appear in every run. `consistent` is true when the first two hold.

Known limits: a JPMorgan table headed "in billions" would be read in millions; a figure that happens to equal an
unrelated cell in a cited chunk counts as grounded; the check is per answer, not per sentence, so a figure is
grounded if any cited chunk has it.

## Outcome labels (per run)

| Label | Meaning |
|---|---|
| `correct` | Commits to the expected figure(s) with the right period, unit and basis, and meets `must_flag`. A warranted caveat does not change this. |
| `confident_wrong` | Commits to a figure, period, unit, basis or ranking that fails the rule, without saying it may not be what was asked. Includes a figure given as the answer to a question the corpus cannot answer. |
| `correct_refusal` | The expected answer is not in the corpus, the answer says so, and gives no figure as the answer. |
| `false_refusal` | The expected answer is in the corpus, and the answer says it is not available and gives no acceptable figure. |
| `hedged_ok` | Does not fully answer, but everything stated is accurate and correctly labelled, and the reason given for not answering fully is true of the retrieved chunks. |
| `hedged_not_ok` | Hedges where the expected figure was in the retrieved chunks, or hedges around a wrong figure, or lists candidates without identifying the expected one. |

Clarification added after the answers were read, because `false_refusal` and `hedged_ok` overlapped: a run is a
refusal when it gives none of the expected figures, and a hedge when it gives some of them (one company out of
three) or gives the expected figure but leaves the question open. A refusal that truthfully reports a retrieval
miss is still `false_refusal`: the label describes the system's result, not whether the generator behaved well.

Each `labels.jsonl` row has `outcome`, `cause` (a list, empty for `correct` and `correct_refusal`), `evidence`
(a verbatim quote from the answer and the source line it was checked against), and where needed `note` and
`context_issue`. A script checked that every answer quote is verbatim.

## Label and check disagreements

`summarize.py` flags a run when: it is labelled `correct` but does not state every expected figure, or an expected
figure was not retrieved, or a figure in it is supported only by an uncited or by no retrieved chunk; it is
labelled `confident_wrong` or `false_refusal` but states the expected figure; it is labelled a refusal but does not
open with refusal language, or the reverse; its cause is `retrieval_miss` but every expected figure was retrieved, or
the reverse; its cause is `memory` but every figure is in a cited chunk.

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
