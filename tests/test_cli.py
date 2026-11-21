from datetime import date

import httpx2
import pytest

from sec_rag.answer import Answer
from sec_rag.cli import autumn, format_answer, ingest, main
from sec_rag.edgar import Filing
from sec_rag.store import Hit, Store

MSFT = Filing("0001193125-26-436133", 789019, "MICROSOFT CORP (MSFT)", "2026-10-28", "2026-09-30",
              "https://www.sec.gov/msft.htm")
AMZN = Filing("0001018724-26-000040", 1018724, "AMAZON COM INC (AMZN)", "2026-10-30", "2026-09-30",
              "https://www.sec.gov/amzn.htm")


class FakeEdgar:
    def __init__(self, documents):
        self.documents = documents
        self.fetched = []

    def fetch(self, url):
        self.fetched.append(url)
        document = self.documents[url]
        if isinstance(document, Exception):
            raise document
        return document


@pytest.mark.parametrize("today, expected", [
    (date(2026, 11, 21), (date(2026, 9, 1), date(2026, 11, 30))),
    (date(2026, 12, 5), (date(2026, 9, 1), date(2026, 11, 30))),
    (date(2027, 3, 1), (date(2026, 9, 1), date(2026, 11, 30))),
])
def test_autumn_is_september_through_november_of_the_latest_autumn(today, expected):
    assert autumn(today) == expected


def test_ingest_indexes_new_filings_skips_known_ones_and_survives_fetch_errors():
    store = Store(":memory:")
    store.add(AMZN, ["already indexed"])
    broken = Filing("0000000001-26-000001", 1, "BROKEN INC", "2026-10-01", "2026-09-30", "https://www.sec.gov/x.htm")
    edgar = FakeEdgar({
        MSFT.url: "<p>Total revenue was $92 billion.</p>",
        broken.url: httpx2.HTTPError("boom"),
    })
    log = []

    indexed = ingest(edgar, store, [MSFT, AMZN, broken], log.append)

    assert indexed == 1
    assert edgar.fetched == [MSFT.url, broken.url]
    assert store.search("revenue", k=1)[0] == Hit(MSFT, "Total revenue was $92 billion.")
    assert any("BROKEN INC" in line and "boom" in line for line in log)


def test_format_answer_lists_cited_sources():
    result = Answer("Revenue was $92.3 billion [2].", {2: Hit(MSFT, "Total revenue | 92,279")})

    assert format_answer(result) == (
        "Revenue was $92.3 billion [2].\n\n"
        "Sources:\n"
        "[2] MICROSOFT CORP (MSFT) 10-Q, period ending 2026-09-30, filed 2026-10-28\n"
        "    https://www.sec.gov/msft.htm"
    )


def test_format_answer_without_sources_is_just_the_text():
    assert format_answer(Answer("No answer.", {})) == "No answer."


def test_ingest_command_requires_sec_user_agent(monkeypatch, capsys):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)

    with pytest.raises(SystemExit):
        main(["ingest", "--tickers", "MSFT"])

    assert "SEC_USER_AGENT" in capsys.readouterr().err
