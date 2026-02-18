"""PII detection: SSN, email, phone, credit card.

Optimized: patterns compiled at module level, Luhn as pure function,
non-digit strip regex compiled once.
"""

from __future__ import annotations

import re

from docops.checks.base import BaseCheck
from docops.config import AppConfig
from docops.models import Severity, Violation
from docops.parsers.base import ParsedDocument

_NON_DIGIT_RE = re.compile(r"[^0-9]")

_PII_PATTERNS = {
    "ssn": {
        "pattern": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "message": "Possible SSN detected.",
    },
    "email": {
        "pattern": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "message": "Email address detected.",
    },
    "phone-us": {
        "pattern": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "message": "Possible US phone number detected.",
    },
    "credit-card": {
        "pattern": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "message": "Possible credit card number detected.",
    },
}


def _luhn_check(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


class PiiCheck(BaseCheck):
    check_id = "pii-detected"
    description = "Scans for personally identifiable information (SSN, email, phone, credit cards)."
    category = "security"

    @property
    def default_severity(self) -> Severity:
        return Severity.ERROR

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        severity = self.get_severity(config)
        violations: list[Violation] = []
        disabled_subtypes = set(
            config.check_option(self.check_id, "disabled_subtypes", [])
        )

        for i, line in enumerate(document.raw_lines, start=1):
            for subtype, spec in _PII_PATTERNS.items():
                if subtype in disabled_subtypes:
                    continue
                for match in spec["pattern"].finditer(line):
                    if subtype == "credit-card":
                        digits_only = _NON_DIGIT_RE.sub("", match.group())
                        if not _luhn_check(digits_only):
                            continue

                    violations.append(Violation(
                        rule_id=f"{self.check_id}.{subtype}",
                        message=spec["message"],
                        severity=severity,
                        file=filepath,
                        line=i,
                        column=match.start() + 1,
                        context=self._redact(line, spec["pattern"]),
                    ))

        return violations

    def _redact(self, line: str, pattern: re.Pattern) -> str:
        return pattern.sub("[REDACTED]", line).strip()
