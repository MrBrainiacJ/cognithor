"""Unit tests for the Observer audit layer."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock

import pytest

from cognithor.core.observer import (
    AuditResult,
    DimensionResult,
    PGEReloopDirective,
    ResponseEnvelope,
)
from cognithor.models import ToolResult


@pytest.fixture
def observer(tmp_path):
    """ObserverAudit with default config and tmp_path audit store."""
    from cognithor.config import JarvisConfig
    from cognithor.core.observer import ObserverAudit
    from cognithor.core.observer_store import AuditStore

    config = JarvisConfig()
    store = AuditStore(db_path=tmp_path / "audits.db")
    return ObserverAudit(config=config, ollama_client=None, audit_store=store)


class TestDataclasses:
    def test_dimension_result_basic(self):
        r = DimensionResult(
            name="hallucination",
            passed=False,
            reason="Claim not in tool results",
            evidence="'TechCorp founded 2015'",
            fix_suggestion="Remove unsupported claim",
        )
        assert r.name == "hallucination"
        assert r.passed is False
        # Frozen dataclass
        with pytest.raises(FrozenInstanceError):
            r.passed = True  # type: ignore[misc]

    def test_audit_result_pass_path(self):
        dim_pass = DimensionResult(
            name="hallucination", passed=True, reason="", evidence="", fix_suggestion=""
        )
        r = AuditResult(
            overall_passed=True,
            dimensions={"hallucination": dim_pass},
            retry_count=0,
            final_action="pass",
            retry_strategy="deliver",
            model="qwen3:32b",
            duration_ms=3200,
            degraded_mode=False,
            error_type=None,
        )
        assert r.overall_passed is True
        assert r.final_action == "pass"

    def test_pge_reloop_directive(self):
        d = PGEReloopDirective(
            reason="tool_ignorance",
            missing_data="current weather data",
            suggested_tools=["web_search", "api_call"],
        )
        assert d.reason == "tool_ignorance"
        assert "web_search" in d.suggested_tools

    def test_response_envelope_delivers(self):
        e = ResponseEnvelope(content="Hello", directive=None)
        assert e.content == "Hello"
        assert e.directive is None

    def test_response_envelope_with_directive(self):
        d = PGEReloopDirective(
            reason="tool_ignorance", missing_data="...", suggested_tools=[]
        )
        e = ResponseEnvelope(content="draft", directive=d)
        assert e.directive is not None
        assert e.directive.reason == "tool_ignorance"


class TestBuildPrompt:
    def test_includes_all_four_dimensions(self, observer):
        messages = observer._build_prompt(
            user_message="What's 2+2?",
            response="The answer is 4.",
            tool_results=[],
        )
        system_msg = messages[0]["content"]
        for dim in ("hallucination", "sycophancy", "laziness", "tool_ignorance"):
            assert dim in system_msg.lower()

    def test_embeds_user_message_and_response(self, observer):
        messages = observer._build_prompt(
            user_message="FOO_USER_MSG",
            response="BAR_RESPONSE",
            tool_results=[],
        )
        user_payload = messages[1]["content"]
        assert "FOO_USER_MSG" in user_payload
        assert "BAR_RESPONSE" in user_payload

    def test_embeds_tool_results(self, observer):
        tool_result = ToolResult(
            tool_name="web_search",
            content="TechCorp was founded in 2015",
            is_error=False,
        )
        messages = observer._build_prompt(
            user_message="When was TechCorp founded?",
            response="TechCorp was founded in 2015.",
            tool_results=[tool_result],
        )
        user_payload = messages[1]["content"]
        assert "web_search" in user_payload
        assert "TechCorp was founded in 2015" in user_payload

    def test_renders_tool_error(self, observer):
        result = ToolResult(
            tool_name="api_call",
            content="",
            is_error=True,
            error_message="timeout",
        )
        messages = observer._build_prompt(
            user_message="Q", response="A", tool_results=[result]
        )
        assert "ERROR: timeout" in messages[1]["content"]

    def test_renders_tool_error_without_message(self, observer):
        result = ToolResult(
            tool_name="api_call",
            content="",
            is_error=True,
            error_message=None,
        )
        messages = observer._build_prompt(
            user_message="Q", response="A", tool_results=[result]
        )
        # Must NOT contain the literal string "None" — use a sentinel instead.
        assert "ERROR: None" not in messages[1]["content"]
        assert "ERROR: (no error message)" in messages[1]["content"]


class TestCallLlmAudit:
    async def test_returns_raw_text_on_success(self, observer):
        _audit_json = (
            '{"hallucination": {"passed": true, "reason": "",'
            ' "evidence": "", "fix_suggestion": ""}}'
        )
        observer._ollama = AsyncMock()
        observer._ollama.chat = AsyncMock(return_value={
            "message": {"content": _audit_json},
        })
        text = await observer._call_llm_audit(
            messages=[{"role": "system", "content": "x"}],
        )
        assert text.startswith("{")

    async def test_timeout_returns_none(self, observer, monkeypatch):
        import asyncio

        async def _slow_chat(**kwargs):
            await asyncio.sleep(10)
            return {"message": {"content": "x"}}

        observer._ollama = AsyncMock()
        observer._ollama.chat = _slow_chat

        # Override timeout to 1s
        observer._config.observer = observer._config.observer.model_copy(
            update={"timeout_seconds": 1}
        )

        result = await observer._call_llm_audit(
            messages=[{"role": "system", "content": "x"}],
        )
        # Must return None on timeout (fail-open signal)
        assert result is None


class TestParseResponse:
    def test_parses_valid_four_dimensions(self, observer):
        raw = (
            '{"hallucination": {"passed": true, "reason": "all claims match tools",'
            ' "evidence": "", "fix_suggestion": ""},'
            ' "sycophancy": {"passed": true, "reason": "neutral tone",'
            ' "evidence": "", "fix_suggestion": ""},'
            ' "laziness": {"passed": true, "reason": "concrete answer",'
            ' "evidence": "", "fix_suggestion": ""},'
            ' "tool_ignorance": {"passed": true, "reason": "appropriate tool use",'
            ' "evidence": "", "fix_suggestion": ""}}'
        )
        dims = observer._parse_response(raw)
        assert dims is not None
        assert set(dims.keys()) == {"hallucination", "sycophancy", "laziness", "tool_ignorance"}
        assert all(d.passed for d in dims.values())

    def test_invalid_json_returns_none(self, observer):
        assert observer._parse_response("this is not json") is None

    def test_missing_dimension_produces_partial(self, observer):
        raw = (
            '{"hallucination": {"passed": false, "reason": "made up date",'
            ' "evidence": "2015", "fix_suggestion": "remove"},'
            ' "sycophancy": {"passed": true, "reason": "",'
            ' "evidence": "", "fix_suggestion": ""}}'
        )
        dims = observer._parse_response(raw)
        assert dims is not None
        assert dims["hallucination"].passed is False
        assert dims["sycophancy"].passed is True
        # Missing dimensions → treated as "skipped" = passed
        assert dims["laziness"].passed is True
        assert dims["laziness"].reason == "skipped (missing from LLM response)"
        assert dims["tool_ignorance"].passed is True

    def test_all_dimensions_missing_returns_none(self, observer):
        assert observer._parse_response("{}") is None

    def test_dict_without_passed_key_treated_as_skipped(self, observer):
        # LLM returns a dict entry but omits the 'passed' field — must be
        # treated as skipped=passed, same as a missing dimension.
        raw = (
            '{"hallucination": {"reason": "claims unsupported"},'
            ' "sycophancy": {"passed": true, "reason": "", "evidence": "",'
            ' "fix_suggestion": ""}}'
        )
        dims = observer._parse_response(raw)
        assert dims is not None
        assert dims["hallucination"].passed is True
        assert dims["hallucination"].reason == "skipped (missing from LLM response)"
        # sycophancy still parses normally from the well-formed dict
        assert dims["sycophancy"].passed is True
