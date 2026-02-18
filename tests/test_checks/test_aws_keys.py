"""Tests for AWS key detection."""

import pytest

from docops.checks.aws_keys import AwsKeyCheck
from docops.config import AppConfig


@pytest.fixture
def check():
    return AwsKeyCheck()


@pytest.fixture
def cfg():
    return AppConfig()


def test_detects_access_key(check, md_parser, cfg):
    doc = md_parser.parse("Key: AKIAIOSFODNN7EXAMPLE\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert len(violations) == 1
    assert "AKIAIOSF" in violations[0].message


def test_detects_secret_key_in_context(check, md_parser, cfg):
    doc = md_parser.parse(
        'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"\n',
        "test.md",
    )
    violations = check.run(doc, "test.md", cfg)
    assert len(violations) >= 1
    assert any("secret" in v.message.lower() for v in violations)


def test_no_false_positive_on_normal_text(check, md_parser, cfg):
    doc = md_parser.parse("This is a normal sentence about configuration.\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert len(violations) == 0


def test_redacts_key_in_context(check, md_parser, cfg):
    doc = md_parser.parse("Key: AKIAIOSFODNN7EXAMPLE\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert "AKIAIOSFODNN7EXAMPLE" not in (violations[0].context or "")


def test_severity_is_error(check, md_parser, cfg):
    doc = md_parser.parse("Key: AKIAIOSFODNN7EXAMPLE\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert violations[0].severity.value == "error"
