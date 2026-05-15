"""
LLM Client - Multi-provider LLM abstraction layer.
Internalized from GenericAgent's llmcore.py pattern.
Supports OpenAI-compatible and Anthropic APIs with native tool calling.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Optional

import httpx

logger = logging.getLogger(__name__)


# --- Tool schema definitions ---

BROWSER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": "Navigate the browser to a URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to navigate to"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click at coordinates (x, y) on the page. Use screenshot to identify coordinates first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate"},
                    "y": {"type": "integer", "description": "Y coordinate"},
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                        "description": "Mouse button",
                    },
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text using keyboard input. For form fields, click on the field first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"},
                    "selector": {
                        "type": "string",
                        "description": "Optional CSS selector to focus before typing",
                    },
                    "clear_first": {
                        "type": "boolean",
                        "description": "Clear existing text first",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Press a keyboard key (Enter, Tab, Escape, ArrowDown, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key to press"},
                    "modifiers": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["Alt", "Control", "Meta", "Shift"]},
                        "description": "Modifier keys to hold",
                    },
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Take a screenshot of the current page. Returns base64 image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_page": {
                        "type": "boolean",
                        "description": "Capture full page or just viewport",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_page_info",
            "description": "Get current page URL, title, and HTML content summary",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll the page",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "left", "right"],
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Pixels to scroll (default 300)",
                    },
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_javascript",
            "description": "Execute JavaScript in the browser page and return the result",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "JavaScript code to execute"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": "Wait for a condition: page load, element appearance, or fixed time",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector to wait for",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Max wait time in seconds (default 10)",
                    },
                    "seconds": {
                        "type": "number",
                        "description": "Fixed wait time in seconds",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_data",
            "description": "Extract structured data from the current page using CSS selectors or description",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "What data to extract (e.g., 'all product names and prices')",
                    },
                    "selectors": {
                        "type": "object",
                        "description": "CSS selectors mapping field names to selectors",
                    },
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "handle_captcha",
            "description": "Detect and attempt to solve CAPTCHA/human verification on the page",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {
                        "type": "string",
                        "enum": ["auto", "click", "slide", "image"],
                        "description": "CAPTCHA solving strategy",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_complete",
            "description": "Mark the current task as complete and provide the result",
            "parameters": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "description": "Whether task succeeded"},
                    "result": {"type": "string", "description": "Task result or error message"},
                    "data": {"type": "object", "description": "Structured output data"},
                },
                "required": ["success", "result"],
            },
        },
    },
]

GRAB_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "prepare_grab",
            "description": (
                "Prepare a millisecond-precision grab plan for time-critical operations "
                "(ticket booking, flash sales, etc). Call AFTER navigating to the page, "
                "logging in, filling forms, and identifying the target button/element. "
                "The grab engine bypasses the LLM loop entirely for maximum speed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_time": {
                        "type": "string",
                        "description": (
                            "ISO 8601 datetime when tickets go on sale or flash sale starts. "
                            "E.g. '2026-05-20T21:00:00'. If omitted, executes immediately."
                        ),
                    },
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["click_selector", "click_xy", "js_eval", "submit_form"],
                                    "description": "Action type",
                                },
                                "selector": {
                                    "type": "string",
                                    "description": "CSS selector for click_selector/submit_form",
                                },
                                "x": {"type": "integer", "description": "X coordinate for click_xy"},
                                "y": {"type": "integer", "description": "Y coordinate for click_xy"},
                                "js_code": {"type": "string", "description": "JavaScript code for js_eval"},
                                "timeout_ms": {
                                    "type": "integer",
                                    "description": "Action timeout in ms (default 3000)",
                                },
                            },
                            "required": ["type"],
                        },
                        "description": "Ordered list of actions to execute at target time",
                    },
                    "verify_selector": {
                        "type": "string",
                        "description": "CSS selector to check after grab to verify success",
                    },
                    "verify_text": {
                        "type": "string",
                        "description": "Text that should appear on page after successful grab",
                    },
                    "retry_count": {
                        "type": "integer",
                        "description": "Number of retry attempts (default 5)",
                    },
                    "retry_interval_ms": {
                        "type": "integer",
                        "description": "Milliseconds between retries (default 100)",
                    },
                    "pre_wait_refresh": {
                        "type": "boolean",
                        "description": "Refresh page 2s before target time for fresh DOM (default true)",
                    },
                },
                "required": ["actions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_grab",
            "description": (
                "Execute a previously prepared grab plan. Use mode='now' to execute "
                "immediately (for testing), or mode='confirm' to start waiting for "
                "the target time. Must call prepare_grab first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["now", "confirm"],
                        "description": (
                            "'now' = execute immediately (ignore target_time), "
                            "'confirm' = wait for target_time then execute"
                        ),
                    },
                },
                "required": ["mode"],
            },
        },
    },
]

PLANNING_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_plan",
            "description": "Create a step-by-step plan for a complex task",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "The task description"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "action": {"type": "string"},
                                "details": {"type": "string"},
                                "depends_on": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                },
                            },
                        },
                        "description": "Ordered steps to complete the task",
                    },
                },
                "required": ["task", "steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_task",
            "description": "Schedule a task for future execution at a specific time",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task description"},
                    "execute_at": {
                        "type": "string",
                        "description": "ISO 8601 datetime or cron expression for when to execute",
                    },
                    "pre_check": {
                        "type": "boolean",
                        "description": "Run pre-execution validation first",
                    },
                },
                "required": ["task", "execute_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Ask the user for input or clarification. Use this when you need login credentials, choices, or any user decision.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Question to ask"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_login",
            "description": "Save login credentials for a website after successful login. This stores encrypted credentials and marks the session as logged in.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site": {
                        "type": "string",
                        "description": "Website domain (e.g., 'amazon.com')",
                    },
                    "username": {
                        "type": "string",
                        "description": "Username or email used to login",
                    },
                    "password": {
                        "type": "string",
                        "description": "Password used to login (will be encrypted)",
                    },
                },
                "required": ["site", "username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_login",
            "description": "Check if we have a saved login session for a website. Returns login status and stored credentials if available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site": {
                        "type": "string",
                        "description": "Website domain to check (e.g., 'amazon.com')",
                    },
                },
                "required": ["site"],
            },
        },
    },
]


def get_all_tools() -> list[dict]:
    """Return all available tools."""
    return BROWSER_TOOLS + GRAB_TOOLS + PLANNING_TOOLS


class LLMClient:
    """Multi-provider LLM client with native tool calling support."""

    def __init__(
        self,
        provider: str = "openai",
        api_key: str = "",
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = httpx.AsyncClient(timeout=120.0)

    async def close(self):
        await self._client.aclose()

    async def verify_connection(self) -> tuple[bool, str]:
        """Verify the LLM API connection is working.

        Returns (success, message) tuple.
        """
        try:
            if self.provider == "anthropic":
                url = self._anthropic_base() + "/messages"
                payload = {
                    "model": self.model,
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "hi"}],
                }
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                }
            else:
                url = self._openai_base() + "/chat/completions"
                payload = {
                    "model": self.model,
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "hi"}],
                }
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

            resp = await self._client.post(url, json=payload, headers=headers, timeout=15.0)
            if resp.status_code == 200:
                return True, f"{self.provider}/{self.model} OK"
            elif resp.status_code == 401:
                return False, "Invalid API key (401 Unauthorized)"
            elif resp.status_code == 403:
                return False, "Access denied (403 Forbidden)"
            elif resp.status_code == 404:
                return False, f"Model not found: {self.model} (404)"
            else:
                return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
        except httpx.ConnectError:
            base = self._anthropic_base() if self.provider == "anthropic" else self._openai_base()
            return False, f"Connection failed: cannot reach {base}"
        except httpx.TimeoutException:
            return False, "Connection timeout (15s)"
        except Exception as e:
            return False, f"Error: {e}"

    def _get_system_prompt(self) -> str:
        return """You are AgentBrowser, an AI-powered browser automation agent. You control a real browser to complete tasks for the user.

CAPABILITIES:
- Navigate to any website
- Click, type, scroll, and interact with page elements
- Take screenshots to see what's on screen
- Extract data from web pages
- Handle CAPTCHAs and human verification challenges
- Create multi-step plans for complex tasks
- Schedule tasks for future execution
- Manage login sessions with persistent cookies

WORKFLOW:
1. For each task, first take a screenshot to see the current state
2. Plan your actions based on what you see
3. Execute actions step by step, taking screenshots to verify each step
4. If you encounter a CAPTCHA, use handle_captcha to solve it
5. If a task involves timing (e.g., ticket booking), create a scheduled task
6. Always verify the final result before marking the task complete

LOGIN WORKFLOW:
1. Before navigating to a site that requires login, use check_login to see if we have a saved session
2. If logged in: proceed normally, cookies are automatically loaded
3. If NOT logged in but credentials exist: navigate to login page and auto-fill credentials
4. If NO credentials stored: use ask_user to request username and password from the user
5. After successful login: use save_login to store credentials (encrypted) and cache cookies
6. If login session appears expired (e.g., redirected to login page): re-login using stored credentials

TICKET GRABBING / FLASH SALES (抢票/秒杀):
For time-critical operations (12306 tickets, JD/Taobao flash sales, etc.):
1. PREPARE phase: Navigate to the page, log in, fill all forms, identify the buy/submit button
2. Call prepare_grab with target_time, actions (click_selector/click_xy/js_eval), and verify criteria
3. Call execute_grab with mode='confirm' to start the precision timer
4. The grab engine bypasses the LLM loop entirely — direct Playwright actions at exact target time
5. Supports retry (default 5 attempts, 100ms interval) and post-grab verification
6. For testing without waiting, use execute_grab mode='now'

Example grab workflow:
  - navigate to 12306.cn, login, search trains, select train
  - prepare_grab(target_time="2026-05-20T21:00:00", actions=[{"type":"click_selector","selector":"#submitOrder_id"}])
  - execute_grab(mode="confirm")

IMPORTANT RULES:
- Always take a screenshot before and after important actions
- Use coordinates from the most recent screenshot for clicks
- Handle errors gracefully - try alternative approaches
- For timed tasks (e.g., "book at 21:15"), use prepare_grab + execute_grab
- If you need user input (login credentials etc.), use ask_user
- After successful login, ALWAYS use save_login to persist the session
- Complete each task with task_complete, providing clear results"""

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        images: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Send a chat request and return the response with any tool calls."""
        if self.provider == "anthropic":
            return await self._chat_anthropic(messages, tools, images)
        else:
            return await self._chat_openai(messages, tools, images)

    def _openai_base(self) -> str:
        """Resolve OpenAI-compatible base URL.

        Users set AB_LLM_BASE_URL to the root endpoint, e.g.
        ``https://api.deepseek.com`` – we append ``/v1`` only when the
        base does not already end with a version segment like ``/v1``.
        """
        base = self.base_url or "https://api.openai.com/v1"
        base = base.rstrip("/")
        # If base already ends with /v1 or /v2 etc., don't append again
        if not base.split("/")[-1].startswith("v"):
            base += "/v1"
        return base

    def _anthropic_base(self) -> str:
        """Resolve Anthropic-compatible base URL.

        If the user provides a custom base_url for an Anthropic-style
        provider (e.g. ``https://api.deepseek.com/anthropic``), use it.
        Otherwise fall back to the official Anthropic API.
        """
        if self.base_url:
            return self.base_url.rstrip("/")
        return "https://api.anthropic.com/v1"

    async def _chat_openai(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        images: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Chat via OpenAI-compatible API."""
        url = self._openai_base() + "/chat/completions"

        # Prepare messages with system prompt
        full_messages = [{"role": "system", "content": self._get_system_prompt()}]
        for msg in messages:
            full_messages.append(msg)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": full_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = await self._client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            message = choice["message"]

            result: dict[str, Any] = {
                "content": message.get("content") or "",
                "tool_calls": [],
                "finish_reason": choice.get("finish_reason", "stop"),
            }

            # Preserve reasoning_content for thinking models (DeepSeek, etc.)
            # Must be passed back in subsequent requests or the API returns 400
            if message.get("reasoning_content"):
                result["reasoning_content"] = message["reasoning_content"]

            if message.get("tool_calls"):
                for tc in message["tool_calls"]:
                    result["tool_calls"].append(
                        {
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "arguments": json.loads(tc["function"]["arguments"]),
                        }
                    )

            return result
        except httpx.HTTPStatusError as e:
            logger.error("LLM API error: %s - %s", e.response.status_code, e.response.text)
            raise
        except Exception as e:
            logger.error("LLM request failed: %s", e)
            raise

    async def _chat_anthropic(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        images: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Chat via Anthropic API."""
        url = self._anthropic_base() + "/messages"

        # Convert OpenAI-style tools to Anthropic format
        anthropic_tools = []
        if tools:
            for t in tools:
                func = t["function"]
                anthropic_tools.append(
                    {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                    }
                )

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self._get_system_prompt(),
            "messages": messages,
        }
        if anthropic_tools:
            payload["tools"] = anthropic_tools

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        try:
            resp = await self._client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            result: dict[str, Any] = {
                "content": "",
                "tool_calls": [],
                "finish_reason": data.get("stop_reason", "end_turn"),
            }

            for block in data.get("content", []):
                if block["type"] == "text":
                    result["content"] += block["text"]
                elif block["type"] == "tool_use":
                    result["tool_calls"].append(
                        {
                            "id": block["id"],
                            "name": block["name"],
                            "arguments": block["input"],
                        }
                    )

            return result
        except httpx.HTTPStatusError as e:
            logger.error("Anthropic API error: %s - %s", e.response.status_code, e.response.text)
            raise
        except Exception as e:
            logger.error("Anthropic request failed: %s", e)
            raise

    async def stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a chat response. Yields partial content and final tool calls."""
        if self.provider == "anthropic":
            async for chunk in self._stream_anthropic(messages, tools):
                yield chunk
        else:
            async for chunk in self._stream_openai(messages, tools):
                yield chunk

    async def _stream_openai(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream via OpenAI-compatible API."""
        url = self._openai_base() + "/chat/completions"
        full_messages = [{"role": "system", "content": self._get_system_prompt()}] + list(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": full_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with self._client.stream("POST", url, json=payload, headers=headers) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {})
                        if delta.get("content"):
                            yield {"type": "content", "content": delta["content"]}
                    except (json.JSONDecodeError, KeyError):
                        continue

    async def _stream_anthropic(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream via Anthropic API."""
        url = self._anthropic_base() + "/messages"
        anthropic_tools = []
        if tools:
            for t in tools:
                func = t["function"]
                anthropic_tools.append(
                    {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                    }
                )

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self._get_system_prompt(),
            "messages": messages,
            "stream": True,
        }
        if anthropic_tools:
            payload["tools"] = anthropic_tools

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        async with self._client.stream("POST", url, json=payload, headers=headers) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        if event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield {"type": "content", "content": delta["text"]}
                    except (json.JSONDecodeError, KeyError):
                        continue
