"""Coverage-Tests fuer executor.py -- fehlende Zeilen (retry, backoff, edge cases)."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.config import JarvisConfig
from jarvis.core.executor import Executor, ExecutionError
from jarvis.models import GateDecision, GateStatus, PlannedAction, RiskLevel, ToolResult


@dataclass
class MockToolResult:
    content: str = "OK"
    is_error: bool = False


@pytest.fixture()
def config(tmp_path) -> JarvisConfig:
    return JarvisConfig(jarvis_home=tmp_path)


@pytest.fixture()
def mock_mcp() -> AsyncMock:
    mcp = AsyncMock()
    mcp.call_tool = AsyncMock(return_value=MockToolResult(content="tool output"))
    return mcp


@pytest.fixture()
def executor(config: JarvisConfig, mock_mcp: AsyncMock) -> Executor:
    return Executor(config, mock_mcp)


def _allow(action=None):
    return GateDecision(
        status=GateStatus.ALLOW, risk_level=RiskLevel.GREEN,
        reason="OK", original_action=action, policy_name="test",
    )


def _block(action=None):
    return GateDecision(
        status=GateStatus.BLOCK, risk_level=RiskLevel.RED,
        reason="Blocked", original_action=action, policy_name="test",
    )


def _approve(action=None):
    return GateDecision(
        status=GateStatus.APPROVE, risk_level=RiskLevel.ORANGE,
        reason="Needs approval", original_action=action, policy_name="test",
    )


# ============================================================================
# Basic execution
# ============================================================================


class TestBasicExecution:
    @pytest.mark.asyncio
    async def test_allow_action_executed(self, executor: Executor, mock_mcp: AsyncMock) -> None:
        action = PlannedAction(tool="list_directory", params={"path": "/tmp"})
        results = await executor.execute([action], [_allow(action)])
        assert results[0].success
        mock_mcp.call_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_block_action_skipped(self, executor: Executor, mock_mcp: AsyncMock) -> None:
        """BLOCK status should skip the action."""
        action = PlannedAction(tool="dangerous_tool", params={})
        results = await executor.execute([action], [_block(action)])
        assert results[0].is_error
        assert "GatekeeperBlock" in (results[0].error_type or "")
        mock_mcp.call_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_approve_action_skipped(self, executor: Executor, mock_mcp: AsyncMock) -> None:
        """APPROVE status is NOT in the allowed set, so it's skipped (needs pre-approval)."""
        action = PlannedAction(tool="exec_command", params={"command": "ls"})
        results = await executor.execute([action], [_approve(action)])
        assert results[0].is_error
        mock_mcp.call_tool.assert_not_called()


# ============================================================================
# Multiple actions with dependencies
# ============================================================================


class TestMultipleActionsWithDeps:
    @pytest.mark.asyncio
    async def test_three_chained_actions(self, executor: Executor) -> None:
        a1 = PlannedAction(tool="read_file", params={"path": "/a"})
        a2 = PlannedAction(tool="read_file", params={"path": "/b"}, depends_on=[0])
        a3 = PlannedAction(tool="write_file", params={"path": "/c"}, depends_on=[1])

        results = await executor.execute(
            [a1, a2, a3],
            [_allow(a1), _allow(a2), _allow(a3)],
        )
        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_unmet_dependency_skipped(self, executor: Executor, mock_mcp: AsyncMock) -> None:
        """If dependency fails, dependent action is skipped."""
        mock_mcp.call_tool = AsyncMock(side_effect=ValueError("fail"))
        a1 = PlannedAction(tool="read_file", params={"path": "/a"})
        a2 = PlannedAction(tool="write_file", params={"path": "/b"}, depends_on=[0])

        results = await executor.execute(
            [a1, a2],
            [_allow(a1), _allow(a2)],
        )
        assert len(results) == 2
        # First action failed, second was skipped due to unmet dependency
        assert results[0].is_error
        assert results[1].is_error
        assert "DependencyError" in (results[1].error_type or "")


# ============================================================================
# Mismatched actions/decisions
# ============================================================================


class TestMismatchedInputs:
    @pytest.mark.asyncio
    async def test_mismatched_lengths(self, executor: Executor) -> None:
        a1 = PlannedAction(tool="test", params={})
        with pytest.raises(ExecutionError):
            await executor.execute([a1], [])


# ============================================================================
# Tool result with is_error from MCP
# ============================================================================


class TestMCPErrorResult:
    @pytest.mark.asyncio
    async def test_mcp_returns_error_result(self, executor: Executor, mock_mcp: AsyncMock) -> None:
        mock_mcp.call_tool = AsyncMock(
            return_value=MockToolResult(content="Permission denied", is_error=True)
        )
        action = PlannedAction(tool="exec_command", params={"command": "rm -rf /"})
        results = await executor.execute([action], [_allow(action)])
        assert results[0].is_error


# ============================================================================
# Timeout behavior
# ============================================================================


class TestTimeoutBehavior:
    @pytest.mark.asyncio
    async def test_timeout_action(self, executor: Executor, mock_mcp: AsyncMock) -> None:
        import asyncio
        mock_mcp.call_tool = AsyncMock(side_effect=asyncio.TimeoutError("Tool timed out"))
        action = PlannedAction(tool="slow_tool", params={})
        results = await executor.execute([action], [_allow(action)])
        assert results[0].is_error


# ============================================================================
# Error type recording
# ============================================================================


class TestErrorTypeRecording:
    @pytest.mark.asyncio
    async def test_error_type_recorded(self, executor: Executor, mock_mcp: AsyncMock) -> None:
        mock_mcp.call_tool = AsyncMock(side_effect=ValueError("bad input"))
        action = PlannedAction(tool="bad_tool", params={})
        results = await executor.execute([action], [_allow(action)])
        assert results[0].error_type == "ValueError"
        assert "bad input" in results[0].content


# ============================================================================
# Agent context
# ============================================================================


class TestAgentContext:
    def test_set_and_clear_agent_context(self, executor: Executor) -> None:
        executor.set_agent_context(
            workspace_dir="/tmp/agent",
            sandbox_overrides={"network": False},
            agent_name="test-agent",
            session_id="sess-123",
        )
        executor.clear_agent_context()

    def test_set_mcp_client(self, config: JarvisConfig) -> None:
        executor = Executor(config)
        mock_mcp = AsyncMock()
        executor.set_mcp_client(mock_mcp)
        assert executor._mcp_client is mock_mcp
