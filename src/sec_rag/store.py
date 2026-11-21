"""Chunk index backed by SQLite FTS5, ranked with BM25."""

import re
import sqlite3
from dataclasses import dataclass
from os import PathLike

from sec_rag.edgar import Filing

SCHEMA = """
CREATE TABLE IF NOT EXISTS filings (
    accession TEXT PRIMARY KEY, cik INTEGER, company TEXT, filed TEXT, period TEXT, url TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
    company, text, accession UNINDEXED, tokenize = 'porter unicode61'
);
"""
COMPANY_WEIGHT = 5.0  # a question naming a company should prefer that company's chunks


@dataclass(frozen=True)
class Hit:
    filing: Filing
    text: str


class Store:
    def __init__(self, path: str | PathLike):
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)

    def has(self, accession: str) -> bool:
        return self._db.execute("SELECT 1 FROM filings WHERE accession = ?", (accession,)).fetchone() is not None

    def add(self, filing: Filing, chunks: list[str]) -> None:
        with self._db:
            self._db.execute("DELETE FROM chunks WHERE accession = ?", (filing.accession,))
            self._db.execute("INSERT OR REPLACE INTO filings VALUES (?, ?, ?, ?, ?, ?)",
                             (filing.accession, filing.cik, filing.company, filing.filed, filing.period, filing.url))
            self._db.executemany("INSERT INTO chunks (company, text, accession) VALUES (?, ?, ?)",
                                 [(filing.company, chunk, filing.accession) for chunk in chunks])

    def search(self, query: str, k: int = 8) -> list[Hit]:
        words = re.findall(r"\w+", query.lower())
        if not words:
            return []
        match = " OR ".join(f'"{w}"' for w in words)
        rows = self._db.execute(
            """SELECT f.accession, f.cik, f.company, f.filed, f.period, f.url, c.text
               FROM chunks c JOIN filings f ON f.accession = c.accession
               WHERE chunks MATCH ? ORDER BY bm25(chunks, ?, 1.0) LIMIT ?""",
            (match, COMPANY_WEIGHT, k),
        )
        return [Hit(Filing(*row[:6]), row[6]) for row in rows]
