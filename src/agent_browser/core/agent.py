"""
Agent Engine - Core agent loop internalized from GenericAgent.
Orchestrates LLM, tools, memory, and browser to complete tasks.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Optional

from agent_browser.config import AppConfig
from agent_browser.core.llm import LLMClient, get_all_tools
from agent_browser.core.memory import WorkingMemory
from agent_browser.core.scheduler import TaskScheduler

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of a single agent step (tool execution)."""
    tool_name: str
    arguments: dict
    result: Any
    success: bool
    error: Optional[str] = None
    duration: float = 0.0


@dataclass
class TaskResult:
    """Final result of a complete task execution."""
    task: str
    success: bool
    result: str
    data: Optional[dict] = None
    steps: list[StepResult] = None
    duration: float = 0.0

    def __post_init__(self):
        if self.steps is None:
            self.steps = []


class AgentBrowser:
    """
    Main agent engine. Combines:
    - GenericAgent's agent loop and task planning
    - browser-harness's CDP browser control
    - CloakBrowser's anti-detection and humanization
    """

    def __init__(self, config: Optional[AppConfig] = None, profile_name: Optional[str] = None):
        self.config = config or AppConfig()
        self._profile_name = profile_name
        self.llm = LLMClient(
            provider=self.config.llm.provider,
            api_key=self.config.llm.api_key,
            model=self.config.llm.model,
            base_url=self.config.llm.base_url,
            max_tokens=self.config.llm.max_tokens,
            temperature=self.config.llm.temperature,
        )
        self.memory = WorkingMemory(self.config.data_path / "memory")
        self.scheduler = TaskScheduler(self.config.data_path / "tasks")
        self.browser = None  # Lazily initialized
        self.tools = get_all_tools()
        self.max_turns = 50
        self._running = False
        self._user_input_callback: Optional[Callable] = None
        self._on_step_callback: Optional[Callable] = None

        # Set scheduler executor
        self.scheduler.set_executor(self._execute_scheduled_task)

    async def initialize(self):
        """Initialize the browser engine."""
        from agent_browser.browser.engine import BrowserEngine
        self.browser = BrowserEngine(self.config.browser, profile_name=self._profile_name)
        await self.browser.launch()
        logger.info("AgentBrowser initialized (provider=%s, model=%s)",
                     self.config.llm.provider, self.config.llm.model)

    async def close(self):
        """Cleanup resources."""
        if self.browser:
            await self.browser.close()
        await self.llm.close()
        self.scheduler.shutdown()
        self.memory.save()

    def set_user_input_callback(self, callback: Callable):
        """Set callback for ask_user tool."""
        self._user_input_callback = callback

    def set_step_callback(self, callback: Callable):
        """Set callback for step-by-step progress updates."""
        self._on_step_callback = callback

    async def run_task(self, task: str) -> TaskResult:
        """
        Execute a natural language task using the agent loop.
        This is the main entry point - the agent will plan, execute,
        and verify the task autonomously.
        """
        self._running = True
        start_time = time.time()
        steps: list[StepResult] = []

        self.memory.clear_working()
        self.memory.set_working("current_task", task)
        self.memory.add_message("user", task)

        if not self.browser:
            await self.initialize()

        logger.info("Starting task: %s", task)

        messages = [{"role": "user", "content": task}]
        turn = 0

        while self._running and turn < self.max_turns:
            turn += 1
            logger.debug("Turn %d/%d", turn, self.max_turns)

            # Add memory context
            context = self.memory.get_context_prompt()
            if context and turn > 1:
                messages.append({
                    "role": "system",
                    "content": f"[Working Memory]\n{context}\n[Turn {turn}/{self.max_turns}]",
                })

            try:
                response = await self.llm.chat(messages, tools=self.tools)
            except Exception as e:
                logger.error("LLM call failed at turn %d: %s", turn, e)
                return TaskResult(
                    task=task,
                    success=False,
                    result=f"LLM error: {e}",
                    steps=steps,
                    duration=time.time() - start_time,
                )

            # Process text response
            if response.get("content"):
                logger.info("Agent: %s", response["content"][:200])
                self.memory.add_message("assistant", response["content"])
                messages.append({"role": "assistant", "content": response["content"]})

            # Process tool calls
            if not response.get("tool_calls"):
                if response.get("content"):
                    # Agent wants to say something without using tools - add and continue
                    continue
                break

            # Build assistant message with tool_calls for OpenAI format
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": response.get("content", "")}
            if self.config.llm.provider != "anthropic":
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in response["tool_calls"]
                ]
            messages.append(assistant_msg)

            for tool_call in response["tool_calls"]:
                tool_name = tool_call["name"]
                args = tool_call["arguments"]
                tool_id = tool_call["id"]

                logger.info("Tool call: %s(%s)", tool_name, json.dumps(args)[:200])

                step_start = time.time()
                step_result = await self._execute_tool(tool_name, args)
                step_duration = time.time() - step_start

                step = StepResult(
                    tool_name=tool_name,
                    arguments=args,
                    result=step_result.get("output", ""),
                    success=step_result.get("success", True),
                    error=step_result.get("error"),
                    duration=step_duration,
                )
                steps.append(step)

                if self._on_step_callback:
                    await self._on_step_callback(step)

                # Add tool result to messages
                tool_result_content = json.dumps(step_result, default=str)
                if len(tool_result_content) > 10000:
                    tool_result_content = tool_result_content[:10000] + "...(truncated)"

                if self.config.llm.provider == "anthropic":
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": tool_result_content,
                            }
                        ],
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": tool_result_content,
                    })

                # Check if task is complete
                if tool_name == "task_complete":
                    self._running = False
                    return TaskResult(
                        task=task,
                        success=args.get("success", True),
                        result=args.get("result", ""),
                        data=args.get("data"),
                        steps=steps,
                        duration=time.time() - start_time,
                    )

            # Safety: warn about loops
            if turn % 10 == 0:
                messages.append({
                    "role": "system",
                    "content": f"WARNING: {turn} turns used. If stuck, try a different approach or ask the user.",
                })

        return TaskResult(
            task=task,
            success=False,
            result=f"Task did not complete within {self.max_turns} turns",
            steps=steps,
            duration=time.time() - start_time,
        )

    async def _execute_tool(self, name: str, args: dict) -> dict:
        """Execute a single tool and return the result."""
        try:
            if name == "navigate":
                await self.browser.navigate(args["url"])
                return {"success": True, "output": f"Navigated to {args['url']}"}

            elif name == "click":
                await self.browser.click(
                    args["x"], args["y"],
                    button=args.get("button", "left"),
                )
                return {"success": True, "output": f"Clicked at ({args['x']}, {args['y']})"}

            elif name == "type_text":
                if args.get("selector"):
                    await self.browser.fill_input(
                        args["selector"], args["text"],
                        clear_first=args.get("clear_first", True),
                    )
                else:
                    await self.browser.type_text(args["text"])
                return {"success": True, "output": f"Typed text: {args['text'][:50]}..."}

            elif name == "press_key":
                await self.browser.press_key(
                    args["key"],
                    modifiers=args.get("modifiers", []),
                )
                return {"success": True, "output": f"Pressed key: {args['key']}"}

            elif name == "screenshot":
                img_data = await self.browser.screenshot(
                    full_page=args.get("full_page", False),
                )
                # Store screenshot for LLM vision
                self.memory.set_working("last_screenshot", img_data[:100] + "...")
                return {
                    "success": True,
                    "output": "Screenshot captured",
                    "image": img_data,
                }

            elif name == "get_page_info":
                info = await self.browser.get_page_info()
                return {"success": True, "output": json.dumps(info)}

            elif name == "scroll":
                direction = args.get("direction", "down")
                amount = args.get("amount", 300)
                await self.browser.scroll(direction, amount)
                return {"success": True, "output": f"Scrolled {direction} by {amount}px"}

            elif name == "run_javascript":
                result = await self.browser.run_javascript(args["code"])
                return {"success": True, "output": str(result)}

            elif name == "wait":
                if args.get("selector"):
                    await self.browser.wait_for_element(
                        args["selector"],
                        timeout=args.get("timeout", 10),
                    )
                    return {"success": True, "output": f"Element found: {args['selector']}"}
                elif args.get("seconds"):
                    await asyncio.sleep(args["seconds"])
                    return {"success": True, "output": f"Waited {args['seconds']}s"}
                else:
                    await self.browser.wait_for_load(timeout=args.get("timeout", 10))
                    return {"success": True, "output": "Page loaded"}

            elif name == "extract_data":
                data = await self.browser.extract_data(
                    args["description"],
                    selectors=args.get("selectors"),
                )
                return {"success": True, "output": json.dumps(data, default=str)}

            elif name == "handle_captcha":
                result = await self._handle_captcha(args.get("strategy", "auto"))
                return result

            elif name == "create_plan":
                plan = args
                self.memory.set_working("current_plan", json.dumps(plan))
                return {"success": True, "output": f"Plan created with {len(plan.get('steps', []))} steps"}

            elif name == "schedule_task":
                task = self.scheduler.add_task(
                    description=args["task"],
                    execute_at=args.get("execute_at"),
                    pre_check=args.get("pre_check", False),
                )
                return {
                    "success": True,
                    "output": f"Task scheduled: id={task.task_id}, execute_at={task.execute_at}",
                }

            elif name == "ask_user":
                if self._user_input_callback:
                    answer = await self._user_input_callback(args["question"])
                    return {"success": True, "output": f"User replied: {answer}"}
                return {"success": True, "output": "No user input handler configured"}

            elif name == "task_complete":
                return {"success": True, "output": "Task marked complete"}

            else:
                return {"success": False, "error": f"Unknown tool: {name}"}

        except Exception as e:
            logger.error("Tool execution error (%s): %s", name, e)
            return {"success": False, "error": str(e)}

    async def _handle_captcha(self, strategy: str = "auto") -> dict:
        """Handle CAPTCHA detection and solving using CloakBrowser techniques."""
        try:
            from agent_browser.browser.captcha import CaptchaHandler
            handler = CaptchaHandler(self.browser)
            result = await handler.detect_and_solve(strategy)
            return {"success": result.solved, "output": result.message}
        except Exception as e:
            return {"success": False, "error": f"CAPTCHA handling failed: {e}"}

    async def _execute_scheduled_task(self, description: str) -> str:
        """Execute a scheduled task (called by scheduler)."""
        result = await self.run_task(description)
        return result.result

    async def run_interactive(self) -> AsyncIterator[dict]:
        """Run in interactive mode, yielding events for UI consumption."""
        if not self.browser:
            await self.initialize()

        yield {"type": "ready", "message": "AgentBrowser ready. Describe your task."}

        while True:
            if self._user_input_callback:
                task = await self._user_input_callback("Enter your task (or 'quit' to exit):")
            else:
                break

            if task.lower() in ("quit", "exit", "q"):
                yield {"type": "exit", "message": "Goodbye!"}
                break

            yield {"type": "task_start", "task": task}

            result = await self.run_task(task)

            yield {
                "type": "task_complete",
                "success": result.success,
                "result": result.result,
                "steps": len(result.steps),
                "duration": result.duration,
            }
