"""Inline suppression comment support.

Supports:
  <!-- docops-disable rule-id -->  (suppress specific rule)
  <!-- docops-disable -->           (suppress all rules)
  <!-- docops-enable rule-id -->   (end block suppression)
  <!-- docops-enable -->            (end all block suppressions)
"""

import re

from docops.models import Violation

_DISABLE_PATTERN = re.compile(r"<!--\s*docops-disable\s*([\w-]*)\s*-->")
_ENABLE_PATTERN = re.compile(r"<!--\s*docops-enable\s*([\w-]*)\s*-->")


class SuppressionMap:
    def __init__(self, raw_lines: list[str]):
        self._suppressed: dict[int, set[str]] = {}
        self._parse(raw_lines)

    def _parse(self, lines: list[str]):
        block_disabled: set[str] = set()

        for i, line in enumerate(lines, start=1):
            disable_match = _DISABLE_PATTERN.search(line)
            enable_match = _ENABLE_PATTERN.search(line)

            if enable_match:
                rule_id = enable_match.group(1).strip()
                if rule_id:
                    block_disabled.discard(rule_id)
                else:
                    block_disabled.clear()
                continue

            if disable_match:
                rule_id = disable_match.group(1).strip()
                # Suppress this line
                self._suppressed.setdefault(i, set()).add(rule_id)
                # Start block suppression
                block_disabled.add(rule_id)
                continue

            if block_disabled:
                self._suppressed.setdefault(i, set()).update(block_disabled)

    def is_suppressed(self, line: int, rule_id: str) -> bool:
        suppressed = self._suppressed.get(line, set())
        return "" in suppressed or rule_id in suppressed


def filter_violations(violations: list[Violation], suppression_map: SuppressionMap) -> list[Violation]:
    return [v for v in violations if not suppression_map.is_suppressed(v.line or 0, v.rule_id)]
