"""Tests for the configuration system."""

import json
import tempfile
from pathlib import Path

import pytest

from agent_browser.config import AppConfig, LLMConfig, BrowserConfig


class TestLLMConfig:
    def test_default_values(self):
        config = LLMConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-4o"
        assert config.max_tokens == 4096
        assert config.temperature == 0.1

    def test_custom_values(self):
        config = LLMConfig(provider="anthropic", model="claude-sonnet-4-20250514", api_key="test-key")
        assert config.provider == "anthropic"
        assert config.model == "claude-sonnet-4-20250514"
        assert config.api_key == "test-key"


class TestBrowserConfig:
    def test_default_values(self):
        config = BrowserConfig()
        assert config.headless is True
        assert config.stealth is True
        assert config.humanize is True
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.proxy is None

    def test_custom_proxy(self):
        config = BrowserConfig(proxy="http://proxy:8080")
        assert config.proxy == "http://proxy:8080"


class TestAppConfig:
    def test_default_values(self):
        config = AppConfig()
        assert config.debug is False
        assert config.log_level == "INFO"
        assert config.web_port == 8899

    def test_data_path_expansion(self):
        config = AppConfig(data_dir="~/.agent-browser")
        assert "~" not in str(config.data_path)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config = AppConfig(
                debug=True,
                log_level="DEBUG",
                web_port=9999,
            )
            config.llm.provider = "anthropic"
            config.llm.model = "claude-sonnet-4-20250514"
            config.browser.headless = False

            config.save(config_path)

            # Verify file exists
            assert config_path.exists()

            # Load and verify
            loaded = AppConfig.load(config_path)
            assert loaded.debug is True
            assert loaded.log_level == "DEBUG"
            assert loaded.web_port == 9999
            assert loaded.llm.provider == "anthropic"
            assert loaded.browser.headless is False

    def test_load_nonexistent_returns_defaults(self):
        config = AppConfig.load(Path("/nonexistent/config.json"))
        assert config.debug is False
        assert config.llm.provider == "openai"

    def test_nested_config(self):
        config = AppConfig()
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.browser, BrowserConfig)
