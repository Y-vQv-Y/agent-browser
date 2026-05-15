"""
Ticket Grabber - Millisecond-precision ticket grabbing engine.

Bypasses the LLM agent loop for time-critical operations like
train ticket booking (12306), flash sales (JD/Taobao), etc.

Architecture:
  Phase 1 (PREPARE): LLM navigates, logs in, fills forms, identifies button
  Phase 2 (EXECUTE): Direct browser actions at exact target time, no LLM
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    CLICK_SELECTOR = "click_selector"
    CLICK_XY = "click_xy"
    JS_EVAL = "js_eval"
    SUBMIT_FORM = "submit_form"


@dataclass
class GrabAction:
    """A single pre-computed browser action for the grab sequence."""
    type: str  # ActionType value
    selector: str = ""
    x: int = 0
    y: int = 0
    js_code: str = ""
    timeout_ms: int = 3000


@dataclass
class GrabPlan:
    """Pre-computed action sequence for millisecond-precision execution."""
    target_time: float  # Unix timestamp
    actions: list[GrabAction] = field(default_factory=list)
    verify_selector: str = ""
    verify_text: str = ""
    retry_count: int = 5
    retry_interval_ms: int = 100
    pre_wait_refresh: bool = True

    def to_dict(self) -> dict:
        return {
            "target_time": self.target_time,
            "target_time_str": datetime.fromtimestamp(self.target_time).isoformat(),
            "actions": [
                {"type": a.type, "selector": a.selector, "x": a.x, "y": a.y}
                for a in self.actions
            ],
            "retry_count": self.retry_count,
            "retry_interval_ms": self.retry_interval_ms,
            "verify_selector": self.verify_selector,
            "verify_text": self.verify_text,
            "pre_wait_refresh": self.pre_wait_refresh,
        }


@dataclass
class GrabResult:
    """Result of a grab execution."""
    success: bool
    message: str
    attempts: int = 0
    actual_time: str = ""
    latency_ms: float = 0.0
    duration_ms: float = 0.0
    verify_passed: Optional[bool] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "attempts": self.attempts,
            "actual_time": self.actual_time,
            "latency_ms": round(self.latency_ms, 2),
            "duration_ms": round(self.duration_ms, 2),
            "verify_passed": self.verify_passed,
        }


class TicketGrabber:
    """
    Millisecond-precision ticket grabbing engine.

    Executes pre-computed browser actions at exact target times,
    completely bypassing the LLM agent loop for maximum speed.
    Uses direct Playwright page operations (no humanization).
    """

    async def execute(self, page: Any, plan: GrabPlan) -> GrabResult:
        """
        Execute a grab plan.

        1. Wait with millisecond precision until target_time
        2. Optional: refresh page just before target time
        3. Execute pre-computed actions directly on the page
        4. Retry on failure
        5. Verify success
        """
        target = plan.target_time
        now = time.time()
        wait_seconds = target - now

        if wait_seconds > 0:
            logger.info(
                "Grab scheduled for %s (%.1fs from now)",
                datetime.fromtimestamp(target).strftime("%H:%M:%S.%f")[:-3],
                wait_seconds,
            )

            # Pre-grab refresh: reload page 2s before target to get fresh DOM
            if plan.pre_wait_refresh and wait_seconds > 3.0:
                pre_refresh_wait = wait_seconds - 2.0
                logger.info("Waiting %.1fs, then refreshing page...", pre_refresh_wait)
                await asyncio.sleep(pre_refresh_wait)
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=5000)
                    logger.info("Page refreshed, entering precision wait...")
                except Exception as e:
                    logger.warning("Pre-grab refresh failed: %s", e)

            # Precise wait until exact target time
            await self._precise_wait(target)
        else:
            logger.info("Target time already passed (%.0fms ago), executing immediately",
                        -wait_seconds * 1000)

        # Execute with retries
        start_time = time.time()
        actual_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        latency_ms = (start_time - target) * 1000

        logger.info(
            "GRAB START at %s (latency: %.1fms from target)",
            actual_time, latency_ms,
        )

        last_error = ""
        for attempt in range(1, plan.retry_count + 1):
            try:
                success = await self._execute_actions(page, plan.actions)
                if success:
                    duration_ms = (time.time() - start_time) * 1000
                    logger.info(
                        "Grab actions succeeded on attempt %d (%.1fms)",
                        attempt, duration_ms,
                    )

                    # Verify success if selector provided
                    verify_passed = None
                    if plan.verify_selector or plan.verify_text:
                        await asyncio.sleep(0.5)  # Brief wait for page update
                        verify_passed = await self._verify_success(page, plan)
                        if not verify_passed and attempt < plan.retry_count:
                            logger.info("Verification failed, retrying...")
                            await asyncio.sleep(plan.retry_interval_ms / 1000.0)
                            continue

                    return GrabResult(
                        success=True,
                        message=f"Grab succeeded on attempt {attempt}",
                        attempts=attempt,
                        actual_time=actual_time,
                        latency_ms=latency_ms,
                        duration_ms=(time.time() - start_time) * 1000,
                        verify_passed=verify_passed,
                    )
            except Exception as e:
                last_error = str(e)
                logger.warning("Attempt %d failed: %s", attempt, e)

            if attempt < plan.retry_count:
                await asyncio.sleep(plan.retry_interval_ms / 1000.0)

        return GrabResult(
            success=False,
            message=f"Grab failed after {plan.retry_count} attempts: {last_error}",
            attempts=plan.retry_count,
            actual_time=actual_time,
            latency_ms=latency_ms,
            duration_ms=(time.time() - start_time) * 1000,
        )

    async def _precise_wait(self, target_time: float):
        """
        Wait until target_time with millisecond precision.

        Three-phase approach:
          Phase 1: asyncio.sleep for bulk waiting (>1s remaining)
          Phase 2: Short sleeps in 5ms chunks (>10ms remaining)
          Phase 3: Spin-wait for final microseconds
        """
        while True:
            remaining = target_time - time.time()
            if remaining <= 0:
                break

            if remaining > 1.0:
                # Phase 1: Sleep for most of the wait (save CPU)
                await asyncio.sleep(remaining - 0.5)
            elif remaining > 0.01:
                # Phase 2: Short sleeps for sub-second precision
                await asyncio.sleep(0.003)
            else:
                # Phase 3: Spin-wait for final ~10ms (maximum precision)
                while time.time() < target_time:
                    pass
                break

    async def _execute_actions(self, page: Any, actions: list[GrabAction]) -> bool:
        """
        Execute grab actions directly on the Playwright page.
        Bypasses BrowserEngine and Humanizer for maximum speed.
        """
        for action in actions:
            if action.type == ActionType.CLICK_SELECTOR:
                # Direct click by CSS selector - fastest method
                try:
                    await page.click(
                        action.selector,
                        force=True,
                        no_wait_after=True,
                        timeout=action.timeout_ms,
                    )
                except Exception:
                    # Fallback: try JavaScript click
                    await page.evaluate(
                        f'document.querySelector("{action.selector}")?.click()'
                    )

            elif action.type == ActionType.CLICK_XY:
                # Direct coordinate click
                await page.mouse.click(action.x, action.y)

            elif action.type == ActionType.JS_EVAL:
                # Execute arbitrary JavaScript
                await page.evaluate(action.js_code)

            elif action.type == ActionType.SUBMIT_FORM:
                # Submit form by selector
                if action.selector:
                    await page.evaluate(
                        f'''(function() {{
                            var el = document.querySelector("{action.selector}");
                            if (el) {{
                                if (el.tagName === "FORM") el.submit();
                                else el.click();
                            }}
                        }})()'''
                    )
                else:
                    await page.evaluate(
                        'document.querySelector("form")?.submit()'
                    )
            else:
                logger.warning("Unknown action type: %s", action.type)

        return True

    async def _verify_success(self, page: Any, plan: GrabPlan) -> bool:
        """Check if the grab was successful by looking for expected elements/text."""
        try:
            if plan.verify_selector:
                el = await page.query_selector(plan.verify_selector)
                if el:
                    if plan.verify_text:
                        text = await el.text_content()
                        return plan.verify_text in (text or "")
                    return True
                return False

            if plan.verify_text:
                content = await page.content()
                return plan.verify_text in content

        except Exception as e:
            logger.warning("Verification error: %s", e)

        return False


def parse_grab_actions(raw_actions: list[dict]) -> list[GrabAction]:
    """Parse raw action dicts (from LLM tool call) into GrabAction objects."""
    actions = []
    for raw in raw_actions:
        actions.append(GrabAction(
            type=raw.get("type", "click_selector"),
            selector=raw.get("selector", ""),
            x=raw.get("x", 0),
            y=raw.get("y", 0),
            js_code=raw.get("js_code", ""),
            timeout_ms=raw.get("timeout_ms", 3000),
        ))
    return actions


def create_grab_plan(
    target_time_str: str,
    actions: list[dict],
    verify_selector: str = "",
    verify_text: str = "",
    retry_count: int = 5,
    retry_interval_ms: int = 100,
    pre_wait_refresh: bool = True,
) -> GrabPlan:
    """Create a GrabPlan from parsed LLM tool arguments."""
    # Parse target time
    dt = datetime.fromisoformat(target_time_str)
    target_ts = dt.timestamp()

    return GrabPlan(
        target_time=target_ts,
        actions=parse_grab_actions(actions),
        verify_selector=verify_selector,
        verify_text=verify_text,
        retry_count=retry_count,
        retry_interval_ms=retry_interval_ms,
        pre_wait_refresh=pre_wait_refresh,
    )
