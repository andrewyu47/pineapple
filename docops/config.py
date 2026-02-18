"""Configuration loading, validation, and type-safe access."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_FILENAME = ".docops.yml"


@dataclass
class LLMConfig:
    enabled: bool = False
    model: str = "gpt-4o"
    max_tokens_per_request: int = 4000


@dataclass
class CheckConfig:
    enabled: bool = True
    severity: str = "warning"
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppConfig:
    output_format: str = "console"
    fail_on: str = "error"
    llm: LLMConfig = field(default_factory=LLMConfig)
    checks: dict[str, CheckConfig] = field(default_factory=dict)
    exclude: list[str] = field(default_factory=lambda: ["node_modules/**", ".git/**", ".venv/**"])
    cache_enabled: bool = False
    cache_dir: str = ".docops_cache"
    max_workers: int = 4

    def get_check(self, check_id: str) -> CheckConfig:
        return self.checks.get(check_id, CheckConfig())

    def is_check_enabled(self, check_id: str) -> bool:
        return self.get_check(check_id).enabled

    def check_severity(self, check_id: str) -> str | None:
        """Return configured severity, or None if not explicitly configured."""
        if check_id in self.checks:
            return self.checks[check_id].severity
        return None

    def check_option(self, check_id: str, key: str, default: Any = None) -> Any:
        return self.get_check(check_id).options.get(key, default)


def load_config(config_path: str | None = None) -> AppConfig:
    """Load config from YAML, return typed AppConfig."""
    raw: dict[str, Any] = {}

    if config_path:
        path = Path(config_path)
    else:
        path = Path.cwd() / DEFAULT_CONFIG_FILENAME

    if path.exists():
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

    return _build_config(raw)


def _build_config(raw: dict[str, Any]) -> AppConfig:
    llm_raw = raw.get("llm", {})
    llm = LLMConfig(
        enabled=llm_raw.get("enabled", False),
        model=llm_raw.get("model", "gpt-4o"),
        max_tokens_per_request=llm_raw.get("max_tokens_per_request", 4000),
    )

    checks: dict[str, CheckConfig] = {}
    for check_id, check_raw in raw.get("checks", {}).items():
        if not isinstance(check_raw, dict):
            continue
        known = {"enabled", "severity"}
        options = {k: v for k, v in check_raw.items() if k not in known}
        checks[check_id] = CheckConfig(
            enabled=check_raw.get("enabled", True),
            severity=check_raw.get("severity", "warning"),
            options=options,
        )

    return AppConfig(
        output_format=raw.get("output_format", "console"),
        fail_on=raw.get("fail_on", "error"),
        llm=llm,
        checks=checks,
        exclude=raw.get("exclude", ["node_modules/**", ".git/**", ".venv/**"]),
        cache_enabled=raw.get("cache_enabled", False),
        cache_dir=raw.get("cache_dir", ".docops_cache"),
        max_workers=raw.get("max_workers", 4),
    )
