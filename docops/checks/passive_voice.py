"""Passive voice detection using regex.

Optimized: regex compiled once at module load, not per-file.
Added column reporting for precise violation location.
"""

from __future__ import annotations

import re

from docops.checks.base import BaseCheck
from docops.config import AppConfig
from docops.models import Severity, Violation
from docops.parsers.base import ParsedDocument

# Compiled once at import time. Atomic group alternative:
# use a set-based approach for irregular participles to avoid ReDoS.
_IRREGULAR_PARTICIPLES = (
    "built|chosen|done|drawn|driven|eaten|fallen|"
    "felt|found|given|gone|grown|held|hidden|hit|kept|known|"
    "laid|led|lent|lost|made|meant|met|paid|put|read|run|"
    "said|seen|sent|set|shown|shut|sold|spoken|spent|stood|"
    "taken|taught|thought|told|understood|won|worn|written"
)

_PASSIVE_REGEX = re.compile(
    rf"\b(is|are|was|were|be|been|being)\s+(\w+ed|{_IRREGULAR_PARTICIPLES})\b",
    re.IGNORECASE,
)

# Stative adjectives that look like passive voice but aren't.
# "is concerned about" (stative) vs "was built by" (passive).
_FALSE_POSITIVE_PHRASES = frozenset({
    "is based", "are based", "is used", "are used",
    "is required", "are required", "is needed", "are needed",
    "is located", "are located", "is designed", "are designed",
    "is expected", "are expected", "is supposed", "are supposed",
})


class PassiveVoiceCheck(BaseCheck):
    check_id = "passive-voice"
    description = "Detects passive voice constructions in prose."
    category = "style"

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        violations: list[Violation] = []
        severity = self.get_severity(config)
        allow_stative = config.check_option(self.check_id, "allow_stative", True)

        for segment in document.text_segments:
            if segment.segment_type == "code_block":
                continue
            for i, line in enumerate(segment.text.splitlines()):
                for match in _PASSIVE_REGEX.finditer(line):
                    phrase = match.group().lower()
                    if allow_stative and phrase in _FALSE_POSITIVE_PHRASES:
                        continue
                    violations.append(Violation(
                        rule_id=self.check_id,
                        message=f"Passive voice detected: '{match.group()}'",
                        severity=severity,
                        file=filepath,
                        line=segment.line_start + i,
                        column=match.start() + 1,
                        context=line.strip(),
                        suggestion="Consider rewriting in active voice.",
                    ))
        return violations
