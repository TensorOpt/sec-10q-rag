"""Command line interface: `sec-rag ingest` builds the index, `sec-rag ask` answers questions."""

import argparse
import os
from collections.abc import Callable
from datetime import date

import anthropic

from sec_rag.answer import Answer, answer
from sec_rag.edgar import Edgar, Filing, make_http_client
from sec_rag.store import Store
from sec_rag.text import chunk_text, html_to_text

DEFAULT_DB = "sec10q.db"


def autumn(today: date) -> tuple[date, date]:
    """Meteorological autumn (September 1 to November 30) of the most recent autumn."""
    year = today.year if today.month >= 9 else today.year - 1
    return date(year, 9, 1), date(year, 11, 30)


def ingest(edgar: Edgar, store: Store, filings: list[Filing], log: Callable[[str], None] = print) -> int:
    """Download, chunk and index filings not yet in the store. Returns how many were indexed."""
    indexed = 0
    for i, filing in enumerate(filings, 1):
        label = f"[{i}/{len(filings)}] {filing.company} filed {filing.filed}"
        if store.has(filing.accession):
            continue
        try:
            chunks = chunk_text(html_to_text(edgar.fetch(filing.url)))
        except Exception as error:  # one bad filing must not stop a long ingest run
            log(f"{label}: skipped ({error})")
            continue
        store.add(filing, chunks)
        indexed += 1
        log(f"{label}: {len(chunks)} chunks")
    return indexed


def format_answer(result: Answer) -> str:
    if not result.sources:
        return result.text
    lines = [result.text, "", "Sources:"]
    for n, hit in result.sources.items():
        f = hit.filing
        lines += [f"[{n}] {f.company} 10-Q, period ending {f.period}, filed {f.filed}", f"    {f.url}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sec-rag", description=__doc__)
    parser.add_argument("--db", default=DEFAULT_DB, help=f"index file (default: {DEFAULT_DB})")
    commands = parser.add_subparsers(dest="command", required=True)

    start, end = autumn(date.today())
    ingest_cmd = commands.add_parser("ingest", help="download and index 10-Q filings from EDGAR")
    ingest_cmd.add_argument("--tickers", help="comma-separated tickers, e.g. MSFT,AMZN (default: all filers)")
    ingest_cmd.add_argument("--start", type=date.fromisoformat, default=start, help=f"default: {start}")
    ingest_cmd.add_argument("--end", type=date.fromisoformat, default=end, help=f"default: {end}")
    ingest_cmd.add_argument("--limit", type=int, help="maximum number of filings")

    ask_cmd = commands.add_parser("ask", help="answer a question from the indexed filings")
    ask_cmd.add_argument("question")
    ask_cmd.add_argument("-k", type=int, default=8, help="number of excerpts to retrieve (default: 8)")

    args = parser.parse_args(argv)

    if args.command == "ingest":
        user_agent = os.environ.get("SEC_USER_AGENT")
        if not user_agent:
            parser.error("set SEC_USER_AGENT to 'Your Name or Company email@example.com' (required by the SEC)")
        edgar = Edgar(make_http_client(user_agent))
        ciks = edgar.ciks_for_tickers(args.tickers.split(",")) if args.tickers else None
        filings = edgar.search_10q(args.start, args.end, ciks=ciks, limit=args.limit)
        print(f"Found {len(filings)} 10-Q filings filed {args.start} to {args.end}")
        print(f"Indexed {ingest(edgar, Store(args.db), filings)} new filings into {args.db}")
    else:
        store = Store(args.db)
        print(format_answer(answer(anthropic.Anthropic(), args.question, store.search(args.question, args.k))))


if __name__ == "__main__":
    main()
