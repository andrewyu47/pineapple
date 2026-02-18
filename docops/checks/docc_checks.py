"""DocC-specific governance checks for Apple documentation.

Four checks that run only on documents with format_type == "docc":
- docc-missing-description: Flags symbols with empty/missing abstract
- docc-stale-platform: Flags deprecated or very old platform metadata
- docc-broken-crossref: Validates cross-references by fetching them
- docc-terminology: Checks text against Apple terminology glossary
"""

from __future__ import annotations

import logging

from docops.checks.base import BaseCheck
from docops.config import AppConfig
from docops.models import Severity, Violation
from docops.parsers.base import ParsedDocument

logger = logging.getLogger(__name__)


class DoccMissingDescriptionCheck(BaseCheck):
    """Flags DocC symbols with empty or missing abstract."""

    check_id = "docc-missing-description"
    description = "Flags DocC symbols with empty or missing abstract."
    category = "docc"

    @property
    def default_severity(self) -> Severity:
        return Severity.WARNING

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        if document.format_type != "docc":
            return []

        severity = self.get_severity(config)
        abstracts = [s for s in document.text_segments if s.segment_type == "abstract"]

        if not abstracts or all(not s.text.strip() for s in abstracts):
            return [Violation(
                rule_id=self.check_id,
                message="Symbol has no description (empty or missing abstract).",
                severity=severity,
                file=filepath,
                line=1,
                suggestion="Add a documentation comment to this symbol.",
            )]
        return []


class DoccStalePlatformCheck(BaseCheck):
    """Flags deprecated symbols or symbols with very old platform versions."""

    check_id = "docc-stale-platform"
    description = "Flags deprecated or stale platform metadata in DocC symbols."
    category = "docc"

    # Current GA versions for staleness detection
    _CURRENT_VERSIONS: dict[str, float] = {
        "iOS": 18.0,
        "iPadOS": 18.0,
        "macOS": 15.0,
        "tvOS": 18.0,
        "watchOS": 11.0,
        "visionOS": 2.0,
        "Mac Catalyst": 18.0,
    }

    @property
    def default_severity(self) -> Severity:
        return Severity.WARNING

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        if document.format_type != "docc":
            return []

        severity = self.get_severity(config)
        metadata = config.check_option(self.check_id, "_docc_metadata", {})
        platforms = metadata.get("metadata", {}).get("platforms", [])
        version_gap = config.check_option(self.check_id, "version_gap", 5)
        violations: list[Violation] = []

        for p in platforms:
            name = p.get("name", "")
            introduced = p.get("introducedAt", "")

            # Flag deprecated platforms
            if p.get("deprecated", False):
                violations.append(Violation(
                    rule_id=self.check_id,
                    message=f"Platform '{name}' is marked as deprecated.",
                    severity=severity,
                    file=filepath,
                    line=1,
                    suggestion="Consider removing deprecated platform support or adding a deprecation notice.",
                ))

            # Flag beta on shipped versions
            if p.get("beta", False) and name in self._CURRENT_VERSIONS:
                try:
                    intro_major = float(introduced.split(".")[0])
                    if intro_major <= self._CURRENT_VERSIONS[name]:
                        violations.append(Violation(
                            rule_id=self.check_id,
                            message=f"Platform '{name} {introduced}' is marked beta but the OS version has shipped.",
                            severity=severity,
                            file=filepath,
                            line=1,
                            suggestion="Update the beta flag or verify this is an unreleased version.",
                        ))
                except (ValueError, IndexError):
                    pass

            # Flag very old introduced versions
            if introduced and name in self._CURRENT_VERSIONS:
                try:
                    intro_major = float(introduced.split(".")[0])
                    current = self._CURRENT_VERSIONS[name]
                    if current - intro_major >= version_gap:
                        violations.append(Violation(
                            rule_id=self.check_id,
                            message=f"Platform '{name}' introduced at {introduced}, {current - intro_major:.0f} major versions behind current ({current}).",
                            severity=Severity.INFO,
                            file=filepath,
                            line=1,
                            context=f"Potential staleness: introduced {introduced}, current {current}",
                        ))
                except (ValueError, IndexError):
                    pass

        return violations


class DoccBrokenCrossrefCheck(BaseCheck):
    """Validates that cross-references in DocC documents resolve successfully."""

    check_id = "docc-broken-crossref"
    description = "Validates that DocC cross-references resolve to existing symbols."
    category = "docc"

    @property
    def default_severity(self) -> Severity:
        return Severity.ERROR

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        if document.format_type != "docc":
            return []

        severity = self.get_severity(config)
        metadata = config.check_option(self.check_id, "_docc_metadata", {})
        references = metadata.get("references", {})
        fetcher = config.check_option(self.check_id, "_docc_fetcher", None)

        if fetcher is None:
            return []

        violations: list[Violation] = []

        for ref_id, ref_data in references.items():
            # Skip external symbols (UIKit, Swift stdlib, etc.)
            if fetcher.is_external(ref_id):
                continue

            # Skip if already in cache (validated)
            if ref_id in fetcher.cache:
                continue

            try:
                result = fetcher.fetch_by_identifier(ref_id)
                if result is None:
                    violations.append(Violation(
                        rule_id=self.check_id,
                        message=f"Broken cross-reference: {ref_id}",
                        severity=severity,
                        file=filepath,
                        line=None,
                        suggestion=f"Verify the symbol path exists: {ref_data.get('url', ref_id)}",
                    ))
            except Exception as e:
                logger.debug(f"Failed to validate reference {ref_id}: {e}")

        return violations


class DoccTerminologyCheck(BaseCheck):
    """Checks DocC text against Apple terminology glossary."""

    check_id = "docc-terminology"
    description = "Checks DocC documentation text against Apple terminology glossary."
    category = "docc"

    @property
    def default_severity(self) -> Severity:
        return Severity.INFO

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        if document.format_type != "docc":
            return []

        from docops.checks.terminology import _load_and_compile_glossary

        glossary_path = config.check_option(self.check_id, "glossary_path", "glossary/apple.yml")
        terms = _load_and_compile_glossary(glossary_path)
        violations: list[Violation] = []

        for term in terms:
            for segment in document.text_segments:
                if segment.segment_type == "code_block":
                    continue
                for i, line in enumerate(segment.text.splitlines()):
                    for match in term.pattern.finditer(line):
                        violations.append(Violation(
                            rule_id=self.check_id,
                            message=f"Terminology: '{match.group()}' -> use '{term.preferred}' instead.",
                            severity=Severity(term.severity),
                            file=filepath,
                            line=segment.line_start + i,
                            column=match.start() + 1,
                            context=line.strip(),
                            suggestion=f"Replace with '{term.preferred}'.",
                        ))

        return violations
