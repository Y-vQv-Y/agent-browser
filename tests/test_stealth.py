"""Tests for the stealth browser launcher."""

import pytest

from agent_browser.browser.stealth import (
    FingerprintProfile,
    StealthLauncher,
    STEALTH_ARGS,
    IGNORE_DEFAULT_ARGS,
)


class TestFingerprintProfile:
    def test_from_seed_deterministic(self):
        """Same seed should produce same fingerprint."""
        fp1 = FingerprintProfile.from_seed("test_seed_123")
        fp2 = FingerprintProfile.from_seed("test_seed_123")
        assert fp1.hardware_concurrency == fp2.hardware_concurrency
        assert fp1.device_memory == fp2.device_memory
        assert fp1.screen_width == fp2.screen_width
        assert fp1.screen_height == fp2.screen_height
        assert fp1.timezone == fp2.timezone
        assert fp1.locale == fp2.locale
        assert fp1.platform == fp2.platform

    def test_different_seeds_different_fingerprints(self):
        """Different seeds should typically produce different fingerprints."""
        fp1 = FingerprintProfile.from_seed("seed_a")
        fp2 = FingerprintProfile.from_seed("seed_b")
        # At least some fields should differ (probabilistic, but very likely)
        fields = ["hardware_concurrency", "device_memory", "screen_width", "timezone"]
        diffs = sum(1 for f in fields if getattr(fp1, f) != getattr(fp2, f))
        assert diffs > 0, "Different seeds should produce different fingerprints"

    def test_valid_hardware_concurrency(self):
        fp = FingerprintProfile.from_seed("test")
        assert fp.hardware_concurrency in [2, 4, 8, 12, 16]

    def test_valid_device_memory(self):
        fp = FingerprintProfile.from_seed("test")
        assert fp.device_memory in [4, 8, 16, 32]

    def test_valid_screen_resolution(self):
        fp = FingerprintProfile.from_seed("test")
        assert fp.screen_width > 0
        assert fp.screen_height > 0
        assert fp.avail_height < fp.screen_height

    def test_platform_override(self):
        fp = FingerprintProfile.from_seed("test", platform="MacIntel")
        assert fp.platform == "MacIntel"


class TestStealthArgs:
    def test_stealth_args_not_empty(self):
        assert len(STEALTH_ARGS) > 0

    def test_automation_disabled(self):
        assert "--disable-blink-features=AutomationControlled" in STEALTH_ARGS

    def test_ignore_default_args(self):
        assert "--enable-automation" in IGNORE_DEFAULT_ARGS


class TestStealthLauncher:
    def test_init_defaults(self):
        launcher = StealthLauncher()
        assert launcher.headless is True
        assert launcher.humanize is True
        assert launcher.viewport_width == 1920

    def test_init_custom(self):
        launcher = StealthLauncher(
            headless=False,
            proxy="http://proxy:8080",
            fingerprint_seed="custom_seed",
            viewport_width=1366,
            viewport_height=768,
        )
        assert launcher.headless is False
        assert launcher.proxy == "http://proxy:8080"
        assert launcher.fingerprint_seed == "custom_seed"
        assert launcher.viewport_width == 1366

    def test_launch_args(self):
        launcher = StealthLauncher(fingerprint_seed="test")
        args = launcher.get_launch_args()
        assert isinstance(args, list)
        assert any("--disable-blink-features" in a for a in args)
        assert any("--window-size=" in a for a in args)

    def test_stealth_scripts(self):
        launcher = StealthLauncher(fingerprint_seed="test")
        scripts = launcher.get_stealth_scripts()
        assert len(scripts) > 0

        # Check key stealth properties
        combined = "\n".join(scripts)
        assert "webdriver" in combined
        assert "platform" in combined
        assert "hardwareConcurrency" in combined
        assert "plugins" in combined
        assert "chrome" in combined

    def test_stealth_scripts_use_fingerprint(self):
        launcher = StealthLauncher(fingerprint_seed="test")
        fp = launcher.fingerprint
        scripts = launcher.get_stealth_scripts()
        combined = "\n".join(scripts)

        assert fp.platform in combined
        assert str(fp.hardware_concurrency) in combined
        assert str(fp.device_memory) in combined
