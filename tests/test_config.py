"""Tests for config loading."""

import os
import tempfile

from docops.config import AppConfig, CheckConfig, load_config


def test_load_defaults():
    config = load_config("/nonexistent/path/.docops.yml")
    assert config.fail_on == "error"
    assert config.llm.enabled is False


def test_load_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("fail_on: warning\nllm:\n  enabled: true\n")
        f.flush()
        config = load_config(f.name)
    os.unlink(f.name)
    assert config.fail_on == "warning"
    assert config.llm.enabled is True


def test_is_check_enabled():
    config = AppConfig(checks={"passive-voice": CheckConfig(enabled=False)})
    assert config.is_check_enabled("passive-voice") is False
    assert config.is_check_enabled("heading-hierarchy") is True  # default enabled


def test_check_option():
    config = AppConfig(checks={"line-length": CheckConfig(options={"max_length": 80})})
    assert config.check_option("line-length", "max_length") == 80
    assert config.check_option("line-length", "missing", 120) == 120


def test_check_severity():
    config = AppConfig(checks={"passive-voice": CheckConfig(severity="error")})
    assert config.check_severity("passive-voice") == "error"
    assert config.check_severity("unknown-check") is None  # not configured
