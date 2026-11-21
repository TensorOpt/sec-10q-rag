"""Turn 10-Q HTML into plain text and split it into retrievable chunks."""

import re
import textwrap

from bs4 import BeautifulSoup, NavigableString

BLOCK_TAGS = ["p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"]
HIDDEN = re.compile(r"display\s*:\s*none", re.IGNORECASE)


def _table_row(tr) -> str:
    cells = [" ".join(td.get_text(" ").split()) for td in tr.find_all(["td", "th"])]
    row = " | ".join(c for c in cells if c)
    # Filings put currency signs, closing parentheses and percent signs in their own cells.
    row = row.replace("$ | ", "$")
    return re.sub(r" \| ([)%])", r"\1", row)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "head", "ix:header"]):
        tag.decompose()
    for tag in soup.find_all(style=HIDDEN):
        tag.decompose()
    for table in soup.find_all("table"):
        rows = [r for r in (_table_row(tr) for tr in table.find_all("tr")) if r]
        table.replace_with(NavigableString("\n" + "\n".join(rows) + "\n"))
    for tag in soup.find_all(BLOCK_TAGS):
        tag.append(NavigableString("\n"))

    lines = (" ".join(line.split()) for line in soup.get_text().splitlines())
    return "\n".join(line for line in lines if line)


def chunk_text(text: str, max_chars: int = 4000, overlap_chars: int = 400) -> list[str]:
    """Pack whole lines into chunks of at most max_chars, repeating trailing lines as overlap."""
    lines = [piece for line in text.splitlines()
             for piece in textwrap.wrap(line, max_chars, break_on_hyphens=False)]
    chunks: list[str] = []
    current: list[str] = []

    def size(parts):
        return sum(map(len, parts)) + max(len(parts) - 1, 0)

    for line in lines:
        if current and size(current + [line]) > max_chars:
            chunks.append("\n".join(current))
            overlap: list[str] = []
            for previous in reversed(current):
                if size([previous] + overlap) > overlap_chars:
                    break
                overlap.insert(0, previous)
            current = overlap if size(overlap + [line]) <= max_chars else []
        current.append(line)
    if current:
        chunks.append("\n".join(current))
    return chunks
