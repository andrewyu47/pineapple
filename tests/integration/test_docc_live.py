"""Live API assertion tests for Apple DocC Render JSON.

These tests validate our schema assumptions against the real API.
Run with: pytest -m network tests/integration/
Skip with: pytest -m "not network"
"""

from __future__ import annotations

import pytest
import httpx

pytestmark = pytest.mark.network


# ──────────────────────────────────────────────────────────────
# Schema Validation: Does Apple's API return what we expect?
# ──────────────────────────────────────────────────────────────


class TestDoccApiSchema:
    """Validate that the DocC Render JSON API matches our assumptions."""

    @pytest.fixture(scope="class")
    def framework_root(self):
        resp = httpx.get(
            "https://developer.apple.com/tutorials/data/documentation/avkit.json",
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    @pytest.fixture(scope="class")
    def symbol_page(self):
        resp = httpx.get(
            "https://developer.apple.com/tutorials/data/documentation/avkit/avplayerviewcontroller.json",
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    # --- Top-level structure ---

    def test_has_schema_version(self, framework_root):
        sv = framework_root["schemaVersion"]
        assert sv["major"] == 0
        assert sv["minor"] >= 3

    def test_has_identifier(self, framework_root):
        ident = framework_root["identifier"]
        assert "url" in ident
        assert "interfaceLanguage" in ident
        assert ident["interfaceLanguage"] in ("swift", "occ")

    def test_has_kind(self, framework_root):
        assert framework_root["kind"] in ("symbol", "article")

    def test_has_abstract(self, framework_root):
        abstract = framework_root["abstract"]
        assert isinstance(abstract, list)
        assert len(abstract) > 0
        assert all("type" in node for node in abstract)

    def test_has_metadata(self, framework_root):
        meta = framework_root["metadata"]
        assert "title" in meta
        assert "role" in meta
        assert "platforms" in meta

    def test_has_topic_sections(self, framework_root):
        sections = framework_root["topicSections"]
        assert isinstance(sections, list)
        assert len(sections) > 0
        for section in sections:
            assert "title" in section
            assert "identifiers" in section
            assert all(isinstance(i, str) for i in section["identifiers"])

    def test_has_references(self, framework_root):
        refs = framework_root["references"]
        assert isinstance(refs, dict)
        assert len(refs) > 0

    def test_has_hierarchy(self, framework_root):
        hierarchy = framework_root["hierarchy"]
        assert "paths" in hierarchy
        assert isinstance(hierarchy["paths"], list)

    # --- Metadata fields ---

    def test_metadata_has_symbol_kind(self, framework_root):
        assert "symbolKind" in framework_root["metadata"]
        assert framework_root["metadata"]["symbolKind"] == "module"

    def test_platforms_have_expected_fields(self, framework_root):
        for p in framework_root["metadata"]["platforms"]:
            assert "name" in p
            assert "introducedAt" in p
            assert "beta" in p

    def test_platforms_include_known_names(self, framework_root):
        names = {p["name"] for p in framework_root["metadata"]["platforms"]}
        assert "iOS" in names
        assert "macOS" in names

    # --- Symbol page specifics ---

    def test_symbol_has_primary_content(self, symbol_page):
        sections = symbol_page["primaryContentSections"]
        assert isinstance(sections, list)
        assert len(sections) > 0
        kinds = [s["kind"] for s in sections]
        assert "declarations" in kinds or "content" in kinds

    def test_symbol_has_relationships(self, symbol_page):
        # Most class symbols have relationships (inheritsFrom, conformsTo)
        if "relationshipsSections" in symbol_page:
            for rel in symbol_page["relationshipsSections"]:
                assert "type" in rel
                assert "identifiers" in rel

    def test_symbol_metadata_has_fragments(self, symbol_page):
        meta = symbol_page["metadata"]
        if "fragments" in meta:
            for frag in meta["fragments"]:
                assert "kind" in frag
                assert "text" in frag

    # --- Inline content format ---

    def test_abstract_nodes_have_type(self, symbol_page):
        for node in symbol_page["abstract"]:
            assert "type" in node
            if node["type"] == "text":
                assert "text" in node
            elif node["type"] == "reference":
                assert "identifier" in node

    # --- Reference entries ---

    def test_references_have_required_fields(self, framework_root):
        for ref_id, ref in framework_root["references"].items():
            assert "type" in ref
            assert "kind" in ref or "role" in ref
            assert "url" in ref or "identifier" in ref
            assert "title" in ref

    def test_reference_urls_are_relative(self, framework_root):
        for ref_id, ref in framework_root["references"].items():
            url = ref.get("url", "")
            if url:
                assert url.startswith("/"), f"Expected relative URL, got: {url}"


# ──────────────────────────────────────────────────────────────
# Parser Validation: Does our parser handle real data correctly?
# ──────────────────────────────────────────────────────────────


class TestDoccParserOnLiveData:
    """Run our parser against real API data to validate it works."""

    @pytest.fixture(scope="class")
    def fetched_data(self):
        from docops.fetchers.docc_fetcher import DoccFetcher
        from docops.parsers.docc_parser import DoccParser

        fetcher = DoccFetcher()
        raw = fetcher.fetch("avkit")
        parser = DoccParser()
        doc = parser.parse(raw, raw["identifier"]["url"])
        return raw, doc

    def test_format_type_is_docc(self, fetched_data):
        _, doc = fetched_data
        assert doc.format_type == "docc"

    def test_extracts_abstract(self, fetched_data):
        _, doc = fetched_data
        abstracts = [s for s in doc.text_segments if s.segment_type == "abstract"]
        assert len(abstracts) >= 1
        assert len(abstracts[0].text) > 10

    def test_raw_text_not_empty(self, fetched_data):
        _, doc = fetched_data
        assert len(doc.raw_text) > 0


# ──────────────────────────────────────────────────────────────
# Check Validation: Do checks produce meaningful results?
# ──────────────────────────────────────────────────────────────


class TestDoccChecksOnLiveData:
    """Run checks against real API data to validate they work."""

    @pytest.fixture(scope="class")
    def avkit_context(self):
        from docops.config import AppConfig, CheckConfig
        from docops.fetchers.docc_fetcher import DoccFetcher
        from docops.parsers.docc_parser import DoccParser

        fetcher = DoccFetcher()
        raw = fetcher.fetch("avkit")
        parser = DoccParser()
        doc = parser.parse(raw, raw["identifier"]["url"])
        config = AppConfig()
        config.checks["docc-stale-platform"] = CheckConfig(options={"_docc_metadata": raw})
        config.checks["docc-missing-description"] = CheckConfig(options={"_docc_metadata": raw})
        return raw, doc, config

    def test_missing_description_passes_for_avkit(self, avkit_context):
        """AVKit has an abstract, so missing-description should not flag it."""
        from docops.checks.docc_checks import DoccMissingDescriptionCheck

        raw, doc, config = avkit_context
        check = DoccMissingDescriptionCheck()
        violations = check.run(doc, "avkit", config)
        assert len(violations) == 0

    def test_stale_platform_runs_without_error(self, avkit_context):
        """Check runs against real data without crashing."""
        from docops.checks.docc_checks import DoccStalePlatformCheck

        raw, doc, config = avkit_context
        check = DoccStalePlatformCheck()
        violations = check.run(doc, "avkit", config)
        # We expect some info-level staleness violations for old platforms (iOS 8.0)
        assert all(hasattr(v, "rule_id") for v in violations)


# ──────────────────────────────────────────────────────────────
# Fetcher Validation: Does URL construction work correctly?
# ──────────────────────────────────────────────────────────────


class TestDoccFetcherOnLiveData:
    """Validate the fetcher works against the real API."""

    def test_fetch_avkit_root(self):
        from docops.fetchers.docc_fetcher import DoccFetcher

        fetcher = DoccFetcher()
        data = fetcher.fetch("avkit")
        assert data["metadata"]["title"] == "AVKit"
        assert data["metadata"]["symbolKind"] == "module"

    def test_external_symbol_detection(self):
        from docops.fetchers.docc_fetcher import DoccFetcher

        fetcher = DoccFetcher()
        assert fetcher.is_external("doc://com.externally.resolved.symbol/s:ScM")
        assert not fetcher.is_external("doc://com.apple.avkit/documentation/AVKit")

    def test_fetch_by_identifier(self):
        from docops.fetchers.docc_fetcher import DoccFetcher

        fetcher = DoccFetcher()
        data = fetcher.fetch_by_identifier(
            "doc://com.apple.avkit/documentation/AVKit/AVPlayerViewController"
        )
        assert data is not None
        assert data["metadata"]["title"] == "AVPlayerViewController"

    def test_external_returns_none(self):
        from docops.fetchers.docc_fetcher import DoccFetcher

        fetcher = DoccFetcher()
        result = fetcher.fetch_by_identifier(
            "doc://com.externally.resolved.symbol/c:objc(cs)UIViewController"
        )
        assert result is None
