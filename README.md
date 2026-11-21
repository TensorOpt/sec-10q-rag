# sec-10q-rag

Ask questions about SEC Form 10-Q quarterly reports filed this autumn and get answers cited back to the filings.

## How it works

1. **Find filings.** `ingest` queries EDGAR full-text search for 10-Q filings in a date range (default: September 1 to November 30 of the most recent autumn), optionally limited to a list of tickers.
2. **Extract text.** Each filing's primary HTML document is converted to plain text. Hidden inline XBRL is dropped and table rows become `Label | value | value` lines, so financial statements stay readable.
3. **Index.** Text is split into overlapping chunks of about 4,000 characters and stored in a local SQLite FTS5 index (`sec10q.db`).
4. **Retrieve.** `ask` ranks chunks with BM25. The company name column is weighted higher, so naming a company favors its filing, and adjacent word pairs from the question ("total revenue", "net interest income") count as phrases.
5. **Answer.** The top chunks go to Claude (`claude-opus-5-5`) as `search_result` blocks. Claude answers from them only, and its citations are printed as numbered sources linking to the filing on EDGAR.

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

# Or index every 10-Q filed in the window (about 5,000 filings; EDGAR search returns at most 10,000)
uv run sec-rag ingest

# Custom window or a sample
uv run sec-rag ingest --start 2026-10-01 --end 2026-10-31 --limit 50

# Ask
uv run sec-rag ask "What was Microsoft's total revenue for the quarter ended September 30, 2026?"
```

Example output shape:

```
Microsoft reported total revenue of $92.3 billion for the quarter ended September 30, 2026 [1].

Sources:
[1] MICROSOFT CORP (MSFT) 10-Q, period ending 2026-09-30, filed 2026-10-28
    https://www.sec.gov/Archives/edgar/data/789019/000119312526436133/msft-20260930.htm
```

Re-running `ingest` skips filings already in the index. Use `--db PATH` (before the subcommand) to pick a different index file.

## Limitations

- Retrieval is lexical (BM25), not semantic. Questions phrased with the filings' own terms ("net sales", "operating income") retrieve best.
- A question comparing several companies retrieves a single top-k list, which one company can dominate. Ask per company or raise `-k`.
- Companies whose fiscal quarter ended outside the window file a 10-K or nothing this autumn (Apple's September quarter is reported in its 10-K, for example), so they have no 10-Q to index.

## Development

```bash
uv run pytest
```

Tests use `httpx2.MockTransport` for EDGAR and the Anthropic API, so they run offline.
