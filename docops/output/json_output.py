"""JSON output reporter."""

import json
import sys

from docops.models import LintResult


class JsonReporter:
    def report(self, results: list[LintResult]):
        output = {
            "version": "1.0",
            "summary": {
                "files_scanned": len(results),
                "total_violations": sum(len(r.violations) for r in results),
                "errors": sum(r.error_count for r in results),
                "warnings": sum(r.warning_count for r in results),
            },
            "results": [
                {
                    "file": r.file,
                    "violations": [
                        {
                            "rule_id": v.rule_id,
                            "severity": v.severity.value,
                            "message": v.message,
                            "line": v.line,
                            "column": v.column,
                            "context": v.context,
                            "suggestion": v.suggestion,
                        }
                        for v in r.violations
                    ],
                    "skipped_checks": r.skipped_checks,
                }
                for r in results
            ],
        }
        json.dump(output, sys.stdout, indent=2)
        print()
