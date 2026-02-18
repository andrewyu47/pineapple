"""Tests for the MediaWiki parser."""


def test_parses_headings(wiki_parser):
    doc = wiki_parser.parse("= Title =\n\n== Subtitle ==\n", "test.wiki")
    assert len(doc.headings) == 2
    assert doc.headings[0].text == "Title"
    assert doc.headings[0].level == 1
    assert doc.headings[1].text == "Subtitle"
    assert doc.headings[1].level == 2


def test_parses_text(wiki_parser):
    doc = wiki_parser.parse("Hello world.\n", "test.wiki")
    texts = [s.text for s in doc.text_segments if s.segment_type == "paragraph"]
    assert any("Hello world" in t for t in texts)


def test_parses_code_blocks(wiki_parser):
    content = '<syntaxhighlight lang="python">print("hi")</syntaxhighlight>\n'
    doc = wiki_parser.parse(content, "test.wiki")
    assert len(doc.code_blocks) == 1
    assert doc.code_blocks[0].language == "python"


def test_code_block_no_language(wiki_parser):
    content = "<syntaxhighlight>some code</syntaxhighlight>\n"
    doc = wiki_parser.parse(content, "test.wiki")
    assert doc.code_blocks[0].language is None


def test_supports_wiki_extensions(wiki_parser):
    assert wiki_parser.supports("page.wiki")
    assert wiki_parser.supports("page.mediawiki")
    assert not wiki_parser.supports("page.md")


def test_format_type(wiki_parser):
    doc = wiki_parser.parse("text\n", "test.wiki")
    assert doc.format_type == "mediawiki"
