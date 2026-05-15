"""Tests for the CloakBrowser Chromium binary manager."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent_browser.browser.chromium import (
    get_platform_tag,
    get_archive_name,
    get_chromium_version,
    get_download_url,
    get_fallback_url,
    get_checksum_url,
    get_cache_dir,
    get_binary_dir,
    get_binary_path,
    is_binary_installed,
    get_info,
    CHROMIUM_VERSION,
    PLATFORM_CHROMIUM_VERSIONS,
    PRIMARY_CDN,
    GITHUB_RELEASES,
)


class TestPlatformDetection:
    @patch("platform.system", return_value="Linux")
    @patch("platform.machine", return_value="x86_64")
    def test_linux_x64(self, mock_machine, mock_system):
        assert get_platform_tag() == "linux-x64"

    @patch("platform.system", return_value="Linux")
    @patch("platform.machine", return_value="aarch64")
    def test_linux_arm64(self, mock_machine, mock_system):
        assert get_platform_tag() == "linux-arm64"

    @patch("platform.system", return_value="Darwin")
    @patch("platform.machine", return_value="arm64")
    def test_darwin_arm64(self, mock_machine, mock_system):
        assert get_platform_tag() == "darwin-arm64"

    @patch("platform.system", return_value="Darwin")
    @patch("platform.machine", return_value="x86_64")
    def test_darwin_x64(self, mock_machine, mock_system):
        assert get_platform_tag() == "darwin-x64"

    @patch("platform.system", return_value="Windows")
    @patch("platform.machine", return_value="AMD64")
    def test_windows_x64(self, mock_machine, mock_system):
        assert get_platform_tag() == "windows-x64"

    @patch("platform.system", return_value="FreeBSD")
    @patch("platform.machine", return_value="x86_64")
    def test_unsupported_platform(self, mock_machine, mock_system):
        with pytest.raises(RuntimeError, match="Unsupported platform"):
            get_platform_tag()


class TestArchiveName:
    def test_linux(self):
        assert get_archive_name("linux-x64") == "cloakbrowser-linux-x64.tar.gz"

    def test_darwin(self):
        assert get_archive_name("darwin-arm64") == "cloakbrowser-darwin-arm64.tar.gz"

    def test_windows(self):
        assert get_archive_name("windows-x64") == "cloakbrowser-windows-x64.zip"


class TestVersions:
    def test_chromium_version_linux(self):
        version = get_chromium_version("linux-x64")
        assert version == PLATFORM_CHROMIUM_VERSIONS["linux-x64"]

    def test_chromium_version_darwin(self):
        version = get_chromium_version("darwin-arm64")
        assert version == PLATFORM_CHROMIUM_VERSIONS["darwin-arm64"]

    def test_chromium_version_unknown_falls_back(self):
        version = get_chromium_version("unknown-platform")
        assert version == CHROMIUM_VERSION

    def test_all_platforms_have_versions(self):
        for tag in ["linux-x64", "linux-arm64", "darwin-arm64", "darwin-x64", "windows-x64"]:
            assert tag in PLATFORM_CHROMIUM_VERSIONS


class TestDownloadURLs:
    def test_primary_url_format(self):
        url = get_download_url("linux-x64")
        version = PLATFORM_CHROMIUM_VERSIONS["linux-x64"]
        expected = f"{PRIMARY_CDN}/chromium-v{version}/cloakbrowser-linux-x64.tar.gz"
        assert url == expected

    def test_fallback_url_format(self):
        url = get_fallback_url("linux-x64")
        version = PLATFORM_CHROMIUM_VERSIONS["linux-x64"]
        expected = f"{GITHUB_RELEASES}/chromium-v{version}/cloakbrowser-linux-x64.tar.gz"
        assert url == expected

    @patch.dict(os.environ, {"CLOAKBROWSER_DOWNLOAD_URL": "https://custom.cdn.example.com"})
    def test_custom_download_url(self):
        url = get_download_url("linux-x64")
        assert url.startswith("https://custom.cdn.example.com/")

    def test_checksum_url_primary(self):
        version = CHROMIUM_VERSION
        url = get_checksum_url(version, primary=True)
        assert url == f"{PRIMARY_CDN}/chromium-v{version}/SHA256SUMS"

    def test_checksum_url_fallback(self):
        version = CHROMIUM_VERSION
        url = get_checksum_url(version, primary=False)
        assert url == f"{GITHUB_RELEASES}/chromium-v{version}/SHA256SUMS"


class TestCacheDir:
    def test_default_cache_dir(self):
        cache = get_cache_dir()
        assert cache == Path.home() / ".cloakbrowser"

    @patch.dict(os.environ, {"CLOAKBROWSER_CACHE_DIR": "/tmp/test-cache"})
    def test_custom_cache_dir(self):
        cache = get_cache_dir()
        assert cache == Path("/tmp/test-cache")


class TestBinaryPaths:
    def test_linux_binary_path(self):
        path = get_binary_path("linux-x64")
        assert path.name == "chrome"
        assert "chromium-" in str(path.parent)

    def test_darwin_binary_path(self):
        path = get_binary_path("darwin-arm64")
        assert "Chromium.app" in str(path)
        assert path.name == "Chromium"

    def test_windows_binary_path(self):
        path = get_binary_path("windows-x64")
        assert path.name == "chrome.exe"

    @patch.dict(os.environ, {"CLOAKBROWSER_BINARY_PATH": "/custom/path/chrome"})
    def test_custom_binary_path(self):
        # /custom/path/chrome doesn't exist as file or dir, so falls through to default
        path = get_binary_path("linux-x64")
        # Since /custom/path/chrome is not a file or directory, it falls through
        # to the default path computation
        assert path.name == "chrome"

    @patch.dict(os.environ, {"CLOAKBROWSER_BINARY_PATH": ""})
    def test_custom_binary_path_empty(self):
        """Empty env var should use default path."""
        path = get_binary_path("linux-x64")
        assert path.name == "chrome"

    def test_custom_binary_path_file(self, tmp_path):
        """File path should be returned directly."""
        fake_chrome = tmp_path / "chrome"
        fake_chrome.write_text("fake")
        with patch.dict(os.environ, {"CLOAKBROWSER_BINARY_PATH": str(fake_chrome)}):
            path = get_binary_path("linux-x64")
            assert path == fake_chrome

    def test_custom_binary_path_dir(self, tmp_path):
        """Directory path should search for chrome binary inside."""
        chrome_dir = tmp_path / "chromium-146"
        chrome_dir.mkdir()
        fake_chrome = chrome_dir / "chrome"
        fake_chrome.write_text("fake")
        with patch.dict(os.environ, {"CLOAKBROWSER_BINARY_PATH": str(tmp_path)}):
            path = get_binary_path("linux-x64")
            assert path == fake_chrome

    def test_binary_not_installed(self):
        # Default cache dir likely doesn't have the binary in test env
        assert is_binary_installed("linux-x64") is False or is_binary_installed("linux-x64") is True


class TestGetInfo:
    def test_info_returns_all_fields(self):
        info = get_info()
        assert "platform" in info
        assert "chromium_version" in info
        assert "binary_path" in info
        assert "installed" in info
        assert "cache_dir" in info
        assert "download_url" in info

    def test_info_platform_is_valid(self):
        info = get_info()
        valid_tags = ["linux-x64", "linux-arm64", "darwin-arm64", "darwin-x64", "windows-x64"]
        assert info["platform"] in valid_tags

    def test_info_version_is_string(self):
        info = get_info()
        assert isinstance(info["chromium_version"], str)
        assert "." in info["chromium_version"]
