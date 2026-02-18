# Optimization.md - What Changed and Why

This document walks through the architectural refactoring of the DocOps Governance Workbench, explaining every optimization, the reasoning behind it, and what you can learn from each one. Think of it as a guided tour through the mind of a senior engineer refactoring a working prototype into production-grade code.

---

## The Big Picture

The original codebase worked. All 73 tests passed. It linted Markdown and MediaWiki files, detected passive voice, formatting issues, AWS keys, PII, and terminology violations. It had a CLI, JSON output, and even LLM-powered terminology checking.

But "works" isn't the same as "works well at scale, is easy to maintain, and won't bite you at 3 AM." The refactoring focused on three pillars:

1. **Correctness under scale** - Will it work when you throw 500 files at it?
2. **Maintainability** - Can a new engineer understand and extend it without reading the whole codebase?
3. **Safety** - Does it handle edge cases, fail gracefully, and resist misuse?

---

## 1. Dependency Injection Over Singletons

### What Changed
`CheckRegistry` was a singleton with `reset()` and `register_many()` methods. The engine imported a global `__register__` list and mutated a shared registry instance.

**Before:**
```python
class LintEngine:
    def __init__(self, config: dict):
        self._registry = CheckRegistry()
        self._registry.reset()          # Wipe global state
        self._registry.register_many(__register__)  # Re-populate
```

**After:**
```python
class LintEngine:
    def __init__(self, config: AppConfig, registry: CheckRegistry | None = None):
        self._registry = registry or _default_registry()
```

`CheckRegistry` is now a plain container that accepts a list of checks in its constructor. No `reset()`, no `register_many()`, no global mutable state.

### Why This Matters
Singletons are the "global variables" of OOP. They make testing painful (you have to reset state between tests), prevent parallelism (shared mutable state + threads = bugs), and create hidden coupling (anyone can import and mutate the singleton from anywhere).

With DI, each engine instance owns its registry. Tests can inject mock registries. You can run multiple engines with different check sets in the same process without them stepping on each other.

### Lesson
**If you're calling `reset()` anywhere, your architecture has a problem.** The need to reset state is a code smell that says "I'm using shared mutable state as a poor man's parameter passing." Fix it by making the dependency an explicit constructor parameter.

---

## 2. Type-Safe Config with Dataclasses

### What Changed
Configuration was a raw `dict` passed around everywhere. Every check did `config.get("checks", {}).get(self.check_id, {}).get("severity", "warning")` - a chain of defensive `.get()` calls that obscured intent and was easy to typo.

**Before:**
```python
def run(self, document, filepath, config: dict):
    max_len = config.get("checks", {}).get("line-length", {}).get("max_length", 120)
```

**After:**
```python
@dataclass
class AppConfig:
    checks: dict[str, CheckConfig]
    llm: LLMConfig
    # ...
    def check_option(self, check_id: str, key: str, default=None):
        return self.get_check(check_id).options.get(key, default)
```
```python
def run(self, document, filepath, config: AppConfig):
    max_len = config.check_option(self.check_id, "max_length", 120)
```

### Why This Matters
Raw dicts are "stringly typed" - the type system can't help you, your IDE can't autocomplete, and a typo like `"enbled"` instead of `"enabled"` silently gives you the default value. Dataclasses give you:

- **Autocomplete and IDE support** - `config.llm.` shows you `enabled`, `model`, `max_tokens_per_request`
- **Constructor-time validation** - Wrong field names are caught immediately
- **Single source of truth for defaults** - Defaults live in the dataclass, not scattered across 15 `.get()` calls
- **Readable code** - `config.llm.enabled` vs `config.get("llm", {}).get("enabled", False)`

### The Severity Bug
This refactoring surfaced a real bug. The old code defaulted all severities to `"warning"` when not configured. But AWS key and PII checks have `default_severity = ERROR` - they should be errors unless explicitly overridden. The fix: `check_severity()` returns `None` for unconfigured checks, letting `BaseCheck.get_severity()` fall back to the check's own default.

### Lesson
**Type your boundaries.** Raw dicts are fine for deserialization (YAML → dict), but the moment data crosses into your domain logic, convert it to typed structures. The conversion layer (`_build_config()`) is where you validate, normalize, and handle missing fields - once. Then everything downstream works with clean, typed data.

---

## 3. Pre-Compiled and Cached Regex Patterns

### What Changed

**Terminology glossary:** Previously loaded and compiled on every `run()` call for every file. Now compiled once and cached with `@lru_cache(maxsize=8)`.

```python
@dataclass(frozen=True)
class CompiledTerm:
    pattern: re.Pattern
    preferred: str
    severity: str
    reason: str

@lru_cache(maxsize=8)
def _load_and_compile_glossary(glossary_path: str) -> tuple[CompiledTerm, ...]:
    # Load YAML, compile all patterns, return frozen tuple (hashable for cache)
```

**PII detection:** `_NON_DIGIT_RE = re.compile(r"[^0-9]")` moved to module level instead of being implicitly recompiled inside `_luhn_check()` on every call.

**Passive voice:** Stative adjective filter added as a `frozenset` for O(1) lookups, reducing false positives on phrases like "is used to" or "was known".

### Why This Matters
Regex compilation is expensive - roughly 100x slower than matching against a compiled pattern. If you're linting 500 files with 8 glossary terms, that's 4,000 unnecessary recompilations. The `@lru_cache` ensures the glossary is loaded and compiled exactly once per unique path.

The `CompiledTerm` is a frozen dataclass (immutable, hashable) so it can be stored in a tuple (hashable for LRU cache keys). This is a common pattern: make your cache values immutable so the cache can safely share them.

### Lesson
**Profile before optimizing, but know your complexity classes.** Regex compilation inside a loop is O(n * compile_cost). Moving it outside is O(compile_cost) + O(n * match_cost). You don't need a profiler to know that's better. But don't prematurely optimize things that run once - focus on hot paths (per-file, per-segment, per-line operations).

---

## 4. O(log n) Line Lookups in MediaWiki Parser

### What Changed
The MediaWiki parser needed to map parsed nodes back to source line numbers. The old approach did a linear scan through the raw content for each node.

**After:**
```python
class _LineIndex:
    __slots__ = ("_offsets",)

    def __init__(self, text: str):
        self._offsets = [0]
        for i, ch in enumerate(text):
            if ch == "\n":
                self._offsets.append(i + 1)

    def line_of(self, offset: int) -> int:
        return bisect.bisect_right(self._offsets, offset)
```

Build a sorted array of line-start offsets once, then use `bisect.bisect_right` (binary search) for each lookup. O(n) build + O(log n) per query vs O(n) per query.

### Why This Matters
If a MediaWiki document has 1,000 lines and 50 nodes, the old approach does ~50,000 character comparisons. The new approach does ~1,000 (build) + ~500 (50 * log2(1000) ~= 10 per query). That's a 50x improvement for large documents.

`__slots__` is a minor memory optimization - prevents the creation of a `__dict__` for each instance. Worth doing for utility classes that may be instantiated frequently.

### Lesson
**Know your data structures.** "Can I do this with a sorted array + binary search?" is a question you should ask whenever you see a linear scan inside a loop. Python's `bisect` module is underused and extremely efficient.

---

## 5. Concurrent File Processing

### What Changed
`lint_paths()` now uses `ThreadPoolExecutor` to lint multiple files concurrently.

```python
def lint_paths(self, paths: list[str]) -> list[LintResult]:
    file_paths = self._collect_files(paths)

    if len(file_paths) == 1:
        return [self.lint_file(file_paths[0])]  # Skip thread overhead

    with ThreadPoolExecutor(max_workers=min(self.config.max_workers, len(file_paths))) as executor:
        future_to_path = {executor.submit(self.lint_file, fp): fp for fp in file_paths}
        for future in as_completed(future_to_path):
            # ...
    results.sort(key=lambda r: r.file)  # Stable ordering
```

### Why This Matters
File linting is I/O-bound (reading files) with some CPU work (regex matching). Python's GIL allows threads to run concurrently during I/O. For 100 files, you get near-linear speedup up to the number of cores.

Key design decisions:
- **Skip for single files** - Thread pool creation has overhead (~1ms). Not worth it for one file.
- **`max_workers` capped** - `min(config.max_workers, len(file_paths))` prevents creating 4 threads for 2 files.
- **Results sorted after completion** - `as_completed` returns results in arbitrary order. Sorting by file path gives deterministic output.
- **Per-file error isolation** - If one file fails, others still complete. The failed file gets a `LintResult` with `skipped_checks=["all"]`.

### Lesson
**Concurrency is about architecture, not just `ThreadPoolExecutor`.** The reason this was easy to add is that `lint_file()` was already stateless - it reads a file, runs checks, returns a result. No shared mutable state. If the original code had checks writing to a shared violation list, parallelism would have been a nightmare. **Design for statelessness first, add concurrency second.**

---

## 6. Content-Hash Caching

### What Changed
Optional SHA-256 content hashing to skip re-linting unchanged files.

```python
if self.config.cache_enabled:
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    cached = self._read_cache(filepath, content_hash)
    if cached is not None:
        return cached
```

Cache entries are JSON files stored in `.docops_cache/` (configurable), keyed by a hash of the filepath. Each entry stores the content hash and the full violation list. If the file's content hash matches the cached hash, we skip all parsing and checking.

### Why This Matters
In CI/CD, you often re-lint a repo where 95% of files haven't changed. Hashing a file is ~1000x faster than parsing and running all checks on it. The cache is opt-in (`cache_enabled: true` in config) because:

- Cache invalidation is hard (what if you change a glossary term? The cache doesn't know)
- The default behavior should always be correct, not fast-but-possibly-stale
- CI environments often start fresh anyway

### Lesson
**Make optimizations opt-in when they trade correctness for speed.** Caching is powerful but introduces a new failure mode: stale data. By making it opt-in with a clear config flag, you let users choose the tradeoff. And always implement the "no cache" path first, test it thoroughly, then add caching as a layer on top.

---

## 7. Parser Improvements

### YAML Front Matter Detection (Markdown)
```python
_FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
```
Strips `---` delimited YAML front matter before parsing. Tracks the line offset so all downstream line numbers remain correct. Without this, front matter content would trigger false positives (terminology matches in YAML keys, line length violations, etc.)

### Stack-Based List Nesting
```python
list_depth = 0  # Increment on list_item_open, decrement on list_item_close
```
The original code had a boolean `in_list_item` flag. This broke for nested lists (a list inside a list would reset to `False` when the inner list closed, even though we're still inside the outer list). A depth counter handles arbitrary nesting correctly.

### Module-Level MarkdownIt Singleton
```python
_MD = MarkdownIt("commonmark", {"breaks": True})
```
`MarkdownIt` instances are stateless per `parse()` call, so a single instance can be safely shared across all files. Avoids re-creating the parser (and its plugin chain) for every file.

### Lesson
**Edge cases in parsers are where bugs live.** Front matter, nested structures, and stateless-vs-stateful parser instances are exactly the kind of things that work fine in happy-path tests but break on real documents. The fix is always the same: enumerate the edge cases explicitly, write tests for them, and handle them in the parser before the data reaches your checks.

---

## 8. LLM Hardening

### Token Budget
```python
_CHARS_PER_TOKEN = 4
max_chars = config.llm.max_tokens_per_request * _CHARS_PER_TOKEN

for chunk in text_chunks:
    if char_count + len(chunk) > max_chars:
        break  # Stop before exceeding budget
```
Without a budget, a 10,000-line document could send a massive prompt that exceeds the model's context window, fails, and wastes money. The budget ensures we send a predictable amount of text.

### Prompt Sanitization
```python
sanitized_text = f"```text\n{combined_text}\n```"
```
User document text is wrapped in a code fence before being sent to the LLM. This is a defense-in-depth measure against prompt injection - if a document contains text like "Ignore all previous instructions and...", the code fence signals to the model that this is data, not instructions.

### Lesson
**Treat LLM calls like external API calls: budget them, sanitize inputs, and handle failures gracefully.** The LLM is the most expensive, slowest, and least predictable component in the system. Every interaction should have a timeout, a retry limit, a budget, and a fallback path.

---

## 9. Severity Resolution Fix

### The Bug
With the new `AppConfig`, `check_severity()` returned `"warning"` for unconfigured checks (the `CheckConfig` default). But checks like `AwsKeyCheck` and `PiiCheck` set `default_severity = Severity.ERROR`. The config default was overriding the check's own default.

### The Fix
`check_severity()` now returns `None` for unconfigured checks. `BaseCheck.get_severity()` uses the check's `default_severity` when config returns `None`:

```python
def get_severity(self, config: AppConfig) -> Severity:
    sev_str = config.check_severity(self.check_id)
    if sev_str is None:
        return self.default_severity  # Check knows its own default
    try:
        return Severity(sev_str)
    except ValueError:
        return self.default_severity
```

### Lesson
**Defaults should flow from the most specific source.** A check knows its own default severity better than a generic config container does. The config should only override when explicitly set. This is the "convention over configuration" principle - the system has sensible defaults, and config only exists to override them.

---

## Summary of Changes

| Area | Before | After | Impact |
|------|--------|-------|--------|
| Registry | Singleton with `reset()` | DI-based plain container | Testable, thread-safe |
| Config | Raw `dict` with `.get()` chains | Typed `AppConfig` dataclass | IDE support, fewer bugs |
| Glossary | Loaded per-file | `@lru_cache`, compiled once | ~100x faster for repeated files |
| MediaWiki lines | Linear scan per node | `bisect` binary search | O(log n) vs O(n) per lookup |
| File processing | Sequential | `ThreadPoolExecutor` | Near-linear speedup on multi-file |
| Caching | None | SHA-256 content-hash | Skip unchanged files entirely |
| Front matter | Not handled | Regex detection + offset | Correct line numbers, no false positives |
| List nesting | Boolean flag | Depth counter | Correct for nested lists |
| LLM calls | Unbounded | Token budget + sanitization | Predictable cost, injection defense |
| Severity | Config overrides check defaults | Config overrides only when explicit | AWS keys and PII correctly report as errors |

**Test count: 74 passing (was 73, added config tests) in 0.24s.**
