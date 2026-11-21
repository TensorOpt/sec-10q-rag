from sec_rag.text import chunk_text, html_to_text

FILING_HTML = """<?xml version='1.0' encoding='ASCII'?>
<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<head><title>10-Q</title><style>.x{color:red}</style></head>
<body>
<div style="display:none"><ix:header><ix:hidden>dei:AmendmentFlag false</ix:hidden></ix:header></div>
<div><span>Item 2. Management&#8217;s </span><span>Discussion</span></div>
<p>Revenue&#160;increased <b>12%</b> driven by cloud.</p>
<table>
  <tr><td>(In millions)</td><td></td><td>2026</td><td></td><td>2025</td></tr>
  <tr><td>Revenue</td><td>$</td><td>77,673</td><td>$</td><td>65,585</td></tr>
  <tr><td>Other expense</td><td></td><td>(1,234</td><td>)</td><td>12</td><td>%</td></tr>
</table>
<script>var x = 1;</script>
</body></html>"""


def test_html_to_text_keeps_prose_and_drops_hidden_xbrl_and_scripts():
    text = html_to_text(FILING_HTML)

    assert "Item 2. Management’s Discussion" in text
    assert "Revenue increased 12% driven by cloud." in text
    assert "AmendmentFlag" not in text
    assert "var x" not in text
    assert "color:red" not in text


def test_html_to_text_renders_table_rows_as_pipe_separated_cells():
    lines = html_to_text(FILING_HTML).splitlines()

    assert "(In millions) | 2026 | 2025" in lines
    assert "Revenue | $77,673 | $65,585" in lines
    assert "Other expense | (1,234) | 12%" in lines


def test_chunk_text_packs_lines_up_to_max_chars_with_overlap():
    text = "\n".join(f"line {i:02d} " + "x" * 20 for i in range(10))  # 10 lines of 28 chars

    chunks = chunk_text(text, max_chars=100, overlap_chars=30)

    assert all(len(c) <= 100 for c in chunks)
    assert chunks[0].startswith("line 00")
    assert chunks[-1].endswith("line 09 " + "x" * 20)
    # the last line of each chunk is repeated at the start of the next one
    for previous, current in zip(chunks, chunks[1:]):
        assert current.splitlines()[0] == previous.splitlines()[-1]


def test_chunk_text_splits_lines_longer_than_max_chars():
    chunks = chunk_text("word " * 100, max_chars=50, overlap_chars=0)

    assert len(chunks) > 1
    assert all(0 < len(c) <= 50 for c in chunks)
    assert " ".join(chunks).split() == ["word"] * 100


def test_chunk_text_of_empty_text_is_empty():
    assert chunk_text("  \n ") == []
