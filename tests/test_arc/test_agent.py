"""Tests for CognithorArcAgent — DSL + LLM hybrid solver agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.arc.agent import CognithorArcAgent
from jarvis.arc.task_parser import ArcTask


class TestCognithorArcAgent:
    def test_create_agent(self):
        agent = CognithorArcAgent(game_id="test_001")
        assert agent.game_id == "test_001"
        assert agent.solver is not None
        assert agent.audit_trail is not None

    def test_accepts_legacy_params(self):
        """Old params (use_llm_planner, etc.) don't crash."""
        agent = CognithorArcAgent(
            game_id="test",
            use_llm_planner=True,
            max_steps_per_level=100,
        )
        assert agent.game_id == "test"

    @pytest.mark.asyncio
    async def test_run_async_with_mock_task(self):
        agent = CognithorArcAgent(game_id="test")

        mock_task = ArcTask(
            task_id="test",
            examples=[([[1, 2], [3, 4]], [[3, 1], [4, 2]])],
            test_input=[[5, 6], [7, 8]],
        )
        agent._load_task = MagicMock(return_value=mock_task)

        result = await agent._run_async()
        assert result.win is True  # DSL should find rotate_90
        assert result.attempts >= 1

    @pytest.mark.asyncio
    async def test_run_async_no_task_returns_loss(self):
        agent = CognithorArcAgent(game_id="nonexistent")
        agent._load_task = MagicMock(return_value=None)

        result = await agent._run_async()
        assert result.win is False
        assert result.attempts == 0
