import pytest

from sec_rag.edgar import Filing
from sec_rag.store import Store

MSFT = Filing("0001193125-26-436133", 789019, "MICROSOFT CORP (MSFT)", "2026-10-28", "2026-09-30",
              "https://www.sec.gov/msft.htm")
AMZN = Filing("0001018724-26-000040", 1018724, "AMAZON COM INC (AMZN)", "2026-10-30", "2026-09-30",
              "https://www.sec.gov/amzn.htm")


@pytest.fixture
def store():
    s = Store(":memory:")
    s.add(MSFT, ["Total revenue | 92,279 | 77,673", "Risk factors: cybersecurity threats."])
    s.add(AMZN, ["Net sales increased 11% to $180 billion.", "Total revenue grew in AWS segment."])
    return s


def test_search_ranks_chunks_matching_company_and_terms_first(store):
    hits = store.search("What was Microsoft's total revenue?", k=2)

    assert hits[0].filing == MSFT
    assert hits[0].text == "Total revenue | 92,279 | 77,673"


def test_search_matches_word_stems(store):
    hits = store.search("sale increases", k=1)

    assert hits[0].text == "Net sales increased 11% to $180 billion."


def test_search_respects_k_and_handles_queries_without_words(store):
    assert len(store.search("revenue", k=1)) == 1
    assert store.search("?!", k=5) == []


def test_has_and_re_adding_a_filing_replaces_its_chunks(store):
    assert store.has(MSFT.accession)
    assert not store.has("0000000000-00-000000")

    store.add(MSFT, ["Restated revenue figures."])

    assert [h.text for h in store.search("microsoft", k=10) if h.filing == MSFT] == ["Restated revenue figures."]


def test_store_persists_to_disk(tmp_path):
    path = tmp_path / "index.db"
    Store(path).add(MSFT, ["Total revenue | 92,279"])

    assert Store(path).search("revenue", k=1)[0].filing == MSFT
