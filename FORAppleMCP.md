# FORAppleMCP: How We Built the Apple DocC Governance Linter

## What This Is

We extended the DocOps Governance Workbench — a production-grade documentation linter with 74 tests — to lint Apple's Swift-DocC documentation. The linter fetches render JSON from Apple's public API, runs governance checks against it, and exposes everything via an MCP server so Claude and other AI agents can use it as a tool.

Think of it like ESLint, but for Apple's documentation quality.

## The Architecture: Two Pipelines, One Check Interface

The original workbench has a clean pipeline:

```
File → Parser → ParsedDocument → Checks → Violations → Reporter → Output
```

The trick was: DocC data doesn't come from files. It comes from Apple's HTTP API. So we built a **parallel pipeline** that reuses the same `ParsedDocument` model and `BaseCheck` interface, but replaces the file-reading layer with a fetcher:

```
Apple API → DoccFetcher → DoccParser → ParsedDocument → Checks → Violations
                                                              ↓
                                                        MCP Server (4 tools)
                                                              ↓
                                                     Claude / SAGE / Pinecone
```

The key insight: we didn't force DocC into the file-based pipeline. `DoccParser` doesn't extend `BaseParser` because DocC data is JSON from HTTP, not text from files. But it outputs the exact same `ParsedDocument`, so all checks (both existing and new) work on it seamlessly.

## The Codebase Structure

```
docops-governance-workbench/
├── docops/
│   ├── checks/
│   │   ├── docc_checks.py          ← 4 new DocC-specific checks
│   │   └── ... (9 existing checks)
│   ├── parsers/
│   │   ├── docc_parser.py          ← DocC JSON → ParsedDocument
│   │   └── ... (markdown, mediawiki)
│   ├── fetchers/
│   │   └── docc_fetcher.py         ← HTTP client for Apple's API
│   ├── docc_engine.py              ← Orchestrator for DocC pipeline
│   ├── cli.py                      ← Now with `lint-docc` command
│   └── ... (engine, config, models, etc.)
├── glossary/
│   ├── default.yml                 ← Inclusive language terms
│   └── apple.yml                   ← Apple capitalization rules
├── mcp_server.py                   ← MCP server with 4 tools
├── tests/
│   ├── integration/
│   │   └── test_docc_live.py       ← 26 live API assertion tests
│   ├── fixtures/
│   │   ├── docc_framework.json     ← Cached API response
│   │   └── docc_symbol.json        ← Cached symbol response
│   └── ... (74 existing tests)
└── pyproject.toml
```

## How the Parts Connect

### 1. The Fetcher: Talking to Apple

`DoccFetcher` is a rate-limited HTTP client that knows how to navigate Apple's documentation API.

**Apple's API pattern:** `https://developer.apple.com/tutorials/data/documentation/{framework}/{symbol}.json`

The fetcher has two modes:
- **Single fetch:** `fetch("avkit", "avplayerviewcontroller")` → one JSON document
- **Framework crawl:** `crawl_framework("avkit", max_depth=2)` → BFS traversal via `topicSections` identifiers, collecting all symbols

The interesting part is the **doc:// identifier system**. Every symbol in Apple's docs has a canonical identifier like `doc://com.apple.avkit/documentation/AVKit/AVPlayerViewController`. The fetcher converts these to API URLs by stripping the `doc://` prefix, lowercasing, and appending `.json`.

**Gotcha we hit:** External symbols (UIKit, Swift stdlib) use a different prefix: `doc://com.externally.resolved.symbol/`. If you try to fetch these, you get 404s. The fetcher filters these out automatically.

**Another gotcha:** The initial URL construction duplicated the framework name (`avkit/avkit/...`) because the identifier already contains the framework path after `documentation/`. Classic off-by-one in string parsing. The integration tests caught this immediately — that's why assertion testing against the live API matters.

### 2. The Parser: Flattening Recursive JSON

Apple uses a recursive inline content format for all documentation text. An abstract isn't a string — it's an array like:

```json
[
  {"type": "text", "text": "A view controller that displays "},
  {"type": "reference", "identifier": "doc://...", "isActive": true},
  {"type": "codeVoice", "code": "AVPlayer"},
  {"type": "strong", "inlineContent": [{"type": "text", "text": "content"}]}
]
```

The parser's `flatten_inline_content()` recursively walks this tree and produces plain text. It handles `text`, `codeVoice`, `reference`, `strong`, `emphasis`, and `newTerm` nodes.

**Synthetic line numbers:** DocC JSON has no line numbers (it's not a text file). We assign synthetic 1-indexed line numbers based on section order — abstract gets line 1, each paragraph/heading increments. This keeps violations reportable with a position.

### 3. The Four Checks

| Check | What it catches | Severity |
|-------|----------------|----------|
| `docc-missing-description` | Symbols with no abstract | WARNING |
| `docc-stale-platform` | Deprecated platforms, very old `introducedAt`, beta on shipped OS | WARNING |
| `docc-broken-crossref` | References that 404 when fetched | ERROR |
| `docc-terminology` | Wrong Apple capitalization (swiftui → SwiftUI) | INFO |

**The metadata injection pattern** is worth understanding. Two checks need the raw JSON (not just ParsedDocument): `docc-stale-platform` needs `metadata.platforms`, and `docc-broken-crossref` needs `references`. But `BaseCheck.run()` takes `(document, filepath, config)` — we didn't want to change the interface for all 13 checks.

Solution: `DoccLintEngine` injects the raw JSON into the config's check options before running:
```python
config.checks["docc-stale-platform"].options["_docc_metadata"] = raw_json
```

Then the check reads it:
```python
metadata = config.check_option(self.check_id, "_docc_metadata", {})
```

It's pragmatic, not beautiful. But it keeps the interface stable and all 74 existing tests passing.

### 4. The Glossary: Case-Sensitive Matching

The existing terminology check uses `re.IGNORECASE` for its glossary patterns. Apple terms need the opposite — we want to catch `swiftui` but NOT `SwiftUI`.

We added a `case_sensitive: true` flag to glossary entries. When present, the regex compiles without `re.IGNORECASE`. The change to `_load_and_compile_glossary()` is one line:

```python
flags = 0 if entry.get("case_sensitive", False) else re.IGNORECASE
```

Backward-compatible: existing glossaries without this field keep their current behavior.

### 5. The MCP Server

Four tools exposed via FastMCP:
- `lint_docc_symbol` — lint a single symbol, return violations
- `lint_docc_framework` — crawl and lint a whole framework
- `get_docc_metadata` — return structured data ready for Pinecone ingestion
- `search_docc_symbols` — keyword search across cached symbols

The metadata output is designed to map directly to Pinecone fields:
- `abstract` → text field for embedding
- `platforms`, `kind`, `identifier` → metadata for filtering
- `hierarchy` → breadcrumb for Glass Box citations

## The Assertion Testing System

This is the answer to "how do we know our assumptions about Apple's API are correct?"

`tests/integration/test_docc_live.py` hits Apple's real API and validates:
- **Schema validation:** Does the JSON have `identifier`, `metadata`, `topicSections`, `abstract`, `references`?
- **Field validation:** Do platforms have `name`, `introducedAt`, `beta`?
- **Parser validation:** Does our parser extract meaningful text from real responses?
- **Check validation:** Do checks run without errors on real data?

Run modes:
```bash
pytest                              # All 100 tests (74 existing + 26 new)
pytest -m "not network"            # Only offline tests (74 original)
pytest -m network                   # Only live API tests (26 new)
```

The live tests serve as canaries: if Apple changes their JSON schema, these tests fail first, before any production code silently breaks.

## Lessons Learned

### 1. Don't Force a Square Peg

The temptation was to make `DoccParser` extend `BaseParser` and register it in the factory. But the file-based pipeline assumes `content: str` input and `filename: str` for parser dispatch. DocC has `dict` input and `doc://` URLs. Forcing it would have required `json.dumps/loads` round-trips and a fake `supports(".json")` method that would match any JSON file.

Building a parallel pipeline was cleaner. Same output type (`ParsedDocument`), different input mechanism. The checks don't care — they just see a `ParsedDocument`.

### 2. Integration Tests Find Real Bugs

The URL construction bug (duplicate framework name) was invisible in unit tests because our fixtures were synthetic. The live API test `test_fetch_by_identifier` caught it immediately. This is why assertion testing against the real product matters — mocked tests validate your logic, live tests validate your assumptions.

### 3. Config Injection > Interface Changes

When two new checks needed data beyond `ParsedDocument`, we had three options:
1. Change `BaseCheck.run()` to accept extra kwargs (breaks 9 existing checks)
2. Store metadata on `ParsedDocument` (pollutes a format-agnostic model)
3. Inject via config options (zero interface changes)

Option 3 wins. It's not the most elegant, but it's the most pragmatic — zero risk to existing functionality.

### 4. Rate Limiting is Mandatory

Apple's API doesn't document rate limits, but hammering it with 50+ concurrent requests during a framework crawl would be rude and likely result in blocks. The 0.25-second delay between requests is a polite default (4 req/sec). The `--no-crossref` flag exists specifically so users can skip the most network-heavy check.

### 5. External Symbols Are a Trap

DocC references include external symbols from other frameworks (UIKit, Swift stdlib). These use `doc://com.externally.resolved.symbol/` and will 404 if you try to fetch them. The first version of `DoccBrokenCrossrefCheck` would have flagged every UIKit reference as "broken." The `is_external()` filter prevents false positives.

## Technologies Used

| Tech | Why |
|------|-----|
| **httpx** | Modern sync HTTP client for Apple API. Cleaner than urllib3, better than requests for JSON APIs. |
| **FastMCP** | Anthropic's MCP SDK. Exposes Python functions as tools that AI agents can call. |
| **pytest markers** | `@pytest.mark.network` separates live API tests from offline tests. |
| **lru_cache** | Glossary loading is cached so repeated calls with the same path don't re-parse YAML. |
| **BFS crawl** | Framework traversal uses breadth-first search with depth tracking for predictable behavior. |

## Test Results

```
100 passed in 0.67s
├── 74 existing tests (unchanged, still passing)
└── 26 new tests
    ├── 17 API schema validation tests
    ├── 3 parser validation tests
    ├── 2 check validation tests
    └── 4 fetcher validation tests
```

## What's Not Built (Future Scope)

- **Pinecone integration:** The `get_docc_metadata` MCP tool outputs Pinecone-ready data, but actual embedding/upserting is a separate project.
- **Discussion section parsing:** The parser handles `primaryContentSections`, but some symbols have separate `discussion` sections that aren't captured yet.
- **ObjC variant handling:** The parser always uses the Swift variant. Adding ObjC support would need variant selection logic.
- **Incremental crawling:** The current crawler re-fetches everything. A smarter version would diff against previous crawls.
