"""Tests for terminology check."""

import pytest

from docops.checks.terminology import TerminologyCheck
from docops.config import AppConfig


@pytest.fixture
def check():
    return TerminologyCheck()


@pytest.fixture
def cfg():
    return AppConfig()


def test_detects_blacklist(check, md_parser, cfg):
    doc = md_parser.parse("Add it to the blacklist.\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert any("blocklist" in v.message for v in violations)


def test_detects_whitelist(check, md_parser, cfg):
    doc = md_parser.parse("Update the whitelist configuration.\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert any("allowlist" in v.message for v in violations)


def test_detects_minimizing_language(check, md_parser, cfg):
    doc = md_parser.parse("This is just easy to configure.\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert len(violations) >= 2  # "just" and "easy"


def test_clean_text_no_violations(check, md_parser, cfg):
    doc = md_parser.parse("Configure the blocklist to filter traffic.\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert len(violations) == 0


def test_skips_code_blocks(check, md_parser, cfg):
    content = "```python\nblacklist = []\n```\n"
    doc = md_parser.parse(content, "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert len(violations) == 0
