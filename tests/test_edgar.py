import json
from datetime import date

import httpx
import pytest

from sec_rag.edgar import Edgar, Filing


def hit(adsh, filename, cik="0000789019", name="MICROSOFT CORP  (MSFT)  (CIK 0000789019)",
        file_type="10-Q", file_date="2026-10-28"):
    return {
        "_id": f"{adsh}:{filename}",
        "_source": {
            "adsh": adsh,
            "ciks": [cik],
            "display_names": [name],
            "file_type": file_type,
            "file_date": file_date,
            "period_ending": "2026-09-30",
        },
    }


def search_response(hits, total=None):
    return {"hits": {"total": {"value": len(hits) if total is None else total}, "hits": hits}}


def edgar_with(handler):
    return Edgar(httpx.Client(transport=httpx.MockTransport(handler)), delay=0)


def test_search_10q_parses_hits_into_filings():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=search_response([hit("0001193125-26-436133", "msft-20260930.htm")]))

    filings = edgar_with(handler).search_10q(date(2026, 9, 1), date(2026, 11, 30))

    assert filings == [
        Filing(
            accession="0001193125-26-436133",
            cik=789019,
            company="MICROSOFT CORP (MSFT)",
            filed="2026-10-28",
            period="2026-09-30",
            url="https://www.sec.gov/Archives/edgar/data/789019/000119312526436133/msft-20260930.htm",
        )
    ]
    params = requests[0].url.params
    assert params["forms"] == "10-Q"
    assert params["startdt"] == "2026-09-01"
    assert params["enddt"] == "2026-11-30"
    assert "ciks" not in params


def test_search_10q_filters_by_cik_and_skips_non_primary_documents():
    def handler(request):
        assert request.url.params["ciks"] == "0000789019,0001018724"
        return httpx.Response(200, json=search_response([
            hit("0001193125-26-436133", "msft-20260930.htm"),
            hit("0001193125-26-436133", "msft-ex31.htm", file_type="EX-31.1"),
        ]))

    filings = edgar_with(handler).search_10q(date(2026, 9, 1), date(2026, 11, 30), ciks=[789019, 1018724])

    assert [f.url.rsplit("/", 1)[1] for f in filings] == ["msft-20260930.htm"]


def test_search_10q_paginates_until_total_and_respects_limit():
    pages = {0: [hit(f"A-{i}", "a.htm") for i in range(100)], 100: [hit(f"B-{i}", "b.htm") for i in range(5)]}

    def handler(request):
        offset = int(request.url.params.get("from", 0))
        return httpx.Response(200, json=search_response(pages[offset], total=105))

    edgar = edgar_with(handler)

    assert len(edgar.search_10q(date(2026, 9, 1), date(2026, 11, 30))) == 105
    assert len(edgar.search_10q(date(2026, 9, 1), date(2026, 11, 30), limit=3)) == 3


def test_ciks_for_tickers_is_case_insensitive_and_rejects_unknown():
    tickers = {"0": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
               "1": {"cik_str": 1018724, "ticker": "AMZN", "title": "AMAZON COM INC"}}
    edgar = edgar_with(lambda request: httpx.Response(200, content=json.dumps(tickers)))

    assert edgar.ciks_for_tickers(["msft", "AMZN"]) == [789019, 1018724]
    with pytest.raises(ValueError, match="NOPE"):
        edgar.ciks_for_tickers(["NOPE"])


def test_fetch_returns_text_and_raises_on_http_error():
    def handler(request):
        if request.url.path.endswith("missing.htm"):
            return httpx.Response(404)
        return httpx.Response(200, text="<html>10-Q</html>")

    edgar = edgar_with(handler)

    assert edgar.fetch("https://www.sec.gov/ok.htm") == "<html>10-Q</html>"
    with pytest.raises(httpx.HTTPStatusError):
        edgar.fetch("https://www.sec.gov/missing.htm")
