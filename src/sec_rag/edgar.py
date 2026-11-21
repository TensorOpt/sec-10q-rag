"""Minimal SEC EDGAR client: find 10-Q filings and download their primary documents."""

import re
import time
from dataclasses import dataclass
from datetime import date

import httpx2

SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FORM = "10-Q"
PAGE_SIZE = 100
MAX_RESULTS = 10_000  # EDGAR full-text search refuses offsets beyond this window
SEC_REQUEST_DELAY = 0.11  # SEC fair-access policy allows at most 10 requests per second


@dataclass(frozen=True)
class Filing:
    accession: str
    cik: int
    company: str
    filed: str
    period: str
    url: str


def make_http_client(user_agent: str) -> httpx2.Client:
    """SEC requires a User-Agent that identifies the requester."""
    return httpx2.Client(headers={"User-Agent": user_agent}, timeout=60, follow_redirects=True)


def _company_name(display_name: str) -> str:
    """'MICROSOFT CORP  (MSFT)  (CIK 0000789019)' -> 'MICROSOFT CORP (MSFT)'."""
    without_cik = re.sub(r"\s*\(CIK \d+\)", "", display_name)
    return " ".join(without_cik.split())


def _to_filing(hit: dict) -> Filing:
    source = hit["_source"]
    cik = int(source["ciks"][0])
    accession = source["adsh"]
    filename = hit["_id"].split(":", 1)[1]
    return Filing(
        accession=accession,
        cik=cik,
        company=_company_name(source["display_names"][0]),
        filed=source["file_date"],
        period=source.get("period_ending") or "",
        url=f"{ARCHIVES_URL}/{cik}/{accession.replace('-', '')}/{filename}",
    )


class Edgar:
    def __init__(self, http: httpx2.Client, delay: float = SEC_REQUEST_DELAY):
        self._http = http
        self._delay = delay

    def _get(self, url: str, **params) -> httpx2.Response:
        time.sleep(self._delay)
        response = self._http.get(url, params=params or None)
        response.raise_for_status()
        return response

    def search_10q(self, start: date, end: date, ciks: list[int] | None = None,
                   limit: int | None = None) -> list[Filing]:
        """10-Q filings filed between start and end (inclusive), newest first."""
        params = {"forms": FORM, "dateRange": "custom",
                  "startdt": start.isoformat(), "enddt": end.isoformat()}
        if ciks:
            params["ciks"] = ",".join(f"{cik:010d}" for cik in ciks)

        filings: list[Filing] = []
        offset = 0
        while offset < MAX_RESULTS and (limit is None or len(filings) < limit):
            page = self._get(SEARCH_URL, **params, **({"from": offset} if offset else {})).json()["hits"]
            filings += [_to_filing(h) for h in page["hits"] if h["_source"]["file_type"] == FORM]
            offset += PAGE_SIZE
            if not page["hits"] or offset >= page["total"]["value"]:
                break
        return filings[:limit]

    def ciks_for_tickers(self, tickers: list[str]) -> list[int]:
        by_ticker = {row["ticker"]: row["cik_str"] for row in self._get(TICKERS_URL).json().values()}
        wanted = [t.upper() for t in tickers]
        unknown = [t for t in wanted if t not in by_ticker]
        if unknown:
            raise ValueError(f"Unknown ticker(s): {', '.join(unknown)}")
        return [by_ticker[t] for t in wanted]

    def fetch(self, url: str) -> str:
        return self._get(url).text
