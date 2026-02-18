"""Rich-based console reporter."""

from rich.console import Console

from docops.models import LintResult, Severity

_SEVERITY_COLORS = {
    Severity.ERROR: "bold red",
    Severity.WARNING: "yellow",
    Severity.INFO: "dim cyan",
}
_SEVERITY_ICONS = {
    Severity.ERROR: "E",
    Severity.WARNING: "W",
    Severity.INFO: "I",
}


class ConsoleReporter:
    def __init__(self, verbose: bool = False):
        self.console = Console()
        self.verbose = verbose

    def report(self, results: list[LintResult]):
        total_errors, total_warnings, total_info = 0, 0, 0

        for result in results:
            if not result.violations and not self.verbose:
                continue

            self.console.print(f"\n[bold]{result.file}[/bold]")

            for v in result.violations:
                icon = _SEVERITY_ICONS[v.severity]
                color = _SEVERITY_COLORS[v.severity]
                line_str = f"L{v.line}" if v.line else "---"
                self.console.print(
                    f"  [{color}]{icon}[/{color}] {line_str:>6}  "
                    f"[{color}]{v.rule_id}[/{color}]  {v.message}"
                )
                if v.suggestion and self.verbose:
                    self.console.print(f"           [dim]Suggestion: {v.suggestion}[/dim]")

            total_errors += result.error_count
            total_warnings += result.warning_count
            total_info += result.info_count

        self.console.print()
        summary_parts = []
        if total_errors:
            summary_parts.append(f"[bold red]{total_errors} error(s)[/bold red]")
        if total_warnings:
            summary_parts.append(f"[yellow]{total_warnings} warning(s)[/yellow]")
        if total_info:
            summary_parts.append(f"[dim cyan]{total_info} info[/dim cyan]")

        if summary_parts:
            self.console.print(f"Found: {', '.join(summary_parts)}")
        else:
            self.console.print("[bold green]No issues found.[/bold green]")
