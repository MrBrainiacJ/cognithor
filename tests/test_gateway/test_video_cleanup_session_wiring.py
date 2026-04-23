"""Regression test for Bug C1-r2: Gateway must fire VideoCleanupWorker.on_session_close
when a session ends (stale sweep OR explicit close), otherwise videos leak until
the 24 h TTL sweep."""

from __future__ import annotations


class TestSessionCloseFiresVideoCleanup:
    def test_stale_cleanup_triggers_on_session_close(self):
        """When _cleanup_stale_sessions evicts a session, the VideoCleanupWorker
        must be told so its registered uploads get deleted immediately."""
        import inspect

        from cognithor.gateway import gateway as gw

        src = inspect.getsource(gw)

        # Find _cleanup_stale_sessions method body and check for a call to
        # video_cleanup.on_session_close inside it.
        # Accept either:
        #   self._video_cleanup.on_session_close(...)
        #   asyncio.ensure_future(self._video_cleanup.on_session_close(...))
        #   await self._video_cleanup.on_session_close(...)
        m_start = src.find("def _cleanup_stale_sessions")
        assert m_start != -1, "Could not locate _cleanup_stale_sessions in gateway.py"
        # Take a reasonable window after the def
        m_end = src.find("\n    def ", m_start + 1)
        if m_end == -1:
            m_end = len(src)
        body = src[m_start:m_end]

        assert "on_session_close" in body, (
            "_cleanup_stale_sessions does not call VideoCleanupWorker.on_session_close. "
            "Session-lifetime cleanup is dead code — videos only deleted by 24h TTL sweep."
        )


class TestFunctionalSessionCloseWiring:
    """Functional test: build a minimally-constructed Gateway (__new__, no __init__)
    and verify _cleanup_stale_sessions schedules on_session_close for each evicted
    session when a running event loop is available.
    """

    def test_cleanup_calls_video_worker_with_each_session_id(self):
        import asyncio
        import threading
        import time
        from dataclasses import dataclass
        from unittest.mock import MagicMock

        from cognithor.gateway.gateway import Gateway

        # Build a bare Gateway without running __init__.
        gw = Gateway.__new__(Gateway)

        # Minimal attribute surface required by _cleanup_stale_sessions.
        @dataclass
        class _FakeSession:
            session_id: str

        gw._session_lock = threading.Lock()
        gw._SESSION_TTL_SECONDS = 1  # type: ignore[attr-defined]
        gw._last_session_cleanup = 0.0
        # Two sessions that are definitely stale (last accessed "forever ago").
        key_a = "channel:user-a:jarvis"
        key_b = "channel:user-b:jarvis"
        gw._sessions = {
            key_a: _FakeSession(session_id="sid-a"),
            key_b: _FakeSession(session_id="sid-b"),
        }
        gw._working_memories = {"sid-a": object(), "sid-b": object()}
        # A time far enough in the past to exceed TTL.
        past = time.monotonic() - 9999.0
        gw._session_last_accessed = {key_a: past, key_b: past}

        # Mock the video cleanup worker.
        calls: list[str] = []

        async def _fake_close(session_id: str) -> None:
            calls.append(session_id)

        mock_worker = MagicMock()
        mock_worker.on_session_close.side_effect = _fake_close
        gw._video_cleanup = mock_worker

        async def _runner():
            gw._cleanup_stale_sessions()
            # Let the scheduled tasks run.
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        asyncio.run(_runner())

        # Each evicted session should have fired on_session_close exactly once.
        assert mock_worker.on_session_close.call_count == 2
        called_ids = {c.args[0] for c in mock_worker.on_session_close.call_args_list}
        assert called_ids == {"sid-a", "sid-b"}

    def test_cleanup_skips_video_worker_when_none(self):
        """Gateway where vLLM is disabled has _video_cleanup=None — must not crash."""
        import threading
        import time
        from dataclasses import dataclass

        from cognithor.gateway.gateway import Gateway

        gw = Gateway.__new__(Gateway)

        @dataclass
        class _FakeSession:
            session_id: str

        gw._session_lock = threading.Lock()
        gw._SESSION_TTL_SECONDS = 1  # type: ignore[attr-defined]
        gw._last_session_cleanup = 0.0
        gw._sessions = {"k": _FakeSession(session_id="sid-x")}
        gw._working_memories = {"sid-x": object()}
        gw._session_last_accessed = {"k": time.monotonic() - 9999.0}
        gw._video_cleanup = None

        # Must not raise even without a video cleanup worker.
        gw._cleanup_stale_sessions()
        assert gw._sessions == {}
        assert gw._working_memories == {}

    def test_cleanup_tolerates_no_running_loop(self):
        """If no event loop is running, we can't schedule the coroutine — must
        not raise (TTL sweep will catch orphans later)."""
        import threading
        import time
        from dataclasses import dataclass
        from unittest.mock import MagicMock

        from cognithor.gateway.gateway import Gateway

        gw = Gateway.__new__(Gateway)

        @dataclass
        class _FakeSession:
            session_id: str

        gw._session_lock = threading.Lock()
        gw._SESSION_TTL_SECONDS = 1  # type: ignore[attr-defined]
        gw._last_session_cleanup = 0.0
        gw._sessions = {"k": _FakeSession(session_id="sid-y")}
        gw._working_memories = {"sid-y": object()}
        gw._session_last_accessed = {"k": time.monotonic() - 9999.0}

        mock_worker = MagicMock()
        # Do not call — simulates no-loop path.
        gw._video_cleanup = mock_worker

        # Running synchronously outside asyncio.run() → no running loop.
        gw._cleanup_stale_sessions()
        # Session should still have been evicted.
        assert gw._sessions == {}
