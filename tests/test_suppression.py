"""Tests for suppression comments."""

from docops.models import Severity, Violation
from docops.suppression import SuppressionMap, filter_violations


def test_suppresses_specific_rule():
    lines = [
        "<!-- docops-disable passive-voice -->",
        "The file was deleted.",
        "<!-- docops-enable passive-voice -->",
        "The file was deleted.",
    ]
    smap = SuppressionMap(lines)
    assert smap.is_suppressed(1, "passive-voice")
    assert smap.is_suppressed(2, "passive-voice")
    assert not smap.is_suppressed(4, "passive-voice")


def test_suppresses_all_rules():
    lines = [
        "<!-- docops-disable -->",
        "The file was deleted and has blacklist.",
        "<!-- docops-enable -->",
    ]
    smap = SuppressionMap(lines)
    assert smap.is_suppressed(2, "passive-voice")
    assert smap.is_suppressed(2, "terminology")


def test_does_not_suppress_other_rules():
    lines = [
        "<!-- docops-disable passive-voice -->",
        "The blacklist was deleted.",
        "<!-- docops-enable passive-voice -->",
    ]
    smap = SuppressionMap(lines)
    assert smap.is_suppressed(2, "passive-voice")
    assert not smap.is_suppressed(2, "terminology")


def test_filter_violations():
    lines = [
        "normal line",
        "<!-- docops-disable passive-voice -->",
        "suppressed line",
        "<!-- docops-enable passive-voice -->",
        "normal line",
    ]
    smap = SuppressionMap(lines)

    violations = [
        Violation(rule_id="passive-voice", message="test", severity=Severity.WARNING, file="f", line=1),
        Violation(rule_id="passive-voice", message="test", severity=Severity.WARNING, file="f", line=3),
        Violation(rule_id="passive-voice", message="test", severity=Severity.WARNING, file="f", line=5),
    ]
    filtered = filter_violations(violations, smap)
    assert len(filtered) == 2
    assert filtered[0].line == 1
    assert filtered[1].line == 5
