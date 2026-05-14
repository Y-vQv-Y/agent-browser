"""Tests for the humanize module."""

import asyncio
import math
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_browser.browser.humanize import (
    HumanPreset,
    HumanMouse,
    HumanKeyboard,
    HumanScroll,
    Humanizer,
    PRESETS,
)


class TestHumanPreset:
    def test_default_preset(self):
        preset = HumanPreset()
        assert preset.mouse_speed == 1.0
        assert preset.type_delay_mean == 0.07
        assert preset.type_mistype_chance == 0.02

    def test_preset_registry(self):
        assert "default" in PRESETS
        assert "careful" in PRESETS
        assert "fast" in PRESETS

    def test_careful_preset(self):
        careful = PRESETS["careful"]
        default = PRESETS["default"]
        assert careful.mouse_speed > default.mouse_speed
        assert careful.type_delay_mean > default.type_delay_mean

    def test_fast_preset(self):
        fast = PRESETS["fast"]
        default = PRESETS["default"]
        assert fast.mouse_speed < default.mouse_speed
        assert fast.type_delay_mean < default.type_delay_mean


class TestHumanMouse:
    def test_bezier_curve_points(self):
        mouse = HumanMouse(HumanPreset())
        points = mouse.bezier_curve((0, 0), (100, 100), num_points=20)
        assert len(points) == 21
        # Final point should be exact target
        assert points[-1] == (100, 100)

    def test_bezier_curve_start(self):
        mouse = HumanMouse(HumanPreset())
        points = mouse.bezier_curve((50, 50), (200, 200), num_points=10)
        # First point should be near start (with possible wobble)
        assert abs(points[0][0] - 50) < 20
        assert abs(points[0][1] - 50) < 20

    def test_bezier_different_each_time(self):
        """Bezier curves should have randomness."""
        mouse = HumanMouse(HumanPreset())
        curve1 = mouse.bezier_curve((0, 0), (100, 100), num_points=10)
        curve2 = mouse.bezier_curve((0, 0), (100, 100), num_points=10)
        # Not all intermediate points should be identical
        differences = sum(1 for p1, p2 in zip(curve1[1:-1], curve2[1:-1]) if p1 != p2)
        assert differences > 0

    @pytest.mark.asyncio
    async def test_move_to(self):
        mouse = HumanMouse(HumanPreset(mouse_speed=0.01))  # Fast for testing
        page = MagicMock()
        page.mouse = MagicMock()
        page.mouse.move = AsyncMock()

        await mouse.move_to(page, 100, 200)
        assert page.mouse.move.call_count > 5
        assert mouse.current_x == 100
        assert mouse.current_y == 200

    @pytest.mark.asyncio
    async def test_click_at(self):
        mouse = HumanMouse(HumanPreset(mouse_speed=0.01, mouse_overshoot_chance=0))
        page = MagicMock()
        page.mouse = MagicMock()
        page.mouse.move = AsyncMock()
        page.mouse.click = AsyncMock()

        await mouse.click_at(page, 100, 200)
        page.mouse.click.assert_called_once()


class TestHumanKeyboard:
    @pytest.mark.asyncio
    async def test_type_text(self):
        kb = HumanKeyboard(HumanPreset(
            type_delay_mean=0.001,
            type_delay_std=0.0001,
            type_mistype_chance=0,
            type_pause_chance=0,
        ))
        page = MagicMock()
        page.keyboard = MagicMock()
        page.keyboard.type = AsyncMock()

        await kb.type_text(page, "hello")
        assert page.keyboard.type.call_count == 5


class TestHumanScroll:
    @pytest.mark.asyncio
    async def test_scroll_smooth(self):
        scroll = HumanScroll(HumanPreset(scroll_smooth=True, scroll_overshoot=False))
        page = MagicMock()
        page.mouse = MagicMock()
        page.mouse.wheel = AsyncMock()

        await scroll.scroll(page, "down", 300)
        assert page.mouse.wheel.call_count > 1  # Multiple smooth steps

    @pytest.mark.asyncio
    async def test_scroll_not_smooth(self):
        scroll = HumanScroll(HumanPreset(scroll_smooth=False))
        page = MagicMock()
        page.mouse = MagicMock()
        page.mouse.wheel = AsyncMock()

        await scroll.scroll(page, "down", 300)
        assert page.mouse.wheel.call_count == 1  # Single step


class TestHumanizer:
    def test_init(self):
        h = Humanizer("default")
        assert h.mouse is not None
        assert h.keyboard is not None
        assert h.scroll is not None

    def test_init_with_presets(self):
        for preset_name in PRESETS:
            h = Humanizer(preset_name)
            assert h.preset is not None
