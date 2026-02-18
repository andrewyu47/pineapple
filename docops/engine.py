"""Lint engine - orchestrates parsing, checking, and suppression.

Optimized:
- Accepts typed AppConfig, not raw dicts.
- Registry injected via constructor, no global singletons.
- ThreadPoolExecutor for concurrent multi-file linting.
- Optional content-hash caching to skip unchanged files.
"""

from __future__ import annotations

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from fnmatch import fnmatch
from pathlib import Path

from docops.config import AppConfig
from docops.models import LintResult, Severity, Violation
from docops.parsers.factory import get_parser
from docops.registry import CheckRegistry
from docops.suppression import SuppressionMap, filter_violations

logger = logging.getLogger(__name__)


def _default_registry() -> CheckRegistry:
    """Build a registry containing all built-in checks."""
    from docops.checks import __register__

    return CheckRegistry(__register__)


class LintEngine:
    def __init__(self, config: AppConfig, registry: CheckRegistry | None = None):
        self.config = config
        self._registry = registry or _default_registry()

    def lint_file(self, filepath: str) -> LintResult:
        path = Path(filepath)
        content = path.read_text(encoding="utf-8")

        # Content-hash cache: skip if file unchanged
        content_hash = ""
        if self.config.cache_enabled:
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            cached = self._read_cache(filepath, content_hash)
            if cached is not None:
                return cached

        parser = get_parser(filepath)
        document = parser.parse(content, filepath)
        suppression_map = SuppressionMap(document.raw_lines)

        all_violations: list[Violation] = []
        skipped_checks: list[str] = []

        for check in self._registry.all_checks():
            if not self.config.is_check_enabled(check.check_id):
                skipped_checks.append(check.check_id)
                continue
            try:
                violations = check.run(document, filepath, self.config)
                violations = filter_violations(violations, suppression_map)
                all_violations.extend(violations)
            except Exception as e:
                logger.error(f"Check '{check.check_id}' failed on {filepath}: {e}")
                skipped_checks.append(check.check_id)

        all_violations.sort(key=lambda v: (v.line or 0, v.rule_id))

        result = LintResult(
            file=filepath,
            violations=all_violations,
            skipped_checks=skipped_checks,
        )

        if self.config.cache_enabled:
            self._write_cache(filepath, content_hash, result)

        return result

    def lint_paths(self, paths: list[str]) -> list[LintResult]:
        file_paths = self._collect_files(paths)

        if not file_paths:
            return []

        # Single file: skip thread overhead
        if len(file_paths) == 1:
            return [self.lint_file(file_paths[0])]

        # Concurrent multi-file linting
        results: list[LintResult] = []
        max_workers = min(self.config.max_workers, len(file_paths))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(self.lint_file, fp): fp for fp in file_paths
            }
            for future in as_completed(future_to_path):
                fp = future_to_path[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error(f"Failed to lint {fp}: {e}")
                    results.append(LintResult(file=fp, skipped_checks=["all"]))

        # Stable ordering by file path
        results.sort(key=lambda r: r.file)
        return results

    def _collect_files(self, paths: list[str]) -> list[str]:
        """Expand directories and filter excluded paths."""
        file_paths: list[str] = []
        for target in paths:
            p = Path(target)
            if p.is_file():
                file_paths.append(str(p))
            elif p.is_dir():
                for ext in ("*.md", "*.markdown", "*.mdx", "*.wiki", "*.mediawiki"):
                    for filepath in p.rglob(ext):
                        if not self._is_excluded(filepath):
                            file_paths.append(str(filepath))
            else:
                logger.warning(f"Path not found: {target}")
        return file_paths

    def _is_excluded(self, filepath: Path) -> bool:
        rel = str(filepath)
        return any(fnmatch(rel, pat) for pat in self.config.exclude)

    # --- Content-hash cache ---

    def _cache_path(self, filepath: str) -> Path:
        key = hashlib.sha256(filepath.encode()).hexdigest()[:16]
        return Path(self.config.cache_dir) / f"{key}.json"

    def _read_cache(self, filepath: str, content_hash: str) -> LintResult | None:
        try:
            cp = self._cache_path(filepath)
            if not cp.exists():
                return None
            data = json.loads(cp.read_text())
            if data.get("hash") != content_hash:
                return None
            violations = [
                Violation(
                    rule_id=v["rule_id"],
                    message=v["message"],
                    severity=Severity(v["severity"]),
                    file=filepath,
                    line=v.get("line"),
                    column=v.get("column"),
                    suggestion=v.get("suggestion"),
                    context=v.get("context"),
                )
                for v in data.get("violations", [])
            ]
            return LintResult(
                file=filepath,
                violations=violations,
                skipped_checks=data.get("skipped_checks", []),
            )
        except Exception:
            return None

    def _write_cache(self, filepath: str, content_hash: str, result: LintResult) -> None:
        try:
            cp = self._cache_path(filepath)
            cp.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "hash": content_hash,
                "violations": [
                    {
                        "rule_id": v.rule_id,
                        "message": v.message,
                        "severity": v.severity.value,
                        "line": v.line,
                        "column": v.column,
                        "suggestion": v.suggestion,
                        "context": v.context,
                    }
                    for v in result.violations
                ],
                "skipped_checks": result.skipped_checks,
            }
            cp.write_text(json.dumps(data))
        except Exception as e:
            logger.debug(f"Failed to write cache for {filepath}: {e}")
