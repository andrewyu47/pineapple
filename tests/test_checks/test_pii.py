"""Tests for PII detection."""

import pytest

from docops.checks.pii import PiiCheck, _luhn_check
from docops.config import AppConfig, CheckConfig


@pytest.fixture
def check():
    return PiiCheck()


@pytest.fixture
def cfg():
    return AppConfig()


def test_detects_ssn(check, md_parser, cfg):
    doc = md_parser.parse("SSN: 123-45-6789\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert any("ssn" in v.rule_id for v in violations)


def test_detects_email(check, md_parser, cfg):
    doc = md_parser.parse("Contact user@example.com for help.\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert any("email" in v.rule_id for v in violations)


def test_detects_phone(check, md_parser, cfg):
    doc = md_parser.parse("Call 555-123-4567 for support.\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert any("phone" in v.rule_id for v in violations)


def test_detects_credit_card_with_luhn(check, md_parser, cfg):
    # 4111-1111-1111-1111 passes Luhn
    doc = md_parser.parse("Card: 4111-1111-1111-1111\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert any("credit-card" in v.rule_id for v in violations)


def test_rejects_non_luhn_credit_card(check, md_parser, cfg):
    # 1234-5678-9012-3456 fails Luhn
    doc = md_parser.parse("Version: 1234-5678-9012-3456\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    cc_violations = [v for v in violations if "credit-card" in v.rule_id]
    assert len(cc_violations) == 0


def test_no_false_positive_normal_text(check, md_parser, cfg):
    doc = md_parser.parse("This is a normal documentation paragraph.\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    assert len(violations) == 0


def test_disabled_subtypes(check, md_parser):
    doc = md_parser.parse("Contact user@example.com\n", "test.md")
    config = AppConfig(checks={"pii-detected": CheckConfig(options={"disabled_subtypes": ["email"]})})
    violations = check.run(doc, "test.md", config)
    assert not any("email" in v.rule_id for v in violations)


def test_redacts_pii_in_context(check, md_parser, cfg):
    doc = md_parser.parse("SSN: 123-45-6789\n", "test.md")
    violations = check.run(doc, "test.md", cfg)
    ssn_v = [v for v in violations if "ssn" in v.rule_id][0]
    assert "123-45-6789" not in (ssn_v.context or "")


def test_luhn_valid():
    assert _luhn_check("4111111111111111") is True


def test_luhn_invalid():
    assert _luhn_check("1234567890123456") is False
