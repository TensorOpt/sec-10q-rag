# Design: sec-10q-rag

Ticket TO-164: build a RAG system that answers questions about SEC 10-Q filings filed this autumn.

This document records why the system is built the way it is, what was traded away, and what to revisit. Guiding constraints from the ticket: TDD, DRY, YAGNI, prefer simple working solutions.

## Architecture

```
ingest:  EDGAR full-text search ──> primary 10-Q HTML ──> plain text ──> chunks ──> SQLite FTS5
ask:     question ──> BM25 top-k chunks ──> Claude (search_result blocks) ──> answer + numbered sources
```

| Module | Responsibility |
|---|---|
| `edgar.py` | Find 10-Q filings in a date range (optionally by CIK), map tickers to CIKs, download documents |
| `text.py` | HTML to plain text; split text into overlapping chunks |
| `store.py` | Persist filings and chunks; BM25 retrieval |
| `answer.py` | Build the Claude request; turn citations into numbered sources |
| `cli.py` | `sec-rag ingest` and `sec-rag ask`; default date window |

Each module has one job and a narrow interface (`Filing`, `Hit`, `Answer` dataclasses), which keeps tests small and lets any stage be swapped without touching the others.

## Decisions

### Language and tooling: Python, uv, pytest

The repository started empty apart from a Python `.gitignore`, so Python was the natural choice. uv manages dependencies and the lockfile. Runtime dependencies are three: `anthropic`, `beautifulsoup4`, `httpx2`.

### Filing discovery: EDGAR full-text search (`efts.sec.gov`)

Alternatives considered:

| Option | Why not chosen |
|---|---|
| Quarterly `full-index/form.idx` | Lists filings but not the primary document; would require fetching each full submission `.txt` (several MB, mostly XBRL and exhibits) or a second index lookup |
| `data.sec.gov/submissions` API | Has `primaryDocument`, but is per company, so "all 10-Qs filed this autumn" needs thousands of requests |
| Full-text search | One paginated query returns form, filing date, period, company and the primary document filename, and supports CIK filtering |

Trade-off: the full-text search endpoint is what EDGAR's own search UI uses but is not formally documented, so its response shape could change. Its result window is capped at 10,000 hits (EDGAR returns `Result window is too large ... must be less than or equal to: [10000]` beyond that). On 2026-11-21 the query for 10-Qs filed 2026-09-01 to 2026-11-30 reported 5,232 hits, so the cap is not binding for one season. Results are filtered to `file_type == "10-Q"` so exhibits are never indexed as filings.

SEC fair-access rules require an identifying User-Agent and at most 10 requests per second ([SEC: Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)). The client sleeps 0.11 s before each request and refuses to run without `SEC_USER_AGENT`. No default contact is embedded in the code, so nobody's identity is sent unknowingly.

### "This autumn": September 1 to November 30

Meteorological autumn of the most recent autumn (Jan to Aug resolves to the previous year). It captures the Q3 (September quarter) 10-Q season. Astronomical autumn (late September to December 21) was the alternative; both are defensible, so the default lives in one function (`cli.autumn`) and `--start/--end` override it.

### HTML to text: BeautifulSoup with table-aware rendering

10-Q primary documents are inline XBRL HTML. Two details matter for answer quality:

- The `ix:header` block and `display:none` elements hold machine-readable facts that are invisible to readers. They are removed so chunks contain only what a reader of the filing sees.
- Financial statements are tables. A naive `get_text()` puts every cell on its own line and separates `$`, values and closing parentheses. Each row is instead rendered as `Label | value | value`, with `$`, `)` and `%` re-attached to their numbers. Example from the Microsoft 10-Q: `Net income | $36,629 | $27,747`.

Block-level elements end with a newline; inline elements do not, so sentences split across styled `<span>`s stay intact.

### Chunking: line packing, about 4,000 characters, 400 characters of overlap

Lines (paragraphs and table rows) are packed whole into chunks of at most 4,000 characters; lines longer than that are wrapped at word boundaries. The trailing lines of a chunk (up to 400 characters) are repeated at the start of the next chunk so a table header or sentence near a boundary is not lost.

Trade-off: no structure-aware splitting by Item or note heading. It would give cleaner chunk boundaries but adds parsing that is fragile across filing agents' HTML. Revisit if answers frequently cite chunks that cut a table off from its header.

### Retrieval: SQLite FTS5 with BM25, no embeddings

This is the largest trade-off in the system.

Why lexical:

- Anthropic does not offer an embeddings endpoint. Semantic retrieval would need a second vendor (API key, network host, cost) or a local model download, both outside the ticket's "simple, working" bar.
- SQLite FTS5 ships with Python's standard library: no server, no extra dependency, one file on disk, BM25 ranking built in.
- 10-Q language is formulaic. Questions about financial line items usually share exact terms with the filing ("net interest income", "capital expenditures").

Tuning, each measured on the live index:

- **Company column weighted 5x.** The company name ("MICROSOFT CORP (MSFT)") is indexed as its own column, so a question that names a company favors that company's chunks.
- **Porter stemming** (`tokenize = 'porter unicode61'`), so "sales" matches "sale" and "increased" matches "increases".
- **Stopwords removed and adjacent word pairs added as phrase terms.** Plain BM25 over single words ranked Microsoft's income-statement chunk 34th for "What was Microsoft's total revenue this quarter?", because prose that repeats "revenue" scored higher. Adding the phrase `"total revenue"` moved it to 5th. Across five sample questions (Microsoft revenue and cash, Amazon capex and operating income, JPMorgan net interest income) the target chunk landed in the top 5 for each. These figures come from a manual spot check on an index of 8 filings ingested 2026-11-21, not a formal evaluation.

Known weaknesses:

- Paraphrased questions that do not share the filing's vocabulary retrieve worse than they would with embeddings.
- A question comparing several companies gets one shared top-k list, which one company can dominate.

The `Store.search(query, k) -> list[Hit]` interface is the seam for replacing or augmenting retrieval (hybrid BM25 plus embeddings, per-company quotas, reranking) without touching ingestion or answering.

### Generation: Claude Opus 5.5 with `search_result` blocks

- **Model:** `claude-opus-5-5`, the current default Opus model.
- **Grounding and citations:** each retrieved chunk is sent as a `search_result` content block (source = EDGAR URL, title = company, period, filing date) with citations enabled. Claude's citations come back as structured `search_result_location` objects pointing at the exact chunk, which the CLI renders as `[n]` markers and a numbered source list. This was preferred over asking the model to write `[n]` markers in free text, which cannot be verified against the inputs.
- **System prompt:** answer only from the provided excerpts, name the company and fiscal period for every figure, and say so when the excerpts do not contain the answer.
- **Effort `medium`**, set explicitly. The task is reading comprehension over supplied text, not open-ended reasoning.
- **Server-side refusal fallback** (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`): if the model declines, the API re-runs the request on a fallback model. Refusals on 10-Q questions should be rare; this is a cheap safety net and easy to remove. A refusal that survives the fallback is reported as such instead of raising.
- **No streaming.** Answers are short, the CLI prints once, and `max_tokens=16000` stays within non-streaming limits.
- **No API call without hits.** An empty index or a query with no matches returns a message telling the user to run `ingest`.

### HTTP client: `httpx2` everywhere

The Anthropic SDK 2.x uses `httpx2` and rejects `httpx` objects. Using `httpx2` for EDGAR as well keeps a single HTTP library and lets tests inject `httpx2.MockTransport` into both clients the same way.

### Ingestion behavior

- Idempotent: filings already in the index (by accession number) are skipped, so `ingest` can be re-run to pick up new filings.
- Re-adding a filing replaces its chunks instead of duplicating them.
- One failing filing is logged and skipped; a long run over thousands of documents does not abort on a single bad download or parse.

## Testing approach

Written test-first, one module at a time. All tests run offline:

- EDGAR and the Anthropic API are exercised through `httpx2.MockTransport`. The answer tests go through the real `anthropic` client, so request serialization, beta headers and citation parsing are tested against the SDK's own types rather than a hand-written fake.
- The store is tested against a real in-memory SQLite database, including a regression test for the phrase-ranking fix.
- The parser is tested on a small HTML fixture with the same features as real filings (hidden XBRL header, split spans, split currency cells).

Verified manually on 2026-11-21: live ingestion of Microsoft, Amazon, JPMorgan and five other filers. NVIDIA correctly returned no filing (its most recent 10-Q was filed 2026-08-26). Not yet verified: a live `ask` against the Claude API, because no API key was available in the development environment.

## Deliberately left out (YAGNI)

| Not built | Add when |
|---|---|
| Embeddings / hybrid retrieval | Paraphrased questions fail in practice |
| Metadata filters (company, date) on `ask` | Users need to scope questions explicitly beyond naming the company |
| Multi-company retrieval quotas | Comparison questions become a primary use case |
| 10-Q/A amendments, 10-K | The scope grows beyond original 10-Qs |
| XBRL fact extraction | Exact numeric answers need machine-readable values instead of text |
| Concurrency in ingestion | Full-season ingests are run regularly; the SEC rate limit caps the gain anyway |
| Web UI or API server | Someone other than a CLI user needs access |
| Answer-quality eval set | Before changing retrieval or prompts, to measure the change |

## Operational notes

- Index file: `sec10q.db` in the working directory (`--db` to change); ignored by git.
- Required environment: `SEC_USER_AGENT` for `ingest`; Anthropic credentials (for example `ANTHROPIC_API_KEY`) for `ask`.
- Cost: each `ask` sends about 8 chunks of up to 4,000 characters plus the question to `claude-opus-5-5`, billed at Anthropic's per-token rates ([pricing](https://www.anthropic.com/pricing)).
