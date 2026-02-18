# Pineapple: DocOps Governance Workbench + Apple DocC + Pinecone

A production-grade documentation linter extended to crawl Apple's Swift-DocC documentation, run automated governance checks, and store every symbol in Pinecone for semantic search.

**Pineapple** = **Pine**cone + **Apple**

## What It Does

```
Apple DocC API → Fetcher → Parser → Governance Checks → Violations
                                          ↓
                                    MCP Server (4 tools)
                                          ↓
                                 Pinecone Vector Search
```

1. **Lints documentation** — 13 automated checks for prose quality, security, terminology, and DocC-specific governance (missing descriptions, stale platforms, broken cross-references, Apple capitalization)
2. **Crawls Apple's API** — BFS traversal of DocC render JSON via `topicSections` identifiers, with rate limiting and caching
3. **Semantic search** — Every symbol stored in Pinecone with structured metadata, queryable by natural language

## Quick Start

```bash
# Install
pip install -e ".[dev,mcp]"

# Lint a Markdown file
docops lint docs/

# Lint an Apple framework symbol
python -m docops.cli lint-docc avkit --symbol avplayerviewcontroller

# Lint an entire framework
python -m docops.cli lint-docc avkit --max-depth 1 --json

# Run MCP server
python mcp_server.py

# Run all tests (74 original + 26 DocC)
pytest

# Run only offline tests
pytest -m "not network"

# Run only live API assertion tests
pytest -m network
```

## The 13 Governance Checks

### Original (9 checks, any Markdown/MediaWiki)
| Check | What It Catches |
|-------|----------------|
| `passive-voice` | Passive voice constructions |
| `heading-hierarchy` | Skipped heading levels (h1 → h3) |
| `heading-capitalization` | Inconsistent heading case |
| `line-length` | Lines exceeding configured max |
| `trailing-whitespace` | Trailing spaces |
| `code-block-language` | Code blocks missing language tag |
| `terminology` | Banned/incorrect terms (glossary-driven) |
| `credential-exposure` | AWS keys, API tokens, passwords in docs |
| `pii-exposure` | SSNs, credit cards, phone numbers, emails |

### DocC-Specific (4 checks, Apple documentation)
| Check | What It Catches | Severity |
|-------|----------------|----------|
| `docc-missing-description` | Symbols with no abstract | WARNING |
| `docc-stale-platform` | Deprecated platforms, very old `introducedAt` | WARNING |
| `docc-broken-crossref` | References that 404 when fetched | ERROR |
| `docc-terminology` | Wrong Apple capitalization (swiftui vs SwiftUI) | INFO |

## MCP Server (4 Tools for AI Agents)

| Tool | Description |
|------|-------------|
| `lint_docc_symbol` | Lint a single Apple DocC symbol |
| `lint_docc_framework` | Crawl and lint an entire framework |
| `get_docc_metadata` | Structured metadata for Pinecone ingestion |
| `search_docc_symbols` | Keyword search across cached symbols |

## Pinecone Integration

DocC symbols are stored in Pinecone with semantic embeddings (llama-text-embed-v2):

```
Query: "How do I play video in a floating window on iPad?"

Results:
1. Playing video content in a standard user interface  (0.50)
2. AVPictureInPictureController                        (0.40)
3. Adopting Picture in Picture in a Standard Player    (0.34)
```

The user never said "Picture in Picture." Semantic search understood the meaning.

## Architecture

Two parallel pipelines sharing a common `ParsedDocument` model:

```
Pipeline 1 (Files):     File → BaseParser → ParsedDocument → Checks → Violations
Pipeline 2 (Apple API): HTTP → DoccFetcher → DoccParser → ParsedDocument → Checks → Violations
```

Both pipelines use the same check interface. All 13 checks work on both. The DocC pipeline adds an MCP server and Pinecone integration on top.

## Test Results

```
100 passed
├── 74 existing tests (unchanged, all passing)
└── 26 new tests
    ├── 17 API schema validation (live Apple API)
    ├── 3 parser validation
    ├── 2 check validation
    └── 4 fetcher validation
```

## Technologies

| Tech | Purpose |
|------|---------|
| Python 3.10+ | Core language |
| Pinecone | Vector database for semantic search |
| FastMCP | MCP server for AI agent integration |
| httpx | HTTP client for Apple's DocC API |
| LangChain | Semantic checks in linting pipeline |
| pytest | Testing with network/offline markers |

## Documentation

- [FORPineapple.md](FORPineapple.md) — Full project story, ELI5, and how the pieces connect
- [FORAppleMCP.md](FORAppleMCP.md) — Technical deep dive on the Apple DocC integration
- [FORDocOps.md](FORDocOps.md) — Original workbench architecture and design decisions

## License

MIT
