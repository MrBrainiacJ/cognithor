"""Tests for auto-new-session after inactivity."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, UTC


def test_session_config_defaults():
    """SessionConfig has correct defaults."""
    from jarvis.config import JarvisConfig
    config = JarvisConfig()
    assert hasattr(config, "session")
    assert config.session.inactivity_timeout_minutes == 30
    assert config.session.chat_history_limit == 100


def test_should_create_new_session_stale(tmp_path):
    """Stale session (>timeout) -> should create new."""
    from jarvis.gateway.session_store import SessionStore
    from jarvis.models import SessionContext

    store = SessionStore(tmp_path / "sessions.db")
    old = SessionContext(
        session_id="old123456789012",
        user_id="web_user",
        channel="webui",
        agent_name="jarvis",
    )
    old.last_activity = datetime.now(tz=UTC) - timedelta(hours=2)
    store.save_session(old)

    assert store.should_create_new_session(
        channel="webui",
        user_id="web_user",
        inactivity_timeout_minutes=30,
    ) is True


def test_should_create_new_session_recent(tmp_path):
    """Recent session (<timeout) -> should resume."""
    from jarvis.gateway.session_store import SessionStore
    from jarvis.models import SessionContext

    store = SessionStore(tmp_path / "sessions.db")
    recent = SessionContext(
        session_id="new4567890123456",
        user_id="web_user",
        channel="webui",
        agent_name="jarvis",
    )
    recent.last_activity = datetime.now(tz=UTC) - timedelta(minutes=5)
    store.save_session(recent)

    assert store.should_create_new_session(
        channel="webui",
        user_id="web_user",
        inactivity_timeout_minutes=30,
    ) is False


def test_should_create_new_session_no_sessions(tmp_path):
    """No sessions exist -> should create new."""
    from jarvis.gateway.session_store import SessionStore

    store = SessionStore(tmp_path / "sessions.db")
    assert store.should_create_new_session(
        channel="webui",
        user_id="web_user",
    ) is True
