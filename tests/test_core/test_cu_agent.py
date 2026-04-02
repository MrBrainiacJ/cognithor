"""Tests for CUAgentExecutor — closed-loop desktop automation agent."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.core.cu_agent import CUAgentConfig, CUAgentExecutor, CUAgentResult


class TestCUAgentConfig:
    def test_defaults(self):
        cfg = CUAgentConfig()
        assert cfg.max_iterations == 30
        assert cfg.max_duration_seconds == 480
        assert cfg.vision_model == "qwen3-vl:32b"
        assert cfg.stuck_detection_threshold == 3

    def test_custom(self):
        cfg = CUAgentConfig(max_iterations=10, max_duration_seconds=120)
        assert cfg.max_iterations == 10
        assert cfg.max_duration_seconds == 120


class TestCUAgentResult:
    def test_defaults(self):
        r = CUAgentResult()
        assert r.success is False
        assert r.iterations == 0
        assert r.duration_ms == 0
        assert r.tool_results == []
        assert r.abort_reason == ""
        assert r.extracted_content == ""
        assert r.action_history == []


class TestCUAgentAbort:
    def _make_agent(self, **config_overrides) -> CUAgentExecutor:
        planner = MagicMock()
        planner._ollama = AsyncMock()
        mcp = MagicMock()
        mcp._builtin_handlers = {}
        return CUAgentExecutor(planner, mcp, MagicMock(), MagicMock(), {}, CUAgentConfig(**config_overrides))

    def test_check_abort_max_iterations(self):
        agent = self._make_agent(max_iterations=5)
        result = CUAgentResult(iterations=5)
        assert agent._check_abort(result, time.monotonic(), None) == "max_iterations"

    def test_check_abort_timeout(self):
        agent = self._make_agent(max_duration_seconds=1)
        result = CUAgentResult(iterations=1)
        start = time.monotonic() - 2
        assert agent._check_abort(result, start, None) == "timeout"

    def test_check_abort_user_cancel(self):
        agent = self._make_agent()
        result = CUAgentResult(iterations=1)
        assert agent._check_abort(result, time.monotonic(), lambda: True) == "user_cancel"

    def test_check_abort_stuck_loop(self):
        agent = self._make_agent(stuck_detection_threshold=3)
        agent._recent_actions = ["click:x=100,y=200"] * 3
        result = CUAgentResult(iterations=3)
        assert agent._check_abort(result, time.monotonic(), None) == "stuck_loop"

    def test_check_abort_no_abort(self):
        agent = self._make_agent()
        result = CUAgentResult(iterations=1)
        assert agent._check_abort(result, time.monotonic(), None) == ""
