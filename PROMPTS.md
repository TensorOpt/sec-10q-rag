# Prompts

## Initial prompt

The prompt this RAG system was created from:

```
Ticket TO-164: Build a RAG system that answers questions
about SEC 10-Q filings filed this autumn.

- Follow TDD, DRY and YAGNI. Prefer simple, working solutions.
- Use conventional commits, e.g. feat(TO-164): <description>
- Commit and push as you go.
```

## Probe run prompt

The prompt for the failure-mode probe run (tag `naive-v1`, results in `probes/results.jsonl`):

```
TO-164 probe run. Observation only: change nothing in src/ or tests/.

1. Tag the current HEAD as naive-v1 and push the tag.
2. List the ingested filings: company, ticker, period end, fiscal
   year end, filing date, and the units each income statement uses.
   If none reports in thousands, ingest two small-cap 10-Qs from the
   same window before running anything.
3. Ask each question below exactly as written, 3 times, against the
   existing database. Save every run to probes/results.jsonl:
   question, run, answer, cited sources, the model that answered,
   and the retrieved chunks (rank, filing, chunk id, full text).
   If the CLI doesn't expose retrieval, call the existing functions
   from a scratch script outside the repo.
4. For numeric questions, add the matching XBRL value from
   data.sec.gov companyfacts (concept, period, unit) where one
   exists, as a reference for me to check. Don't grade the answers.
5. Commit: chore(TO-164): add failure-mode probe results. Push.

Report one table: question, the figure each run gave, cited
source, XBRL reference.

Period (Microsoft's fiscal year ends June 30)
- What was Microsoft's revenue in Q3 2026?
- What was Microsoft's revenue last quarter?
- What was Microsoft's revenue for fiscal year 2026?

Column (current vs prior year, quarter vs nine months)
- What was Amazon's operating income in the third quarter of 2025?
- What was Amazon's operating income in the third quarter of 2026?
- What were Amazon's net sales for the nine months ended September 30, 2026?
- What was JPMorgan's net interest income for the first nine months of 2026?

Wording
- What was Amazon's revenue last quarter?
- How much profit did Amazon make last quarter?
- What was Microsoft's top line last quarter?

Segment vs total
- What was Microsoft's cloud revenue last quarter?
- What was Amazon's operating income last quarter?

GAAP vs non-GAAP
- What was Microsoft's earnings per share last quarter?
- What was JPMorgan's revenue last quarter?

Not in the corpus, but mentioned in it
- What was NVIDIA's revenue last quarter?
- What was Alphabet's cloud revenue last quarter?
- How much did OpenAI lose last quarter?

Comparison
- Which made more operating income last quarter, Microsoft or Amazon?
- Rank Microsoft, Amazon and JPMorgan by net income for the quarter ended September 30, 2026.

Units
- What was <each thousands-reporting filer>'s revenue last quarter?

--

Also save this prompt to @PROMPTS.md, commit it, and the results also separately, push to main.
```
