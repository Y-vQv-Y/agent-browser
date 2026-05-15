"""
Session & Login Manager - Persistent login session management.
Solves the problem of websites requiring login by:

1. Persistent browser profiles - cookies/localStorage persist across sessions
2. Named profiles - manage multiple login identities
3. Cookie export/import - transfer sessions between environments
4. Login flow assistance - AI-guided login when needed
5. Cookie expiry detection - detect and handle expired sessions
6. Credential storage - encrypted storage of site credentials
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Default cookie max-age if not specified (30 days in seconds)
DEFAULT_COOKIE_MAX_AGE = 30 * 24 * 3600

# Session check interval (seconds) - don't re-check within this window
SESSION_CHECK_INTERVAL = 300  # 5 minutes


class SessionProfile:
    """A named browser session profile with persistent login state."""

    def __init__(self, name: str, data_dir: Path):
        self.name = name
        self.profile_dir = data_dir / "profiles" / name
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.profile_dir / "profile.json"
        self.cookies_file = self.profile_dir / "cookies.json"
        self.credentials_file = self.profile_dir / "credentials.json"
        self.meta = self._load_meta()

    def _load_meta(self) -> dict:
        if self.meta_file.exists():
            return json.loads(self.meta_file.read_text())
        # First creation — write the initial meta file so get()/list_profiles() can find it
        meta = {"name": self.name, "created_at": time.time(), "sites": {}}
        self.meta_file.write_text(json.dumps(meta, indent=2))
        return meta

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
            "last_verified": time.time(),
        }
        self._save_meta()

    def mark_session_expired(self, site: str):
        """Mark a site's session as expired."""
        sites = self.meta.get("sites", {})
        if site in sites:
            sites[site]["logged_in"] = False
            sites[site]["expired_at"] = time.time()
            self._save_meta()
            logger.info("Session expired for %s on profile '%s'", site, self.name)

    def is_logged_in(self, site: str) -> bool:
        """Check if we have a recorded login for a site."""
        return self.meta.get("sites", {}).get(site, {}).get("logged_in", False)

    def needs_session_check(self, site: str) -> bool:
        """Check if we should verify the session (not checked recently)."""
        site_info = self.meta.get("sites", {}).get(site, {})
        if not site_info.get("logged_in"):
            return True
        last_verified = site_info.get("last_verified", 0)
        return (time.time() - last_verified) > SESSION_CHECK_INTERVAL

    def update_verified(self, site: str):
        """Update the last verification timestamp."""
        sites = self.meta.get("sites", {})
        if site in sites:
            sites[site]["last_verified"] = time.time()
            self._save_meta()

    def get_login_info(self, site: str) -> Optional[dict]:
        """Get recorded login info for a site."""
        return self.meta.get("sites", {}).get(site)

    def save_credentials(self, site: str, username: str, password: str):
        """Save encrypted credentials for a site."""
        from agent_browser.crypto import encrypt

        data_dir = self.profile_dir.parent.parent  # ~/.agent-browser
        creds = self._load_credentials()
        creds[site] = {
            "username": encrypt(username, data_dir),
            "password": encrypt(password, data_dir),
            "saved_at": time.time(),
        }
        self.credentials_file.write_text(json.dumps(creds, indent=2))

        # Set restrictive permissions
        try:
            import stat
            self.credentials_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except (OSError, AttributeError):
            pass

    def get_credentials(self, site: str) -> Optional[dict]:
        """Get decrypted credentials for a site."""
        from agent_browser.crypto import decrypt

        data_dir = self.profile_dir.parent.parent
        creds = self._load_credentials()
        if site not in creds:
            return None
        entry = creds[site]
        return {
            "username": decrypt(entry.get("username", ""), data_dir),
            "password": decrypt(entry.get("password", ""), data_dir),
        }

    def _load_credentials(self) -> dict:
        """Load credentials file."""
        if self.credentials_file.exists():
            try:
                return json.loads(self.credentials_file.read_text())
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def has_credentials(self, site: str) -> bool:
        """Check if we have stored credentials for a site."""
        creds = self._load_credentials()
        return site in creds

    async def check_cookies_valid(self, context) -> dict:
        """Check cookie expiry status for the current context.

        Returns dict with:
          - valid: bool - whether cookies appear valid
          - expired: list[str] - list of expired cookie domains
          - expiring_soon: list[str] - cookies expiring within 1 hour
        """
        try:
            cookies = await context.cookies()
        except Exception:
            return {"valid": True, "expired": [], "expiring_soon": []}

        now = time.time()
        expired = set()
        expiring_soon = set()

        for cookie in cookies:
            expires = cookie.get("expires", -1)
            domain = cookie.get("domain", "")
            if expires <= 0:
                continue  # Session cookie, no explicit expiry
            if expires < now:
                expired.add(domain)
            elif expires < now + 3600:
                expiring_soon.add(domain)

        return {
            "valid": len(expired) == 0,
            "expired": list(expired),
            "expiring_soon": list(expiring_soon),
        }

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

        # Filter out expired cookies
        now = time.time()
        valid_cookies = [
            c for c in cookies
            if c.get("expires", -1) <= 0 or c.get("expires", 0) > now
        ]
        expired_count = len(cookies) - len(valid_cookies)
        if expired_count > 0:
            logger.info("Skipped %d expired cookies", expired_count)

        if valid_cookies:
            await context.add_cookies(valid_cookies)
            logger.info("Imported %d cookies for profile '%s'", len(valid_cookies), self.name)
        return len(valid_cookies)

    def delete(self):
        """Delete this profile and all its data."""
        if self.profile_dir.exists():
            shutil.rmtree(self.profile_dir)
            logger.info("Deleted profile: %s", self.name)

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract the base domain from a URL for site matching."""
        try:
            parsed = urlparse(url if "://" in url else f"https://{url}")
            host = parsed.hostname or url
            # Remove 'www.' prefix for consistency
            if host.startswith("www."):
                host = host[4:]
            return host
        except Exception:
            return url


class SessionManager:
    """
    Manages multiple named browser profiles.

    Login Workflow:
    1. First visit: Browser navigates to login page. If credentials are stored,
       auto-fill is attempted. Otherwise, the AI asks the user for credentials
       via the ask_user tool.
    2. After login: Cookies are automatically persisted in the profile's
       chrome_data/ directory (Playwright persistent context).
    3. Subsequent visits: Cookies are loaded automatically. If expired,
       the system detects this and re-triggers login.
    4. Credential storage: Username/password encrypted with machine-local key.
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
        domain = SessionProfile.extract_domain(site)
        for name in self.list_profiles():
            profile = SessionProfile(name, self.data_dir)
            if profile.is_logged_in(domain):
                return profile
        return None
