"""Tests for passive voice detection."""

import pytest

from docops.checks.passive_voice import PassiveVoiceCheck
from docops.config import AppConfig, CheckConfig


@pytest.fixture
def check():
    return PassiveVoiceCheck()


@pytest.fixture
def cfg():
    return AppConfig()


def test_detects_passive_voice(check, md_parser, cfg):
    doc = md_parser.parse("The report was generated yesterday.\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert len(violations) == 1
    assert "was generated" in violations[0].message


def test_detects_multiple_passive(check, md_parser, cfg):
    content = "The file was deleted.\n\nThe server is maintained daily.\n"
    doc = md_parser.parse(content, "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert len(violations) == 2


def test_ignores_active_voice(check, md_parser, cfg):
    doc = md_parser.parse("The team generated the report yesterday.\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert len(violations) == 0


def test_ignores_code_blocks(check, md_parser, cfg):
    content = "```python\nresult was computed\n```\n"
    doc = md_parser.parse(content, "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert len(violations) == 0


def test_severity_override(check, md_parser):
    doc = md_parser.parse("The file was deleted.\n", "test.md")
    config = AppConfig(checks={"passive-voice": CheckConfig(severity="error")})
    violations = check.run(doc, "test.md", config)
    assert violations[0].severity.value == "error"


def test_irregular_past_participles(check, md_parser, cfg):
    doc = md_parser.parse("The code was written by the team.\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert len(violations) == 1
    assert "was written" in violations[0].message
