"""Shared test fixtures."""

import pytest

from docops.parsers.markdown_parser import MarkdownParser
from docops.parsers.mediawiki_parser import MediaWikiParser


@pytest.fixture
def md_parser():
    return MarkdownParser()


@pytest.fixture
def wiki_parser():
    return MediaWikiParser()
