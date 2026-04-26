"""Tests for the Claude Code hook bridge router.

Uses the standalone ``build_claude_code_hooks_app`` factory (mirrors
``build_backends_app`` style) so we exercise the router in isolation with
mocked Gatekeeper / Observer / ToolHookRunner collaborators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from cognithor.gateway.claude_code_hooks import build_claude_code_hooks_app
from cognithor.hitl.types import ApprovalResponse, ApprovalStatus
from cognithor.models import GateDecision, GateStatus, PlannedAction, RiskLevel

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _make_decision(
    *,
    status: GateStatus,
    risk: RiskLevel = RiskLevel.GREEN,
    reason: str = "",
    masked_params: dict | None = None,
) -> GateDecision:
    return GateDecision(
        status=status,
        risk_level=risk,
        reason=reason,
        policy_name="test",
        original_action=PlannedAction(tool="Bash", params={"command": "ls"}),
        masked_params=masked_params,
    )


@pytest.fixture
def gatekeeper_allowing() -> MagicMock:
    gk = MagicMock()
    gk.evaluate.return_value = _make_decision(status=GateStatus.ALLOW, reason="allowed")
    return gk


@pytest.fixture
def gatekeeper_blocking() -> MagicMock:
    gk = MagicMock()
    gk.evaluate.return_value = _make_decision(
        status=GateStatus.BLOCK,
        risk=RiskLevel.RED,
        reason="destructive command blocked",
    )
    return gk


@pytest.fixture
def gatekeeper_approving() -> MagicMock:
    gk = MagicMock()
    gk.evaluate.return_value = _make_decision(
        status=GateStatus.APPROVE,
        risk=RiskLevel.ORANGE,
        reason="needs user confirmation",
    )
    return gk


@pytest.fixture
def gatekeeper_masking() -> MagicMock:
    gk = MagicMock()
    gk.evaluate.return_value = _make_decision(
        status=GateStatus.MASK,
        risk=RiskLevel.YELLOW,
        reason="credentials masked",
        masked_params={"command": "echo ***"},
    )
    return gk


def _payload(tool: str = "Bash", **tool_input) -> dict:
    return {
        "session_id": "sess-abc-1234",
        "transcript_path": "/tmp/t.jsonl",
        "cwd": "/workspace",
        "permission_mode": "default",
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": tool_input or {"command": "ls"},
        "tool_use_id": "toolu_1",
    }


# ─────────────────────────────────────────────────────────────────────────────
# PreToolUse
# ─────────────────────────────────────────────────────────────────────────────


class TestPreToolUse:
    def test_allow_status_maps_to_allow(self, gatekeeper_allowing):
        app = build_claude_code_hooks_app(gatekeeper=gatekeeper_allowing)
        client = TestClient(app)
        r = client.post("/api/claude-hooks/pre-tool-use", json=_payload())
        assert r.status_code == 200
        out = r.json()["hookSpecificOutput"]
        assert out["hookEventName"] == "PreToolUse"
        assert out["permissionDecision"] == "allow"
        assert "allowed" in out["permissionDecisionReason"]

    def test_block_status_maps_to_deny(self, gatekeeper_blocking):
        app = build_claude_code_hooks_app(gatekeeper=gatekeeper_blocking)
        client = TestClient(app)
        r = client.post("/api/claude-hooks/pre-tool-use", json=_payload())
        assert r.status_code == 200
        out = r.json()["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny"
        assert "destructive" in out["permissionDecisionReason"]

    def test_approve_status_maps_to_ask(self, gatekeeper_approving):
        app = build_claude_code_hooks_app(gatekeeper=gatekeeper_approving)
        client = TestClient(app)
        r = client.post("/api/claude-hooks/pre-tool-use", json=_payload())
        assert r.status_code == 200
        out = r.json()["hookSpecificOutput"]
        assert out["permissionDecision"] == "ask"

    def test_mask_status_surfaces_updated_input(self, gatekeeper_masking):
        app = build_claude_code_hooks_app(gatekeeper=gatekeeper_masking)
        client = TestClient(app)
        r = client.post(
            "/api/claude-hooks/pre-tool-use",
            json=_payload(command="echo SECRET"),
        )
        out = r.json()["hookSpecificOutput"]
        assert out["permissionDecision"] == "allow"
        assert out["updatedInput"] == {"command": "echo ***"}

    def test_bypass_permission_mode_short_circuits_to_allow(self):
        gk = MagicMock()
        gk.evaluate.side_effect = AssertionError("must not be called in bypass mode")
        app = build_claude_code_hooks_app(gatekeeper=gk)
        client = TestClient(app)
        payload = _payload()
        payload["permission_mode"] = "bypassPermissions"
        r = client.post("/api/claude-hooks/pre-tool-use", json=payload)
        out = r.json()["hookSpecificOutput"]
        assert out["permissionDecision"] == "allow"
        assert "bypass" in out["permissionDecisionReason"].lower()
        gk.evaluate.assert_not_called()

    def test_no_gatekeeper_wired_fails_open(self):
        app = build_claude_code_hooks_app(gatekeeper=None)
        client = TestClient(app)
        r = client.post("/api/claude-hooks/pre-tool-use", json=_payload())
        out = r.json()["hookSpecificOutput"]
        assert out["permissionDecision"] == "allow"
        assert "not wired" in out["permissionDecisionReason"]

    def test_gatekeeper_raises_fails_open(self):
        gk = MagicMock()
        gk.evaluate.side_effect = RuntimeError("boom")
        app = build_claude_code_hooks_app(gatekeeper=gk)
        client = TestClient(app)
        r = client.post("/api/claude-hooks/pre-tool-use", json=_payload())
        out = r.json()["hookSpecificOutput"]
        assert out["permissionDecision"] == "allow"
        assert "failing open" in out["permissionDecisionReason"]

    def test_session_context_is_reused_across_pre_calls(self, gatekeeper_allowing):
        app = build_claude_code_hooks_app(gatekeeper=gatekeeper_allowing)
        client = TestClient(app)
        for _ in range(3):
            client.post("/api/claude-hooks/pre-tool-use", json=_payload())
        # All three calls should have been evaluated against the same SessionContext.
        sessions = {call.args[1].session_id for call in gatekeeper_allowing.evaluate.call_args_list}
        assert len(sessions) == 1
        assert next(iter(sessions)) == "sess-abc-1234"


# ─────────────────────────────────────────────────────────────────────────────
# PostToolUse
# ─────────────────────────────────────────────────────────────────────────────


class TestPostToolUse:
    def _payload(self, **over) -> dict:
        base = {
            "session_id": "sess-post-1",
            "cwd": "/w",
            "permission_mode": "default",
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_response": "file1\nfile2",
            "tool_use_id": "t1",
            "duration_ms": 12,
        }
        base.update(over)
        return base

    def test_success_returns_empty_body(self):
        app = build_claude_code_hooks_app()
        client = TestClient(app)
        r = client.post("/api/claude-hooks/post-tool-use", json=self._payload())
        assert r.status_code == 200
        assert r.json() == {}

    def test_error_response_injects_warning_context(self):
        app = build_claude_code_hooks_app()
        client = TestClient(app)
        r = client.post(
            "/api/claude-hooks/post-tool-use",
            json=self._payload(tool_response={"error": "disk full"}),
        )
        out = r.json()
        assert "hookSpecificOutput" in out
        assert "additionalContext" in out["hookSpecificOutput"]
        assert "disk full" in out["hookSpecificOutput"]["additionalContext"]

    def test_bash_nonzero_exit_heuristic(self):
        app = build_claude_code_hooks_app()
        client = TestClient(app)
        r = client.post(
            "/api/claude-hooks/post-tool-use",
            json=self._payload(tool_response="Command failed with exit code 1"),
        )
        out = r.json()
        assert "hookSpecificOutput" in out
        assert "non-zero exit" in out["hookSpecificOutput"]["additionalContext"]

    def test_hook_runner_is_forwarded(self):
        runner = MagicMock()
        app = build_claude_code_hooks_app(hook_runner=runner)
        client = TestClient(app)
        client.post("/api/claude-hooks/post-tool-use", json=self._payload())
        runner.run_post_tool_use.assert_called_once()
        args = runner.run_post_tool_use.call_args.args
        assert args[0] == "Bash"
        assert args[1] == {"command": "ls"}
        assert "file1" in args[2]


# ─────────────────────────────────────────────────────────────────────────────
# Stop
# ─────────────────────────────────────────────────────────────────────────────


class TestStop:
    def _payload(self) -> dict:
        return {
            "session_id": "sess-stop-1",
            "cwd": "/w",
            "permission_mode": "default",
            "hook_event_name": "Stop",
        }

    def test_stop_without_observer_is_noop(self):
        app = build_claude_code_hooks_app()
        client = TestClient(app)
        r = client.post("/api/claude-hooks/stop", json=self._payload())
        assert r.status_code == 200
        assert r.json() == {}


# ─────────────────────────────────────────────────────────────────────────────
# SessionStart + health
# ─────────────────────────────────────────────────────────────────────────────


class TestSessionStart:
    def test_session_start_injects_cognithor_banner(self):
        app = build_claude_code_hooks_app()
        client = TestClient(app)
        r = client.post(
            "/api/claude-hooks/session-start",
            json={
                "session_id": "sess-start-1",
                "cwd": "/w",
                "hook_event_name": "SessionStart",
                "source": "startup",
                "model": "sonnet",
            },
        )
        out = r.json()["hookSpecificOutput"]
        assert out["hookEventName"] == "SessionStart"
        assert "Cognithor" in out["additionalContext"]


class TestHealth:
    def test_health_reports_wired_components(self, gatekeeper_allowing):
        app = build_claude_code_hooks_app(gatekeeper=gatekeeper_allowing)
        client = TestClient(app)
        r = client.get("/api/claude-hooks/health")
        data = r.json()
        assert data["ok"] is True
        assert data["gatekeeper"] is True
        assert data["observer"] is False
        assert data["approval_manager"] is False
        assert "hitl_timeout_seconds" in data


# ─────────────────────────────────────────────────────────────────────────────
# APPROVE → HITL routing
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class _StubRequest:
    request_id: str = "apr_stub"
    status: ApprovalStatus = ApprovalStatus.PENDING


@dataclass
class _StubTask:
    request: _StubRequest = field(default_factory=_StubRequest)
    responses: list[ApprovalResponse] = field(default_factory=list)


def _make_approval_manager(*, final_status: ApprovalStatus, comment: str = "") -> MagicMock:
    """Build an ApprovalManager mock that resolves to the given final status."""
    mgr = MagicMock()
    request = _StubRequest(request_id="apr_test")
    mgr.create_request = AsyncMock(return_value=request)

    task = _StubTask(request=_StubRequest(request_id="apr_test", status=final_status))
    if comment:
        task.responses.append(
            ApprovalResponse(decision=final_status, reviewer="tester", comment=comment)
        )
    mgr.wait_for_resolution = AsyncMock(return_value=task)
    return mgr


class TestApproveRouting:
    def test_approved_status_maps_to_allow(self, gatekeeper_approving):
        mgr = _make_approval_manager(
            final_status=ApprovalStatus.APPROVED, comment="ok by reviewer"
        )
        app = build_claude_code_hooks_app(
            gatekeeper=gatekeeper_approving, approval_manager=mgr
        )
        client = TestClient(app)
        r = client.post("/api/claude-hooks/pre-tool-use", json=_payload())
        out = r.json()["hookSpecificOutput"]
        assert out["permissionDecision"] == "allow"
        assert "HITL approved" in out["permissionDecisionReason"]
        assert "ok by reviewer" in out["permissionDecisionReason"]
        mgr.create_request.assert_awaited_once()
        mgr.wait_for_resolution.assert_awaited_once()

    def test_rejected_status_maps_to_deny(self, gatekeeper_approving):
        mgr = _make_approval_manager(
            final_status=ApprovalStatus.REJECTED, comment="too risky"
        )
        app = build_claude_code_hooks_app(
            gatekeeper=gatekeeper_approving, approval_manager=mgr
        )
        client = TestClient(app)
        r = client.post("/api/claude-hooks/pre-tool-use", json=_payload())
        out = r.json()["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny"
        assert "HITL rejected" in out["permissionDecisionReason"]
        assert "too risky" in out["permissionDecisionReason"]

    def test_timed_out_status_denies_for_safety(self, gatekeeper_approving):
        mgr = _make_approval_manager(final_status=ApprovalStatus.TIMED_OUT)
        app = build_claude_code_hooks_app(
            gatekeeper=gatekeeper_approving, approval_manager=mgr
        )
        client = TestClient(app)
        r = client.post("/api/claude-hooks/pre-tool-use", json=_payload())
        out = r.json()["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny"
        assert "unresolved" in out["permissionDecisionReason"]

    def test_no_approval_manager_falls_back_to_ask(self, gatekeeper_approving):
        app = build_claude_code_hooks_app(
            gatekeeper=gatekeeper_approving, approval_manager=None
        )
        client = TestClient(app)
        r = client.post("/api/claude-hooks/pre-tool-use", json=_payload())
        out = r.json()["hookSpecificOutput"]
        assert out["permissionDecision"] == "ask"

    def test_approval_manager_create_failure_falls_back_to_ask(
        self, gatekeeper_approving
    ):
        mgr = MagicMock()
        mgr.create_request = AsyncMock(side_effect=RuntimeError("notifier offline"))
        app = build_claude_code_hooks_app(
            gatekeeper=gatekeeper_approving, approval_manager=mgr
        )
        client = TestClient(app)
        r = client.post("/api/claude-hooks/pre-tool-use", json=_payload())
        out = r.json()["hookSpecificOutput"]
        assert out["permissionDecision"] == "ask"

    def test_approval_manager_wait_failure_denies_for_safety(
        self, gatekeeper_approving
    ):
        mgr = MagicMock()
        mgr.create_request = AsyncMock(return_value=_StubRequest(request_id="apr_x"))
        mgr.wait_for_resolution = AsyncMock(side_effect=RuntimeError("event loop dead"))
        app = build_claude_code_hooks_app(
            gatekeeper=gatekeeper_approving, approval_manager=mgr
        )
        client = TestClient(app)
        r = client.post("/api/claude-hooks/pre-tool-use", json=_payload())
        out = r.json()["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny"
        assert "wait error" in out["permissionDecisionReason"]
