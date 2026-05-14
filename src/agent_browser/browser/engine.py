"""
Browser Engine - Core browser control layer.
Combines browser-harness CDP primitives with CloakBrowser stealth.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from agent_browser.config import BrowserConfig
from agent_browser.browser.stealth import StealthLauncher
from agent_browser.browser.humanize import Humanizer

logger = logging.getLogger(__name__)


class BrowserEngine:
    """
    High-level browser control engine.
    Wraps Playwright with stealth and humanization.
    """

    def __init__(self, config: Optional[BrowserConfig] = None, profile_name: Optional[str] = None):
        self.config = config or BrowserConfig()
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._humanizer: Optional[Humanizer] = None
        self._stealth: Optional[StealthLauncher] = None
        self._launched = False
        self._profile_name = profile_name
        self._session_profile = None

    async def launch(self):
        """Launch the stealth browser."""
        if self._launched:
            return

        # Set up session profile for persistent login
        user_data_dir = self.config.user_data_dir
        if self._profile_name:
            from agent_browser.browser.session import SessionManager
            data_dir = Path(self.config.screenshot_dir).parent  # Use config's data dir
            manager = SessionManager(data_dir.parent if "screenshots" in str(data_dir) else data_dir)
            self._session_profile = manager.get_or_create(self._profile_name)
            user_data_dir = self._session_profile.user_data_dir
            logger.info("Using session profile: %s (%s)", self._profile_name, user_data_dir)

        self._stealth = StealthLauncher(
            headless=self.config.headless,
            proxy=self.config.proxy,
            fingerprint_seed=self.config.fingerprint_seed,
            viewport_width=self.config.viewport_width,
            viewport_height=self.config.viewport_height,
            user_data_dir=user_data_dir,
            humanize=self.config.humanize,
            human_preset=self.config.human_preset,
        )

        self._pw, self._browser, self._context = await self._stealth.launch()

        # Get or create a page
        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()

        # Initialize humanizer
        if self.config.humanize:
            self._humanizer = Humanizer(self.config.human_preset)

        # Create screenshot directory
        Path(self.config.screenshot_dir).mkdir(parents=True, exist_ok=True)

        self._launched = True
        logger.info("Browser launched (headless=%s, stealth=%s, humanize=%s)",
                     self.config.headless, self.config.stealth, self.config.humanize)

    async def close(self):
        """Close the browser and cleanup."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._launched = False
        logger.info("Browser closed")

    @property
    def page(self):
        """Get the current page."""
        if not self._page:
            raise RuntimeError("Browser not launched. Call launch() first.")
        return self._page

    # --- Navigation ---

    async def navigate(self, url: str, wait_until: str = "domcontentloaded"):
        """Navigate to a URL."""
        try:
            await self.page.goto(url, wait_until=wait_until, timeout=self.config.timeout)
            logger.info("Navigated to: %s", url)
        except Exception as e:
            logger.warning("Navigation to %s had issues: %s", url, e)
            # Still might have partially loaded

    async def wait_for_load(self, timeout: int = 10):
        """Wait for page to fully load."""
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout * 1000)
        except Exception:
            logger.debug("Network idle timeout, page may still be usable")

    async def wait_for_element(self, selector: str, timeout: int = 10, visible: bool = False):
        """Wait for an element to appear."""
        state = "visible" if visible else "attached"
        await self.page.wait_for_selector(selector, state=state, timeout=timeout * 1000)

    # --- Input ---

    async def click(self, x: int, y: int, button: str = "left", clicks: int = 1):
        """Click at coordinates with optional humanization."""
        if self._humanizer:
            await self._humanizer.mouse.click_at(self.page, x, y, button=button, clicks=clicks)
        else:
            await self.page.mouse.click(x, y, button=button, click_count=clicks)
        logger.debug("Clicked at (%d, %d)", x, y)

    async def type_text(self, text: str):
        """Type text with optional humanization."""
        if self._humanizer:
            await self._humanizer.keyboard.type_text(self.page, text)
        else:
            await self.page.keyboard.type(text)
        logger.debug("Typed: %s", text[:50])

    async def fill_input(self, selector: str, text: str, clear_first: bool = True):
        """Fill an input field (framework-aware)."""
        element = await self.page.wait_for_selector(selector, timeout=5000)
        if not element:
            raise ValueError(f"Element not found: {selector}")

        await element.click()
        await asyncio.sleep(0.1)

        if clear_first:
            await self.page.keyboard.press("Control+a")
            await asyncio.sleep(0.05)
            await self.page.keyboard.press("Delete")
            await asyncio.sleep(0.05)

        if self._humanizer:
            await self._humanizer.keyboard.type_text(self.page, text)
        else:
            await element.type(text)

        # Dispatch input/change events for React/Vue
        await self.page.evaluate(f"""
            const el = document.querySelector('{selector}');
            if (el) {{
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
        """)
        logger.debug("Filled input %s with: %s", selector, text[:50])

    async def press_key(self, key: str, modifiers: Optional[list[str]] = None):
        """Press a keyboard key with optional modifiers."""
        if modifiers:
            key_combo = "+".join(modifiers + [key])
            await self.page.keyboard.press(key_combo)
        else:
            await self.page.keyboard.press(key)

    async def scroll(self, direction: str = "down", amount: int = 300):
        """Scroll the page."""
        if self._humanizer:
            await self._humanizer.scroll.scroll(self.page, direction, amount)
        else:
            dy = -amount if direction == "down" else amount if direction == "up" else 0
            dx = -amount if direction == "right" else amount if direction == "left" else 0
            await self.page.mouse.wheel(dx, dy)

    # --- Information ---

    async def screenshot(self, full_page: bool = False, path: Optional[str] = None) -> str:
        """Take a screenshot and return base64-encoded PNG."""
        screenshot_bytes = await self.page.screenshot(full_page=full_page)

        if path:
            Path(path).write_bytes(screenshot_bytes)
        else:
            # Auto-save with timestamp
            ts = int(time.time())
            save_path = Path(self.config.screenshot_dir) / f"screenshot_{ts}.png"
            save_path.write_bytes(screenshot_bytes)

        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def get_page_info(self) -> dict:
        """Get current page information."""
        url = self.page.url
        title = await self.page.title()

        # Get simplified HTML structure
        html_summary = await self.page.evaluate("""
            () => {
                const getVisibleText = (el, depth = 0) => {
                    if (depth > 3) return '';
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') return '';

                    let text = '';
                    for (const child of el.childNodes) {
                        if (child.nodeType === 3) {
                            text += child.textContent.trim() + ' ';
                        } else if (child.nodeType === 1) {
                            const tag = child.tagName.toLowerCase();
                            if (['script', 'style', 'noscript'].includes(tag)) continue;
                            text += getVisibleText(child, depth + 1);
                        }
                    }
                    return text;
                };

                const text = getVisibleText(document.body).substring(0, 5000);

                const links = Array.from(document.querySelectorAll('a[href]')).slice(0, 20).map(a => ({
                    text: a.textContent.trim().substring(0, 50),
                    href: a.href
                }));

                const inputs = Array.from(document.querySelectorAll('input, textarea, select, button')).slice(0, 20).map(el => ({
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    placeholder: el.placeholder || '',
                    value: el.type === 'password' ? '***' : (el.value || '').substring(0, 50),
                    text: el.textContent?.trim().substring(0, 50) || '',
                }));

                return { text, links, inputs };
            }
        """)

        return {
            "url": url,
            "title": title,
            "content": html_summary.get("text", ""),
            "links": html_summary.get("links", []),
            "inputs": html_summary.get("inputs", []),
        }

    async def run_javascript(self, code: str) -> Any:
        """Execute JavaScript in the page."""
        return await self.page.evaluate(code)

    async def extract_data(self, description: str, selectors: Optional[dict] = None) -> dict:
        """Extract data from the page using CSS selectors."""
        result = {}
        if selectors:
            for field_name, selector in selectors.items():
                try:
                    elements = await self.page.query_selector_all(selector)
                    values = []
                    for el in elements:
                        text = await el.text_content()
                        values.append(text.strip() if text else "")
                    result[field_name] = values if len(values) > 1 else (values[0] if values else "")
                except Exception as e:
                    result[field_name] = f"Error: {e}"
        else:
            # Use page info as fallback
            info = await self.get_page_info()
            result = {"description": description, "page_content": info}

        return result

    # --- Tab Management ---

    async def new_tab(self, url: Optional[str] = None):
        """Open a new tab."""
        self._page = await self._context.new_page()
        if url:
            await self.navigate(url)
        return self._page

    async def list_tabs(self) -> list[dict]:
        """List all open tabs."""
        tabs = []
        for i, page in enumerate(self._context.pages):
            tabs.append({
                "index": i,
                "url": page.url,
                "title": await page.title(),
                "active": page == self._page,
            })
        return tabs

    async def switch_tab(self, index: int):
        """Switch to a tab by index."""
        pages = self._context.pages
        if 0 <= index < len(pages):
            self._page = pages[index]
            await self._page.bring_to_front()
