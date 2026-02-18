"""MediaWiki markup parser using mwparserfromhell.

Optimized: pre-computed line index for O(log n) line number lookups
instead of O(n) string scanning per node.
"""

from __future__ import annotations

import bisect
import logging

import mwparserfromhell

from docops.parsers.base import (
    BaseParser,
    CodeBlock,
    HeadingNode,
    ParsedDocument,
    TextSegment,
)

logger = logging.getLogger(__name__)


class _LineIndex:
    """Pre-computed newline offset table for O(log n) byte-offset to line-number lookups."""

    __slots__ = ("_offsets",)

    def __init__(self, content: str):
        self._offsets: list[int] = [0]
        pos = 0
        while True:
            pos = content.find("\n", pos)
            if pos == -1:
                break
            pos += 1
            self._offsets.append(pos)

    def line_at(self, byte_offset: int) -> int:
        """Return 1-indexed line number for a byte offset."""
        return bisect.bisect_right(self._offsets, byte_offset)


class MediaWikiParser(BaseParser):
    def supports(self, filename: str) -> bool:
        return filename.lower().endswith((".wiki", ".mediawiki"))

    def parse(self, content: str, filename: str) -> ParsedDocument:
        wikicode = mwparserfromhell.parse(content)
        raw_lines = content.splitlines()
        line_index = _LineIndex(content)
        headings: list[HeadingNode] = []
        text_segments: list[TextSegment] = []
        code_blocks: list[CodeBlock] = []

        offset = 0

        for node in wikicode.nodes:
            node_str = str(node)
            idx = content.find(node_str, offset)
            if idx == -1:
                idx = content.find(node_str)
            if idx == -1:
                logger.debug(f"Could not locate node in content: {node_str[:40]}...")
                continue

            line_num = line_index.line_at(idx)
            node_end = line_num + node_str.count("\n")

            if isinstance(node, mwparserfromhell.nodes.Heading):
                heading_text = node.title.strip_code().strip()
                headings.append(HeadingNode(text=heading_text, level=node.level, line_number=line_num))
                text_segments.append(TextSegment(text=heading_text, line_start=line_num, line_end=line_num, segment_type="heading"))

            elif isinstance(node, mwparserfromhell.nodes.Tag):
                tag_name = str(node.tag)
                if tag_name in ("syntaxhighlight", "source", "code", "pre"):
                    lang_attr = node.get("lang") if node.has("lang") else None
                    lang = str(lang_attr.value) if lang_attr else None
                    code_blocks.append(CodeBlock(
                        language=lang,
                        content=node.contents.strip_code() if node.contents else "",
                        line_start=line_num, line_end=node_end,
                    ))
                else:
                    tag_text = node.contents.strip_code().strip() if node.contents else ""
                    if tag_text:
                        text_segments.append(TextSegment(text=tag_text, line_start=line_num, line_end=node_end, segment_type="paragraph"))

            elif isinstance(node, mwparserfromhell.nodes.Text):
                text = str(node).strip()
                if text:
                    text_segments.append(TextSegment(text=text, line_start=line_num, line_end=node_end, segment_type="paragraph"))

            elif isinstance(node, mwparserfromhell.nodes.Wikilink):
                link_text = str(node.text or node.title).strip()
                if link_text:
                    text_segments.append(TextSegment(text=link_text, line_start=line_num, line_end=line_num, segment_type="paragraph"))

            offset = idx + len(node_str)

        return ParsedDocument(
            raw_lines=raw_lines,
            text_segments=text_segments,
            headings=headings,
            code_blocks=code_blocks,
            raw_text=content,
            format_type="mediawiki",
        )
