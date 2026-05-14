"""
CloakBrowser Binary Manager - Downloads and manages the patched Chromium binary.
Internalized from CloakBrowser's config.py + download.py.

The patched Chromium binary has anti-detection built in at the C++ level,
which is far more effective than JavaScript injection alone.
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# --- Version and platform config (from CloakBrowser config.py) ---

CHROMIUM_VERSION = "146.0.7680.177.3"

PLATFORM_CHROMIUM_VERSIONS = {
    "linux-x64": "146.0.7680.177.3",
    "linux-arm64": "146.0.7680.177.3",
    "darwin-arm64": "145.0.7632.109.2",
    "darwin-x64": "145.0.7632.109.2",
    "windows-x64": "146.0.7680.177.4",
}

PRIMARY_CDN = "https://cloakbrowser.dev"
GITHUB_RELEASES = "https://github.com/CloakHQ/cloakbrowser/releases/download"


def get_platform_tag() -> str:
    """Detect the current platform tag."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        arch = "arm64" if machine in ("aarch64", "arm64") else "x64"
        return f"linux-{arch}"
    elif system == "darwin":
        arch = "arm64" if machine == "arm64" else "x64"
        return f"darwin-{arch}"
    elif system == "windows":
        return "windows-x64"
    else:
        raise RuntimeError(f"Unsupported platform: {system}-{machine}")


def get_archive_name(platform_tag: Optional[str] = None) -> str:
    """Get the archive filename for this platform."""
    tag = platform_tag or get_platform_tag()
    ext = ".zip" if tag.startswith("windows") else ".tar.gz"
    return f"cloakbrowser-{tag}{ext}"


def get_chromium_version(platform_tag: Optional[str] = None) -> str:
    """Get the Chromium version for this platform."""
    tag = platform_tag or get_platform_tag()
    return PLATFORM_CHROMIUM_VERSIONS.get(tag, CHROMIUM_VERSION)


def get_download_url(platform_tag: Optional[str] = None) -> str:
    """Get the primary CDN download URL."""
    tag = platform_tag or get_platform_tag()
    version = get_chromium_version(tag)
    archive = get_archive_name(tag)
    custom_url = os.environ.get("CLOAKBROWSER_DOWNLOAD_URL")
    base = custom_url.rstrip("/") if custom_url else PRIMARY_CDN
    return f"{base}/chromium-v{version}/{archive}"


def get_fallback_url(platform_tag: Optional[str] = None) -> str:
    """Get the GitHub Releases fallback URL."""
    tag = platform_tag or get_platform_tag()
    version = get_chromium_version(tag)
    archive = get_archive_name(tag)
    return f"{GITHUB_RELEASES}/chromium-v{version}/{archive}"


def get_checksum_url(version: str, primary: bool = True) -> str:
    """Get the SHA256SUMS file URL."""
    if primary:
        return f"{PRIMARY_CDN}/chromium-v{version}/SHA256SUMS"
    return f"{GITHUB_RELEASES}/chromium-v{version}/SHA256SUMS"


def get_cache_dir() -> Path:
    """Get the cache directory."""
    custom = os.environ.get("CLOAKBROWSER_CACHE_DIR")
    if custom:
        return Path(custom)
    return Path.home() / ".cloakbrowser"


def get_binary_dir(platform_tag: Optional[str] = None) -> Path:
    """Get the directory where the binary is extracted."""
    tag = platform_tag or get_platform_tag()
    version = get_chromium_version(tag)
    return get_cache_dir() / f"chromium-{version}"


def get_binary_path(platform_tag: Optional[str] = None) -> Path:
    """Get the expected path of the Chromium executable."""
    # Check env override first
    custom = os.environ.get("CLOAKBROWSER_BINARY_PATH")
    if custom:
        return Path(custom)

    tag = platform_tag or get_platform_tag()
    binary_dir = get_binary_dir(tag)

    if tag.startswith("darwin"):
        return binary_dir / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
    elif tag.startswith("windows"):
        return binary_dir / "chrome.exe"
    else:
        return binary_dir / "chrome"


def is_binary_installed(platform_tag: Optional[str] = None) -> bool:
    """Check if the CloakBrowser Chromium binary is installed."""
    path = get_binary_path(platform_tag)
    return path.exists() and path.is_file()


def _verify_checksum(archive_path: Path, platform_tag: Optional[str] = None) -> bool:
    """Verify the SHA-256 checksum of a downloaded archive."""
    tag = platform_tag or get_platform_tag()
    version = get_chromium_version(tag)
    archive_name = get_archive_name(tag)

    # Compute hash
    sha256 = hashlib.sha256()
    with open(archive_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    actual_hash = sha256.hexdigest()

    # Fetch SHA256SUMS
    for primary in [True, False]:
        url = get_checksum_url(version, primary=primary)
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code == 200:
                for line in resp.text.strip().split("\n"):
                    parts = line.split()
                    if len(parts) >= 2:
                        expected_hash = parts[0]
                        filename = parts[1].lstrip("*")
                        if filename == archive_name:
                            if actual_hash == expected_hash:
                                logger.info("Checksum verified: %s", archive_name)
                                return True
                            else:
                                logger.error(
                                    "Checksum mismatch! Expected %s, got %s",
                                    expected_hash, actual_hash,
                                )
                                return False
        except Exception as e:
            logger.debug("Failed to fetch checksums from %s: %s", url, e)

    logger.warning("Could not verify checksum (SHA256SUMS not available)")
    return True  # Skip verification if checksums unavailable


def _extract_archive(archive_path: Path, target_dir: Path, platform_tag: str):
    """Extract the downloaded archive."""
    target_dir.mkdir(parents=True, exist_ok=True)

    if str(archive_path).endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(target_dir)
    else:
        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(target_dir)

    # Flatten single top-level directory (CloakBrowser convention)
    entries = list(target_dir.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        single_dir = entries[0]
        # Don't flatten .app bundles on macOS
        if not single_dir.name.endswith(".app"):
            for item in single_dir.iterdir():
                shutil.move(str(item), str(target_dir / item.name))
            single_dir.rmdir()

    # Set executable permissions
    binary = get_binary_path(platform_tag)
    if binary.exists() and not platform_tag.startswith("windows"):
        binary.chmod(binary.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # macOS: remove quarantine
    if platform_tag.startswith("darwin"):
        try:
            subprocess.run(
                ["xattr", "-cr", str(target_dir)],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass


def download_binary(
    platform_tag: Optional[str] = None,
    force: bool = False,
    skip_checksum: bool = False,
) -> Path:
    """
    Download the CloakBrowser patched Chromium binary.
    Returns the path to the executable.
    """
    tag = platform_tag or get_platform_tag()

    # Check env override
    custom = os.environ.get("CLOAKBROWSER_BINARY_PATH")
    if custom:
        path = Path(custom)
        if not path.exists():
            raise FileNotFoundError(f"Custom binary not found: {custom}")
        logger.info("Using custom binary: %s", path)
        return path

    binary_path = get_binary_path(tag)

    if binary_path.exists() and not force:
        logger.info("CloakBrowser binary already installed: %s", binary_path)
        return binary_path

    archive_name = get_archive_name(tag)
    version = get_chromium_version(tag)
    binary_dir = get_binary_dir(tag)

    # Try primary CDN, then fallback
    urls = [get_download_url(tag), get_fallback_url(tag)]

    logger.info(
        "Downloading CloakBrowser Chromium v%s for %s (~200MB)...",
        version, tag,
    )

    for url in urls:
        try:
            with tempfile.NamedTemporaryFile(suffix=archive_name, delete=False) as tmp:
                tmp_path = Path(tmp.name)

            logger.info("Downloading from: %s", url)

            with httpx.stream("GET", url, timeout=300, follow_redirects=True) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0

                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = downloaded * 100 // total
                            if downloaded % (10 * 1024 * 1024) < 65536:
                                logger.info("  %d%% (%dMB / %dMB)",
                                            pct, downloaded // (1024*1024), total // (1024*1024))

            # Verify checksum
            skip = skip_checksum or os.environ.get("CLOAKBROWSER_SKIP_CHECKSUM", "").lower() == "true"
            if not skip:
                if not _verify_checksum(tmp_path, tag):
                    tmp_path.unlink(missing_ok=True)
                    raise RuntimeError("Checksum verification failed")

            # Extract
            if binary_dir.exists():
                shutil.rmtree(binary_dir)
            logger.info("Extracting to %s...", binary_dir)
            _extract_archive(tmp_path, binary_dir, tag)
            tmp_path.unlink(missing_ok=True)

            if binary_path.exists():
                logger.info("CloakBrowser Chromium installed: %s", binary_path)
                return binary_path
            else:
                raise RuntimeError(f"Binary not found after extraction: {binary_path}")

        except httpx.HTTPStatusError as e:
            logger.warning("Download failed from %s: HTTP %d", url, e.response.status_code)
            continue
        except Exception as e:
            logger.warning("Download failed from %s: %s", url, e)
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            continue

    raise RuntimeError(
        f"Failed to download CloakBrowser Chromium binary for {tag}. "
        f"You can manually download from {urls[0]} and set "
        f"CLOAKBROWSER_BINARY_PATH to the chrome executable path."
    )


def ensure_binary(platform_tag: Optional[str] = None) -> Path:
    """Ensure the binary is available, downloading if necessary."""
    return download_binary(platform_tag)


def clear_cache():
    """Remove all cached binaries."""
    cache = get_cache_dir()
    if cache.exists():
        shutil.rmtree(cache)
        logger.info("Cache cleared: %s", cache)


def get_info() -> dict:
    """Get info about the installed binary."""
    tag = get_platform_tag()
    version = get_chromium_version(tag)
    binary = get_binary_path(tag)
    return {
        "platform": tag,
        "chromium_version": version,
        "binary_path": str(binary),
        "installed": binary.exists(),
        "cache_dir": str(get_cache_dir()),
        "download_url": get_download_url(tag),
    }
