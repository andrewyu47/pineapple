# FORDocOps: The DocOps Governance Workbench

## What Is This?

The DocOps Governance Workbench is a CLI prose linter that reads your documentation files and tells you what's wrong with them — passive voice, skipped heading levels, exposed AWS keys, credit card numbers, banned terminology, the works. Think of it as ESLint, but for docs.

You run `docops lint docs/` and it scans every Markdown and MediaWiki file, applies 9 checks, and tells you what to fix. Exit code 0 means clean, exit code 1 means violations. That's all a CI pipeline needs.

The tool was born from a real problem at Splunk: 100+ contributors writing docs, no automated way to enforce standards. Manual review was the bottleneck. This tool replaces the bottleneck with automation.

---

## Technical Architecture

The workbench follows a pipeline architecture. Data flows one direction:

```
File → Parser → ParsedDocument → Checks → Violations → Reporter → Output
```

Each stage is decoupled. The parser doesn't know about checks. Checks don't know about output. This means you can swap any piece without touching the others.

### The Parser Layer

The central insight is that checks shouldn't care whether the input is Markdown or MediaWiki. So we parse everything into a shared `ParsedDocument` — a format-agnostic representation that contains:
- **Text segments** (paragraphs, headings, list items) with line numbers
- **Headings** with level and position
- **Code blocks** with optional language tag
- **Raw lines** for line-level scanning (security checks)

Two parsers implement this interface:
- `MarkdownParser` uses **markdown-it-py**, which tokenizes Markdown into a stream of open/close/inline tokens. Each token carries a `map` attribute with `[start_line, end_line]`, so we get accurate line numbers for free. The parser detects and strips YAML front matter (`---` delimited blocks at file start) before parsing, tracking the line offset so all downstream line numbers remain correct. It uses a stack-based `list_depth` counter to handle arbitrarily nested lists without double-counting content. The `MarkdownIt` instance is a module-level singleton, since it's stateless per `parse()` call.
- `MediaWikiParser` uses **mwparserfromhell**, which parses wikitext into a node tree. The catch: mwparserfromhell doesn't track line numbers natively. We build a `_LineIndex` — a sorted array of line-start offsets computed once per file — and use `bisect.bisect_right` (binary search) for O(log n) lookups instead of scanning the raw content linearly for each node.

The parser factory (`factory.py`) routes files by extension: `.md` → Markdown parser, `.wiki` → MediaWiki parser.

### The Check Engine

Every check is a self-contained class that implements `BaseCheck`:

```python
class BaseCheck(ABC):
    check_id: str       # "passive-voice", "aws-key-exposed", etc.
    description: str    # Human-readable
    category: str       # "style", "formatting", "security", "terminology"

    def run(self, document: ParsedDocument, filepath: str, config: AppConfig) -> list[Violation]:
        ...

    def get_severity(self, config: AppConfig) -> Severity:
        # Config overrides only when explicit; otherwise uses check's default_severity
        ...
```

Checks are listed in `checks/__init__.py` as a `__register__` list. The `LintEngine` receives a `CheckRegistry` via dependency injection (or builds a default one from `__register__`). The engine iterates all registered checks, runs each one against the parsed document, collects violations, applies suppression filters, and returns results. Adding a new check is one file + one import line.

The engine also supports:
- **Concurrent file processing** via `ThreadPoolExecutor` — when linting multiple files, they're processed in parallel (configurable `max_workers`, defaults to 4). Single files skip thread overhead.
- **Content-hash caching** — optional SHA-256 hashing to skip re-linting unchanged files. Cache entries are JSON files keyed by filepath hash. Opt-in via `cache_enabled: true` in config.

The 9 checks break into two categories:

**Deterministic (regex/rule-based):**
- `passive-voice` — regex matching "to be" verb + past participle (with an irregular verb list for common English verbs like "written", "built", "chosen"). Includes a stative adjective filter (`frozenset`) to reduce false positives on phrases like "is used to" or "was known for". Reports column positions for precise editor integration.
- `heading-hierarchy` — walks the heading list and flags any jump > 1 level
- `heading-casing` — sentence case or title case, configurable
- `line-length` — raw line scan with configurable max (default 120)
- `list-consistency` — detects mixed markers (`-` and `*`) in the same list block
- `code-block-language` — flags fenced code blocks with no language tag
- `aws-key-exposed` — regex for `AKIA` prefixed keys and secret keys in assignment context
- `pii-detected` — SSN, email, phone, credit card patterns (credit cards validated with Luhn algorithm)

**Hybrid (deterministic + LLM):**
- `terminology` — two-phase: first runs pre-compiled regex patterns against a YAML glossary of preferred/forbidden terms (glossary is loaded once and cached via `@lru_cache`, patterns compiled at load time into frozen `CompiledTerm` dataclasses), then optionally sends prose to GPT-4o via LangChain for nuanced terminology review. The LLM client is injectable via constructor for testability.

### The Hybrid LLM Architecture

This is the most architecturally interesting piece. The terminology check demonstrates a pattern you'll see in production AI tooling: **deterministic first, LLM second**.

Phase 1 runs regex against the glossary. This catches "blacklist" → "blocklist", "whitelist" → "allowlist", minimizing words like "just" and "simply", etc. It's fast, free, and 100% reliable.

Phase 2 sends prose chunks to GPT-4o with the glossary as context. The LLM catches things regex can't: conceptually similar but wrong terms, inconsistent abbreviations, informal language patterns. But it costs money, takes seconds, and might hallucinate.

The design rule: **LLM findings are always `info` severity, never `error`.** Deterministic checks gate the build. LLM findings are advisory. This means a flaky API response can never break your CI pipeline.

Graceful degradation is baked in at every level:
1. No `OPENAI_API_KEY`? Skip LLM checks, log info, continue.
2. API timeout? Catch exception, return empty list, log warning.
3. Response isn't valid JSON? Catch parse error, return empty list.
4. `--no-llm` flag? Skip LLM entirely. Designed for CI.

Safety measures:
- **Token budget** — LLM requests accumulate text chunks until hitting a configurable character limit (`max_tokens_per_request * 4`), preventing context window overflow and runaway costs.
- **Prompt sanitization** — User document text is wrapped in a code fence before being sent to the LLM, mitigating prompt injection from document content.

### Suppression System

Sometimes passive voice is intentional. The suppression system lets you silence specific rules:

```markdown
<!-- docops-disable passive-voice -->
This sentence was written deliberately in passive voice.
<!-- docops-enable passive-voice -->
```

The `SuppressionMap` parses all HTML comments at load time and builds a lookup table: `{line_number: set_of_suppressed_rule_ids}`. After checks run, `filter_violations()` removes any violation that falls on a suppressed line.

Block suppressions work across ranges. `<!-- docops-disable -->` with no rule ID suppresses everything until the matching enable.

### Configuration

A `.docops.yml` file in the repo root controls everything: which checks are enabled, severity levels, glossary path, line length limit, LLM toggle, concurrency settings, and caching. The config layer uses typed dataclasses (`AppConfig`, `LLMConfig`, `CheckConfig`) instead of raw dicts, giving you IDE autocomplete, constructor-time validation, and a single source of truth for defaults. The YAML loader parses raw config into these typed structures once, so all downstream code works with clean, typed data.

---

## Codebase Structure

```
docops-governance-workbench/
├── docops/
│   ├── cli.py              ← Typer CLI: lint, init, list-checks
│   ├── config.py           ← Typed AppConfig/LLMConfig/CheckConfig dataclasses + YAML loader
│   ├── engine.py           ← Lint orchestrator (ThreadPoolExecutor, content-hash cache)
│   ├── models.py           ← Violation, LintResult, Severity
│   ├── registry.py         ← DI-based check registry (plain container, no singleton)
│   ├── suppression.py      ← Inline comment suppression
│   ├── parsers/
│   │   ├── base.py         ← ParsedDocument + BaseParser ABC
│   │   ├── markdown_parser.py  ← YAML front matter, stack-based list nesting
│   │   ├── mediawiki_parser.py ← bisect-based O(log n) line index
│   │   └── factory.py      ← Extension → parser routing
│   ├── checks/
│   │   ├── base.py         ← BaseCheck ABC (typed config, severity resolution)
│   │   ├── passive_voice.py ← Stative adjective filter, column reporting
│   │   ├── formatting.py   ← 5 sub-checks in one file
│   │   ├── terminology.py  ← LRU-cached glossary, pre-compiled patterns, LLM DI
│   │   ├── aws_keys.py
│   │   └── pii.py          ← Luhn validation, column reporting
│   ├── llm/
│   │   ├── client.py       ← LangChain wrapper (token budget, prompt sanitization)
│   │   └── prompts.py      ← System/user prompt templates
│   └── output/
│       ├── console.py      ← Rich-based colored output
│       └── json_output.py  ← Machine-readable JSON
├── glossary/
│   └── default.yml         ← Terminology: preferred/forbidden terms
├── tests/                  ← 74 tests, all passing in 0.24s
├── .docops.yml             ← Default config
├── Optimization.md         ← Detailed writeup of all architectural optimizations
└── pyproject.toml          ← Package metadata + dependencies
```

**How the pieces connect:** `cli.py` calls `config.py` to load settings into a typed `AppConfig`, passes it to `LintEngine` in `engine.py`. The engine builds a `CheckRegistry` via dependency injection (or uses the default one from `checks/__init__.py`). For multiple files, the engine fans out work across a thread pool. For each file, it uses `factory.py` to get the right parser, parses the file, runs every registered check, applies suppression from `suppression.py`, and returns `LintResult` objects. The CLI then passes results to either `console.py` or `json_output.py` for display.

---

## Technology Choices

| Technology | Why |
|---|---|
| **Python** | The lingua franca of tooling and scripting. Every CI system supports it. |
| **Typer** | CLI framework built on Click but uses type hints for argument definition. Auto-generates help docs. Minimal boilerplate. |
| **Rich** | Terminal formatting library. Gives us colored output, severity icons, and clean tables without managing ANSI escape codes. |
| **markdown-it-py** | CommonMark-compliant Markdown parser that produces a token stream with line numbers. Most alternatives (mistune, markdown) parse to HTML, losing structural information we need. |
| **mwparserfromhell** | The only serious Python library for MediaWiki parsing. Used by Wikipedia's own tooling. |
| **LangChain + OpenAI** | LangChain abstracts the OpenAI API, gives us retry logic, message types, and makes it trivial to swap providers later. |
| **PyYAML** | Config and glossary files are YAML. It's the standard for human-editable configuration. |
| **pytest** | Test framework. No question here — it's the Python standard. |

---

## Lessons Learned

### 1. The Duplicate List Item Bug (and Its Evolution)

When we first built the Markdown parser, list items generated duplicate violations. The reason: `markdown-it-py` wraps list item content in `paragraph_open` / `paragraph_close` tokens. Our parser was adding the text once when it hit the `list_item_open` handler (where we walked inner tokens) and again when the main loop hit the `paragraph_open` inside the list item.

**First fix:** Track an `in_list_item` boolean. When inside a list item, skip the `paragraph_open` handler.

**Second fix (optimization pass):** The boolean broke for nested lists — a list inside a list would reset to `False` when the inner list closed, even though we're still inside the outer list. Replaced it with a `list_depth` integer counter. Increment on `list_item_open`, decrement on `list_item_close` (clamped to 0). Skip `paragraph_open` when `list_depth > 0`.

**Lesson:** When walking token streams, always be aware of nesting. And when your first fix uses a boolean, ask "will this break with two levels of nesting?" A counter is almost always the right generalization.

### 2. MediaWiki Doesn't Give You Line Numbers (and How We Got Fast)

`mwparserfromhell` parses into a string-based AST. Nodes know their text content but not their position in the original file.

**First approach:** Search for each node's text within the raw content using `content.find(node_str)`. This broke when the same text appears twice. Fixed with an advancing `offset` cursor.

**Optimized approach:** Build a `_LineIndex` once per file — a sorted array of byte offsets where each line starts. Then use `bisect.bisect_right` for O(log n) line number lookups instead of O(n) linear scans. For a 1,000-line document with 50 nodes, this cuts character comparisons from ~50,000 to ~1,500.

**Lesson:** Not all parsers give you what you need. When they don't, choose the right data structure for the workaround. Sorted array + binary search is an underused combination in Python (`bisect` module).

### 3. Credit Card False Positives and the Luhn Algorithm

Version numbers, port ranges, and hex sequences all look like credit card numbers to a naive regex. The Luhn algorithm is the standard checksum validation for credit card numbers. By running Luhn on every regex match, we eliminate nearly all false positives for free. A version string like `1234-5678-9012-3456` fails Luhn; a real card number like `4111-1111-1111-1111` passes.

**Lesson:** For patterns with high false positive rates, add a secondary validation step. Regex gets you candidates; validation confirms them.

### 4. LLM Results Should Never Gate a Build

If you let LLM output determine whether a build passes or fails, you've made your CI pipeline dependent on an external API that has variable latency, costs money per call, and occasionally hallucinates. The architecture decision here is firm: deterministic checks return `error` or `warning` severity. LLM checks return `info`. Only `error` severity (configurable to `warning`) gates the build.

**Lesson:** AI-assisted tooling works best when the AI is advisory, not authoritative. Let deterministic rules be the guardrails. Let the LLM be the reviewer.

### 5. The Registry Pattern Makes Extension Easy (Now With DI)

Every check is a standalone class with a `run()` method. Adding a new check requires: (1) create a new file in `checks/`, (2) import it in `checks/__init__.py`, (3) add it to the `__register__` list. Zero changes to the engine, CLI, or output layer.

The original implementation used a singleton registry with `reset()` and `register_many()`. The optimization pass replaced it with dependency injection: the engine accepts an optional `CheckRegistry` in its constructor, defaulting to one built from `__register__`. This made tests cleaner (inject a mock registry with just the check you're testing), enabled thread safety (no shared mutable state), and eliminated the `reset()` smell.

**Lesson:** If you're calling `reset()` anywhere, your architecture has a problem. The need to reset state is a code smell for "I'm using shared mutable state as a poor man's parameter passing." Fix it by making the dependency an explicit constructor parameter.

### 6. Type Your Boundaries (The Severity Bug)

When we migrated from raw `dict` config to typed `AppConfig` dataclasses, we uncovered a real bug. The `CheckConfig` dataclass defaults `severity` to `"warning"`. But checks like `AwsKeyCheck` and `PiiCheck` set `default_severity = Severity.ERROR`. When config had no entry for a check, `check_severity()` returned the `CheckConfig` default (`"warning"`), silently overriding the check's own default.

**Fix:** `check_severity()` returns `None` for unconfigured checks. `BaseCheck.get_severity()` uses the check's own `default_severity` when config returns `None`. Config overrides only when explicit.

**Lesson:** Defaults should flow from the most specific source. A check knows its own default severity better than a generic config container. Type migrations are the best time to find these hidden assumption mismatches — the compiler (or in Python, the type checker) forces you to think about every code path.

### 7. The `.pth` File Saga

Python's editable install mechanism (`pip install -e .`) uses `.pth` files in `site-packages` to add source directories to `sys.path`. On some Python installations, these `.pth` files silently fail to load. We spent time debugging why `import docops` failed after a successful install — the `.pth` file was present but not being processed.

**Fix:** Switched from `src/` layout to flat layout (package at repo root) and recreated the venv with upgraded setuptools.

**Lesson:** Python packaging is still fragile. When editable installs break, the first thing to try is a fresh venv with `pip install --upgrade pip setuptools wheel` before the editable install.

---

## How to Plug Into CI/CD

The tool is designed for CI but doesn't ship CI config. Here's what makes it pluggable:

**Exit codes:** 0 = clean, 1 = violations above threshold, 2 = tool error.

**GitHub Actions:**
```yaml
name: Docs Lint
on:
  pull_request:
    paths: ["docs/**", "*.md"]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install docops-governance-workbench
      - run: docops lint docs/ --no-llm
```

**GitLab CI:**
```yaml
docs-lint:
  image: python:3.12-slim
  script:
    - pip install docops-governance-workbench
    - docops lint docs/ --no-llm
  rules:
    - changes: ["docs/**", "*.md"]
```

**Key flags for CI:**
- `--no-llm` — skip LLM checks (no API key needed, no cost, deterministic)
- `--json` — machine-readable output for PR comment bots
- `--checks aws-key-exposed,pii-detected` — run only security checks as a fast pre-merge gate

**To add LLM checks in CI:** Set `OPENAI_API_KEY` as a CI secret. Remove `--no-llm`. LLM findings will appear in output but won't fail the build (they're `info` severity).

---

## Running It

```bash
# Create venv and install
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Lint files
docops lint README.md
docops lint docs/
docops lint docs/ --json
docops lint docs/ --no-llm
docops lint docs/ --checks passive-voice,terminology --verbose

# Generate config
docops init

# List checks
docops list-checks

# Run tests
pytest tests/ -v
```
