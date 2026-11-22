# Probe round 1 (TO-164)

Observation run against tag `naive-v1`. Nothing in `src/` or `tests/` was changed.
The prompt is in [PROMPTS.md](../../PROMPTS.md#probe-round-1-prompt). `questions.txt` lists the questions as asked:
the prompt's "Units" placeholder resolved to the two thousands-reporting filers below. It was written after the run.

## Corpus

There was no `sec10q.db` before this run, so it was built with the existing CLI
(`sec-rag ingest --tickers MSFT,AMZN,JPM`, then `--tickers CSV,NRC`), default window 2026-09-01 to 2026-11-30.
All three named filers report in millions, so two small-cap 10-Qs that report in thousands were added
(public float from the filers' latest `dei:EntityPublicFloat`: Carriage Services $699M, NRC Health $195M).

| Company | Ticker | Period end | Fiscal year end | Filed | Income statement units | Chunks |
|---|---|---|---|---|---|---|
| Microsoft Corp | MSFT | 2026-09-30 (Q1 FY2027) | June 30 | 2026-10-28 | In millions, except per share amounts | 59 |
| Amazon.com Inc | AMZN | 2026-09-30 | December 31 | 2026-10-30 | in millions, except per share data | 61 |
| JPMorgan Chase & Co | JPM | 2026-09-30 | December 31 | 2026-11-03 | in millions, except per share data | 185 |
| Carriage Services Inc | CSV | 2026-09-30 | December 31 | 2026-11-05 | in thousands, except per share data | 40 |
| NRC Health | NRC | 2026-09-30 | December 31 | 2026-11-04 | In thousands, except for per share amounts | 22 |

Fiscal year ends come from `data.sec.gov/submissions`. Amazon's income statement lists the prior year column first (2025 | 2026).

## Method

Each question was asked 3 times, exactly as written, with `k=8` (the CLI default). The CLI prints only the
answer and sources, so a scratch script outside the repo called `Store.search` and `answer()` directly and
read the model name from the API response. Chunk ids are `chunks.rowid` in `sec10q.db`.
"Units" used the two thousands-reporting filers by name.

## `results.jsonl` fields

`category`, `question`, `run`, `answer`, `cited_sources` (citation number, chunk id, filing),
`model_requested`, `model` (from the response), `stop_reason`, `usage`, `k`,
`retrieved_chunks` (rank, filing, chunk id, full text), `timestamp`,
`xbrl_reference` (companyfacts concept, period, unit, value, form, accession; empty where no concept exists)
and `xbrl_note` where it is empty. XBRL values are references only; answers are not graded.
