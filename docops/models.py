"""Core data models for the DocOps linter."""

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}


@dataclass
class Violation:
    rule_id: str
    message: str
    severity: Severity
    file: str
    line: int | None = None
    column: int | None = None
    suggestion: str | None = None
    context: str | None = None


@dataclass
class LintResult:
    file: str
    violations: list[Violation] = field(default_factory=list)
    skipped_checks: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(v.severity == Severity.ERROR for v in self.violations)

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.INFO)
