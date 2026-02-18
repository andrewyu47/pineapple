"""Terminology check: YAML glossary exact match + LLM fallback.

Optimized:
- Glossary loaded and compiled once, cached per glossary path.
- All glossary patterns compiled at load time, not per-file.
- LLM client injected as dependency, not lazily created.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from docops.checks.base import BaseCheck
from docops.config import AppConfig
from docops.models import Severity, Violation
from docops.parsers.base import ParsedDocument

logger = logging.getLogger(__name__)

_MAX_GLOSSARY_TERMS_FOR_LLM = 30


@dataclass(frozen=True)
class CompiledTerm:
    pattern: re.Pattern
    preferred: str
    severity: str
    reason: str


@lru_cache(maxsize=8)
def _load_and_compile_glossary(glossary_path: str) -> tuple[CompiledTerm, ...]:
    """Load glossary from YAML and compile all regex patterns once.

    Cached by path so repeated calls with the same glossary don't re-parse.
    """
    path = Path(glossary_path)
    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        pkg_path = Path(__file__).parent.parent.parent / glossary_path
        if pkg_path.exists():
            path = pkg_path
        else:
            logger.warning(f"Glossary not found: {glossary_path}")
            return ()

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    compiled: list[CompiledTerm] = []
    for entry in data.get("terms", []):
        try:
            flags = 0 if entry.get("case_sensitive", False) else re.IGNORECASE
            compiled.append(CompiledTerm(
                pattern=re.compile(entry["pattern"], flags),
                preferred=entry["preferred"],
                severity=entry.get("severity", "warning"),
                reason=entry.get("reason", ""),
            ))
        except (re.error, KeyError) as e:
            logger.warning(f"Skipping invalid glossary entry: {e}")

    return tuple(compiled)


class TerminologyCheck(BaseCheck):
    check_id = "terminology"
    description = "Enforces preferred terminology using a glossary and optional LLM fallback."
    category = "terminology"

    def __init__(self, llm_client: Any = None):
        self._llm_client = llm_client

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        glossary_path = config.check_option(self.check_id, "glossary_path", "glossary/default.yml")
        terms = _load_and_compile_glossary(glossary_path)
        violations: list[Violation] = []

        # Phase 1: Deterministic glossary matching with pre-compiled patterns
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

        # Phase 2: LLM fallback
        llm_enabled = (
            config.llm.enabled
            and config.check_option(self.check_id, "llm_enabled", False)
        )

        if llm_enabled and os.environ.get("OPENAI_API_KEY"):
            llm_violations = self._run_llm_check(document, filepath, config, terms)
            violations.extend(llm_violations)
        elif llm_enabled:
            logger.info("LLM terminology check skipped: OPENAI_API_KEY not set.")

        return violations

    def _run_llm_check(
        self, document: ParsedDocument, filepath: str, config: AppConfig, terms: tuple[CompiledTerm, ...]
    ) -> list[Violation]:
        try:
            if self._llm_client is None:
                from docops.llm.client import LLMClient
                self._llm_client = LLMClient(config)

            text_chunks = [
                seg.text for seg in document.text_segments
                if seg.segment_type != "code_block" and seg.text.strip()
            ]
            if not text_chunks:
                return []

            glossary_summary = "\n".join(
                f"- Use '{t.preferred}' instead of: {t.pattern.pattern}"
                for t in terms[:_MAX_GLOSSARY_TERMS_FOR_LLM]
            )

            return self._llm_client.check_terminology(text_chunks, glossary_summary, filepath)
        except Exception as e:
            logger.warning(f"LLM terminology check failed, skipping: {e}")
            return []
