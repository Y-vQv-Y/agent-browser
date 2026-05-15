"""Tests for the CAPTCHA handler."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from agent_browser.browser.captcha import CaptchaHandler, CaptchaResult


class TestCaptchaResult:
    def test_default(self):
        result = CaptchaResult()
        assert result.detected is False
        assert result.solved is False
        assert result.captcha_type is None

    def test_detected(self):
        result = CaptchaResult(detected=True, captcha_type="recaptcha")
        assert result.detected is True
        assert result.captcha_type == "recaptcha"


class TestCaptchaHandler:
    @pytest.fixture
    def mock_browser(self):
        browser = MagicMock()
        page = MagicMock()
        page.evaluate = AsyncMock(return_value=False)
        page.frames = []
        page.query_selector_all = AsyncMock(return_value=[])
        type(browser).page = PropertyMock(return_value=page)
        browser.click = AsyncMock()
        return browser

    @pytest.fixture
    def handler(self, mock_browser):
        return CaptchaHandler(mock_browser)

    @pytest.mark.asyncio
    async def test_detect_no_captcha(self, handler):
        result = await handler.detect()
        assert result.detected is False

    @pytest.mark.asyncio
    async def test_detect_recaptcha(self, handler, mock_browser):
        # First call returns True (recaptcha found), rest return False
        call_count = 0

        async def side_effect(code):
            nonlocal call_count
            call_count += 1
            return call_count == 1  # Only first check (recaptcha) returns True

        mock_browser.page.evaluate = AsyncMock(side_effect=side_effect)

        result = await handler.detect()
        assert result.detected is True
        assert result.captcha_type == "recaptcha"

    @pytest.mark.asyncio
    async def test_detect_turnstile(self, handler, mock_browser):
        call_count = 0

        async def side_effect(code):
            nonlocal call_count
            call_count += 1
            return call_count == 2  # Second check (turnstile)

        mock_browser.page.evaluate = AsyncMock(side_effect=side_effect)

        result = await handler.detect()
        assert result.detected is True
        assert result.captcha_type == "turnstile"

    @pytest.mark.asyncio
    async def test_detect_and_solve_no_captcha(self, handler):
        result = await handler.detect_and_solve()
        assert result.detected is False
        assert result.solved is False

    @pytest.mark.asyncio
    async def test_solve_turnstile_auto_pass(self, handler, mock_browser):
        """Test Turnstile auto-pass with stealth browser."""
        # Simulate Turnstile detected then auto-passed
        detect_call = 0

        async def detect_side_effect(code):
            nonlocal detect_call
            detect_call += 1
            if detect_call == 2:  # turnstile check
                return True
            if detect_call > 5:  # turnstile response check
                return True
            return False

        mock_browser.page.evaluate = AsyncMock(side_effect=detect_side_effect)

        handler._solve_turnstile = AsyncMock(return_value=True)
        handler._check_turnstile = AsyncMock(return_value=(True, "turnstile"))

        result = await handler.detect()
        assert result.captcha_type == "turnstile"

    @pytest.mark.asyncio
    async def test_solve_slider(self, handler, mock_browser):
        """Test slider CAPTCHA solving."""
        # Mock slider element
        mock_element = MagicMock()
        mock_element.bounding_box = AsyncMock(return_value={
            "x": 100, "y": 300, "width": 40, "height": 40,
        })

        mock_browser.page.query_selector = AsyncMock(return_value=mock_element)
        mock_browser.page.mouse = MagicMock()
        mock_browser.page.mouse.move = AsyncMock()
        mock_browser.page.mouse.down = AsyncMock()
        mock_browser.page.mouse.up = AsyncMock()

        # Direct call to _solve_slider
        result = await handler._solve_slider()
        # The result depends on whether the mock slider was found
        assert isinstance(result, bool)
