# Probe round 2 (TO-164)

Same database (`sec10q.db`: MSFT, AMZN, JPM, CSV, NRC; see [../round1/README.md](../round1/README.md#corpus)) and same
harness as round 1: each question in `questions.txt` asked 3 times, exactly as written, `k=8`, through
`Store.search` and `answer()` from a scratch script outside the repo. Nothing in `src/` or `tests/` changed.
The prompt is in [PROMPTS.md](../../PROMPTS.md#probe-round-2-prompt).

`results.jsonl` uses the round 1 fields. In `xbrl_reference`, entries whose `label` starts with
"input, not the asked figure" are components for computed or comparative questions, not the asked value;
`xbrl_note` explains gaps (non-GAAP measures, year-to-date-only cash flows, dimensional segment data).
Answers are not graded.
