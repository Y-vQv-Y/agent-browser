"""
Session & Login Manager - Persistent login session management.
Solves the problem of websites requiring login by:

1. Persistent browser profiles - cookies/localStorage persist across sessions
2. Named profiles - manage multiple login identities
3. Cookie export/import - transfer sessions between environments
4. Login flow assistance - AI-guided login when needed
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SessionProfile:
    """A named browser session profile with persistent login state."""

    def __init__(self, name: str, data_dir: Path):
        self.name = name
        self.profile_dir = data_dir / "profiles" / name
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.profile_dir / "profile.json"
        self.cookies_file = self.profile_dir / "cookies.json"
        self.meta = self._load_meta()

    def _load_meta(self) -> dict:
        if self.meta_file.exists():
            return json.loads(self.meta_file.read_text())
        return {"name": self.name, "created_at": time.time(), "sites": {}}

    def _save_meta(self):
        self.meta_file.write_text(json.dumps(self.meta, indent=2))

    @property
    def user_data_dir(self) -> str:
        """Chrome user data directory for this profile."""
        chrome_dir = self.profile_dir / "chrome_data"
        chrome_dir.mkdir(exist_ok=True)
        return str(chrome_dir)

    def mark_logged_in(self, site: str, username: str = ""):
        """Record that we've logged in to a site."""
        self.meta.setdefault("sites", {})[site] = {
            "logged_in": True,
            "username": username,
            "last_login": time.time(),
        }
        self._save_meta()

    def is_logged_in(self, site: str) -> bool:
        """Check if we have a recorded login for a site."""
        return self.meta.get("sites", {}).get(site, {}).get("logged_in", False)

    def get_login_info(self, site: str) -> Optional[dict]:
        """Get recorded login info for a site."""
        return self.meta.get("sites", {}).get(site)

    async def export_cookies(self, context) -> list[dict]:
        """Export cookies from the browser context."""
        cookies = await context.cookies()
        self.cookies_file.write_text(json.dumps(cookies, indent=2))
        logger.info("Exported %d cookies for profile '%s'", len(cookies), self.name)
        return cookies

    async def import_cookies(self, context) -> int:
        """Import saved cookies into the browser context."""
        if not self.cookies_file.exists():
            return 0
        cookies = json.loads(self.cookies_file.read_text())
        if cookies:
            await context.add_cookies(cookies)
            logger.info("Imported %d cookies for profile '%s'", len(cookies), self.name)
        return len(cookies)

    def delete(self):
        """Delete this profile and all its data."""
        if self.profile_dir.exists():
            shutil.rmtree(self.profile_dir)
            logger.info("Deleted profile: %s", self.name)


class SessionManager:
    """
    Manages multiple named browser profiles.

    Usage:
        manager = SessionManager(data_dir)
        profile = manager.get_or_create("my-amazon-account")

        # Launch browser with this profile's persistent data
        config.browser.user_data_dir = profile.user_data_dir

        # After login, record it
        profile.mark_logged_in("amazon.com", username="user@email.com")

        # Next time, cookies are automatically preserved via user_data_dir
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("~/.agent-browser").expanduser()
        self.profiles_dir = self.data_dir / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[str]:
        """List all available profile names."""
        if not self.profiles_dir.exists():
            return []
        return [
            d.name for d in self.profiles_dir.iterdir()
            if d.is_dir() and (d / "profile.json").exists()
        ]

    def get_or_create(self, name: str) -> SessionProfile:
        """Get an existing profile or create a new one."""
        return SessionProfile(name, self.data_dir)

    def get(self, name: str) -> Optional[SessionProfile]:
        """Get a profile if it exists."""
        profile_dir = self.profiles_dir / name
        if profile_dir.exists() and (profile_dir / "profile.json").exists():
            return SessionProfile(name, self.data_dir)
        return None

    def delete(self, name: str) -> bool:
        """Delete a profile."""
        profile = self.get(name)
        if profile:
            profile.delete()
            return True
        return False

    def get_default(self) -> SessionProfile:
        """Get or create the default profile."""
        return self.get_or_create("default")

    def find_profile_for_site(self, site: str) -> Optional[SessionProfile]:
        """Find a profile that has a login for the given site."""
        for name in self.list_profiles():
            profile = SessionProfile(name, self.data_dir)
            if profile.is_logged_in(site):
                return profile
        return None
