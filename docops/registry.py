"""Check registry - plain container, no singleton. Injected into the engine."""

from __future__ import annotations

from docops.checks.base import BaseCheck


class CheckRegistry:
    """Holds registered checks. Created per-engine instance, not global state."""

    def __init__(self, checks: list[BaseCheck] | None = None):
        self._checks: dict[str, BaseCheck] = {}
        if checks:
            for check in checks:
                self.register(check)

    def register(self, check: BaseCheck) -> None:
        self._checks[check.check_id] = check

    def get(self, check_id: str) -> BaseCheck | None:
        return self._checks.get(check_id)

    def all_checks(self) -> list[BaseCheck]:
        return list(self._checks.values())

    def __len__(self) -> int:
        return len(self._checks)
