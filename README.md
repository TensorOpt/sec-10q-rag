# sec-10q-rag

A question-answering system over SEC 10-Q filings, built by a coding agent from a short prompt, then probed with
questions designed to make it fail, then evaluated against expected answers that the evaluation prompt required to be
written from the question text only and committed before any answer was opened.

## What this is

Three terms used throughout:

- **10-Q**: the quarterly financial report a US public company files with the SEC.
- **RAG** (retrieval-augmented generation): find the passages in a document collection that look relevant to a
  question, give them to an LLM, and have it answer from those passages only, citing them.
- **BM25**: a standard keyword-ranking formula. It scores a passage by how many of the question's words it
  contains, giving rare words more weight. It matches words, not meanings.

The experiment had three steps:

1. **Build.** A coding agent built a RAG system for 10-Qs filed in autumn 2026 from this prompt
   ([PROMPTS.md](PROMPTS.md#initial-prompt)):
   ```
   Ticket TO-164: Build a RAG system that answers questions
   about SEC 10-Q filings filed this autumn.

   - Follow TDD, DRY and YAGNI. Prefer simple, working solutions.
   - Use conventional commits, e.g. feat(TO-164): <description>
   - Commit and push as you go.
   ```
2. **Probe.** The finished system was asked 37 questions in two rounds, 3 times each (111 runs). Each question
   was written to trigger a specific failure: the wrong period, the wrong table column, a segment figure passed
   off as a total, a company that is not in the index, and so on.
3. **Evaluate.** A labeller wrote the expected answer to every question from the filings themselves and committed
   it before opening any of the system's answers. It then labelled every run and ran mechanical checks over all
   of them.

The system itself is small. `ingest` downloads 10-Qs from EDGAR (the SEC's public filing database), converts each
to plain text, splits it into chunks of about 4,000 characters, and stores them in a local SQLite full-text index.
`ask` ranks the chunks with BM25, sends the top 8 to Claude, and prints Claude's answer with numbered citations
that link back to the filing on EDGAR.

## The experiment, step by step

### 1. The build

- **Prompt:** [PROMPTS.md](PROMPTS.md#initial-prompt), quoted above. PROMPTS.md also holds the later prompts
  for the probes and the evaluation, verbatim.
- **Choices and reasons:** [DESIGN.md](DESIGN.md). The largest trade-off was keyword retrieval (BM25 in SQLite)
  instead of embeddings, because Anthropic offers no embeddings endpoint, SQLite's full-text index ships with
  Python, and 10-Q wording is formulaic. The agent tuned retrieval with a manual spot check of five sample
  questions and recorded that no live `ask` against the Claude API was run during the build, because no API key
  was available.
- **Build tag:** `naive-v1`, commit `0f21a35`, the last commit that changed `src/`. Both probe rounds ran against
  this code.

### 2. The probes ([probes/](probes/))

The index held five 10-Qs for the quarter ended 2026-09-30: Microsoft, Amazon and JPMorgan, plus two smaller
companies that report in thousands rather than millions, Carriage Services and NRC Health. That is 367 chunks.
The index was built at the start of round 1 ([probes/round1/README.md](probes/round1/README.md)).

| Round | Questions | Runs | What it targeted |
|---|---|---|---|
| [1](probes/round1/) | 21 | 63 | Fiscal vs calendar quarters (Microsoft's fiscal year ends June 30), prior-year and nine-month columns, informal wording ("profit", "top line"), segment vs total, GAAP vs non-GAAP (standard accounting figures vs company-adjusted ones), companies mentioned in the filings but not in the index, comparisons, units |
| [2](probes/round2/) | 16 | 48 | Cash flow periods, figures the model must compute (margins, shares, ratios), year-over-year changes, false premises, choosing between similar figures, facts outside the tables |

Each round's folder has `questions.txt`, `results.jsonl` and a README. Every run in `results.jsonl` records the
answer, its citations, the model that answered and all 8 retrieved chunks in full. Numeric questions carry the
matching XBRL value from the SEC's companyfacts data (XBRL is the machine-readable tagging of figures in a filing)
as a reference.

### 3. The evaluation

- **Method and labels:** [eval/README.md](eval/README.md). For each question, `eval/expected.jsonl` gives the
  figure, period, unit, the verbatim line in the filing and an acceptance rule. Each round's expected answers were
  committed before any answer from that round was opened (commits `a6fe6c0` and `a6e291d`). Mechanical checks
  (`eval/checks.py`) measure context recall (was the expected figure retrieved, and at what rank), groundedness
  (is every figure in the answer in a cited chunk) and consistency across the three runs. Each run is labelled
  `correct`, `correct_refusal`, `false_refusal`, `hedged_ok`, `hedged_not_ok` or `confident_wrong`, with a cause
  for failures (`retrieval_miss`, `misread` or `memory`). A question's outcome is its worst run.
- **Findings:** [EVAL.md](EVAL.md).

### Models by role

| Role | Model | Effort |
|---|---|---|
| Build agent | Claude Opus 5.5 | high |
| Answering, inside the system ([src/sec_rag/answer.py](src/sec_rag/answer.py)) | Claude Opus 5.5 (`claude-opus-5-5`) | medium |
| Labeller (expected answers, checks, labels) | Claude Fable 5.2 | high |

## What it found

Numbers are from [EVAL.md](EVAL.md).

1. **No made-up figures.** No run gave a confident wrong answer: 0 of 111 runs, 0 of 37 questions. No answer
   contained a figure absent from the retrieved chunks, apart from differences and percentages computed from
   figures that were there. All 6 questions with no answer in the corpus were refused correctly in every run, and
   no false premise was accepted.
2. **Every failure traced to retrieval.** All 30 runs that were neither correct nor a correct refusal have the
   cause `retrieval_miss`. No run was labelled misread or memory. When the expected figure, or every input of a
   computed one, was retrieved (19 questions), the answer was correct in every run. Example: for "What was
   Microsoft's revenue in Q3 2026?", all 8 retrieved chunks came from Amazon. Amazon's 10-Q contains the string
   "Q3 2026" 46 times and Microsoft's contains it 0 times, and the retriever scores "q3 2026" as a phrase. The
   system said it had no Microsoft figure, while Microsoft's revenue ($92,279 million) was in the index.
3. **False refusals read exactly like correct ones.** 7 questions (21 runs) were refused although the answer was
   in the index. Compare "The search results don't include Amazon's profit for the quarter." (Amazon's net income,
   $20,685 million, was in the index) with "The search results don't include Alphabet's cloud revenue." (Alphabet
   was not). Nothing in the wording separates the failure from the correct behavior.
4. **The grounding check flagged none of the failures.** In EVAL.md's words: "Every failure is fully grounded,
   because the failures are refusals and hedges that quote what was retrieved. A grounding check would not have
   caught any of them." It also passed the one mislabelled figure found in round 2, because the number was in the
   cited chunk and only its label was wrong.
5. **The build shipped without an eval, by its own account.** DESIGN.md lists "Answer-quality eval set" under
   "Deliberately left out (YAGNI)", to be added "Before changing retrieval or prompts, to measure the change."

## What the findings don't show

From EVAL.md's Limitations:

- **No accuracy rate.** The questions were chosen to break the system. They are not a sample of what users ask,
  and the counts should not be turned into an accuracy figure.
- **Small n.** 37 questions, 5 filings, one corpus build, two days. Each failure mode has 2 to 4 questions. The
  three runs of a question share one retrieval result, so a retrieval failure seen 3/3 was observed once.
- **Untested is not passed.** In 10 questions retrieval failed before the model reached the trap the question was
  written for.
- **Same-family labeller, no human check yet.** The labeller is a Claude model from the same family as the
  answering model, and it also wrote the expected answers and the rules. Shared blind spots would not show up. No
  label has been checked by a person; the runs that most need it are listed under "Needs human review" in EVAL.md.
- **One corpus, one build, one point in time.** Five 10-Qs for one quarter, build `naive-v1`, run on 2026-11-21
  and 2026-11-22.

## Repository map

| Path | What it is |
|---|---|
| `README.md` | This file |
| `PROMPTS.md` | The prompts for the build, the probes and the evaluation, verbatim |
| `DESIGN.md` | The build agent's decisions, trade-offs and what it left out |
| `EVAL.md` | Evaluation findings |
| `src/sec_rag/` | The system: EDGAR client, HTML to text and chunking, index and retrieval, answering, CLI |
| `tests/` | Unit tests for the system, offline |
| `probes/` | Probe questions and results, one folder per round |
| `eval/` | Expected answers, mechanical checks, labels and the scripts that produce EVAL.md's tables |
| `pyproject.toml`, `uv.lock` | Project definition and locked dependencies |
| `LICENSE` | Apache License 2.0 |

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
export SEC_USER_AGENT="Your Name or Company you@example.com"  # SEC requires an identifying User-Agent
export ANTHROPIC_API_KEY=...                                  # only needed for `ask`
```

## Usage

```bash
# Index this autumn's 10-Qs for specific companies
uv run sec-rag ingest --tickers MSFT,AMZN,JPM

# Or index every 10-Q filed in the window (EDGAR reported 5,232 hits for 2026-09-01 to 2026-11-30 on 2026-11-21;
# EDGAR search returns at most 10,000)
uv run sec-rag ingest

# Custom window or a sample
uv run sec-rag ingest --start 2026-10-01 --end 2026-10-31 --limit 50

# Ask (-k sets how many chunks are retrieved; default 8)
uv run sec-rag ask "What was Amazon's operating income in the third quarter of 2025?"
```

The default window is September 1 to November 30 of the most recent autumn. Re-running `ingest` skips filings
already in the index. Use `--db PATH` (before the subcommand) to pick an index file other than `sec10q.db`.

Example output, from probe round 1 (question q04, run 2), abridged:

```
Amazon's operating income for the third quarter of 2025 was **$17.4 billion** ($17,422 million). This figure comes from the prior-year comparison in Amazon's 10-Q for the quarter ended September 30, 2026.

The filing reports that operating income increased from $17.4 billion in Q3 2025 to $28.1 billion in Q3 2026 [7].

[...]

Sources:
[7] AMAZON COM INC (AMZN) 10-Q, period ending 2026-09-30, filed 2026-10-30
    https://www.sec.gov/Archives/edgar/data/1018724/000101872426000040/amzn-20260930.htm
```

## Development

```bash
uv run pytest                     # system tests (tests/); EDGAR and the Anthropic API are mocked, so they run offline
uv run pytest eval                # tests for the evaluation's number parser and checks
uv run python eval/checks.py      # re-run the mechanical checks; rewrites eval/checks.jsonl and eval/consistency.jsonl
uv run python eval/summarize.py   # print EVAL.md's tables; rewrites eval/review.jsonl
```

## System limitations

From [DESIGN.md](DESIGN.md):

- Retrieval is lexical (BM25), not semantic. Questions phrased with the filings' own terms ("net sales",
  "operating income") retrieve best; paraphrases retrieve worse.
- A question comparing several companies retrieves a single top-k list, which one company can dominate. Ask per
  company or raise `-k`.
- Chunks are cut by size, not by section, so a table can be split from its header or its total line.
- Only original 10-Qs are indexed, not amendments (10-Q/A) or annual reports (10-K). A company with no 10-Q filed
  in the window has nothing to index: NVIDIA's most recent 10-Q, for example, was filed 2026-08-26.
- `ask` has no company or date filters. Naming the company in the question is the only way to scope it.
- Filing discovery uses EDGAR's full-text search endpoint, which is not formally documented and returns at most
  10,000 results per query.

## License

Apache License 2.0. See [LICENSE](LICENSE).

Built by TensorOpt ([tensoropt.ai](https://tensoropt.ai)), independent search and retrieval evaluation.
