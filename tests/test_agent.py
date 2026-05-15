"""Tests for the agent engine."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_browser.config import AppConfig
from agent_browser.core.agent import AgentBrowser, TaskResult, StepResult


class TestStepResult:
    def test_creation(self):
        step = StepResult(
            tool_name="navigate",
            arguments={"url": "https://example.com"},
            result="Navigated",
            success=True,
            duration=1.5,
        )
        assert step.tool_name == "navigate"
        assert step.success is True
        assert step.duration == 1.5


class TestTaskResult:
    def test_creation(self):
        result = TaskResult(task="Test", success=True, result="Done")
        assert result.task == "Test"
        assert result.success is True
        assert result.steps == []

    def test_with_steps(self):
        steps = [
            StepResult("navigate", {}, "OK", True),
            StepResult("click", {"x": 1, "y": 2}, "OK", True),
        ]
        result = TaskResult(task="Test", success=True, result="Done", steps=steps)
        assert len(result.steps) == 2


class TestAgentBrowser:
    @pytest.fixture
    def config(self):
        return AppConfig(
            llm={"provider": "openai", "api_key": "test-key", "model": "gpt-4o"},
            browser={"headless": True},
        )

    def test_init(self, config):
        agent = AgentBrowser(config)
        assert agent.llm is not None
        assert agent.memory is not None
        assert agent.scheduler is not None
        assert agent.browser is None  # Lazy init

    def test_tools_loaded(self, config):
        agent = AgentBrowser(config)
        assert len(agent.tools) > 10
        tool_names = {t["function"]["name"] for t in agent.tools}
        assert "navigate" in tool_names
        assert "click" in tool_names
        assert "screenshot" in tool_names
        assert "handle_captcha" in tool_names
        assert "schedule_task" in tool_names

    @pytest.mark.asyncio
    async def test_execute_tool_navigate(self, config):
        agent = AgentBrowser(config)
        agent.browser = MagicMock()
        agent.browser.navigate = AsyncMock()

        result = await agent._execute_tool("navigate", {"url": "https://example.com"})
        assert result["success"] is True
        agent.browser.navigate.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_execute_tool_click(self, config):
        agent = AgentBrowser(config)
        agent.browser = MagicMock()
        agent.browser.click = AsyncMock()

        result = await agent._execute_tool("click", {"x": 100, "y": 200})
        assert result["success"] is True
        agent.browser.click.assert_called_once_with(100, 200, button="left")

    @pytest.mark.asyncio
    async def test_execute_tool_type(self, config):
        agent = AgentBrowser(config)
        agent.browser = MagicMock()
        agent.browser.type_text = AsyncMock()

        result = await agent._execute_tool("type_text", {"text": "hello"})
        assert result["success"] is True
        agent.browser.type_text.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_execute_tool_screenshot(self, config):
        agent = AgentBrowser(config)
        agent.browser = MagicMock()
        agent.browser.screenshot = AsyncMock(return_value="base64data")

        result = await agent._execute_tool("screenshot", {})
        assert result["success"] is True
        assert result["image"] == "base64data"

    @pytest.mark.asyncio
    async def test_execute_tool_schedule(self, config):
        agent = AgentBrowser(config)
        result = await agent._execute_tool("schedule_task", {
            "task": "Book ticket",
            "execute_at": "2025-12-31T21:15:00",
        })
        assert result["success"] is True
        assert "scheduled" in result["output"].lower()

    @pytest.mark.asyncio
    async def test_execute_tool_unknown(self, config):
        agent = AgentBrowser(config)
        result = await agent._execute_tool("unknown_tool", {})
        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_tool_error_handling(self, config):
        agent = AgentBrowser(config)
        agent.browser = MagicMock()
        agent.browser.navigate = AsyncMock(side_effect=Exception("Connection failed"))

        result = await agent._execute_tool("navigate", {"url": "https://example.com"})
        assert result["success"] is False
        assert "Connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_user_input_callback(self, config):
        agent = AgentBrowser(config)
        callback = AsyncMock(return_value="user answer")
        agent.set_user_input_callback(callback)

        result = await agent._execute_tool("ask_user", {"question": "What's your email?"})
        assert result["success"] is True
        assert "user answer" in result["output"]

    @pytest.mark.asyncio
    async def test_close(self, config):
        agent = AgentBrowser(config)
        agent.browser = MagicMock()
        agent.browser.close = AsyncMock()
        await agent.close()
