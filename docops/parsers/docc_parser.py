"""DocC Render JSON parser: converts Apple's API JSON into ParsedDocument.

Does not extend BaseParser since DocC data comes from HTTP, not files.
Produces the same ParsedDocument output for compatibility with all checks.
"""

from __future__ import annotations

import json

from docops.parsers.base import CodeBlock, HeadingNode, ParsedDocument, TextSegment


class DoccParser:
    """Parse Apple DocC Render JSON into a ParsedDocument."""

    def parse(self, data: dict, source_url: str) -> ParsedDocument:
        """Convert a DocC Render JSON dict into a ParsedDocument."""
        text_segments = self._extract_text_segments(data)
        headings = self._extract_headings(data)
        code_blocks = self._extract_code_blocks(data)

        raw_text = "\n".join(seg.text for seg in text_segments)
        raw_lines = raw_text.splitlines() if raw_text else []

        return ParsedDocument(
            raw_lines=raw_lines,
            text_segments=text_segments,
            headings=headings,
            code_blocks=code_blocks,
            raw_text=raw_text,
            format_type="docc",
        )

    def flatten_inline_content(self, nodes: list[dict]) -> str:
        """Recursively flatten inline content array into plain text."""
        parts: list[str] = []
        for node in nodes:
            node_type = node.get("type", "")
            if node_type == "text":
                parts.append(node.get("text", ""))
            elif node_type == "codeVoice":
                parts.append(node.get("code", ""))
            elif node_type == "reference":
                # Use title from the node if available, else identifier
                parts.append(node.get("title", node.get("identifier", "")))
            elif node_type in ("strong", "emphasis", "newTerm"):
                inner = node.get("inlineContent", [])
                parts.append(self.flatten_inline_content(inner))
            # Skip image nodes and unknown types
        return " ".join(p for p in parts if p)

    def _extract_text_segments(self, data: dict) -> list[TextSegment]:
        """Extract text segments from abstract, overview, and content sections."""
        segments: list[TextSegment] = []
        line = 1

        # Abstract
        abstract = data.get("abstract", [])
        if abstract:
            text = self.flatten_inline_content(abstract)
            if text.strip():
                segments.append(TextSegment(
                    text=text, line_start=line, line_end=line, segment_type="abstract",
                ))
                line += 1

        # Primary content sections
        for section in data.get("primaryContentSections", []):
            if section.get("kind") != "content":
                continue
            for block in section.get("content", []):
                block_type = block.get("type", "")
                if block_type == "paragraph":
                    text = self.flatten_inline_content(block.get("inlineContent", []))
                    if text.strip():
                        segments.append(TextSegment(
                            text=text, line_start=line, line_end=line, segment_type="paragraph",
                        ))
                        line += 1
                elif block_type == "heading":
                    text = block.get("text", "")
                    if text.strip():
                        segments.append(TextSegment(
                            text=text, line_start=line, line_end=line, segment_type="heading",
                        ))
                        line += 1
                elif block_type == "aside":
                    for inner_block in block.get("content", []):
                        if inner_block.get("type") == "paragraph":
                            text = self.flatten_inline_content(inner_block.get("inlineContent", []))
                            if text.strip():
                                segments.append(TextSegment(
                                    text=text, line_start=line, line_end=line, segment_type="paragraph",
                                ))
                                line += 1
                elif block_type in ("unorderedList", "orderedList"):
                    for item in block.get("items", []):
                        for item_block in item.get("content", []):
                            if item_block.get("type") == "paragraph":
                                text = self.flatten_inline_content(item_block.get("inlineContent", []))
                                if text.strip():
                                    segments.append(TextSegment(
                                        text=text, line_start=line, line_end=line, segment_type="list_item",
                                    ))
                                    line += 1

        return segments

    def _extract_headings(self, data: dict) -> list[HeadingNode]:
        """Extract headings from primaryContentSections content blocks."""
        headings: list[HeadingNode] = []
        line = 2  # Start after abstract

        for section in data.get("primaryContentSections", []):
            if section.get("kind") != "content":
                continue
            for block in section.get("content", []):
                if block.get("type") == "heading":
                    headings.append(HeadingNode(
                        text=block.get("text", ""),
                        level=block.get("level", 2),
                        line_number=line,
                    ))
                line += 1

        return headings

    def _extract_code_blocks(self, data: dict) -> list[CodeBlock]:
        """Extract codeListing nodes from primaryContentSections."""
        code_blocks: list[CodeBlock] = []
        line = 2

        for section in data.get("primaryContentSections", []):
            if section.get("kind") != "content":
                continue
            for block in section.get("content", []):
                if block.get("type") == "codeListing":
                    code_lines = block.get("code", [])
                    content = "\n".join(code_lines)
                    end_line = line + max(len(code_lines) - 1, 0)
                    code_blocks.append(CodeBlock(
                        language=block.get("syntax"),
                        content=content,
                        line_start=line,
                        line_end=end_line,
                    ))
                    line = end_line + 1
                else:
                    line += 1

        return code_blocks
