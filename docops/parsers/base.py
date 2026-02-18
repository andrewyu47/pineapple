"""Abstract parser interface and shared document model."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TextSegment:
    """A chunk of prose text with location info."""
    text: str
    line_start: int
    line_end: int
    segment_type: str  # "paragraph", "heading", "list_item", "code_block"


@dataclass
class HeadingNode:
    """A heading with its level and location."""
    text: str
    level: int
    line_number: int


@dataclass
class CodeBlock:
    """A fenced code block."""
    language: str | None
    content: str
    line_start: int
    line_end: int


@dataclass
class ParsedDocument:
    """Format-agnostic representation of a document."""
    raw_lines: list[str]
    text_segments: list[TextSegment] = field(default_factory=list)
    headings: list[HeadingNode] = field(default_factory=list)
    code_blocks: list[CodeBlock] = field(default_factory=list)
    raw_text: str = ""
    format_type: str = "unknown"


class BaseParser(ABC):
    @abstractmethod
    def parse(self, content: str, filename: str) -> ParsedDocument:
        ...

    @abstractmethod
    def supports(self, filename: str) -> bool:
        ...
