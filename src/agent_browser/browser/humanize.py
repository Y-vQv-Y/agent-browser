"""
Humanize - Human-like behavior simulation.
Internalized from CloakBrowser's human/ module.
Provides realistic mouse movements, typing, and scrolling.
"""

from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class HumanPreset:
    """Configuration preset for human-like behavior."""
    # Mouse movement
    mouse_speed: float = 1.0  # multiplier (lower = faster)
    mouse_wobble: float = 2.0  # pixels of wobble
    mouse_overshoot_chance: float = 0.15
    mouse_overshoot_distance: float = 5.0
    # Typing
    type_delay_mean: float = 0.07  # seconds
    type_delay_std: float = 0.04
    type_pause_chance: float = 0.10
    type_pause_duration: tuple[float, float] = (0.4, 1.0)
    type_mistype_chance: float = 0.02
    # Scrolling
    scroll_smooth: bool = True
    scroll_overshoot: bool = True
    # Idle
    idle_drift: bool = False
    idle_drift_interval: float = 5.0


PRESETS = {
    "default": HumanPreset(),
    "careful": HumanPreset(
        mouse_speed=1.5,
        mouse_wobble=1.5,
        type_delay_mean=0.10,
        type_delay_std=0.05,
        type_pause_chance=0.15,
        type_mistype_chance=0.01,
        idle_drift=True,
    ),
    "fast": HumanPreset(
        mouse_speed=0.5,
        mouse_wobble=1.0,
        type_delay_mean=0.03,
        type_delay_std=0.02,
        type_pause_chance=0.05,
        type_mistype_chance=0.0,
    ),
}


class HumanMouse:
    """Human-like mouse movement using Bezier curves."""

    def __init__(self, preset: HumanPreset):
        self.preset = preset
        self.current_x = 0
        self.current_y = 0

    def bezier_curve(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        num_points: int = 20,
    ) -> list[tuple[float, float]]:
        """Generate points along a Bezier curve with random control points."""
        sx, sy = start
        ex, ey = end
        distance = math.sqrt((ex - sx) ** 2 + (ey - sy) ** 2)

        # Random control points for natural curve
        cp1x = sx + (ex - sx) * random.uniform(0.2, 0.4) + random.gauss(0, distance * 0.1)
        cp1y = sy + (ey - sy) * random.uniform(0.2, 0.4) + random.gauss(0, distance * 0.1)
        cp2x = sx + (ex - sx) * random.uniform(0.6, 0.8) + random.gauss(0, distance * 0.1)
        cp2y = sy + (ey - sy) * random.uniform(0.6, 0.8) + random.gauss(0, distance * 0.1)

        points = []
        for i in range(num_points + 1):
            t = i / num_points
            # Ease-in-out timing
            t = t * t * (3 - 2 * t)

            x = (1 - t) ** 3 * sx + 3 * (1 - t) ** 2 * t * cp1x + 3 * (1 - t) * t ** 2 * cp2x + t ** 3 * ex
            y = (1 - t) ** 3 * sy + 3 * (1 - t) ** 2 * t * cp1y + 3 * (1 - t) * t ** 2 * cp2y + t ** 3 * ey

            # Add wobble
            wobble = self.preset.mouse_wobble
            x += random.gauss(0, wobble * (1 - abs(2 * t - 1)))
            y += random.gauss(0, wobble * (1 - abs(2 * t - 1)))

            points.append((x, y))

        # Ensure final point is exact
        points[-1] = end
        return points

    async def move_to(self, page, x: float, y: float):
        """Move mouse to target with human-like Bezier curve."""
        points = self.bezier_curve(
            (self.current_x, self.current_y),
            (x, y),
            num_points=max(10, int(math.sqrt((x - self.current_x) ** 2 + (y - self.current_y) ** 2) / 10)),
        )

        for px, py in points:
            await page.mouse.move(px, py)
            delay = random.uniform(0.005, 0.015) * self.preset.mouse_speed
            await asyncio.sleep(delay)

        # Overshoot simulation
        if random.random() < self.preset.mouse_overshoot_chance:
            overshoot = self.preset.mouse_overshoot_distance
            ox = x + random.gauss(0, overshoot)
            oy = y + random.gauss(0, overshoot)
            await page.mouse.move(ox, oy)
            await asyncio.sleep(random.uniform(0.05, 0.15))
            await page.mouse.move(x, y)

        self.current_x = x
        self.current_y = y

    async def click_at(self, page, x: float, y: float, button: str = "left", clicks: int = 1):
        """Click at coordinates with human-like movement."""
        await self.move_to(page, x, y)
        await asyncio.sleep(random.uniform(0.05, 0.15))
        await page.mouse.click(x, y, button=button, click_count=clicks)


class HumanKeyboard:
    """Human-like keyboard input with realistic timing."""

    # Adjacent key map for mistype simulation
    ADJACENT_KEYS = {
        'a': 'sq', 'b': 'vn', 'c': 'xv', 'd': 'sf', 'e': 'wr',
        'f': 'dg', 'g': 'fh', 'h': 'gj', 'i': 'uo', 'j': 'hk',
        'k': 'jl', 'l': 'k;', 'm': 'n,', 'n': 'bm', 'o': 'ip',
        'p': 'o[', 'q': 'w', 'r': 'et', 's': 'ad', 't': 'ry',
        'u': 'yi', 'v': 'cb', 'w': 'qe', 'x': 'zc', 'y': 'tu',
        'z': 'x',
    }

    def __init__(self, preset: HumanPreset):
        self.preset = preset

    async def type_text(self, page, text: str):
        """Type text with human-like timing and occasional mistypes."""
        for char in text:
            # Mistype simulation
            if random.random() < self.preset.type_mistype_chance and char.lower() in self.ADJACENT_KEYS:
                wrong_char = random.choice(self.ADJACENT_KEYS[char.lower()])
                await page.keyboard.type(wrong_char)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.05, 0.15))

            await page.keyboard.type(char)

            # Per-character delay
            delay = max(0.01, random.gauss(
                self.preset.type_delay_mean,
                self.preset.type_delay_std,
            ))
            await asyncio.sleep(delay)

            # Random pauses (thinking)
            if random.random() < self.preset.type_pause_chance:
                pause = random.uniform(*self.preset.type_pause_duration)
                await asyncio.sleep(pause)


class HumanScroll:
    """Human-like scrolling with acceleration and deceleration."""

    def __init__(self, preset: HumanPreset):
        self.preset = preset

    async def scroll(self, page, direction: str = "down", amount: int = 300):
        """Scroll with human-like acceleration pattern."""
        if not self.preset.scroll_smooth:
            delta = -amount if direction in ("down", "right") else amount
            await page.mouse.wheel(
                0 if direction in ("up", "down") else delta,
                delta if direction in ("up", "down") else 0,
            )
            return

        # Smooth scrolling: accelerate -> cruise -> decelerate
        total = abs(amount)
        scrolled = 0
        step = 0
        num_steps = random.randint(5, 12)

        while scrolled < total:
            remaining = total - scrolled
            # Acceleration curve
            progress = scrolled / total
            if progress < 0.3:
                factor = progress / 0.3  # accelerate
            elif progress > 0.7:
                factor = (1.0 - progress) / 0.3  # decelerate
            else:
                factor = 1.0  # cruise

            divisor = max(1, num_steps - step + 1)
            step_size = max(10, int(remaining / divisor * max(factor, 0.1)))
            step_size = min(step_size, remaining)

            delta = -step_size if direction in ("down", "right") else step_size
            if direction in ("up", "down"):
                await page.mouse.wheel(0, delta)
            else:
                await page.mouse.wheel(delta, 0)

            scrolled += step_size
            step += 1
            await asyncio.sleep(random.uniform(0.02, 0.06))

        # Overshoot correction
        if self.preset.scroll_overshoot and random.random() < 0.3:
            correction = random.randint(20, 50)
            delta = correction if direction in ("down", "right") else -correction
            if direction in ("up", "down"):
                await page.mouse.wheel(0, delta)
            else:
                await page.mouse.wheel(delta, 0)
            await asyncio.sleep(random.uniform(0.1, 0.2))


class Humanizer:
    """Unified human-like behavior controller."""

    def __init__(self, preset_name: str = "default"):
        preset = PRESETS.get(preset_name, PRESETS["default"])
        self.mouse = HumanMouse(preset)
        self.keyboard = HumanKeyboard(preset)
        self.scroll = HumanScroll(preset)
        self.preset = preset
