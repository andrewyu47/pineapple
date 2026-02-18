"""Tests for LLM client (mocked)."""

from unittest.mock import MagicMock, patch

from docops.config import AppConfig, LLMConfig
from docops.llm.client import LLMClient


def _llm_config() -> AppConfig:
    return AppConfig(llm=LLMConfig(enabled=True, model="gpt-4o"))


def test_graceful_failure_on_api_error():
    with patch("docops.llm.client.ChatOpenAI") as mock_cls:
        mock_cls.return_value.invoke.side_effect = Exception("API timeout")
        client = LLMClient(_llm_config())
        result = client.check_terminology(["some text"], "glossary", "test.md")
        assert result == []


def test_graceful_failure_on_bad_json():
    with patch("docops.llm.client.ChatOpenAI") as mock_cls:
        mock_response = MagicMock()
        mock_response.content = "not valid json"
        mock_cls.return_value.invoke.return_value = mock_response
        client = LLMClient(_llm_config())
        result = client.check_terminology(["some text"], "glossary", "test.md")
        assert result == []


def test_parses_valid_response():
    with patch("docops.llm.client.ChatOpenAI") as mock_cls:
        mock_response = MagicMock()
        mock_response.content = '{"issues": [{"message": "Use instance", "context": "server", "suggestion": "instance", "line": null}]}'
        mock_cls.return_value.invoke.return_value = mock_response
        client = LLMClient(_llm_config())
        result = client.check_terminology(["the server is running"], "prefer 'instance'", "test.md")
        assert len(result) == 1
        assert "instance" in result[0].suggestion


def test_empty_issues():
    with patch("docops.llm.client.ChatOpenAI") as mock_cls:
        mock_response = MagicMock()
        mock_response.content = '{"issues": []}'
        mock_cls.return_value.invoke.return_value = mock_response
        client = LLMClient(_llm_config())
        result = client.check_terminology(["clean text"], "glossary", "test.md")
        assert result == []
