"""Answer questions with Claude, grounded in retrieved 10-Q chunks and cited back to them."""

from dataclasses import dataclass

import anthropic

from sec_rag.store import Hit

MODEL = "claude-opus-5-5"
SYSTEM = (
    "You answer questions about SEC Form 10-Q quarterly reports using only the provided search results, "
    "which are excerpts from the filings. When you state a figure, name the company and the fiscal period "
    "it covers. If the search results do not contain the answer, say so plainly instead of guessing."
)


@dataclass(frozen=True)
class Answer:
    text: str
    sources: dict[int, Hit]  # citation number -> cited chunk


def _search_result(hit: Hit) -> dict:
    f = hit.filing
    return {
        "type": "search_result",
        "source": f.url,
        "title": f"{f.company} 10-Q for period ending {f.period}, filed {f.filed}",
        "content": [{"type": "text", "text": hit.text}],
        "citations": {"enabled": True},
    }


def answer(client: anthropic.Anthropic, question: str, hits: list[Hit]) -> Answer:
    if not hits:
        return Answer("No indexed 10-Q excerpts matched the question. Run `sec-rag ingest` first.", {})

    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        output_config={"effort": "medium"},
        # On a safety decline, re-run the request on a fallback model the API picks.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": [*map(_search_result, hits), {"type": "text", "text": question}]}],
    )
    if response.stop_reason == "refusal":
        return Answer("Claude declined to answer this question.", {})

    parts: list[str] = []
    sources: dict[int, Hit] = {}
    for block in response.content:
        if block.type != "text":
            continue
        parts.append(block.text)
        numbers = sorted({c.search_result_index + 1 for c in block.citations or []
                          if c.type == "search_result_location"})
        for n in numbers:
            sources[n] = hits[n - 1]
        if numbers:
            parts.append(" " + "".join(f"[{n}]" for n in numbers))
    return Answer("".join(parts), dict(sorted(sources.items())))
