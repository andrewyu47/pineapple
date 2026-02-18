"""LangChain OpenAI client with retry, graceful failure, and token budget.

Optimized:
- Accepts typed AppConfig instead of raw dict.
- Enforces a character budget to avoid token overflow.
- Sanitizes user text in prompts to mitigate injection.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from docops.config import AppConfig
from docops.llm.prompts import TERMINOLOGY_SYSTEM_PROMPT, build_terminology_user_prompt
from docops.models import Severity, Violation

logger = logging.getLogger(__name__)

# Approximate chars-per-token ratio for English prose
_CHARS_PER_TOKEN = 4
_DEFAULT_MAX_TOKENS = 4000


class LLMClient:
    def __init__(self, config: AppConfig):
        self._max_chars = config.llm.max_tokens_per_request * _CHARS_PER_TOKEN
        self._model = ChatOpenAI(
            model=config.llm.model,
            temperature=0,
            max_tokens=2048,
            max_retries=2,
            timeout=30,
        )

    def check_terminology(
        self, text_chunks: list[str], glossary_summary: str, filepath: str
    ) -> list[Violation]:
        try:
            # Budget-aware batching: accumulate chunks until we hit the char limit
            combined_parts: list[str] = []
            char_count = 0
            for chunk in text_chunks:
                if char_count + len(chunk) > self._max_chars:
                    break
                combined_parts.append(chunk)
                char_count += len(chunk)

            if not combined_parts:
                return []

            combined_text = "\n\n---\n\n".join(combined_parts)

            # Sanitize: wrap user text in a code fence so the LLM treats it as data
            sanitized_text = f"```text\n{combined_text}\n```"

            messages = [
                SystemMessage(content=TERMINOLOGY_SYSTEM_PROMPT),
                HumanMessage(content=build_terminology_user_prompt(sanitized_text, glossary_summary)),
            ]
            response = self._model.invoke(messages)
            return self._parse_response(response.content, filepath)
        except Exception as e:
            logger.warning(f"LLM terminology check failed: {e}")
            return []

    def _parse_response(self, response_text: str, filepath: str) -> list[Violation]:
        try:
            findings = json.loads(response_text)
            return [
                Violation(
                    rule_id="terminology.llm",
                    message=finding.get("message", "Terminology issue found by LLM."),
                    severity=Severity.INFO,
                    file=filepath,
                    line=finding.get("line"),
                    context=finding.get("context"),
                    suggestion=finding.get("suggestion"),
                )
                for finding in findings.get("issues", [])
            ]
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return []
