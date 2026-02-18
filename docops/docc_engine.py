"""DocC Lint Engine: orchestrates fetch -> parse -> check for Apple documentation.

Parallel to LintEngine but for DocC Render JSON from Apple's API.
Does not modify the existing file-based LintEngine.
"""

from __future__ import annotations

import logging

from docops.config import AppConfig, CheckConfig
from docops.fetchers.docc_fetcher import DoccFetcher
from docops.models import LintResult, Violation
from docops.parsers.docc_parser import DoccParser
from docops.registry import CheckRegistry

logger = logging.getLogger(__name__)


def _docc_registry() -> CheckRegistry:
    """Build a registry containing DocC-specific checks plus passive-voice."""
    from docops.checks.docc_checks import (
        DoccBrokenCrossrefCheck,
        DoccMissingDescriptionCheck,
        DoccStalePlatformCheck,
        DoccTerminologyCheck,
    )
    from docops.checks.passive_voice import PassiveVoiceCheck

    return CheckRegistry([
        DoccMissingDescriptionCheck(),
        DoccStalePlatformCheck(),
        DoccBrokenCrossrefCheck(),
        DoccTerminologyCheck(),
        PassiveVoiceCheck(),
    ])


class DoccLintEngine:
    """Orchestrate linting of Apple DocC documentation."""

    def __init__(
        self,
        config: AppConfig,
        registry: CheckRegistry | None = None,
        fetcher: DoccFetcher | None = None,
    ):
        self.config = config
        self._registry = registry or _docc_registry()
        self._fetcher = fetcher or DoccFetcher()
        self._parser = DoccParser()

    def lint_symbol(self, framework: str, symbol_path: str = "") -> LintResult:
        """Fetch and lint a single DocC symbol."""
        raw_json = self._fetcher.fetch(framework, symbol_path)
        return self._lint_json(raw_json)

    def lint_framework(self, framework: str, max_depth: int = 2) -> list[LintResult]:
        """Crawl and lint an entire framework."""
        docs = self._fetcher.crawl_framework(framework, max_depth)
        return [self._lint_json(doc) for doc in docs]

    def get_metadata(self, framework: str, symbol_path: str = "") -> dict:
        """Return structured metadata suitable for Pinecone ingestion."""
        raw = self._fetcher.fetch(framework, symbol_path)
        meta = raw.get("metadata", {})
        return {
            "identifier": raw.get("identifier", {}).get("url", ""),
            "title": meta.get("title", ""),
            "kind": meta.get("symbolKind", meta.get("role", "")),
            "platforms": meta.get("platforms", []),
            "abstract": self._parser.flatten_inline_content(raw.get("abstract", [])),
            "hierarchy": raw.get("hierarchy", {}).get("paths", []),
            "children": [
                ident for section in raw.get("topicSections", [])
                for ident in section.get("identifiers", [])
            ],
        }

    def _lint_json(self, raw_json: dict) -> LintResult:
        """Parse and lint a single DocC JSON document."""
        source_url = raw_json.get("identifier", {}).get("url", "unknown")
        document = self._parser.parse(raw_json, source_url)

        # Inject raw metadata and fetcher for checks that need them
        for check_id in ("docc-missing-description", "docc-stale-platform", "docc-broken-crossref"):
            self.config.checks.setdefault(check_id, CheckConfig()).options["_docc_metadata"] = raw_json
        self.config.checks.setdefault("docc-broken-crossref", CheckConfig()).options["_docc_fetcher"] = self._fetcher

        all_violations: list[Violation] = []
        skipped: list[str] = []

        for check in self._registry.all_checks():
            if not self.config.is_check_enabled(check.check_id):
                skipped.append(check.check_id)
                continue
            try:
                violations = check.run(document, source_url, self.config)
                all_violations.extend(violations)
            except Exception as e:
                logger.error(f"Check '{check.check_id}' failed on {source_url}: {e}")
                skipped.append(check.check_id)

        all_violations.sort(key=lambda v: (v.line or 0, v.rule_id))
        return LintResult(file=source_url, violations=all_violations, skipped_checks=skipped)
