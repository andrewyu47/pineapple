"""DocOps CLI - Typer application.

Optimized:
- Uses typed AppConfig instead of raw dicts.
- CLI flags mutate AppConfig fields directly (no dict spelunking).
"""

from __future__ import annotations

import sys
from typing import Optional

import typer

app = typer.Typer(
    name="docops",
    help="DocOps Governance Workbench - A CLI prose linter for documentation quality, style, and security.",
    add_completion=False,
)


@app.command("lint")
def lint(
    paths: list[str] = typer.Argument(..., help="Files or directories to lint."),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file."),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON."),
    severity: Optional[str] = typer.Option(None, "--severity", "-s", help="Minimum severity to report: error, warning, info."),
    checks: Optional[str] = typer.Option(None, "--checks", help="Comma-separated list of check IDs to run."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Disable LLM-based checks."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output."),
):
    """Lint documentation files for quality, style, and security violations."""
    from docops.config import CheckConfig, load_config
    from docops.engine import LintEngine
    from docops.models import SEVERITY_RANK
    from docops.output.console import ConsoleReporter
    from docops.output.json_output import JsonReporter

    cfg = load_config(config)

    if no_llm:
        cfg.llm.enabled = False
        for check_cfg in cfg.checks.values():
            check_cfg.options["llm_enabled"] = False

    if checks:
        specified = set(checks.split(","))
        for check_id in list(cfg.checks.keys()):
            if check_id not in specified:
                cfg.checks[check_id].enabled = False
        # Ensure specified checks that aren't in config are enabled
        for check_id in specified:
            if check_id not in cfg.checks:
                cfg.checks[check_id] = CheckConfig(enabled=True)

    engine = LintEngine(cfg)
    results = engine.lint_paths(paths)

    # Filter by minimum severity if specified
    if severity:
        min_rank = SEVERITY_RANK.get(severity, 2)
        for result in results:
            result.violations = [
                v for v in result.violations
                if SEVERITY_RANK.get(v.severity.value, 2) <= min_rank
            ]

    if json_output:
        reporter = JsonReporter()
    else:
        reporter = ConsoleReporter(verbose=verbose)

    reporter.report(results)

    # Exit code
    threshold = SEVERITY_RANK.get(cfg.fail_on, 0)
    has_failures = any(
        any(SEVERITY_RANK.get(v.severity.value, 2) <= threshold for v in r.violations)
        for r in results
    )
    sys.exit(1 if has_failures else 0)


@app.command("init")
def init():
    """Generate a default .docops.yml config file in the current directory."""
    from pathlib import Path

    target = Path.cwd() / ".docops.yml"
    if target.exists():
        typer.echo(f"Config file already exists: {target}")
        raise typer.Exit(1)

    default_config = """\
# DocOps Governance Workbench Configuration

output_format: "console"
fail_on: "error"

llm:
  enabled: false
  model: "gpt-4o"

checks:
  passive-voice:
    enabled: true
    severity: "warning"

  heading-hierarchy:
    enabled: true
    severity: "warning"

  heading-casing:
    enabled: true
    severity: "info"
    style: "sentence"

  line-length:
    enabled: true
    severity: "info"
    max_length: 120

  list-consistency:
    enabled: true
    severity: "warning"

  code-block-language:
    enabled: true
    severity: "warning"

  terminology:
    enabled: true
    severity: "warning"
    glossary_path: "glossary/default.yml"
    llm_enabled: false

  aws-key-exposed:
    enabled: true
    severity: "error"

  pii-detected:
    enabled: true
    severity: "error"
    disabled_subtypes: []

exclude:
  - "node_modules/**"
  - ".git/**"
  - ".venv/**"
"""
    target.write_text(default_config)
    typer.echo(f"Created config file: {target}")


@app.command("lint-docc")
def lint_docc(
    framework: str = typer.Argument(..., help="Apple framework name (e.g., 'avkit', 'swiftui')."),
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s", help="Specific symbol path within the framework."),
    max_depth: int = typer.Option(2, "--max-depth", "-d", help="Max crawl depth for framework-wide linting."),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON."),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file."),
    no_crossref: bool = typer.Option(False, "--no-crossref", help="Skip broken cross-reference checks (avoids extra network requests)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output."),
):
    """Lint Apple DocC documentation from the Render JSON API."""
    from docops.config import CheckConfig, load_config
    from docops.docc_engine import DoccLintEngine
    from docops.models import SEVERITY_RANK
    from docops.output.console import ConsoleReporter
    from docops.output.json_output import JsonReporter

    cfg = load_config(config)

    if no_crossref:
        cfg.checks.setdefault("docc-broken-crossref", CheckConfig()).enabled = False

    engine = DoccLintEngine(cfg)

    try:
        if symbol:
            results = [engine.lint_symbol(framework, symbol)]
        else:
            results = engine.lint_framework(framework, max_depth)
    except Exception as e:
        typer.echo(f"Error fetching DocC data: {e}", err=True)
        raise typer.Exit(1)

    if json_output:
        reporter = JsonReporter()
    else:
        reporter = ConsoleReporter(verbose=verbose)

    reporter.report(results)

    total_symbols = len(results)
    total_violations = sum(len(r.violations) for r in results)
    typer.echo(f"\nScanned {total_symbols} symbols, found {total_violations} violations.")

    threshold = SEVERITY_RANK.get(cfg.fail_on, 0)
    has_failures = any(
        any(SEVERITY_RANK.get(v.severity.value, 2) <= threshold for v in r.violations)
        for r in results
    )
    sys.exit(1 if has_failures else 0)


@app.command("list-checks")
def list_checks():
    """List all available checks with their IDs and descriptions."""
    from docops.checks import __register__

    for check in __register__:
        typer.echo(f"  {check.check_id:<25} [{check.category}]  {check.description}")


def main():
    app()
