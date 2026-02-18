"""Formatting checks: heading hierarchy, heading casing, line length, list consistency, code block language.

Optimized: regex compiled at module level, config accessed via typed AppConfig.
"""

from __future__ import annotations

import re

from docops.checks.base import BaseCheck
from docops.config import AppConfig
from docops.models import Severity, Violation
from docops.parsers.base import ParsedDocument

_SMALL_WORDS = frozenset({"a", "an", "the", "and", "but", "or", "for", "nor", "in", "on", "at", "to", "by", "of", "up", "is"})
_LIST_MARKER_RE = re.compile(r"^(\s*)([-*+]|\d+[.)]) ")


class HeadingHierarchyCheck(BaseCheck):
    check_id = "heading-hierarchy"
    description = "Ensures heading levels don't skip (e.g., h1 -> h3)."
    category = "formatting"

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        violations: list[Violation] = []
        severity = self.get_severity(config)
        prev_level = 0

        for heading in document.headings:
            if heading.level > prev_level + 1 and prev_level > 0:
                violations.append(Violation(
                    rule_id=self.check_id,
                    message=f"Heading level skipped: h{prev_level} -> h{heading.level}",
                    severity=severity,
                    file=filepath,
                    line=heading.line_number,
                    context=heading.text,
                    suggestion=f"Use h{prev_level + 1} instead.",
                ))
            prev_level = heading.level

        return violations


class HeadingCasingCheck(BaseCheck):
    check_id = "heading-casing"
    description = "Checks heading casing consistency (title case or sentence case)."
    category = "formatting"

    @property
    def default_severity(self) -> Severity:
        return Severity.INFO

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        style = config.check_option(self.check_id, "style", "sentence")
        severity = self.get_severity(config)
        violations: list[Violation] = []

        for heading in document.headings:
            text = heading.text.strip()
            if not text:
                continue

            if style == "title" and not self._is_title_case(text):
                violations.append(Violation(
                    rule_id=self.check_id,
                    message=f"Heading not in title case: '{text}'",
                    severity=severity,
                    file=filepath,
                    line=heading.line_number,
                    context=text,
                    suggestion="Capitalize major words.",
                ))
            elif style == "sentence" and not self._is_sentence_case(text):
                violations.append(Violation(
                    rule_id=self.check_id,
                    message=f"Heading not in sentence case: '{text}'",
                    severity=severity,
                    file=filepath,
                    line=heading.line_number,
                    context=text,
                    suggestion="Only capitalize the first word and proper nouns.",
                ))

        return violations

    def _is_title_case(self, text: str) -> bool:
        words = text.split()
        for i, word in enumerate(words):
            if "/" in word or "_" in word or "." in word:
                continue
            if i == 0 or word.lower() not in _SMALL_WORDS:
                if word.isalpha() and not word[0].isupper():
                    return False
        return True

    def _is_sentence_case(self, text: str) -> bool:
        words = text.split()
        if not words:
            return True
        if words[0].isalpha() and words[0][0].islower():
            return False
        return True


class LineLengthCheck(BaseCheck):
    check_id = "line-length"
    description = "Flags lines exceeding the configured maximum length."
    category = "formatting"

    @property
    def default_severity(self) -> Severity:
        return Severity.INFO

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        max_len = config.check_option(self.check_id, "max_length", 120)
        severity = self.get_severity(config)
        violations: list[Violation] = []

        for i, line in enumerate(document.raw_lines, start=1):
            length = len(line)
            if length > max_len:
                violations.append(Violation(
                    rule_id=self.check_id,
                    message=f"Line exceeds {max_len} characters ({length}).",
                    severity=severity,
                    file=filepath,
                    line=i,
                    column=max_len + 1,
                ))

        return violations


class ListConsistencyCheck(BaseCheck):
    check_id = "list-consistency"
    description = "Checks that list items use consistent markers within each list."
    category = "formatting"

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        severity = self.get_severity(config)
        violations: list[Violation] = []
        current_list: list[tuple[int, str]] = []
        current_indent = -1

        for i, line in enumerate(document.raw_lines, start=1):
            match = _LIST_MARKER_RE.match(line)
            if match:
                indent = len(match.group(1))
                marker = match.group(2)
                marker_type = "ordered" if marker[0].isdigit() else marker[0]

                if current_indent == -1:
                    current_indent = indent
                if indent == current_indent:
                    current_list.append((i, marker_type))
                else:
                    self._flush(current_list, severity, filepath, violations)
                    current_list = [(i, marker_type)]
                    current_indent = indent
            elif current_list and line.strip() == "":
                self._flush(current_list, severity, filepath, violations)
                current_list = []
                current_indent = -1

        self._flush(current_list, severity, filepath, violations)
        return violations

    def _flush(self, items: list[tuple[int, str]], severity: Severity, filepath: str, out: list[Violation]) -> None:
        if len(items) < 2:
            return
        markers = {m for _, m in items}
        if len(markers) > 1:
            out.append(Violation(
                rule_id=self.check_id,
                message=f"Mixed list markers in list: {', '.join(sorted(markers))}",
                severity=severity,
                file=filepath,
                line=items[0][0],
                suggestion="Use the same marker type throughout the list.",
            ))
        items.clear()


class CodeBlockLanguageCheck(BaseCheck):
    check_id = "code-block-language"
    description = "Ensures fenced code blocks have a language tag."
    category = "formatting"

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        severity = self.get_severity(config)
        return [
            Violation(
                rule_id=self.check_id,
                message="Code block missing language tag.",
                severity=severity,
                file=filepath,
                line=block.line_start,
                suggestion="Add a language identifier after the opening fence (e.g., ```python).",
            )
            for block in document.code_blocks
            if block.language is None
        ]
