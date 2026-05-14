"""Tests for the session/login persistence manager."""

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_browser.browser.session import SessionProfile, SessionManager


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory for tests."""
    return tmp_path / "agent-browser-data"


@pytest.fixture
def session_manager(tmp_data_dir):
    """Create a SessionManager with a temp directory."""
    return SessionManager(tmp_data_dir)


@pytest.fixture
def session_profile(tmp_data_dir):
    """Create a SessionProfile in a temp directory."""
    return SessionProfile("test-profile", tmp_data_dir)


class TestSessionProfile:
    def test_create_profile(self, session_profile):
        assert session_profile.name == "test-profile"
        assert session_profile.profile_dir.exists()

    def test_user_data_dir(self, session_profile):
        udd = session_profile.user_data_dir
        assert "chrome_data" in udd
        assert Path(udd).exists()

    def test_meta_file_created(self, session_profile):
        # Meta is lazy - access it to trigger creation
        assert "name" in session_profile.meta
        assert session_profile.meta["name"] == "test-profile"

    def test_mark_logged_in(self, session_profile):
        session_profile.mark_logged_in("example.com", username="user@test.com")
        assert session_profile.is_logged_in("example.com")

    def test_not_logged_in(self, session_profile):
        assert session_profile.is_logged_in("example.com") is False

    def test_get_login_info(self, session_profile):
        session_profile.mark_logged_in("example.com", username="user@test.com")
        info = session_profile.get_login_info("example.com")
        assert info is not None
        assert info["username"] == "user@test.com"
        assert info["logged_in"] is True
        assert "last_login" in info

    def test_get_login_info_nonexistent(self, session_profile):
        info = session_profile.get_login_info("nothere.com")
        assert info is None

    def test_multiple_sites(self, session_profile):
        session_profile.mark_logged_in("site1.com", "user1")
        session_profile.mark_logged_in("site2.com", "user2")
        assert session_profile.is_logged_in("site1.com")
        assert session_profile.is_logged_in("site2.com")
        assert not session_profile.is_logged_in("site3.com")

    def test_meta_persists(self, tmp_data_dir):
        """Profile metadata persists across instances."""
        p1 = SessionProfile("persist-test", tmp_data_dir)
        p1.mark_logged_in("example.com", "user@test.com")

        p2 = SessionProfile("persist-test", tmp_data_dir)
        assert p2.is_logged_in("example.com")
        info = p2.get_login_info("example.com")
        assert info["username"] == "user@test.com"

    def test_delete_profile(self, session_profile):
        profile_dir = session_profile.profile_dir
        assert profile_dir.exists()
        session_profile.delete()
        assert not profile_dir.exists()

    @pytest.mark.asyncio(mode="strict")
    async def test_export_cookies(self, session_profile):
        mock_context = AsyncMock()
        mock_context.cookies.return_value = [
            {"name": "session", "value": "abc123", "domain": "example.com"},
        ]
        cookies = await session_profile.export_cookies(mock_context)
        assert len(cookies) == 1
        assert session_profile.cookies_file.exists()
        saved = json.loads(session_profile.cookies_file.read_text())
        assert saved[0]["name"] == "session"

    @pytest.mark.asyncio(mode="strict")
    async def test_import_cookies(self, session_profile):
        # Write cookies file first
        cookies = [{"name": "token", "value": "xyz", "domain": "example.com"}]
        session_profile.cookies_file.write_text(json.dumps(cookies))

        mock_context = AsyncMock()
        count = await session_profile.import_cookies(mock_context)
        assert count == 1
        mock_context.add_cookies.assert_called_once_with(cookies)

    @pytest.mark.asyncio(mode="strict")
    async def test_import_cookies_no_file(self, session_profile):
        mock_context = AsyncMock()
        count = await session_profile.import_cookies(mock_context)
        assert count == 0
        mock_context.add_cookies.assert_not_called()


class TestSessionManager:
    def test_create_manager(self, session_manager):
        assert session_manager.profiles_dir.exists()

    def test_list_profiles_empty(self, session_manager):
        assert session_manager.list_profiles() == []

    def test_get_or_create(self, session_manager):
        profile = session_manager.get_or_create("my-profile")
        assert profile.name == "my-profile"
        assert profile.profile_dir.exists()

    def test_list_profiles_after_create(self, session_manager):
        p = session_manager.get_or_create("profile-a")
        p.mark_logged_in("x.com")  # Trigger meta save
        names = session_manager.list_profiles()
        assert "profile-a" in names

    def test_get_existing(self, session_manager):
        session_manager.get_or_create("existing").mark_logged_in("x.com")
        profile = session_manager.get("existing")
        assert profile is not None
        assert profile.name == "existing"

    def test_get_nonexistent(self, session_manager):
        profile = session_manager.get("nonexistent")
        assert profile is None

    def test_delete_existing(self, session_manager):
        session_manager.get_or_create("to-delete").mark_logged_in("x.com")
        result = session_manager.delete("to-delete")
        assert result is True
        assert session_manager.get("to-delete") is None

    def test_delete_nonexistent(self, session_manager):
        result = session_manager.delete("no-such")
        assert result is False

    def test_get_default(self, session_manager):
        profile = session_manager.get_default()
        assert profile.name == "default"

    def test_find_profile_for_site(self, session_manager):
        p1 = session_manager.get_or_create("amazon")
        p1.mark_logged_in("amazon.com", "user@email.com")

        p2 = session_manager.get_or_create("google")
        p2.mark_logged_in("google.com", "user@gmail.com")

        found = session_manager.find_profile_for_site("amazon.com")
        assert found is not None
        assert found.name == "amazon"

    def test_find_profile_for_site_not_found(self, session_manager):
        found = session_manager.find_profile_for_site("unknown.com")
        assert found is None

    def test_multiple_profiles_independent(self, session_manager):
        """Multiple profiles don't share state."""
        p1 = session_manager.get_or_create("profile1")
        p2 = session_manager.get_or_create("profile2")

        p1.mark_logged_in("site.com", "user1")
        assert p1.is_logged_in("site.com")
        assert not p2.is_logged_in("site.com")
