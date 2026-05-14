"""
Stealth Launcher - Internalized from CloakBrowser.
Configures anti-detection browser launch with fingerprint spoofing.
"""

from __future__ import annotations

import hashlib
import logging
import random
import struct
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class FingerprintProfile:
    """A deterministic fingerprint profile generated from a seed."""
    seed: str
    platform: str = "Win32"
    hardware_concurrency: int = 8
    device_memory: int = 8
    screen_width: int = 1920
    screen_height: int = 1080
    avail_width: int = 1920
    avail_height: int = 1032
    color_depth: int = 24
    timezone: str = "America/New_York"
    locale: str = "en-US"
    webrtc_ip: Optional[str] = None
    user_agent: Optional[str] = None

    @classmethod
    def from_seed(cls, seed: str, platform: Optional[str] = None) -> "FingerprintProfile":
        """Generate a consistent fingerprint from a seed string."""
        h = hashlib.sha256(seed.encode()).digest()

        # Deterministic random from seed
        rng = random.Random(seed)

        hw_options = [2, 4, 8, 12, 16]
        mem_options = [4, 8, 16, 32]
        screen_options = [
            (1920, 1080), (2560, 1440), (1366, 768),
            (1440, 900), (1536, 864), (1680, 1050),
        ]
        tz_options = [
            "America/New_York", "America/Chicago", "America/Denver",
            "America/Los_Angeles", "Europe/London", "Europe/Berlin",
            "Asia/Tokyo", "Asia/Shanghai",
        ]
        locale_map = {
            "America/New_York": "en-US", "America/Chicago": "en-US",
            "America/Denver": "en-US", "America/Los_Angeles": "en-US",
            "Europe/London": "en-GB", "Europe/Berlin": "de-DE",
            "Asia/Tokyo": "ja-JP", "Asia/Shanghai": "zh-CN",
        }

        sw, sh = rng.choice(screen_options)
        tz = rng.choice(tz_options)

        return cls(
            seed=seed,
            platform=platform or rng.choice(["Win32", "MacIntel", "Linux x86_64"]),
            hardware_concurrency=rng.choice(hw_options),
            device_memory=rng.choice(mem_options),
            screen_width=sw,
            screen_height=sh,
            avail_width=sw,
            avail_height=sh - rng.randint(40, 60),
            color_depth=24,
            timezone=tz,
            locale=locale_map.get(tz, "en-US"),
        )


# Default stealth arguments applied to every launch
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-site-isolation-trials",
    "--disable-web-security",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-infobars",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-ipc-flooding-protection",
    "--password-store=basic",
    "--use-mock-keychain",
    "--disable-hang-monitor",
    "--disable-prompt-on-repost",
    "--disable-domain-reliability",
    "--disable-component-update",
    "--metrics-recording-only",
    "--no-service-autorun",
]

# Args that Playwright adds but should be removed for stealth
IGNORE_DEFAULT_ARGS = [
    "--enable-automation",
    "--enable-blink-features=IdleDetection",
]


class StealthLauncher:
    """
    Configures and launches stealth browsers using Playwright
    with CloakBrowser-inspired anti-detection measures.
    """

    def __init__(
        self,
        headless: bool = True,
        proxy: Optional[str] = None,
        fingerprint_seed: Optional[str] = None,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        user_data_dir: Optional[str] = None,
        humanize: bool = True,
        human_preset: str = "default",
    ):
        self.headless = headless
        self.proxy = proxy
        self.fingerprint_seed = fingerprint_seed or str(random.randint(100000, 999999))
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.user_data_dir = user_data_dir
        self.humanize = humanize
        self.human_preset = human_preset
        self.fingerprint = FingerprintProfile.from_seed(self.fingerprint_seed)

    def get_launch_args(self) -> list[str]:
        """Get browser launch arguments for stealth mode."""
        args = list(STEALTH_ARGS)

        # Fingerprint args
        args.append(f"--lang={self.fingerprint.locale}")

        # Window size
        args.append(f"--window-size={self.viewport_width},{self.viewport_height}")

        return args

    def get_stealth_scripts(self) -> list[str]:
        """Get JavaScript scripts to inject for stealth."""
        fp = self.fingerprint
        return [
            # Override navigator.webdriver
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});",

            # Override navigator.platform
            f"Object.defineProperty(navigator, 'platform', {{get: () => '{fp.platform}'}});",

            # Override navigator.hardwareConcurrency
            f"Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {fp.hardware_concurrency}}});",

            # Override navigator.deviceMemory
            f"Object.defineProperty(navigator, 'deviceMemory', {{get: () => {fp.device_memory}}});",

            # Override screen properties
            f"""Object.defineProperty(screen, 'width', {{get: () => {fp.screen_width}}});
Object.defineProperty(screen, 'height', {{get: () => {fp.screen_height}}});
Object.defineProperty(screen, 'availWidth', {{get: () => {fp.avail_width}}});
Object.defineProperty(screen, 'availHeight', {{get: () => {fp.avail_height}}});
Object.defineProperty(screen, 'colorDepth', {{get: () => {fp.color_depth}}});""",

            # Override navigator.languages
            f"Object.defineProperty(navigator, 'languages', {{get: () => ['{fp.locale}', '{fp.locale.split('-')[0]}']}});",

            # Fix chrome object
            """window.chrome = {
    runtime: {
        onConnect: { addListener: function() {}, removeListener: function() {} },
        onMessage: { addListener: function() {}, removeListener: function() {} },
        sendMessage: function() {},
        connect: function() { return { onDisconnect: { addListener: function() {} } }; }
    },
    loadTimes: function() { return {}; },
    csi: function() { return {}; }
};""",

            # Fix navigator.plugins
            """Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format'},
            {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: ''},
            {name: 'Native Client', filename: 'internal-nacl-plugin', description: ''},
            {name: 'Chromium PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format'},
            {name: 'Chromium PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: ''},
        ];
        plugins.length = 5;
        return plugins;
    }
});""",

            # Fix permissions API
            """const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);""",

            # Fix WebGL vendor/renderer
            """const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return 'Intel Inc.';
    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
    return getParameter.call(this, parameter);
};""",
        ]

    def _resolve_executable(self) -> Optional[str]:
        """
        Resolve the browser executable path.
        Priority: CloakBrowser binary > Playwright bundled > system Chrome.
        """
        from agent_browser.browser.chromium import is_binary_installed, get_binary_path

        # 1. CloakBrowser patched Chromium (best anti-detection)
        if is_binary_installed():
            path = str(get_binary_path())
            logger.info("Using CloakBrowser Chromium: %s", path)
            return path

        # 2. Try to download CloakBrowser binary
        try:
            from agent_browser.browser.chromium import ensure_binary
            path = str(ensure_binary())
            logger.info("Downloaded CloakBrowser Chromium: %s", path)
            return path
        except Exception as e:
            logger.warning("CloakBrowser binary unavailable (%s), falling back to Playwright", e)

        # 3. Fall back to Playwright's bundled Chromium
        return None

    async def launch(self):
        """Launch a stealth browser using CloakBrowser's Chromium or Playwright's."""
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()

        executable_path = self._resolve_executable()

        launch_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "args": self.get_launch_args(),
            "ignore_default_args": IGNORE_DEFAULT_ARGS,
        }

        # Use CloakBrowser's patched Chromium binary if available
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
            # CloakBrowser binary supports native fingerprint flags
            fp = self.fingerprint
            launch_kwargs["args"].extend([
                f"--fingerprint={self.fingerprint_seed}",
                f"--fingerprint-timezone={fp.timezone}",
                f"--fingerprint-locale={fp.locale}",
            ])
            if fp.webrtc_ip:
                launch_kwargs["args"].append(f"--fingerprint-webrtc-ip={fp.webrtc_ip}")

        if self.proxy:
            launch_kwargs["proxy"] = {"server": self.proxy}

        if self.user_data_dir:
            # Persistent context (preserves login sessions)
            context = await pw.chromium.launch_persistent_context(
                self.user_data_dir,
                viewport={"width": self.viewport_width, "height": self.viewport_height},
                locale=self.fingerprint.locale,
                timezone_id=self.fingerprint.timezone,
                **launch_kwargs,
            )
            browser = None
        else:
            browser = await pw.chromium.launch(**launch_kwargs)
            context = await browser.new_context(
                viewport={"width": self.viewport_width, "height": self.viewport_height},
                locale=self.fingerprint.locale,
                timezone_id=self.fingerprint.timezone,
                user_agent=self.fingerprint.user_agent,
            )

        # Inject stealth scripts (still useful even with CloakBrowser binary)
        for script in self.get_stealth_scripts():
            await context.add_init_script(script)

        return pw, browser, context
