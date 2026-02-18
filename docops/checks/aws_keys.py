"""AWS key exposure scanning."""

from __future__ import annotations

import re

from docops.checks.base import BaseCheck
from docops.config import AppConfig
from docops.models import Severity, Violation
from docops.parsers.base import ParsedDocument

_AWS_ACCESS_KEY_PATTERN = re.compile(
    r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"
)

_AWS_SECRET_CONTEXT_PATTERN = re.compile(
    r"(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY|secret.?key)\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?",
    re.IGNORECASE,
)


class AwsKeyCheck(BaseCheck):
    check_id = "aws-key-exposed"
    description = "Scans for exposed AWS access keys and secret keys."
    category = "security"

    @property
    def default_severity(self) -> Severity:
        return Severity.ERROR

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        severity = self.get_severity(config)
        violations = []

        for i, line in enumerate(document.raw_lines, start=1):
            for match in _AWS_ACCESS_KEY_PATTERN.finditer(line):
                violations.append(Violation(
                    rule_id=self.check_id,
                    message=f"Possible AWS access key ID detected: {match.group()[:8]}...",
                    severity=severity,
                    file=filepath,
                    line=i,
                    context=self._redact(line),
                ))

            for match in _AWS_SECRET_CONTEXT_PATTERN.finditer(line):
                violations.append(Violation(
                    rule_id=self.check_id,
                    message="Possible AWS secret access key detected.",
                    severity=severity,
                    file=filepath,
                    line=i,
                    context=self._redact(line),
                ))

        return violations

    def _redact(self, line: str) -> str:
        line = _AWS_ACCESS_KEY_PATTERN.sub("[REDACTED_KEY_ID]", line)
        line = _AWS_SECRET_CONTEXT_PATTERN.sub("[REDACTED_SECRET]", line)
        return line.strip()
