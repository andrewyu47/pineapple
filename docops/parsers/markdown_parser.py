"""Markdown parser using markdown-it-py.

Optimized:
- YAML front matter detection: skips --- delimited blocks at file start.
- Stack-based list nesting: handles nested lists correctly.
- MarkdownIt instance reused across files (it's stateless per parse call).
"""

from __future__ import annotations

import re

from markdown_it import MarkdownIt

from docops.parsers.base import (
    BaseParser,
    CodeBlock,
    HeadingNode,
    ParsedDocument,
    TextSegment,
)

_FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)

# Module-level singleton: MarkdownIt is stateless per parse() call, safe to share.
_MD = MarkdownIt("commonmark", {"breaks": True})


class MarkdownParser(BaseParser):
    def supports(self, filename: str) -> bool:
        return filename.lower().endswith((".md", ".markdown", ".mdx"))

    def parse(self, content: str, filename: str) -> ParsedDocument:
        # Strip YAML front matter before parsing
        front_matter_offset = 0
        fm_match = _FRONT_MATTER_RE.match(content)
        if fm_match:
            front_matter_offset = fm_match.group().count("\n")
            content_to_parse = content[fm_match.end():]
        else:
            content_to_parse = content

        tokens = _MD.parse(content_to_parse)
        raw_lines = content.splitlines()
        headings: list[HeadingNode] = []
        text_segments: list[TextSegment] = []
        code_blocks: list[CodeBlock] = []

        i = 0
        list_depth = 0  # Stack counter for nested lists
        while i < len(tokens):
            token = tokens[i]

            if token.type == "heading_open":
                level = int(token.tag[1])
                line_start = self._line(token, front_matter_offset)
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    heading_text = tokens[i + 1].content
                    headings.append(HeadingNode(text=heading_text, level=level, line_number=line_start))
                    text_segments.append(TextSegment(text=heading_text, line_start=line_start, line_end=line_start, segment_type="heading"))

            elif token.type == "paragraph_open" and list_depth == 0:
                line_start = self._line(token, front_matter_offset)
                line_end = self._line_end(token, front_matter_offset)
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    text_segments.append(TextSegment(
                        text=tokens[i + 1].content,
                        line_start=line_start, line_end=line_end,
                        segment_type="paragraph",
                    ))

            elif token.type == "fence":
                lang = token.info.strip() or None
                line_start = self._line(token, front_matter_offset)
                line_end = self._line_end(token, front_matter_offset)
                code_blocks.append(CodeBlock(language=lang, content=token.content, line_start=line_start, line_end=line_end))

            elif token.type == "list_item_open":
                list_depth += 1
                line_start = self._line(token, front_matter_offset)
                line_end = self._line_end(token, front_matter_offset)
                j = i + 1
                while j < len(tokens) and tokens[j].type != "list_item_close":
                    if tokens[j].type == "inline":
                        text_segments.append(TextSegment(
                            text=tokens[j].content,
                            line_start=line_start, line_end=line_end,
                            segment_type="list_item",
                        ))
                    j += 1

            elif token.type == "list_item_close":
                list_depth = max(0, list_depth - 1)

            i += 1

        return ParsedDocument(
            raw_lines=raw_lines,
            text_segments=text_segments,
            headings=headings,
            code_blocks=code_blocks,
            raw_text=content,
            format_type="markdown",
        )

    @staticmethod
    def _line(token, offset: int) -> int:
        return (token.map[0] + 1 + offset) if token.map else 1

    @staticmethod
    def _line_end(token, offset: int) -> int:
        return (token.map[1] + offset) if token.map else 1
