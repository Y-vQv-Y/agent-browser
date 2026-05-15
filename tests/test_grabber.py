"""Tests for the millisecond-precision ticket grabber engine."""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_browser.core.grabber import (
    ActionType,
    GrabAction,
    GrabPlan,
    GrabResult,
    TicketGrabber,
    create_grab_plan,
    parse_grab_actions,
)


# --- Data class tests ---


class TestGrabAction:
    def test_create_click_selector(self):
        action = GrabAction(type="click_selector", selector="#buyBtn")
        assert action.type == "click_selector"
        assert action.selector == "#buyBtn"
        assert action.timeout_ms == 3000

    def test_create_click_xy(self):
        action = GrabAction(type="click_xy", x=100, y=200)
        assert action.x == 100
        assert action.y == 200

    def test_create_js_eval(self):
        action = GrabAction(type="js_eval", js_code="document.querySelector('#btn').click()")
        assert action.js_code == "document.querySelector('#btn').click()"

    def test_create_submit_form(self):
        action = GrabAction(type="submit_form", selector="form#order")
        assert action.type == "submit_form"


class TestGrabPlan:
    def test_create_plan(self):
        target = time.time() + 60
        actions = [GrabAction(type="click_selector", selector="#btn")]
        plan = GrabPlan(target_time=target, actions=actions)
        assert plan.target_time == target
        assert len(plan.actions) == 1
        assert plan.retry_count == 5
        assert plan.retry_interval_ms == 100
        assert plan.pre_wait_refresh is True

    def test_to_dict(self):
        target = time.time() + 60
        actions = [
            GrabAction(type="click_selector", selector="#btn"),
            GrabAction(type="click_xy", x=50, y=100),
        ]
        plan = GrabPlan(
            target_time=target,
            actions=actions,
            verify_selector=".success",
            verify_text="订单成功",
        )
        d = plan.to_dict()
        assert "target_time" in d
        assert "target_time_str" in d
        assert len(d["actions"]) == 2
        assert d["verify_selector"] == ".success"
        assert d["verify_text"] == "订单成功"
        assert d["retry_count"] == 5


class TestGrabResult:
    def test_success_result(self):
        r = GrabResult(
            success=True,
            message="Grab succeeded on attempt 1",
            attempts=1,
            actual_time="21:00:00.012",
            latency_ms=12.3,
            duration_ms=45.6,
            verify_passed=True,
        )
        assert r.success is True
        d = r.to_dict()
        assert d["latency_ms"] == 12.3
        assert d["duration_ms"] == 45.6
        assert d["verify_passed"] is True

    def test_failure_result(self):
        r = GrabResult(
            success=False,
            message="Grab failed after 5 attempts",
            attempts=5,
            latency_ms=1.0,
            duration_ms=600.0,
        )
        assert r.success is False
        assert r.verify_passed is None


# --- Parse functions ---


class TestParseGrabActions:
    def test_parse_single_action(self):
        raw = [{"type": "click_selector", "selector": "#submit"}]
        actions = parse_grab_actions(raw)
        assert len(actions) == 1
        assert actions[0].type == "click_selector"
        assert actions[0].selector == "#submit"

    def test_parse_multiple_actions(self):
        raw = [
            {"type": "click_selector", "selector": "#agree"},
            {"type": "click_xy", "x": 200, "y": 300},
            {"type": "js_eval", "js_code": "alert('ok')"},
        ]
        actions = parse_grab_actions(raw)
        assert len(actions) == 3
        assert actions[1].x == 200
        assert actions[2].js_code == "alert('ok')"

    def test_parse_defaults(self):
        raw = [{}]
        actions = parse_grab_actions(raw)
        assert actions[0].type == "click_selector"
        assert actions[0].selector == ""
        assert actions[0].timeout_ms == 3000

    def test_parse_custom_timeout(self):
        raw = [{"type": "click_selector", "selector": "#btn", "timeout_ms": 5000}]
        actions = parse_grab_actions(raw)
        assert actions[0].timeout_ms == 5000


class TestCreateGrabPlan:
    def test_create_from_iso_time(self):
        future = datetime.now() + timedelta(hours=1)
        plan = create_grab_plan(
            target_time_str=future.isoformat(),
            actions=[{"type": "click_selector", "selector": "#buy"}],
            verify_text="success",
        )
        assert abs(plan.target_time - future.timestamp()) < 1.0
        assert len(plan.actions) == 1
        assert plan.verify_text == "success"

    def test_create_with_custom_retry(self):
        future = datetime.now() + timedelta(minutes=5)
        plan = create_grab_plan(
            target_time_str=future.isoformat(),
            actions=[{"type": "click_xy", "x": 100, "y": 200}],
            retry_count=10,
            retry_interval_ms=50,
        )
        assert plan.retry_count == 10
        assert plan.retry_interval_ms == 50


# --- TicketGrabber engine tests ---


class TestTicketGrabber:
    @pytest.fixture
    def grabber(self):
        return TicketGrabber()

    @pytest.fixture
    def mock_page(self):
        page = AsyncMock()
        page.click = AsyncMock()
        page.evaluate = AsyncMock()
        page.mouse = AsyncMock()
        page.mouse.click = AsyncMock()
        page.query_selector = AsyncMock(return_value=None)
        page.content = AsyncMock(return_value="<html></html>")
        page.reload = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_execute_immediate(self, grabber, mock_page):
        """Test grab execution when target time is already past."""
        plan = GrabPlan(
            target_time=time.time() - 1,  # Already past
            actions=[GrabAction(type="click_selector", selector="#btn")],
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        assert result.success is True
        assert result.attempts == 1
        mock_page.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_click_selector(self, grabber, mock_page):
        plan = GrabPlan(
            target_time=time.time(),
            actions=[GrabAction(type="click_selector", selector="#submit")],
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        assert result.success is True
        mock_page.click.assert_called_once_with(
            "#submit", force=True, no_wait_after=True, timeout=3000
        )

    @pytest.mark.asyncio
    async def test_execute_click_xy(self, grabber, mock_page):
        plan = GrabPlan(
            target_time=time.time(),
            actions=[GrabAction(type="click_xy", x=150, y=250)],
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        assert result.success is True
        mock_page.mouse.click.assert_called_once_with(150, 250)

    @pytest.mark.asyncio
    async def test_execute_js_eval(self, grabber, mock_page):
        plan = GrabPlan(
            target_time=time.time(),
            actions=[GrabAction(type="js_eval", js_code="window.buy()")],
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        assert result.success is True
        mock_page.evaluate.assert_called_with("window.buy()")

    @pytest.mark.asyncio
    async def test_execute_submit_form(self, grabber, mock_page):
        plan = GrabPlan(
            target_time=time.time(),
            actions=[GrabAction(type="submit_form", selector="#orderForm")],
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_multiple_actions(self, grabber, mock_page):
        plan = GrabPlan(
            target_time=time.time(),
            actions=[
                GrabAction(type="click_selector", selector="#agree"),
                GrabAction(type="click_selector", selector="#submit"),
            ],
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        assert result.success is True
        assert mock_page.click.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, grabber, mock_page):
        """Test retry logic when actions fail."""
        mock_page.click = AsyncMock(
            side_effect=[Exception("Element not found"), Exception("Timeout"), None]
        )
        mock_page.evaluate = AsyncMock(
            side_effect=[Exception("JS fallback failed"), Exception("JS fallback failed"), None]
        )
        plan = GrabPlan(
            target_time=time.time(),
            actions=[GrabAction(type="click_selector", selector="#btn")],
            retry_count=3,
            retry_interval_ms=10,
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        # The third attempt should succeed
        assert result.success is True
        assert result.attempts == 3

    @pytest.mark.asyncio
    async def test_all_retries_fail(self, grabber, mock_page):
        """Test when all retry attempts fail."""
        mock_page.click = AsyncMock(side_effect=Exception("Always fails"))
        mock_page.evaluate = AsyncMock(side_effect=Exception("JS also fails"))
        plan = GrabPlan(
            target_time=time.time(),
            actions=[GrabAction(type="click_selector", selector="#btn")],
            retry_count=2,
            retry_interval_ms=10,
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        assert result.success is False
        assert result.attempts == 2
        assert "Always fails" in result.message or "JS also fails" in result.message

    @pytest.mark.asyncio
    async def test_verify_success_by_selector(self, grabber, mock_page):
        mock_el = AsyncMock()
        mock_el.text_content = AsyncMock(return_value="订单提交成功")
        mock_page.query_selector = AsyncMock(return_value=mock_el)

        plan = GrabPlan(
            target_time=time.time(),
            actions=[GrabAction(type="click_selector", selector="#btn")],
            verify_selector=".result",
            verify_text="订单提交成功",
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        assert result.success is True
        assert result.verify_passed is True

    @pytest.mark.asyncio
    async def test_verify_success_by_text(self, grabber, mock_page):
        mock_page.content = AsyncMock(return_value="<html>购票成功</html>")

        plan = GrabPlan(
            target_time=time.time(),
            actions=[GrabAction(type="click_selector", selector="#btn")],
            verify_text="购票成功",
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        assert result.success is True
        assert result.verify_passed is True

    @pytest.mark.asyncio
    async def test_verify_failure_retries(self, grabber, mock_page):
        """Test that verification failure triggers retry."""
        mock_page.query_selector = AsyncMock(return_value=None)

        plan = GrabPlan(
            target_time=time.time(),
            actions=[GrabAction(type="click_selector", selector="#btn")],
            verify_selector=".success",
            retry_count=2,
            retry_interval_ms=10,
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        # Last attempt still succeeds (actions work) but verify fails
        assert result.success is True
        assert result.verify_passed is False

    @pytest.mark.asyncio
    async def test_timing_measurement(self, grabber, mock_page):
        """Test that timing fields are populated."""
        target = time.time() - 0.01  # Slightly in the past
        plan = GrabPlan(
            target_time=target,
            actions=[GrabAction(type="click_selector", selector="#btn")],
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        assert result.actual_time != ""
        assert result.latency_ms > 0
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_precise_wait_short(self, grabber):
        """Test that precise_wait returns within acceptable tolerance."""
        target = time.time() + 0.05  # 50ms in the future
        start = time.time()
        await grabber._precise_wait(target)
        elapsed = time.time() - start
        # Should wait at least ~50ms but not more than 100ms
        assert elapsed >= 0.04  # Allow 10ms early
        assert elapsed < 0.15  # Should not overshoot by more than 100ms

    @pytest.mark.asyncio
    async def test_precise_wait_already_past(self, grabber):
        """Test precise_wait when target time is already past."""
        target = time.time() - 1.0
        start = time.time()
        await grabber._precise_wait(target)
        elapsed = time.time() - start
        assert elapsed < 0.01  # Should return almost immediately

    @pytest.mark.asyncio
    async def test_click_selector_js_fallback(self, grabber, mock_page):
        """Test that JS fallback is used when Playwright click fails."""
        mock_page.click = AsyncMock(side_effect=Exception("Element detached"))
        mock_page.evaluate = AsyncMock(return_value=None)

        plan = GrabPlan(
            target_time=time.time(),
            actions=[GrabAction(type="click_selector", selector="#btn")],
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        assert result.success is True
        # JS fallback should have been called
        mock_page.evaluate.assert_called()

    @pytest.mark.asyncio
    async def test_pre_wait_refresh(self, grabber, mock_page):
        """Test that page is refreshed before grab when pre_wait_refresh=True."""
        plan = GrabPlan(
            target_time=time.time() + 4.0,  # 4s in future (>3s threshold)
            actions=[GrabAction(type="click_selector", selector="#btn")],
            pre_wait_refresh=True,
        )
        # Patch precise_wait to avoid actual waiting
        grabber._precise_wait = AsyncMock()
        result = await grabber.execute(mock_page, plan)
        assert result.success is True
        mock_page.reload.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_form_no_selector(self, grabber, mock_page):
        """Test submit_form without selector falls back to first form."""
        plan = GrabPlan(
            target_time=time.time(),
            actions=[GrabAction(type="submit_form")],
            pre_wait_refresh=False,
        )
        result = await grabber.execute(mock_page, plan)
        assert result.success is True
        mock_page.evaluate.assert_called_with(
            'document.querySelector("form")?.submit()'
        )
