"""Tests for the LLM client module."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_browser.core.llm import LLMClient, get_all_tools, BROWSER_TOOLS, PLANNING_TOOLS


class TestToolDefinitions:
    def test_browser_tools_count(self):
        assert len(BROWSER_TOOLS) >= 10

    def test_planning_tools_count(self):
        assert len(PLANNING_TOOLS) >= 3

    def test_all_tools_have_required_fields(self):
        for tool in get_all_tools():
            assert tool["type"] == "function"
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            assert func["parameters"]["type"] == "object"

    def test_tool_names_unique(self):
        names = [t["function"]["name"] for t in get_all_tools()]
        assert len(names) == len(set(names))

    def test_required_tools_present(self):
        names = {t["function"]["name"] for t in get_all_tools()}
        required = {"navigate", "click", "type_text", "screenshot", "handle_captcha",
                     "task_complete", "schedule_task", "ask_user"}
        assert required.issubset(names)


class TestLLMClient:
    def test_init_openai(self):
        client = LLMClient(provider="openai", api_key="test", model="gpt-4o")
        assert client.provider == "openai"
        assert client.model == "gpt-4o"

    def test_init_anthropic(self):
        client = LLMClient(provider="anthropic", api_key="test", model="claude-sonnet-4-20250514")
        assert client.provider == "anthropic"
        assert client.model == "claude-sonnet-4-20250514"

    def test_system_prompt_exists(self):
        client = LLMClient()
        prompt = client._get_system_prompt()
        assert "AgentBrowser" in prompt
        assert "browser" in prompt.lower()
        assert len(prompt) > 100

    # --- Base URL resolution tests ---

    def test_openai_base_default(self):
        client = LLMClient(provider="openai", api_key="test")
        assert client._openai_base() == "https://api.openai.com/v1"

    def test_openai_base_custom_no_version(self):
        """e.g. AB_LLM_BASE_URL=https://api.deepseek.com -> appends /v1"""
        client = LLMClient(provider="openai", api_key="test",
                           base_url="https://api.deepseek.com")
        assert client._openai_base() == "https://api.deepseek.com/v1"

    def test_openai_base_custom_with_version(self):
        """e.g. AB_LLM_BASE_URL=https://api.deepseek.com/v1 -> no double /v1"""
        client = LLMClient(provider="openai", api_key="test",
                           base_url="https://api.deepseek.com/v1")
        assert client._openai_base() == "https://api.deepseek.com/v1"

    def test_openai_base_trailing_slash(self):
        client = LLMClient(provider="openai", api_key="test",
                           base_url="https://api.deepseek.com/")
        assert client._openai_base() == "https://api.deepseek.com/v1"

    def test_anthropic_base_default(self):
        client = LLMClient(provider="anthropic", api_key="test")
        assert client._anthropic_base() == "https://api.anthropic.com/v1"

    def test_anthropic_base_custom(self):
        """e.g. AB_LLM_BASE_URL=https://api.deepseek.com/anthropic"""
        client = LLMClient(provider="anthropic", api_key="test",
                           base_url="https://api.deepseek.com/anthropic")
        assert client._anthropic_base() == "https://api.deepseek.com/anthropic"

    def test_anthropic_base_trailing_slash(self):
        client = LLMClient(provider="anthropic", api_key="test",
                           base_url="https://custom.api.com/v1/")
        assert client._anthropic_base() == "https://custom.api.com/v1"

    @pytest.mark.asyncio
    async def test_close(self):
        client = LLMClient(api_key="test")
        await client.close()
        # Should not raise

    @pytest.mark.asyncio
    async def test_chat_openai_format(self):
        """Test that OpenAI request is properly formatted."""
        client = LLMClient(provider="openai", api_key="test-key", model="gpt-4o")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "I'll navigate to the page.",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "function": {
                                    "name": "navigate",
                                    "arguments": '{"url": "https://example.com"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

        client._client = AsyncMock()
        client._client.post = AsyncMock(return_value=mock_response)

        result = await client.chat(
            [{"role": "user", "content": "Go to example.com"}],
            tools=get_all_tools(),
        )

        assert result["content"] == "I'll navigate to the page."
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "navigate"
        assert result["tool_calls"][0]["arguments"]["url"] == "https://example.com"

        await client.close()

    @pytest.mark.asyncio
    async def test_chat_anthropic_format(self):
        """Test that Anthropic request is properly formatted."""
        client = LLMClient(provider="anthropic", api_key="test-key", model="claude-sonnet-4-20250514")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [
                {"type": "text", "text": "I'll click there."},
                {
                    "type": "tool_use",
                    "id": "tu_123",
                    "name": "click",
                    "input": {"x": 100, "y": 200},
                },
            ],
            "stop_reason": "tool_use",
        }

        client._client = AsyncMock()
        client._client.post = AsyncMock(return_value=mock_response)

        result = await client.chat(
            [{"role": "user", "content": "Click the button"}],
            tools=get_all_tools(),
        )

        assert "click" in result["content"].lower()
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "click"
        assert result["tool_calls"][0]["arguments"]["x"] == 100

        await client.close()
