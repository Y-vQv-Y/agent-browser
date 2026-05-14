"""
Integration tests for AgentBrowser.

Tests simulate real-world scenarios (product price extraction, form filling,
navigation flows, scheduling, CAPTCHA handling) using mocked browser and LLM
to verify the full agent loop without network dependencies.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from agent_browser.config import AppConfig, LLMConfig, BrowserConfig
from agent_browser.core.agent import AgentBrowser, StepResult, TaskResult
from agent_browser.core.llm import LLMClient, get_all_tools
from agent_browser.core.memory import WorkingMemory
from agent_browser.core.scheduler import TaskScheduler


# --- Helper: build a mock LLM response with tool calls ---

def openai_response(content="", tool_calls=None, finish_reason="stop"):
    """Build a mock LLM response dict."""
    resp = {"content": content, "tool_calls": tool_calls or [], "finish_reason": finish_reason}
    return resp


def tool_call(name, arguments, call_id="call_1"):
    return {"id": call_id, "name": name, "arguments": arguments}


# --- Scenario: Extract product prices ---

class TestExtractProductPrices:
    """Simulate: 'Go to amazon.com and get the price of iPhone 15'"""

    @pytest.mark.asyncio(mode="strict")
    async def test_navigate_and_extract(self):
        config = AppConfig(llm=LLMConfig(api_key="test-key"))
        agent = AgentBrowser(config)

        # Mock browser
        agent.browser = AsyncMock()
        agent.browser.navigate = AsyncMock()
        agent.browser.screenshot = AsyncMock(return_value="base64img")
        agent.browser.get_page_info = AsyncMock(return_value={
            "url": "https://www.amazon.com/dp/B0FAKE",
            "title": "Apple iPhone 15 128GB",
            "content": "Apple iPhone 15 128GB  $799.00  Free delivery",
            "links": [],
            "inputs": [],
        })
        agent.browser.extract_data = AsyncMock(return_value={
            "product": "Apple iPhone 15 128GB",
            "price": "$799.00",
        })
        agent.browser.type_text = AsyncMock()
        agent.browser.press_key = AsyncMock()
        agent.browser.click = AsyncMock()
        agent.browser.close = AsyncMock()

        # Simulate LLM responses: navigate -> screenshot -> extract -> task_complete
        call_seq = [
            openai_response("Let me navigate", [tool_call("navigate", {"url": "https://www.amazon.com"}, "c1")]),
            openai_response("Taking screenshot", [tool_call("screenshot", {}, "c2")]),
            openai_response("Searching", [tool_call("type_text", {"text": "iPhone 15"}, "c3")]),
            openai_response("Pressing enter", [tool_call("press_key", {"key": "Enter"}, "c4")]),
            openai_response("Extracting price", [tool_call("extract_data", {"description": "product name and price"}, "c5")]),
            openai_response("Done!", [tool_call("task_complete", {"success": True, "result": "iPhone 15: $799.00", "data": {"price": "$799.00"}}, "c6")]),
        ]
        agent.llm = AsyncMock()
        agent.llm.chat = AsyncMock(side_effect=call_seq)
        agent.llm.close = AsyncMock()

        result = await agent.run_task("Go to amazon.com and get the price of iPhone 15")

        assert result.success is True
        assert "$799.00" in result.result
        assert result.data["price"] == "$799.00"
        assert len(result.steps) == 6
        assert result.steps[0].tool_name == "navigate"
        assert result.steps[-1].tool_name == "task_complete"

    @pytest.mark.asyncio(mode="strict")
    async def test_extract_multiple_products(self):
        """Extract prices for multiple products from a search results page."""
        config = AppConfig(llm=LLMConfig(api_key="test-key"))
        agent = AgentBrowser(config)
        agent.browser = AsyncMock()
        agent.browser.navigate = AsyncMock()
        agent.browser.screenshot = AsyncMock(return_value="base64")
        agent.browser.extract_data = AsyncMock(return_value={
            "products": [
                {"name": "iPhone 15", "price": "$799.00"},
                {"name": "iPhone 15 Pro", "price": "$999.00"},
                {"name": "iPhone 15 Pro Max", "price": "$1199.00"},
            ]
        })
        agent.browser.close = AsyncMock()

        call_seq = [
            openai_response("", [tool_call("navigate", {"url": "https://store.apple.com"}, "c1")]),
            openai_response("", [tool_call("extract_data", {"description": "all iPhone models and prices"}, "c2")]),
            openai_response("", [tool_call("task_complete", {
                "success": True,
                "result": "Found 3 products",
                "data": {"count": 3},
            }, "c3")]),
        ]
        agent.llm = AsyncMock()
        agent.llm.chat = AsyncMock(side_effect=call_seq)
        agent.llm.close = AsyncMock()

        result = await agent.run_task("List all iPhone prices on Apple store")
        assert result.success
        assert len(result.steps) == 3


# --- Scenario: Food delivery price check ---

class TestFoodDeliveryPrices:
    """Simulate: 'Check the delivery price on Meituan/Uber Eats'"""

    @pytest.mark.asyncio(mode="strict")
    async def test_food_delivery_search(self):
        config = AppConfig(llm=LLMConfig(api_key="test-key"))
        agent = AgentBrowser(config)
        agent.browser = AsyncMock()
        agent.browser.navigate = AsyncMock()
        agent.browser.screenshot = AsyncMock(return_value="base64")
        agent.browser.get_page_info = AsyncMock(return_value={
            "url": "https://www.ubereats.com/search?q=pizza",
            "title": "Pizza near me - Uber Eats",
            "content": "Domino's Pizza  $12.99 delivery  Papa John's  $14.99 delivery",
            "links": [],
            "inputs": [],
        })
        agent.browser.type_text = AsyncMock()
        agent.browser.click = AsyncMock()
        agent.browser.extract_data = AsyncMock(return_value={
            "restaurants": [
                {"name": "Domino's Pizza", "delivery_fee": "$2.99", "price": "$12.99"},
                {"name": "Papa John's", "delivery_fee": "$3.49", "price": "$14.99"},
            ]
        })
        agent.browser.close = AsyncMock()

        call_seq = [
            openai_response("", [tool_call("navigate", {"url": "https://www.ubereats.com"}, "c1")]),
            openai_response("", [tool_call("type_text", {"text": "pizza", "selector": "input[name='search']"}, "c2")]),
            openai_response("", [tool_call("screenshot", {}, "c3")]),
            openai_response("", [tool_call("extract_data", {"description": "restaurant names and delivery prices"}, "c4")]),
            openai_response("", [tool_call("task_complete", {
                "success": True,
                "result": "Found 2 pizza restaurants. Cheapest delivery: Domino's at $2.99",
                "data": {"cheapest": "Domino's", "fee": "$2.99"},
            }, "c5")]),
        ]
        agent.llm = AsyncMock()
        agent.llm.chat = AsyncMock(side_effect=call_seq)
        agent.llm.close = AsyncMock()

        result = await agent.run_task("Search for pizza delivery on Uber Eats and compare prices")
        assert result.success
        assert "Domino" in result.result


# --- Scenario: CAPTCHA handling ---

class TestCaptchaHandling:
    """Simulate: agent encounters a CAPTCHA during task execution"""

    @pytest.mark.asyncio(mode="strict")
    async def test_captcha_auto_detect_and_solve(self):
        config = AppConfig(llm=LLMConfig(api_key="test-key"))
        agent = AgentBrowser(config)
        agent.browser = AsyncMock()
        agent.browser.navigate = AsyncMock()
        agent.browser.screenshot = AsyncMock(return_value="base64")
        agent.browser.close = AsyncMock()

        # Mock captcha handler
        mock_captcha_result = MagicMock()
        mock_captcha_result.solved = True
        mock_captcha_result.message = "reCAPTCHA solved via checkbox click"

        with patch("agent_browser.core.agent.CaptchaHandler", create=True) as MockHandler:
            mock_handler_instance = MagicMock()
            mock_handler_instance.detect_and_solve = AsyncMock(return_value=mock_captcha_result)
            MockHandler.return_value = mock_handler_instance

            # Patch the import path
            with patch.dict("sys.modules", {"agent_browser.browser.captcha": MagicMock(CaptchaHandler=MockHandler)}):
                call_seq = [
                    openai_response("", [tool_call("navigate", {"url": "https://example.com/login"}, "c1")]),
                    openai_response("I see a CAPTCHA", [tool_call("handle_captcha", {"strategy": "auto"}, "c2")]),
                    openai_response("", [tool_call("task_complete", {"success": True, "result": "CAPTCHA solved"}, "c3")]),
                ]
                agent.llm = AsyncMock()
                agent.llm.chat = AsyncMock(side_effect=call_seq)
                agent.llm.close = AsyncMock()

                result = await agent.run_task("Navigate to login page and handle CAPTCHA")
                assert result.success
                assert len(result.steps) == 3


# --- Scenario: Scheduled task (ticket booking) ---

class TestScheduledTask:
    """Simulate: 'Book ticket at 21:15'"""

    @pytest.mark.asyncio(mode="strict")
    async def test_schedule_future_task(self, tmp_path):
        config = AppConfig(llm=LLMConfig(api_key="test-key"), data_dir=str(tmp_path))
        agent = AgentBrowser(config)
        agent.browser = AsyncMock()
        agent.browser.close = AsyncMock()

        call_seq = [
            openai_response("I'll schedule this task", [
                tool_call("schedule_task", {
                    "task": "Go to booking.com and book flight LAX->PEK at 21:15",
                    "execute_at": "2026-06-01T21:10:00",
                    "pre_check": True,
                }, "c1"),
            ]),
            openai_response("", [tool_call("task_complete", {
                "success": True,
                "result": "Task scheduled for 2026-06-01 21:10 (5 min before target time)",
            }, "c2")]),
        ]
        agent.llm = AsyncMock()
        agent.llm.chat = AsyncMock(side_effect=call_seq)
        agent.llm.close = AsyncMock()

        result = await agent.run_task("Book the 21:15 flight from LAX to PEK on June 1st")
        assert result.success
        assert "scheduled" in result.result.lower()

        # Verify the task was actually added to scheduler
        tasks = agent.scheduler.list_tasks()
        assert len(tasks) == 1
        assert "21:15" in tasks[0].description or "LAX" in tasks[0].description


# --- Scenario: Login with ask_user ---

class TestLoginFlow:
    """Simulate: agent asks user for credentials during login"""

    @pytest.mark.asyncio(mode="strict")
    async def test_ask_user_for_credentials(self):
        config = AppConfig(llm=LLMConfig(api_key="test-key"))
        agent = AgentBrowser(config)
        agent.browser = AsyncMock()
        agent.browser.navigate = AsyncMock()
        agent.browser.fill_input = AsyncMock()
        agent.browser.click = AsyncMock()
        agent.browser.screenshot = AsyncMock(return_value="base64")
        agent.browser.get_page_info = AsyncMock(return_value={
            "url": "https://example.com/dashboard",
            "title": "Dashboard",
            "content": "Welcome, user@test.com",
            "links": [], "inputs": [],
        })
        agent.browser.close = AsyncMock()

        # Simulate user providing credentials
        agent.set_user_input_callback(AsyncMock(side_effect=["user@test.com", "password123"]))

        call_seq = [
            openai_response("", [tool_call("navigate", {"url": "https://example.com/login"}, "c1")]),
            openai_response("I need your email", [tool_call("ask_user", {"question": "Please enter your email"}, "c2")]),
            openai_response("I need your password", [tool_call("ask_user", {"question": "Please enter your password"}, "c3")]),
            openai_response("", [tool_call("type_text", {"text": "user@test.com", "selector": "#email"}, "c4")]),
            openai_response("", [tool_call("type_text", {"text": "password123", "selector": "#password"}, "c5")]),
            openai_response("", [tool_call("click", {"x": 500, "y": 400}, "c6")]),
            openai_response("", [tool_call("task_complete", {"success": True, "result": "Logged in successfully"}, "c7")]),
        ]
        agent.llm = AsyncMock()
        agent.llm.chat = AsyncMock(side_effect=call_seq)
        agent.llm.close = AsyncMock()

        result = await agent.run_task("Login to example.com")
        assert result.success
        assert "logged in" in result.result.lower()


# --- Scenario: Multi-step plan ---

class TestMultiStepPlan:
    """Simulate: agent creates and executes a multi-step plan."""

    @pytest.mark.asyncio(mode="strict")
    async def test_create_and_execute_plan(self):
        config = AppConfig(llm=LLMConfig(api_key="test-key"))
        agent = AgentBrowser(config)
        agent.browser = AsyncMock()
        agent.browser.navigate = AsyncMock()
        agent.browser.screenshot = AsyncMock(return_value="base64")
        agent.browser.click = AsyncMock()
        agent.browser.type_text = AsyncMock()
        agent.browser.extract_data = AsyncMock(return_value={"results": ["item1", "item2"]})
        agent.browser.close = AsyncMock()

        call_seq = [
            # Step 1: Create plan
            openai_response("", [tool_call("create_plan", {
                "task": "Compare prices across 2 sites",
                "steps": [
                    {"id": 1, "action": "Search site A", "details": "Navigate and extract"},
                    {"id": 2, "action": "Search site B", "details": "Navigate and extract"},
                    {"id": 3, "action": "Compare", "details": "Compare results", "depends_on": [1, 2]},
                ],
            }, "c1")]),
            # Step 2: Execute plan steps
            openai_response("", [tool_call("navigate", {"url": "https://siteA.com"}, "c2")]),
            openai_response("", [tool_call("extract_data", {"description": "prices"}, "c3")]),
            openai_response("", [tool_call("navigate", {"url": "https://siteB.com"}, "c4")]),
            openai_response("", [tool_call("extract_data", {"description": "prices"}, "c5")]),
            openai_response("", [tool_call("task_complete", {
                "success": True,
                "result": "Site A: $10, Site B: $12. Site A is cheaper.",
                "data": {"siteA": "$10", "siteB": "$12"},
            }, "c6")]),
        ]
        agent.llm = AsyncMock()
        agent.llm.chat = AsyncMock(side_effect=call_seq)
        agent.llm.close = AsyncMock()

        result = await agent.run_task("Compare product prices between siteA.com and siteB.com")
        assert result.success
        assert "cheaper" in result.result.lower()
        assert result.data is not None


# --- Scenario: Error recovery ---

class TestErrorRecovery:
    """Simulate: agent handles errors gracefully."""

    @pytest.mark.asyncio(mode="strict")
    async def test_navigation_error_recovery(self):
        config = AppConfig(llm=LLMConfig(api_key="test-key"))
        agent = AgentBrowser(config)
        agent.browser = AsyncMock()
        agent.browser.navigate = AsyncMock(side_effect=[Exception("Connection timeout"), None])
        agent.browser.screenshot = AsyncMock(return_value="base64")
        agent.browser.close = AsyncMock()

        call_seq = [
            openai_response("", [tool_call("navigate", {"url": "https://slow-site.com"}, "c1")]),
            # Agent gets error, tries again
            openai_response("Let me try again", [tool_call("navigate", {"url": "https://slow-site.com"}, "c2")]),
            openai_response("", [tool_call("task_complete", {"success": True, "result": "Navigation succeeded on retry"}, "c3")]),
        ]
        agent.llm = AsyncMock()
        agent.llm.chat = AsyncMock(side_effect=call_seq)
        agent.llm.close = AsyncMock()

        result = await agent.run_task("Navigate to slow-site.com")
        assert result.success
        # First step failed, second succeeded
        assert result.steps[0].success is False
        assert result.steps[1].success is True

    @pytest.mark.asyncio(mode="strict")
    async def test_max_turns_limit(self):
        config = AppConfig(llm=LLMConfig(api_key="test-key"))
        agent = AgentBrowser(config)
        agent.max_turns = 3
        agent.browser = AsyncMock()
        agent.browser.screenshot = AsyncMock(return_value="base64")
        agent.browser.close = AsyncMock()

        # Agent keeps taking screenshots, never completes
        call_seq = [
            openai_response("", [tool_call("screenshot", {}, f"c{i}")]) for i in range(5)
        ]
        agent.llm = AsyncMock()
        agent.llm.chat = AsyncMock(side_effect=call_seq)
        agent.llm.close = AsyncMock()

        result = await agent.run_task("Do something that never finishes")
        assert result.success is False
        assert "did not complete" in result.result.lower()


# --- Scenario: JavaScript execution ---

class TestJavaScriptExecution:
    """Simulate: agent uses run_javascript for data extraction."""

    @pytest.mark.asyncio(mode="strict")
    async def test_run_javascript_to_extract(self):
        config = AppConfig(llm=LLMConfig(api_key="test-key"))
        agent = AgentBrowser(config)
        agent.browser = AsyncMock()
        agent.browser.navigate = AsyncMock()
        agent.browser.run_javascript = AsyncMock(return_value={"total": 42, "items": 5})
        agent.browser.close = AsyncMock()

        call_seq = [
            openai_response("", [tool_call("navigate", {"url": "https://shop.example.com/cart"}, "c1")]),
            openai_response("", [tool_call("run_javascript", {
                "code": "(() => { const items = document.querySelectorAll('.cart-item'); return {total: 42, items: items.length}; })()"
            }, "c2")]),
            openai_response("", [tool_call("task_complete", {
                "success": True, "result": "Cart total: $42.00 with 5 items",
                "data": {"total": 42, "items": 5},
            }, "c3")]),
        ]
        agent.llm = AsyncMock()
        agent.llm.chat = AsyncMock(side_effect=call_seq)
        agent.llm.close = AsyncMock()

        result = await agent.run_task("Get shopping cart total from shop.example.com")
        assert result.success
        assert result.data["total"] == 42


# --- Scenario: Wait and scroll ---

class TestWaitAndScroll:
    """Simulate: agent scrolls down to load lazy content and waits."""

    @pytest.mark.asyncio(mode="strict")
    async def test_scroll_and_wait_for_content(self):
        config = AppConfig(llm=LLMConfig(api_key="test-key"))
        agent = AgentBrowser(config)
        agent.browser = AsyncMock()
        agent.browser.navigate = AsyncMock()
        agent.browser.scroll = AsyncMock()
        agent.browser.wait_for_element = AsyncMock()
        agent.browser.screenshot = AsyncMock(return_value="base64")
        agent.browser.extract_data = AsyncMock(return_value={"items": ["a", "b", "c"]})
        agent.browser.close = AsyncMock()

        call_seq = [
            openai_response("", [tool_call("navigate", {"url": "https://infinite-scroll.com"}, "c1")]),
            openai_response("", [tool_call("scroll", {"direction": "down", "amount": 500}, "c2")]),
            openai_response("", [tool_call("wait", {"seconds": 2}, "c3")]),
            openai_response("", [tool_call("scroll", {"direction": "down", "amount": 500}, "c4")]),
            openai_response("", [tool_call("extract_data", {"description": "loaded items"}, "c5")]),
            openai_response("", [tool_call("task_complete", {"success": True, "result": "Found 3 items"}, "c6")]),
        ]
        agent.llm = AsyncMock()
        agent.llm.chat = AsyncMock(side_effect=call_seq)
        agent.llm.close = AsyncMock()

        result = await agent.run_task("Scroll down and extract all lazy-loaded items")
        assert result.success
        assert result.steps[1].tool_name == "scroll"
        assert result.steps[2].tool_name == "wait"


# --- Scenario: Custom base URL with DeepSeek ---

class TestCustomBaseURL:
    """Test that custom API base URLs work correctly."""

    def test_deepseek_openai_format(self):
        """DeepSeek with OpenAI format: base_url=https://api.deepseek.com"""
        client = LLMClient(
            provider="openai",
            api_key="sk-deep-test",
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
        )
        assert client._openai_base() == "https://api.deepseek.com/v1"

    def test_deepseek_anthropic_format(self):
        """DeepSeek with Anthropic format: base_url=https://api.deepseek.com/anthropic"""
        client = LLMClient(
            provider="anthropic",
            api_key="sk-deep-test",
            model="deepseek-chat",
            base_url="https://api.deepseek.com/anthropic",
        )
        assert client._anthropic_base() == "https://api.deepseek.com/anthropic"

    def test_config_env_var_base_url(self):
        """AB_LLM_BASE_URL env var should set LLMConfig.base_url"""
        import os
        with patch.dict(os.environ, {"AB_LLM_BASE_URL": "https://api.deepseek.com"}):
            config = LLMConfig()
            assert config.base_url == "https://api.deepseek.com"

    def test_config_base_url_passed_to_agent(self):
        """AppConfig's base_url should flow through to the LLM client."""
        config = AppConfig(llm=LLMConfig(
            api_key="test",
            base_url="https://custom-api.example.com",
        ))
        agent = AgentBrowser(config)
        assert agent.llm.base_url == "https://custom-api.example.com"


# --- Scenario: Profile-based session management ---

class TestProfileSession:
    """Test that profile_name flows through the agent correctly."""

    def test_profile_name_stored(self):
        config = AppConfig(llm=LLMConfig(api_key="test"))
        agent = AgentBrowser(config, profile_name="my-amazon")
        assert agent._profile_name == "my-amazon"

    def test_default_profile_none(self):
        config = AppConfig(llm=LLMConfig(api_key="test"))
        agent = AgentBrowser(config)
        assert agent._profile_name is None


# --- Step callback ---

class TestStepCallback:
    """Test step-by-step progress tracking."""

    @pytest.mark.asyncio(mode="strict")
    async def test_step_callback_fires(self):
        config = AppConfig(llm=LLMConfig(api_key="test-key"))
        agent = AgentBrowser(config)
        agent.browser = AsyncMock()
        agent.browser.navigate = AsyncMock()
        agent.browser.close = AsyncMock()

        steps_received = []

        async def on_step(step):
            steps_received.append(step)

        agent.set_step_callback(on_step)

        call_seq = [
            openai_response("", [tool_call("navigate", {"url": "https://example.com"}, "c1")]),
            openai_response("", [tool_call("task_complete", {"success": True, "result": "Done"}, "c2")]),
        ]
        agent.llm = AsyncMock()
        agent.llm.chat = AsyncMock(side_effect=call_seq)
        agent.llm.close = AsyncMock()

        await agent.run_task("Go to example.com")
        assert len(steps_received) == 2
        assert steps_received[0].tool_name == "navigate"
        assert steps_received[1].tool_name == "task_complete"
