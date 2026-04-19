"""Unit tests for the Observer audit layer."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cognithor.core.observer import (
    AuditResult,
    DimensionResult,
    PGEReloopDirective,
    ResponseEnvelope,
)


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
