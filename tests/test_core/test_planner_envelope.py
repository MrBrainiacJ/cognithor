"""Tests for Planner.formulate_response() returning ResponseEnvelope."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cognithor.config import JarvisConfig
from cognithor.core.observer import ResponseEnvelope


@pytest.fixture
def planner_with_mocks():
    from cognithor.core.model_router import ModelRouter
    from cognithor.core.planner import Planner

    cfg = JarvisConfig()
    cfg.observer.enabled = False  # isolate this test from observer integration (Task 15)
    ollama = AsyncMock()
    ollama.chat = AsyncMock(return_value={"message": {"content": "hello"}})
    router = MagicMock(spec=ModelRouter)
    router.select_model = MagicMock(return_value="qwen3:8b")
    p = Planner(
        config=cfg,
        ollama=ollama,
        model_router=router,
    )
    return p


class TestFormulateResponseReturnsEnvelope:
    async def test_returns_response_envelope(self, planner_with_mocks):
        from cognithor.models import WorkingMemory

        wm = WorkingMemory(session_id="s1")
        envelope = await planner_with_mocks.formulate_response(
            user_message="hi",
            results=[],
            working_memory=wm,
        )
        assert isinstance(envelope, ResponseEnvelope)
        assert envelope.content == "hello"
        assert envelope.directive is None
