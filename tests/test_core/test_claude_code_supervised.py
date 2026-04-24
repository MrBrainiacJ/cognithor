"""Tests for the ClaudeCodeSupervisor autonomous loop driver.

Mocks ``asyncio.create_subprocess_exec`` to return a fake process whose
stdout yields a scripted NDJSON event stream. We do not actually spawn the
real ``claude`` CLI.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cognithor.core.claude_code_supervised import (
    ClaudeCodeSupervisor,
    GoalEvaluation,
    SupervisorResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fake subprocess plumbing
# ─────────────────────────────────────────────────────────────────────────────


class _FakeStdout:
    """Async stream that yields scripted NDJSON lines, then EOF."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        for event in events:
            self._queue.put_nowait((json.dumps(event) + "\n").encode("utf-8"))
        self._queue.put_nowait(b"")  # EOF

    async def readline(self) -> bytes:
        line = await self._queue.get()
        return line


class _FakeStdin:
    def __init__(self) -> None:
        self.buffer: list[bytes] = []
        self._closed = False

    def write(self, data: bytes) -> None:
        self.buffer.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self._closed = True


class _FakeProc:
    def __init__(self, events: list[dict[str, Any]], *, returncode: int = 0) -> None:
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout(events)
        self.stderr = _FakeStdout([])  # never produces output in tests
        self.returncode = returncode
        self._wait = asyncio.Event()
        self._wait.set()

    async def wait(self) -> int:
        await self._wait.wait()
        return self.returncode

    def kill(self) -> None:
        self.returncode = -9
        self._wait.set()


def _script_events(
    *, session_id: str = "sess-xyz", text: str = "done", cost: float = 0.01
) -> list[dict[str, Any]]:
    return [
        {"type": "system", "subtype": "init", "session_id": session_id, "cwd": "/w"},
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
        },
        {
            "type": "result",
            "subtype": "success",
            "total_cost_usd": cost,
            "result": text,
            "is_error": False,
        },
    ]


def _script_events_with_tool(
    *, session_id: str = "sess-tool", text: str = "finished"
) -> list[dict[str, Any]]:
    return [
        {"type": "system", "subtype": "init", "session_id": session_id, "cwd": "/w"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "tu_1", "name": "Bash", "input": {"command": "ls"}},
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "tu_1", "content": "file1\nfile2"},
                ],
            },
        },
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": text}]},
        },
        {"type": "result", "subtype": "success", "total_cost_usd": 0.02, "result": text, "is_error": False},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSingleTurn:
    @pytest.mark.asyncio
    async def test_single_turn_success(self):
        proc = _FakeProc(_script_events(text="hello"))
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            sup = ClaudeCodeSupervisor(
                claude_path="claude",
                goal_evaluator=AsyncMock(return_value=GoalEvaluation(verdict="done")),
            )
            result = await sup.run("do the thing")

        assert isinstance(result, SupervisorResult)
        assert result.verdict == "done"
        assert result.final_text == "hello"
        assert len(result.turns) == 1
        turn = result.turns[0]
        assert turn.session_id == "sess-xyz"
        assert turn.cost_usd == pytest.approx(0.01)
        assert turn.is_error is False
        # Stdin should have received one user frame.
        assert len(proc.stdin.buffer) == 1
        frame = json.loads(proc.stdin.buffer[0].decode())
        assert frame["type"] == "user"
        assert frame["message"]["content"] == "do the thing"

    @pytest.mark.asyncio
    async def test_tool_use_and_result_are_paired(self):
        proc = _FakeProc(_script_events_with_tool(text="finished"))
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            sup = ClaudeCodeSupervisor(
                claude_path="claude",
                goal_evaluator=AsyncMock(return_value=GoalEvaluation(verdict="done")),
            )
            result = await sup.run("ls the dir")

        assert result.verdict == "done"
        turn = result.turns[0]
        assert len(turn.tool_results) == 1
        tr = turn.tool_results[0]
        assert tr.tool_name == "Bash"
        assert "file1" in tr.content
        assert tr.is_error is False


class TestBudgets:
    @pytest.mark.asyncio
    async def test_max_turns_enforced(self):
        proc_factory = AsyncMock(side_effect=lambda *a, **kw: _FakeProc(_script_events()))
        with patch("asyncio.create_subprocess_exec", proc_factory):
            sup = ClaudeCodeSupervisor(
                claude_path="claude",
                max_turns=2,
                goal_evaluator=AsyncMock(
                    return_value=GoalEvaluation(verdict="continue", next_prompt="again")
                ),
            )
            result = await sup.run("never-ending")

        assert result.verdict == "abort"
        assert "max_turns" in result.reason
        assert len(result.turns) == 2

    @pytest.mark.asyncio
    async def test_max_cost_enforced(self):
        proc_factory = AsyncMock(
            side_effect=lambda *a, **kw: _FakeProc(_script_events(cost=10.0))
        )
        with patch("asyncio.create_subprocess_exec", proc_factory):
            sup = ClaudeCodeSupervisor(
                claude_path="claude",
                max_turns=10,
                max_cost_usd=1.0,
                goal_evaluator=AsyncMock(
                    return_value=GoalEvaluation(verdict="continue", next_prompt="again")
                ),
            )
            result = await sup.run("pricey")

        assert result.verdict == "abort"
        assert "max_cost" in result.reason


class TestEvaluatorVerdicts:
    @pytest.mark.asyncio
    async def test_done_stops_immediately(self):
        proc = _FakeProc(_script_events(text="first"))
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            evaluator = AsyncMock(return_value=GoalEvaluation(verdict="done", reason="satisfied"))
            sup = ClaudeCodeSupervisor(
                claude_path="claude", goal_evaluator=evaluator, max_turns=5
            )
            result = await sup.run("query")

        assert result.verdict == "done"
        assert result.reason == "satisfied"
        assert len(result.turns) == 1
        evaluator.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_abort_stops_and_propagates_reason(self):
        proc = _FakeProc(_script_events())
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            sup = ClaudeCodeSupervisor(
                claude_path="claude",
                goal_evaluator=AsyncMock(
                    return_value=GoalEvaluation(verdict="abort", reason="policy failure")
                ),
            )
            result = await sup.run("q")

        assert result.verdict == "abort"
        assert result.reason == "policy failure"


class TestClaudeMissing:
    @pytest.mark.asyncio
    async def test_file_not_found_returns_error_turn(self):
        with patch("asyncio.create_subprocess_exec", AsyncMock(side_effect=FileNotFoundError())):
            sup = ClaudeCodeSupervisor(
                claude_path="claude-nope",
                goal_evaluator=AsyncMock(return_value=GoalEvaluation(verdict="done")),
            )
            result = await sup.run("q")

        assert result.verdict == "abort"
        assert len(result.turns) == 1
        assert result.turns[0].is_error is True
        assert "claude CLI not found" in (result.turns[0].error or "")
