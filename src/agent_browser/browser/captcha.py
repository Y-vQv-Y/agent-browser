"""
CAPTCHA Handler - Detection and auto-solving of human verification challenges.
Uses CloakBrowser's stealth + behavioral approach.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from agent_browser.browser.engine import BrowserEngine

logger = logging.getLogger(__name__)


@dataclass
class CaptchaResult:
    """Result of a CAPTCHA solving attempt."""
    detected: bool = False
    captcha_type: Optional[str] = None  # recaptcha, turnstile, hcaptcha, slider, image
    solved: bool = False
    message: str = ""
    attempts: int = 0


class CaptchaHandler:
    """
    CAPTCHA detection and solving.

    Strategy:
    1. CloakBrowser's stealth makes most CAPTCHAs not trigger at all
    2. For CAPTCHAs that do appear, use behavioral solving:
       - reCAPTCHA v2: Click the checkbox with human-like behavior
       - Cloudflare Turnstile: Wait for auto-pass (stealth browser)
       - Slider CAPTCHAs: Drag with Bezier curve movement
       - Image CAPTCHAs: Fall back to user input
    """

    def __init__(self, browser: "BrowserEngine"):
        self.browser = browser

    async def detect(self) -> CaptchaResult:
        """Detect if there's a CAPTCHA on the current page."""
        page = self.browser.page
        result = CaptchaResult()

        checks = [
            self._check_recaptcha,
            self._check_turnstile,
            self._check_hcaptcha,
            self._check_slider,
            self._check_generic,
        ]

        for check in checks:
            try:
                detected, captcha_type = await check(page)
                if detected:
                    result.detected = True
                    result.captcha_type = captcha_type
                    result.message = f"Detected {captcha_type} CAPTCHA"
                    logger.info("CAPTCHA detected: %s", captcha_type)
                    return result
            except Exception as e:
                logger.debug("CAPTCHA check error: %s", e)

        result.message = "No CAPTCHA detected"
        return result

    async def detect_and_solve(self, strategy: str = "auto") -> CaptchaResult:
        """Detect and attempt to solve any CAPTCHA."""
        result = await self.detect()
        if not result.detected:
            return result

        max_attempts = 3
        for attempt in range(max_attempts):
            result.attempts = attempt + 1
            logger.info("CAPTCHA solve attempt %d/%d (type=%s)",
                        attempt + 1, max_attempts, result.captcha_type)

            try:
                if result.captcha_type == "recaptcha":
                    solved = await self._solve_recaptcha()
                elif result.captcha_type == "turnstile":
                    solved = await self._solve_turnstile()
                elif result.captcha_type == "hcaptcha":
                    solved = await self._solve_hcaptcha()
                elif result.captcha_type == "slider":
                    solved = await self._solve_slider()
                else:
                    solved = await self._solve_generic()

                if solved:
                    result.solved = True
                    result.message = f"Successfully solved {result.captcha_type} CAPTCHA"
                    logger.info("CAPTCHA solved on attempt %d", attempt + 1)
                    return result

            except Exception as e:
                logger.warning("CAPTCHA solve attempt %d failed: %s", attempt + 1, e)

            await asyncio.sleep(random.uniform(1, 3))

        result.message = f"Failed to solve {result.captcha_type} after {max_attempts} attempts"
        return result

    # --- Detection Methods ---

    async def _check_recaptcha(self, page) -> tuple[bool, str]:
        """Check for reCAPTCHA."""
        found = await page.evaluate("""
            () => {
                return !!(
                    document.querySelector('iframe[src*="recaptcha"]') ||
                    document.querySelector('.g-recaptcha') ||
                    document.querySelector('#recaptcha') ||
                    document.querySelector('[data-sitekey]')
                );
            }
        """)
        return found, "recaptcha"

    async def _check_turnstile(self, page) -> tuple[bool, str]:
        """Check for Cloudflare Turnstile."""
        found = await page.evaluate("""
            () => {
                return !!(
                    document.querySelector('iframe[src*="challenges.cloudflare.com"]') ||
                    document.querySelector('.cf-turnstile') ||
                    document.querySelector('[data-turnstile-callback]')
                );
            }
        """)
        return found, "turnstile"

    async def _check_hcaptcha(self, page) -> tuple[bool, str]:
        """Check for hCaptcha."""
        found = await page.evaluate("""
            () => {
                return !!(
                    document.querySelector('iframe[src*="hcaptcha"]') ||
                    document.querySelector('.h-captcha') ||
                    document.querySelector('[data-hcaptcha-sitekey]')
                );
            }
        """)
        return found, "hcaptcha"

    async def _check_slider(self, page) -> tuple[bool, str]:
        """Check for slider CAPTCHAs."""
        found = await page.evaluate("""
            () => {
                const sliderSelectors = [
                    '.slider-captcha', '.slide-verify', '.geetest',
                    '[class*="slider"]', '[class*="slide-"]',
                    '.nc-container', '#nc_1_n1z',
                ];
                return sliderSelectors.some(sel => document.querySelector(sel));
            }
        """)
        return found, "slider"

    async def _check_generic(self, page) -> tuple[bool, str]:
        """Check for generic verification challenges."""
        found = await page.evaluate("""
            () => {
                const text = document.body?.innerText?.toLowerCase() || '';
                const keywords = [
                    'verify you are human', 'prove you are not a robot',
                    'security check', 'bot detection', 'verification required',
                    '人机验证', '安全验证', '请完成验证', '滑动验证',
                ];
                return keywords.some(kw => text.includes(kw));
            }
        """)
        return found, "generic"

    # --- Solving Methods ---

    async def _solve_recaptcha(self) -> bool:
        """Solve reCAPTCHA by clicking the checkbox with human behavior."""
        page = self.browser.page

        # Find the reCAPTCHA iframe
        frame = None
        for f in page.frames:
            if "recaptcha" in (f.url or ""):
                frame = f
                break

        if not frame:
            return False

        # Click the checkbox
        checkbox = await frame.query_selector("#recaptcha-anchor")
        if checkbox:
            box = await checkbox.bounding_box()
            if box:
                x = box["x"] + box["width"] / 2
                y = box["y"] + box["height"] / 2
                await self.browser.click(int(x), int(y))
                await asyncio.sleep(random.uniform(2, 4))

                # Check if solved (checkbox turns green)
                is_checked = await frame.evaluate("""
                    () => {
                        const anchor = document.querySelector('#recaptcha-anchor');
                        return anchor?.getAttribute('aria-checked') === 'true';
                    }
                """)
                return is_checked

        return False

    async def _solve_turnstile(self) -> bool:
        """Wait for Cloudflare Turnstile to auto-pass (stealth browser advantage)."""
        page = self.browser.page

        # Turnstile usually auto-passes with a stealth browser
        for _ in range(20):
            success = await page.evaluate("""
                () => {
                    const input = document.querySelector('[name="cf-turnstile-response"]');
                    return !!(input && input.value);
                }
            """)
            if success:
                return True
            await asyncio.sleep(0.5)

        # Try clicking the Turnstile widget
        turnstile = await page.query_selector('.cf-turnstile iframe')
        if turnstile:
            box = await turnstile.bounding_box()
            if box:
                await self.browser.click(
                    int(box["x"] + box["width"] / 2),
                    int(box["y"] + box["height"] / 2),
                )
                await asyncio.sleep(3)

                success = await page.evaluate("""
                    () => {
                        const input = document.querySelector('[name="cf-turnstile-response"]');
                        return !!(input && input.value);
                    }
                """)
                return success

        return False

    async def _solve_hcaptcha(self) -> bool:
        """Attempt to solve hCaptcha checkbox."""
        page = self.browser.page

        frame = None
        for f in page.frames:
            if "hcaptcha" in (f.url or ""):
                frame = f
                break

        if not frame:
            return False

        checkbox = await frame.query_selector("#checkbox")
        if checkbox:
            box = await checkbox.bounding_box()
            if box:
                await self.browser.click(int(box["x"] + box["width"] / 2),
                                         int(box["y"] + box["height"] / 2))
                await asyncio.sleep(random.uniform(2, 4))
                return True

        return False

    async def _solve_slider(self) -> bool:
        """Solve slider CAPTCHAs with Bezier curve drag."""
        page = self.browser.page

        # Find slider handle
        slider_selectors = [
            '.slider-handle', '.slide-btn', '.geetest_slider_button',
            '.nc_iconfont', '[class*="slider"] button',
        ]

        handle = None
        for sel in slider_selectors:
            handle = await page.query_selector(sel)
            if handle:
                break

        if not handle:
            return False

        box = await handle.bounding_box()
        if not box:
            return False

        start_x = box["x"] + box["width"] / 2
        start_y = box["y"] + box["height"] / 2

        # Slide distance (usually 200-300px)
        slide_distance = random.randint(200, 300)

        # Human-like drag
        await page.mouse.move(start_x, start_y)
        await asyncio.sleep(random.uniform(0.1, 0.2))
        await page.mouse.down()

        # Move with acceleration/deceleration
        steps = random.randint(15, 25)
        for i in range(steps):
            progress = (i + 1) / steps
            # Ease-out curve
            eased = 1 - (1 - progress) ** 2
            current_x = start_x + slide_distance * eased
            current_y = start_y + random.gauss(0, 1)  # slight vertical wobble
            await page.mouse.move(current_x, current_y)
            await asyncio.sleep(random.uniform(0.01, 0.04))

        await asyncio.sleep(random.uniform(0.05, 0.15))
        await page.mouse.up()
        await asyncio.sleep(1)

        return True

    async def _solve_generic(self) -> bool:
        """Try generic approaches for unknown CAPTCHAs."""
        page = self.browser.page

        # Look for a "verify" or "confirm" button
        buttons = await page.query_selector_all("button, [role='button'], input[type='submit']")
        for btn in buttons:
            text = await btn.text_content()
            if text and any(kw in text.lower() for kw in ["verify", "confirm", "continue", "验证", "确认"]):
                box = await btn.bounding_box()
                if box:
                    await self.browser.click(
                        int(box["x"] + box["width"] / 2),
                        int(box["y"] + box["height"] / 2),
                    )
                    await asyncio.sleep(2)
                    return True

        return False
