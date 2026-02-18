"""Tests for the Markdown parser."""

from docops.parsers.markdown_parser import MarkdownParser


def test_parses_headings(md_parser):
    doc = md_parser.parse("# Title\n\n## Subtitle\n", "test.md")
    assert len(doc.headings) == 2
    assert doc.headings[0].text == "Title"
    assert doc.headings[0].level == 1
    assert doc.headings[1].text == "Subtitle"
    assert doc.headings[1].level == 2


def test_parses_paragraphs(md_parser):
    doc = md_parser.parse("Hello world.\n\nAnother paragraph.\n", "test.md")
    paragraphs = [s for s in doc.text_segments if s.segment_type == "paragraph"]
    assert len(paragraphs) == 2
    assert paragraphs[0].text == "Hello world."


def test_parses_code_blocks(md_parser):
    content = "```python\nprint('hi')\n```\n"
    doc = md_parser.parse(content, "test.md")
    assert len(doc.code_blocks) == 1
    assert doc.code_blocks[0].language == "python"
    assert "print" in doc.code_blocks[0].content


def test_code_block_no_language(md_parser):
    content = "```\nsome code\n```\n"
    doc = md_parser.parse(content, "test.md")
    assert doc.code_blocks[0].language is None


def test_parses_list_items(md_parser):
    content = "- Item one\n- Item two\n"
    doc = md_parser.parse(content, "test.md")
    list_items = [s for s in doc.text_segments if s.segment_type == "list_item"]
    assert len(list_items) == 2


def test_no_duplicate_list_paragraph(md_parser):
    content = "- First item\n- Second item\n"
    doc = md_parser.parse(content, "test.md")
    paragraphs = [s for s in doc.text_segments if s.segment_type == "paragraph"]
    assert len(paragraphs) == 0


def test_supports_md_extensions(md_parser):
    assert md_parser.supports("readme.md")
    assert md_parser.supports("DOC.MARKDOWN")
    assert md_parser.supports("file.mdx")
    assert not md_parser.supports("file.wiki")


def test_raw_lines_preserved(md_parser):
    content = "line one\nline two\n"
    doc = md_parser.parse(content, "test.md")
    assert doc.raw_lines == ["line one", "line two"]
    assert doc.format_type == "markdown"
