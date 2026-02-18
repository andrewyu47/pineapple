"""Abstract check interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from docops.config import AppConfig
from docops.models import Severity, Violation
from docops.parsers.base import ParsedDocument


class BaseCheck(ABC):
    @property
    @abstractmethod
    def check_id(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    def default_severity(self) -> Severity:
        return Severity.WARNING

    @property
    def category(self) -> str:
        return "general"

    @abstractmethod
    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        ...

    def get_severity(self, config: AppConfig) -> Severity:
        sev_str = config.check_severity(self.check_id)
        if sev_str is None:
            return self.default_severity
        try:
            return Severity(sev_str)
        except ValueError:
            return self.default_severity
