"""Tests for the CLI."""

import os

from typer.testing import CliRunner

from docops.cli import app

runner = CliRunner()
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_lint_violations_exit_code():
    result = runner.invoke(app, ["lint", os.path.join(FIXTURES, "sample_violations.md"), "--no-llm"])
    assert result.exit_code == 1


def test_lint_clean_exit_code():
    result = runner.invoke(app, ["lint", os.path.join(FIXTURES, "sample_clean.md"), "--no-llm"])
    assert result.exit_code == 0


def test_lint_json_output():
    result = runner.invoke(app, ["lint", os.path.join(FIXTURES, "sample_violations.md"), "--no-llm", "--json"])
    assert result.exit_code == 1
    assert '"version": "1.0"' in result.stdout
    assert '"violations"' in result.stdout


def test_lint_specific_checks():
    result = runner.invoke(app, [
        "lint", os.path.join(FIXTURES, "sample_violations.md"),
        "--no-llm", "--checks", "passive-voice"
    ])
    assert "passive-voice" in result.stdout


def test_list_checks():
    result = runner.invoke(app, ["list-checks"])
    assert result.exit_code == 0
    assert "passive-voice" in result.stdout
    assert "aws-key-exposed" in result.stdout
