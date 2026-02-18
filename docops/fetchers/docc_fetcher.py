"""DocC Render JSON fetcher: HTTP client for Apple's public documentation API.

Handles single-symbol fetches and recursive framework crawls.
Includes in-memory caching and rate limiting.
"""

from __future__ import annotations

import logging
import re
import time

import httpx

logger = logging.getLogger(__name__)

_EXTERNAL_PREFIX = "doc://com.externally.resolved.symbol/"
_DOC_PREFIX_RE = re.compile(r"^doc://com\.apple\.\w+/documentation/")


class DoccFetcher:
    """Fetch and crawl Apple's DocC Render JSON API."""

    BASE_URL = "https://developer.apple.com/tutorials/data/documentation"

    def __init__(
        self,
        cache: dict[str, dict] | None = None,
        rate_limit: float = 0.25,
        timeout: float = 15.0,
    ):
        self._cache: dict[str, dict] = cache if cache is not None else {}
        self._rate_limit = rate_limit
        self._timeout = timeout
        self._last_request_time = 0.0

    @property
    def cache(self) -> dict[str, dict]:
        return self._cache

    def fetch(self, framework: str, symbol_path: str = "") -> dict:
        """Fetch a single DocC JSON document by framework and optional symbol path."""
        path = f"{framework}/{symbol_path}".rstrip("/").lower()
        url = f"{self.BASE_URL}/{path}.json"

        cache_key = f"doc://com.apple.{framework}/documentation/{path}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        data = self._http_get(url)
        self._cache[cache_key] = data
        return data

    def fetch_by_identifier(self, identifier: str) -> dict | None:
        """Fetch a DocC JSON document by its doc:// identifier. Returns None for external symbols."""
        if self.is_external(identifier):
            return None

        if identifier in self._cache:
            return self._cache[identifier]

        url = self._build_url(identifier)
        if url is None:
            return None

        try:
            data = self._http_get(url)
            self._cache[identifier] = data
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"404 for identifier: {identifier}")
                return None
            raise

    def crawl_framework(self, framework: str, max_depth: int = 2) -> list[dict]:
        """BFS crawl a framework via topicSections identifiers."""
        root = self.fetch(framework)
        results = [root]

        # BFS queue: (identifier, depth)
        queue: list[tuple[str, int]] = []
        seen: set[str] = {root.get("identifier", {}).get("url", "")}

        # Seed from root topicSections
        for section in root.get("topicSections", []):
            for ident in section.get("identifiers", []):
                if not self.is_external(ident) and ident not in seen:
                    queue.append((ident, 1))
                    seen.add(ident)

        while queue:
            identifier, depth = queue.pop(0)
            data = self.fetch_by_identifier(identifier)
            if data is None:
                continue

            results.append(data)

            if depth < max_depth:
                for section in data.get("topicSections", []):
                    for child_ident in section.get("identifiers", []):
                        if not self.is_external(child_ident) and child_ident not in seen:
                            queue.append((child_ident, depth + 1))
                            seen.add(child_ident)

        return results

    def _build_url(self, identifier: str) -> str | None:
        """Convert a doc:// identifier to an API URL.

        Example: doc://com.apple.avkit/documentation/AVKit/AVPlayerViewController
        -> https://developer.apple.com/tutorials/data/documentation/avkit/avplayerviewcontroller.json
        """
        if self.is_external(identifier):
            return None

        # Strip doc:// prefix up to and including "documentation/"
        match = _DOC_PREFIX_RE.match(identifier)
        if not match:
            logger.debug(f"Cannot parse identifier: {identifier}")
            return None

        # Everything after "documentation/" is the path (e.g. "AVKit/AVPlayerViewController")
        path = identifier[match.end():].lower()
        # Extract framework name from the prefix
        fw_match = re.search(r"doc://com\.apple\.(\w+)/", identifier)
        fw_name = fw_match.group(1).lower() if fw_match else ""

        # The path already starts with the framework (AVKit -> avkit), so check
        # if it does and avoid duplication
        if path.startswith(fw_name + "/") or path == fw_name:
            return f"{self.BASE_URL}/{path}.json"
        return f"{self.BASE_URL}/{fw_name}/{path}.json"

    @staticmethod
    def is_external(identifier: str) -> bool:
        """Check if an identifier is an external (non-Apple-framework) symbol."""
        return identifier.startswith(_EXTERNAL_PREFIX)

    def _http_get(self, url: str) -> dict:
        """Make a rate-limited HTTP GET request."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)

        response = httpx.get(url, timeout=self._timeout, follow_redirects=True)
        self._last_request_time = time.monotonic()
        response.raise_for_status()
        return response.json()
