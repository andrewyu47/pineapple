"""Parser factory - routes file extensions to the correct parser."""

from docops.parsers.base import BaseParser
from docops.parsers.markdown_parser import MarkdownParser
from docops.parsers.mediawiki_parser import MediaWikiParser

_PARSERS: list[BaseParser] = [MarkdownParser(), MediaWikiParser()]


def get_parser(filename: str) -> BaseParser:
    for parser in _PARSERS:
        if parser.supports(filename):
            return parser
    raise ValueError(f"No parser available for file: {filename}")
