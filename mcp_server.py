"""DocC Governance MCP Server.

Exposes DocC linting and metadata tools via the Model Context Protocol.
Install with: pip install "docops-governance-workbench[mcp]"
Run with: python mcp_server.py
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from docops.config import CheckConfig, load_config
from docops.docc_engine import DoccLintEngine
from docops.fetchers.docc_fetcher import DoccFetcher
from docops.parsers.docc_parser import DoccParser

mcp = FastMCP("docops-docc")


@mcp.tool()
def lint_docc_symbol(framework: str, symbol_path: str = "") -> str:
    """Lint a single Apple DocC symbol for governance issues.

    Args:
        framework: Apple framework name (e.g., "avkit", "swiftui")
        symbol_path: Optional symbol path within the framework (e.g., "avplayerviewcontroller")
    """
    cfg = load_config()
    engine = DoccLintEngine(cfg)
    result = engine.lint_symbol(framework, symbol_path)

    output = {
        "symbol": result.file,
        "violations": [
            {
                "rule_id": v.rule_id,
                "severity": v.severity.value,
                "message": v.message,
                "line": v.line,
                "suggestion": v.suggestion,
            }
            for v in result.violations
        ],
        "summary": {
            "errors": result.error_count,
            "warnings": result.warning_count,
            "info": result.info_count,
        },
    }
    return json.dumps(output, indent=2)


@mcp.tool()
def lint_docc_framework(framework: str, max_depth: int = 2) -> str:
    """Crawl and lint an entire Apple framework's DocC documentation.

    Args:
        framework: Apple framework name (e.g., "avkit", "swiftui")
        max_depth: Maximum crawl depth for child symbols (default: 2)
    """
    cfg = load_config()
    engine = DoccLintEngine(cfg)
    results = engine.lint_framework(framework, max_depth)

    output = {
        "framework": framework,
        "symbols_scanned": len(results),
        "total_violations": sum(len(r.violations) for r in results),
        "results": [
            {
                "symbol": r.file,
                "errors": r.error_count,
                "warnings": r.warning_count,
                "info": r.info_count,
            }
            for r in results
        ],
        "summary": {
            "errors": sum(r.error_count for r in results),
            "warnings": sum(r.warning_count for r in results),
            "info": sum(r.info_count for r in results),
        },
    }
    return json.dumps(output, indent=2)


@mcp.tool()
def get_docc_metadata(framework: str, symbol_path: str = "") -> str:
    """Return structured metadata for a DocC symbol, suitable for Pinecone ingestion.

    Args:
        framework: Apple framework name (e.g., "avkit", "swiftui")
        symbol_path: Optional symbol path within the framework
    """
    cfg = load_config()
    engine = DoccLintEngine(cfg)
    metadata = engine.get_metadata(framework, symbol_path)
    return json.dumps(metadata, indent=2)


@mcp.tool()
def search_docc_symbols(keyword: str, framework: str = "") -> str:
    """Search cached DocC symbols by keyword in title or abstract.

    Args:
        keyword: Search term to match against symbol titles and descriptions
        framework: Optional framework to crawl first (populates cache)
    """
    fetcher = DoccFetcher()
    parser = DoccParser()

    if framework:
        fetcher.crawl_framework(framework, max_depth=1)

    keyword_lower = keyword.lower()
    matches = []

    for doc_id, data in fetcher.cache.items():
        title = data.get("metadata", {}).get("title", "")
        abstract_text = parser.flatten_inline_content(data.get("abstract", []))

        if keyword_lower in title.lower() or keyword_lower in abstract_text.lower():
            matches.append({
                "identifier": doc_id,
                "title": title,
                "abstract": abstract_text,
                "kind": data.get("metadata", {}).get("symbolKind", ""),
            })

    return json.dumps({"query": keyword, "matches": matches}, indent=2)


if __name__ == "__main__":
    mcp.run()
