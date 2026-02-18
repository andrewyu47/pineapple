"""Tests for formatting checks."""

import pytest

from docops.checks.formatting import (
    CodeBlockLanguageCheck,
    HeadingCasingCheck,
    HeadingHierarchyCheck,
    LineLengthCheck,
    ListConsistencyCheck,
)
from docops.config import AppConfig, CheckConfig


@pytest.fixture
def cfg():
    return AppConfig()


class TestHeadingHierarchy:
    @pytest.fixture
    def check(self):
        return HeadingHierarchyCheck()

    def test_detects_skipped_level(self, check, md_parser, cfg):
        doc = md_parser.parse("# Title\n\n### Skipped\n", "test.md")
        violations = check.run(doc, "test.md", cfg)
        assert len(violations) == 1
        assert "h1 -> h3" in violations[0].message

    def test_allows_sequential_levels(self, check, md_parser, cfg):
        doc = md_parser.parse("# Title\n\n## Subtitle\n\n### Sub-sub\n", "test.md")
        violations = check.run(doc, "test.md", cfg)
        assert len(violations) == 0

    def test_allows_going_back_up(self, check, md_parser, cfg):
        doc = md_parser.parse("# Title\n\n## Sub\n\n# Another\n\n## Sub2\n", "test.md")
        violations = check.run(doc, "test.md", cfg)
        assert len(violations) == 0


class TestHeadingCasing:
    @pytest.fixture
    def check(self):
        return HeadingCasingCheck()

    def test_sentence_case_default(self, check, md_parser, cfg):
        doc = md_parser.parse("# Getting started\n", "test.md")
        violations = check.run(doc, "test.md", cfg)
        assert len(violations) == 0

    def test_detects_non_sentence_case(self, check, md_parser, cfg):
        doc = md_parser.parse("# getting started\n", "test.md")
        violations = check.run(doc, "test.md", cfg)
        assert len(violations) == 1


class TestLineLength:
    @pytest.fixture
    def check(self):
        return LineLengthCheck()

    def test_detects_long_lines(self, check, md_parser, cfg):
        long_line = "x" * 121 + "\n"
        doc = md_parser.parse(long_line, "test.md")
        violations = check.run(doc, "test.md", cfg)
        assert len(violations) == 1

    def test_allows_short_lines(self, check, md_parser, cfg):
        doc = md_parser.parse("Short line.\n", "test.md")
        violations = check.run(doc, "test.md", cfg)
        assert len(violations) == 0

    def test_custom_max_length(self, check, md_parser):
        doc = md_parser.parse("x" * 81 + "\n", "test.md")
        config = AppConfig(checks={"line-length": CheckConfig(options={"max_length": 80})})
        violations = check.run(doc, "test.md", config)
        assert len(violations) == 1


class TestListConsistency:
    @pytest.fixture
    def check(self):
        return ListConsistencyCheck()

    def test_detects_mixed_markers(self, check, md_parser, cfg):
        content = "- Item one\n* Item two\n"
        doc = md_parser.parse(content, "test.md")
        violations = check.run(doc, "test.md", cfg)
        assert len(violations) == 1

    def test_allows_consistent_markers(self, check, md_parser, cfg):
        content = "- Item one\n- Item two\n- Item three\n"
        doc = md_parser.parse(content, "test.md")
        violations = check.run(doc, "test.md", cfg)
        assert len(violations) == 0


class TestCodeBlockLanguage:
    @pytest.fixture
    def check(self):
        return CodeBlockLanguageCheck()

    def test_detects_missing_language(self, check, md_parser, cfg):
        doc = md_parser.parse("```\ncode\n```\n", "test.md")
        violations = check.run(doc, "test.md", cfg)
        assert len(violations) == 1

    def test_allows_language_tag(self, check, md_parser, cfg):
        doc = md_parser.parse("```python\ncode\n```\n", "test.md")
        violations = check.run(doc, "test.md", cfg)
        assert len(violations) == 0
