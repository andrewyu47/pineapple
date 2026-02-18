# FORPineapple: The Full Story of Pineapple (Pinecone + Apple)

## What Is Pineapple?

**Pineapple** is the DocOps Governance Workbench extended with two new integrations: Apple's Swift-DocC documentation system and Pinecone's vector database. It's a documentation quality engine that can crawl Apple's entire developer documentation, lint it for governance issues, and store every symbol in Pinecone for semantic search.

Think of it as three things in a trench coat:
1. **A documentation linter** (like ESLint, but for prose)
2. **A live API crawler** for Apple's developer docs
3. **A semantic search engine** powered by Pinecone vector embeddings

The name "Pineapple" is Pinecone + Apple. Also, the Pinecone index we use is literally called "pineapple."

---

## Explain It Like I'm 5

Imagine you have a giant library with thousands of books (that's Apple's developer documentation). Some books have missing pages. Some have the wrong title on the spine. Some say "visionos" when they should say "visionOS." And nobody has checked them in years.

**Pineapple is a robot librarian.**

It walks through the library, opens every book, checks for problems (missing descriptions, wrong names, broken links, old information), and writes a report. Then it takes every book and puts a smart label on it, so if someone asks "how do I play a video in a little floating window?", the robot knows exactly which book to hand them, even though they didn't say the exact right words.

The "checking for problems" part is the **DocOps Governance Workbench**.
The "walking through the library" part is the **Apple DocC integration**.
The "smart labels" part is **Pinecone**.

---

## The Interview Version (Mapped to Your Battlecard)

### How Pineapple Connects to Every Story

Pineapple isn't a side project. It's the **live, working proof** that your Splunk stories weren't just one-time wins. You rebuilt the same architecture, end to end, against a completely different data source, in a completely different domain, and it works.

| Battlecard Story | What You Said You Built | What Pineapple Proves |
|------------------|------------------------|----------------------|
| **SAGE** (Story 1) | RAG-powered doc agent with semantic search, Glass Box citations, confusion telemetry | Pineapple's Pinecone integration does the same thing: semantic search over structured doc metadata. Query "how do I play video in a floating window?" and it returns AVPictureInPictureController, even though you never said "Picture in Picture." That's RAG retrieval working on real Apple docs. |
| **DocOps Workbench** (Story 3) | CI/CD prose linter, automated governance at commit level | Pineapple IS the Workbench, extended. 74 original tests still passing, 4 new DocC-specific checks (missing descriptions, stale platforms, broken cross-references, terminology), 100 tests total. You didn't just talk about automated governance, you shipped it. |
| **Asset Migration** (Story 5) | 5,000+ assets, unified metadata, controlled vocabulary, lifecycle rules | Pineapple crawls Apple's DocC API and extracts structured metadata: title, kind, platforms, identifier, hierarchy. Every symbol gets classification metadata. 45 AVKit symbols are live in Pinecone right now with platform, kind, and framework fields, queryable by natural language. This is the same data model you built at Splunk, running against Apple's data. |
| **Docs-as-Code** (Story 2) | Treating docs like code, CI/CD pipeline, Architecture of Participation | Swift-DocC IS Docs-as-Code. Doc comments live in source code, compiled by DocC into structured JSON. Pineapple hooks into that output, and the Workbench lints at the same layer a CI/CD pipeline would. |
| **Red Teaming** (Story 4) | Structured evaluation of AI tools, adversarial testing | The 26 live API assertion tests ARE a form of structured validation. They test Apple's real API against your schema assumptions, the same way red teaming tests an AI tool against reliability assumptions. If Apple changes their JSON schema, these tests fail first. |

### The One-Liner for Nate Adams

> "I didn't just describe these systems in interviews. After Splunk, I built a working version against Apple's own documentation API. Pineapple crawls Swift-DocC render JSON, lints it for governance issues, and stores every symbol in Pinecone for semantic search. It's the Workbench, SAGE, and the asset migration data model, running against real Apple data, with 100 passing tests."

### If They Ask "How Would You Apply Your Tools to Apple?"

You don't have to hypothesize. You can say:

> "I already did. I built Pineapple as a proof of concept. It fetches Apple's DocC render JSON, which is the structured output of Swift-DocC, and runs governance checks: missing descriptions, stale platform metadata, broken cross-references, and Apple terminology violations. Then it stores every symbol's metadata in Pinecone for semantic search. An engineer can search 'how do I handle video in a small floating window' and find AVPictureInPictureController without knowing the exact API name. I have 100 tests passing, 26 of which validate against Apple's live API."

### If They're Surprised You Know Swift-DocC (From Your Battlecard)

Instead of just saying "I researched it," you can now say:

> "I researched it, and then I built on it. Swift-DocC compiles doc comments into render JSON with a recursive inline content format for abstractions, structured platform metadata, topic sections with doc:// identifiers, and cross-references. I wrote a parser that flattens the recursive content into searchable text, a fetcher that does BFS crawls via topic sections, and four governance checks that validate the structured output. The render JSON is clean enough that you can build reliable governance tooling against it, which is exactly what this role requires."

---

## The Technical Architecture

### How the Three Layers Connect

```
Layer 1: GOVERNANCE (DocOps Workbench)
  File/API → Parser → ParsedDocument → Checks → Violations → Reporter
  ├── Markdown pipeline (existing, 9 checks, 74 tests)
  └── DocC pipeline (new, 4 checks, 26 tests)

Layer 2: CRAWLING (Apple DocC Integration)
  Apple API → DoccFetcher → DoccParser → ParsedDocument
  ├── Single symbol: fetch("avkit", "avplayerviewcontroller")
  └── Full framework: crawl_framework("avkit", max_depth=2) → BFS via topicSections

Layer 3: SEARCH (Pinecone Integration)
  ParsedDocument → Metadata extraction → Pinecone upsert → Semantic search
  ├── 45 AVKit symbols live in "pineapple" index, "docc" namespace
  ├── llama-text-embed-v2 embeddings (1024 dimensions)
  └── Natural language queries → ranked results with metadata filters
```

### The MCP Server (4 Tools for AI Agents)

```
mcp_server.py (FastMCP)
├── lint_docc_symbol     → Lint one symbol, return violations
├── lint_docc_framework  → Crawl + lint entire framework
├── get_docc_metadata    → Structured data ready for Pinecone
└── search_docc_symbols  → Keyword search across cached symbols
```

This means Claude, SAGE, or any MCP-compatible AI agent can call these tools directly. An agent could:
1. Crawl a framework → find governance violations → auto-file tickets
2. Search for symbols semantically → cite the canonical Apple URL (Glass Box)
3. Extract metadata → pipe it into Pinecone for a knowledge base

---

## What's Actually In Pinecone Right Now

45 AVKit symbols, each stored as a record with:
- **text**: Title + abstract (embedded by llama-text-embed-v2 for semantic search)
- **title**: Symbol name (e.g., "AVPlayerViewController")
- **kind**: Symbol type (class, protocol, struct, article, sampleCode, enum, var)
- **identifier**: Canonical doc:// URI
- **platforms**: Where it runs (e.g., "iOS 8.0, iPadOS 8.0, Mac Catalyst 13.1, tvOS 9.0, visionOS 1.0")
- **framework**: "AVKit"

**Real semantic search results** for "How do I play video in a floating window on iPad?":

| Rank | Symbol | Score | Why It Matched |
|------|--------|-------|----------------|
| 1 | Playing video content in a standard user interface | 0.497 | "floating Picture in Picture (PiP) window" |
| 2 | AVPictureInPictureController | 0.403 | "Picture in Picture playback of video in a floating, resizable window" |
| 3 | Adopting Picture in Picture in a Standard Player | 0.343 | "Add Picture in Picture (PiP) playback" |
| 4 | VideoPlayer | 0.318 | "displays content from a player" |
| 5 | Adopting Picture in Picture Playback in tvOS | 0.314 | "Picture in Picture playback" |

The user never said "Picture in Picture" or "PiP" or "AVPictureInPictureController." They said "floating window." Pinecone's embeddings understood the meaning. This is the same capability SAGE uses, running on Apple's data.

---

## Why This Matters for the Apple Role

### The Job Description Asks For:

| JD Requirement | Pineapple Proves It |
|----------------|-------------------|
| "AI-powered tools" | MCP server with 4 tools, Pinecone semantic search |
| "Documentation standards at scale" | 13 automated checks (9 original + 4 DocC), 100 tests |
| "Content lifecycle" | Stale platform detection, broken cross-ref validation |
| "Discoverability & IA" | Semantic search over structured metadata in Pinecone |
| "Engineering audiences" | Built for the exact API surface engineers use daily |
| "Knowledge management systems" | End-to-end pipeline: crawl → parse → lint → store → search |

### Nate's Specific Priorities (From Battlecard Section 7):

| Nate's Priority | What Pineapple Shows |
|-----------------|---------------------|
| AI/ML indexing of assets | 45 symbols indexed in Pinecone with semantic embeddings |
| Vendor selection & third-party tools | Built with Pinecone (vector DB), FastMCP (AI protocol), httpx (HTTP client), evaluated and chose each |
| DAM strategy & product ownership | Structured metadata extraction from Apple's content API, ready for asset management |
| Agile adoption | Iterative build: foundation → checks → fetcher → engine → CLI → MCP → Pinecone, each layer tested independently |

---

## Lessons Learned (The Good Engineer Stuff)

### 1. Don't Force a Square Peg

The temptation was to make DoccParser extend BaseParser and register it in the factory. But the file-based pipeline assumes `content: str` input from files. DocC has `dict` input from HTTP. Forcing it would have required fake JSON round-trips and a bogus `supports(".json")` method.

Building a parallel pipeline was cleaner. Same output type (ParsedDocument), different input mechanism. The checks don't care how they get their data.

**Interview translation:** "I evaluated extending the existing architecture versus building a parallel pipeline. The parallel approach preserved all 74 existing tests while cleanly supporting the new data source. I chose stability over cleverness."

### 2. Integration Tests Find Real Bugs

The URL construction bug (duplicate framework name in the path) was invisible in unit tests because our fixtures were synthetic. The live API test caught it immediately. The fix was one conditional in `_build_url()`, but without the assertion test against the real product, it would have silently produced 404s in production.

**Interview translation:** "I run assertion tests against the live API, not just mocked data. This caught a URL construction bug that unit tests missed entirely. Mocked tests validate logic; live tests validate assumptions."

### 3. Config Injection > Interface Changes

Two new checks needed raw JSON metadata that ParsedDocument doesn't carry. Three options: change BaseCheck.run() (breaks 9 checks), store metadata on ParsedDocument (pollutes a format-agnostic model), or inject via config options (zero interface changes). Option 3 wins.

**Interview translation:** "When extending a system, I prefer injection over modification. Zero risk to existing functionality, zero changes to shared interfaces."

### 4. Semantic Search Requires Governed Data

The Pinecone search works because the data is clean: consistent schema, structured metadata, meaningful abstracts. If we'd dumped raw JSON blobs without parsing, the embeddings would be noisy and search would be unreliable. This is the same lesson from Story 5 (Asset Migration): governance is the prerequisite for trustworthy AI.

**Interview translation:** "AI search on ungoverned content gives unreliable results. The governance layer, structured metadata, consistent terminology, clean abstracts, is what makes the vector embeddings meaningful. Foundation first, intelligence second."

### 5. External Symbols Are a Trap

DocC references include symbols from other frameworks (UIKit, Swift stdlib) with a different identifier prefix: `doc://com.externally.resolved.symbol/`. If you try to fetch these, you get 404s. The first version of the broken cross-ref check would have flagged every UIKit reference as "broken." The `is_external()` filter prevents false positives.

**Interview translation:** "I learned to handle boundary conditions in Apple's API, like external symbol references that use a different identifier scheme. Building reliable tooling means understanding these edge cases before they become production issues."

---

## Technologies Used

| Tech | Why | Battlecard Connection |
|------|-----|----------------------|
| **Python** | Same language as the existing Workbench | Story 3: DocOps Workbench |
| **Pinecone** | Vector database for semantic search | Story 1: SAGE uses Pinecone for RAG retrieval |
| **llama-text-embed-v2** | Pinecone's integrated embedding model | "Search by meaning, not keywords" |
| **FastMCP** | Anthropic's MCP SDK for tool exposure | Story 1: "MCP connects the data" |
| **httpx** | Modern HTTP client for Apple's API | Clean, typed, async-capable |
| **pytest** | Test framework with markers for live/offline | Story 4: Structured evaluation |
| **BFS crawl** | Breadth-first traversal of framework symbols | Predictable, depth-limited exploration |

---

## The Numbers

```
100 tests passing
 ├── 74 existing (all unchanged, all passing)
 └── 26 new
     ├── 17 API schema validation tests
     ├── 3 parser validation tests
     ├── 2 check validation tests
     └── 4 fetcher validation tests

13 governance checks (9 original + 4 DocC)
45 Apple symbols in Pinecone
4 MCP tools for AI agents
1 CLI command (docops lint-docc)
0 existing tests broken
```

---

## File Map

```
docops-governance-workbench/  (aka "Pineapple")
├── docops/
│   ├── checks/
│   │   ├── docc_checks.py         ← 4 DocC governance checks
│   │   ├── terminology.py         ← Extended with case_sensitive support
│   │   └── ... (9 original checks)
│   ├── parsers/
│   │   ├── docc_parser.py         ← DocC JSON → ParsedDocument
│   │   └── ... (markdown, mediawiki)
│   ├── fetchers/
│   │   └── docc_fetcher.py        ← HTTP client for Apple's API
│   ├── docc_engine.py             ← Orchestrator for DocC pipeline
│   ├── cli.py                     ← Now with lint-docc command
│   └── ... (engine, config, models)
├── glossary/
│   ├── default.yml                ← Inclusive language terms
│   └── apple.yml                  ← Apple capitalization rules
├── mcp_server.py                  ← MCP server (4 tools)
├── tests/
│   ├── integration/
│   │   └── test_docc_live.py      ← 26 live API assertion tests
│   ├── fixtures/
│   │   ├── docc_framework.json    ← Cached API response
│   │   └── docc_symbol.json       ← Cached symbol response
│   └── ... (74 existing tests)
├── FORPineapple.md                ← This file
├── FORAppleMCP.md                 ← Technical deep dive
├── FORDocOps.md                   ← Original workbench docs
└── pyproject.toml
```
