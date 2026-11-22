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

## Probe evaluation prompt

The prompt for labelling the probe results (expected answers in `eval/expected.jsonl`, findings in `EVAL.md`):

```
TO-164: label the probe results and write EVAL.md.

Input: probes/results.jsonl (build naive-v1). Don't change src/,
tests/ or probes/.

1. Expected answers first. Read only the question field. For each
   question, work out the correct answer from the filing on EDGAR
   and from data.sec.gov XBRL: figure(s), period, unit, where it
   sits in the filing, and whether it's in the ingested corpus at
   all. Check the XBRL references in results.jsonl; don't trust
   them. Write an acceptance rule per question: what counts as
   correct, and whether a correct answer must flag an ambiguity
   (e.g. fiscal vs calendar quarter). Commit eval/expected.jsonl
   before opening any answer.

2. Mechanical checks, in a script under eval/. Test the number
   parser (commas, parentheses, millions vs billions, rounding).
   - Context recall: does a retrieved chunk contain the expected
     figure, and at what rank?
   - Groundedness: does each figure in the answer appear in a
     cited chunk?
   - Consistency: same figure across the 3 runs?

3. Label every run against its acceptance rule:
   - Outcome: correct, confident_wrong, correct_refusal,
     false_refusal, hedged_ok, hedged_not_ok
   - Cause, for wrong answers: retrieval_miss, misread (column,
     period, segment, basis, units), memory
   - One line of evidence quoting the answer and the source
   Put every confident_wrong, and every case where your label and
   the mechanical checks disagree, under "Needs human review".

4. Write EVAL.md:
   - What ran: build tag, models that answered, corpus, number of
     questions and runs, date
   - Method, stating that the labeller is a Claude model
   - Per-question table and outcome counts. The question is the
     unit, not the run.
   - Grounded × correct cross-tab
   - Per failure mode: reproduced in 3/3, 2/3, 1/3 or not, with
     the clearest example (question, answer excerpt, cited
     excerpt, correct figure and its source)
   - Limitations: the questions were chosen to break the system,
     so report no accuracy figure; small n; the labeller is from
     the same model family; a failure that doesn't reproduce may
     just be phrasing
   - Needs human review
   Write plainly. No em dashes.

Use conventional commits, e.g. docs(TO-164): add probe evaluation
findings. Commit after each step and push.

--

Also persist this prompt to @PROMPTS.md

Commit and push everything to main.
```

## Probe round 2 prompt

The prompt for the second probe round (questions in `probes/round2/questions.txt`, results in `probes/round2/results.jsonl`):

```
TO-164 probe round 2. Observation only: change nothing in src/
or tests/, and use the existing database.

0. If the naive-v1 tag isn't on the remote, tag the last commit
   before the probe results were added and push the tag.
1. Commit the questions below to probes/round2/questions.txt
   before running anything.
2. Ask each question exactly as written, 3 times. Don't rephrase,
   drop or add questions. Save every run to
   probes/round2/results.jsonl: question, run, answer, cited
   sources, the model that answered, and the retrieved chunks
   (rank, filing, chunk id, full text).
3. For numeric questions, add the matching XBRL value from
   data.sec.gov companyfacts (concept, period, unit) where one
   exists. Don't grade the answers.
4. Commit: chore(TO-164): add round 2 probe results. Push.

Report one table: question, the figure or claim each run gave,
cited source, XBRL reference.

Period
- What was Amazon's free cash flow last quarter?
- What was JPMorgan's cash flow from operating activities in the third quarter of 2026?
- What was NRC Health's operating cash flow last quarter?

Computed
- What was Amazon's operating margin last quarter?
- What share of Microsoft's revenue came from Microsoft Cloud last quarter?
- What was JPMorgan's efficiency ratio last quarter?
- By how many dollars did Amazon's net sales grow year over year last quarter?

Change
- By what percentage did Carriage Services' revenue change compared with the same quarter last year?
- Did NRC Health's net income rise or fall last quarter compared with a year earlier, and by how much?

False premise
- Why did Microsoft's revenue fall last quarter?
- Why did JPMorgan report a net loss last quarter?
- How much did Amazon's AWS segment lose last quarter?

Which figure
- What was Carriage Services' total debt at the end of last quarter?
- How many NRC Health shares were outstanding?

Facts outside the tables
- What did JPMorgan agree to pay for the Apple Card portfolio?
- Who signed Carriage Services' 10-Q as principal executive officer?

--

Also persist to @PROMPTS.md
```
