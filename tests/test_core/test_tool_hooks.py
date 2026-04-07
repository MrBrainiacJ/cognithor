"""Tests fuer das Tool-Hook-System."""

from __future__ import annotations

from jarvis.core.tool_hooks import (
    HookEvent,
    HookResult,
    ToolHookRunner,
    audit_logging_hook,
    secret_redacting_hook,
)


# ── ToolHookRunner ───────────────────────────────────────────────────


class TestToolHookRunner:
    def test_empty_runner(self):
        runner = ToolHookRunner()
        result = runner.run_pre_tool_use("test_tool", {"key": "val"})
        assert not result.denied
        assert result.updated_input is None
        assert runner.hook_count == 0

    def test_register_and_count(self):
        runner = ToolHookRunner()
        runner.register(HookEvent.PRE_TOOL_USE, "h1", lambda t, i: None)
        runner.register(HookEvent.POST_TOOL_USE, "h2", lambda t, i, o, d: None)
        assert runner.hook_count == 2

    def test_pre_hook_deny(self):
        runner = ToolHookRunner()
        runner.register(
            HookEvent.PRE_TOOL_USE,
            "blocker",
            lambda t, i: {"deny": True, "reason": "blocked by test"},
        )
        result = runner.run_pre_tool_use("any_tool", {})
        assert result.denied
        assert "blocked by test" in result.deny_reason

    def test_pre_hook_update_input(self):
        runner = ToolHookRunner()
        runner.register(
            HookEvent.PRE_TOOL_USE,
            "modifier",
            lambda t, i: {"updated_input": {**i, "extra": True}},
        )
        result = runner.run_pre_tool_use("tool", {"key": "val"})
        assert not result.denied
        assert result.updated_input == {"key": "val", "extra": True}

    def test_pre_hook_exception_ignored(self):
        runner = ToolHookRunner()
        runner.register(
            HookEvent.PRE_TOOL_USE,
            "crasher",
            lambda t, i: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        # Should not raise, just log
        result = runner.run_pre_tool_use("tool", {})
        assert not result.denied
        assert any("failed" in m for m in result.messages)

    def test_post_hook_fires(self):
        calls = []
        runner = ToolHookRunner()
        runner.register(
            HookEvent.POST_TOOL_USE,
            "recorder",
            lambda t, i, o, d: calls.append((t, len(o), d)),
        )
        runner.run_post_tool_use("my_tool", {}, "output text", 42)
        assert len(calls) == 1
        assert calls[0] == ("my_tool", 11, 42)

    def test_post_failure_hook(self):
        errors = []
        runner = ToolHookRunner()
        runner.register(
            HookEvent.POST_TOOL_USE_FAILURE,
            "error_recorder",
            lambda t, i, e: errors.append((t, e)),
        )
        runner.run_post_failure("failing_tool", {}, "connection refused")
        assert len(errors) == 1
        assert errors[0] == ("failing_tool", "connection refused")

    def test_first_deny_wins(self):
        runner = ToolHookRunner()
        runner.register(
            HookEvent.PRE_TOOL_USE,
            "first",
            lambda t, i: {"deny": True, "reason": "first"},
        )
        runner.register(
            HookEvent.PRE_TOOL_USE,
            "second",
            lambda t, i: {"deny": True, "reason": "second"},
        )
        result = runner.run_pre_tool_use("tool", {})
        assert result.deny_reason == "first"


# ── secret_redacting_hook ────────────────────────────────────────────


class TestSecretRedactingHook:
    def test_redacts_openai_key(self):
        result = secret_redacting_hook(
            "shell_exec",
            {"command": "export OPENAI_KEY=sk-abcdefghij1234567890"},
        )
        assert result is not None
        assert "[REDACTED]" in result["updated_input"]["command"]
        assert "sk-" not in result["updated_input"]["command"]

    def test_redacts_github_pat(self):
        result = secret_redacting_hook(
            "shell_exec",
            {
                "command": "git clone https://ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@github.com/repo"
            },
        )
        assert result is not None
        assert "ghp_" not in result["updated_input"]["command"]

    def test_no_secrets_returns_none(self):
        result = secret_redacting_hook(
            "shell_exec",
            {"command": "ls -la"},
        )
        assert result is None

    def test_ignores_non_shell_tools(self):
        result = secret_redacting_hook(
            "web_search",
            {"command": "sk-secret12345678901234"},
        )
        assert result is None

    def test_redacts_aws_key(self):
        result = secret_redacting_hook(
            "exec_command",
            {"command": "export AWS_KEY=AKIAIOSFODNN7EXAMPLE"},
        )
        assert result is not None
        assert "AKIA" not in result["updated_input"]["command"]


# ── audit_logging_hook ───────────────────────────────────────────────


class TestAuditLoggingHook:
    def test_no_exception(self):
        # Should not raise
        audit_logging_hook("test_tool", {"key": "val"}, "output text", 100)
