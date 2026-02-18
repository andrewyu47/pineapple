"""Tests for the lint engine."""

import os

from docops.config import AppConfig, CheckConfig, LLMConfig
from docops.engine import LintEngine

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _base_config(**overrides) -> AppConfig:
    """Build a test config with LLM disabled and no excludes."""
    checks = overrides.pop("checks", {})
    return AppConfig(
        llm=LLMConfig(enabled=False),
        checks=checks,
        exclude=[],
        **overrides,
    )


def test_lint_violations_file():
    engine = LintEngine(_base_config())
    result = engine.lint_file(os.path.join(FIXTURES, "sample_violations.md"))
    assert result.has_errors
    assert result.error_count > 0
    assert result.warning_count > 0


def test_lint_clean_file():
    engine = LintEngine(_base_config())
    result = engine.lint_file(os.path.join(FIXTURES, "sample_clean.md"))
    assert not result.has_errors


def test_lint_directory():
    engine = LintEngine(_base_config())
    results = engine.lint_paths([FIXTURES])
    assert len(results) >= 2  # At least the two .md files


def test_disabled_check():
    config = _base_config(checks={
        "passive-voice": CheckConfig(enabled=False),
    })
    engine = LintEngine(config)
    result = engine.lint_file(os.path.join(FIXTURES, "sample_violations.md"))
    assert not any(v.rule_id == "passive-voice" for v in result.violations)
    assert "passive-voice" in result.skipped_checks
