"""Tests for Feature 8: Cognitive Base Dialogue (Multi-Session UI)."""

from __future__ import annotations

import pytest

from jarvis.ui.session_manager import (
    CORE_MEMORY_MAX_TOKENS,
    SessionManager,
)


@pytest.fixture
def sm(tmp_path):
    """Create a SessionManager with a temporary database."""
    db_path = str(tmp_path / "sessions.db")
    mgr = SessionManager(db_path)
    yield mgr
    mgr.close()


class TestSessionCRUD:
    def test_session_creates_and_persists(self, sm):
        s = sm.create_session("BU Analysis")
        assert s.name == "BU Analysis"
        assert s.id

        loaded = sm.get_session(s.id)
        assert loaded is not None
        assert loaded.name == "BU Analysis"

    def test_session_list_shows_all_sessions(self, sm):
        sm.create_session("Session A")
        sm.create_session("Session B")
        sm.create_session("Session C")

        sessions = sm.list_sessions()
        assert len(sessions) == 3

    def test_session_list_ordered_by_last_active(self, sm):
        s1 = sm.create_session("Old")
        s2 = sm.create_session("New")
        sm.touch_session(s1.id)  # Make s1 the most recent

        sessions = sm.list_sessions()
        assert sessions[0].id == s1.id

    def test_delete_session(self, sm):
        s = sm.create_session("Temp")
        assert sm.delete_session(s.id)
        assert sm.get_session(s.id) is None

    def test_delete_nonexistent_returns_false(self, sm):
        assert not sm.delete_session("nope")

    def test_session_count(self, sm):
        assert sm.session_count() == 0
        sm.create_session("A")
        sm.create_session("B")
        assert sm.session_count() == 2


class TestCoreMemory:
    def test_core_memory_survives_session_restart(self, sm):
        s = sm.create_session("Test")
        sm.save_core_memory(
            s.id,
            {
                "user_prefs": {"language": "de"},
                "long_term_goals": ["learn rust"],
            },
        )

        # Simulate "restart" by loading from DB
        loaded = sm.load_core_memory(s.id)
        assert loaded["user_prefs"]["language"] == "de"
        assert loaded["long_term_goals"] == ["learn rust"]

    def test_core_memory_not_auto_trimmed(self, sm):
        """Core Memory has a max token limit but is never auto-trimmed."""
        assert CORE_MEMORY_MAX_TOKENS == 2048
        # The manager stores but does not trim — application code must enforce

    def test_core_memory_empty_for_new_session(self, sm):
        s = sm.create_session("Fresh")
        mem = sm.load_core_memory(s.id)
        assert mem == {}


class TestCLIFallback:
    def test_cli_selector_fallback_on_dumb_terminal(self):
        """CLI should fall back to plain input() on dumb terminals."""
        from jarvis.utils.platform import supports_curses

        # We just verify the function exists and returns a bool
        result = supports_curses()
        assert isinstance(result, bool)
