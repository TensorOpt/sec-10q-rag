import json

import anthropic
import httpx2

from sec_rag.answer import MODEL, answer
from sec_rag.edgar import Filing
from sec_rag.store import Hit

MSFT = Filing("0001193125-26-436133", 789019, "MICROSOFT CORP (MSFT)", "2026-10-28", "2026-09-30",
              "https://www.sec.gov/msft.htm")
HITS = [Hit(MSFT, "Risk factors: cybersecurity."), Hit(MSFT, "Total revenue | 92,279 | 77,673")]


def text(value, cited=()):
    citations = [{"type": "search_result_location", "cited_text": HITS[i].text, "search_result_index": i,
                  "source": MSFT.url, "title": "t", "start_block_index": 0, "end_block_index": 1} for i in cited]
    return {"type": "text", "text": value, "citations": citations or None}


def message(*blocks, stop_reason="end_turn"):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": MODEL, "content": list(blocks),
            "stop_reason": stop_reason, "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}


def client_returning(body, requests):
    def handler(request):
        requests.append(request)
        return httpx2.Response(200, json=body)

    return anthropic.Anthropic(api_key="test", http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))


def test_answer_sends_hits_as_citable_search_results_followed_by_the_question():
    requests = []

    answer(client_returning(message(text("ok")), requests), "What was Microsoft's revenue?", HITS)

    body = json.loads(requests[0].content)
    assert body["model"] == MODEL
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in requests[0].headers["anthropic-beta"]
    content = body["messages"][0]["content"]
    assert content[0] == {
        "type": "search_result",
        "source": MSFT.url,
        "title": "MICROSOFT CORP (MSFT) 10-Q for period ending 2026-09-30, filed 2026-10-28",
        "content": [{"type": "text", "text": "Risk factors: cybersecurity."}],
        "citations": {"enabled": True},
    }
    assert len(content) == 3
    assert content[-1] == {"type": "text", "text": "What was Microsoft's revenue?"}


def test_answer_marks_citations_and_returns_only_cited_sources():
    body = message(text("Microsoft reported revenue of "), text("$92.3 billion", cited=[1]), text(" for the quarter."))

    result = answer(client_returning(body, []), "revenue?", HITS)

    assert result.text == "Microsoft reported revenue of $92.3 billion [2] for the quarter."
    assert result.sources == {2: HITS[1]}


def test_answer_ignores_non_text_blocks():
    body = message({"type": "thinking", "thinking": "", "signature": "sig"}, text("Answer."))

    assert answer(client_returning(body, []), "q", HITS).text == "Answer."


def test_answer_without_hits_does_not_call_claude():
    requests = []

    result = answer(client_returning(message(text("unused")), requests), "revenue?", [])

    assert requests == []
    assert "No indexed 10-Q" in result.text
    assert result.sources == {}


def test_answer_reports_refusal():
    body = message(stop_reason="refusal")

    assert "declined" in answer(client_returning(body, []), "q", HITS).text
