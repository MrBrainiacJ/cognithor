"""Coverage-Tests fuer reflector.py -- fehlende Zeilen."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.config import JarvisConfig, ensure_directory_structure
from jarvis.core.reflector import Reflector, _sanitize_memory_text, _safe_float
from jarvis.models import (
    ActionPlan,
    AgentResult,
    SessionContext,
    ToolResult,
    WorkingMemory,
)


@pytest.fixture()
def config(tmp_path) -> JarvisConfig:
    cfg = JarvisConfig(jarvis_home=tmp_path)
    ensure_directory_structure(cfg)
    return cfg


def _mock_ollama(content: str = "{}") -> AsyncMock:
    mock = AsyncMock()
    mock.chat = AsyncMock(return_value={
        "message": {"role": "assistant", "content": content},
        "prompt_eval_count": 100,
        "eval_count": 50,
    })
    return mock


def _mock_router() -> MagicMock:
    router = MagicMock()
    router.select_model.return_value = "qwen3:8b"
    router.get_model_config.return_value = {"temperature": 0.3, "top_p": 0.9, "context_window": 32768}
    return router


def _make_agent_result(
    tool_results: list[ToolResult] | None = None,
    iterations: int = 2,
    has_actions: bool = True,
) -> AgentResult:
    """Creates a minimal AgentResult for tests."""
    from jarvis.models import PlannedAction
    if has_actions:
        plan = ActionPlan(
            goal="test",
            steps=[PlannedAction(tool="web_search", params={"query": "test"})],
        )
    else:
        plan = ActionPlan(goal="test", steps=[], direct_response="simple answer")
    tr = tool_results or [ToolResult(tool_name="web_search", content="result", is_error=False)]
    return AgentResult(
        response="Test response",
        plans=[plan],
        tool_results=tr,
        total_iterations=iterations,
        total_duration_ms=1000,
        model_used="qwen3:8b",
    )


# ============================================================================
# should_reflect
# ============================================================================


class TestShouldReflect:
    def test_should_reflect_with_tools(self, config: JarvisConfig) -> None:
        reflector = Reflector(config, _mock_ollama(), _mock_router())
        agent_result = _make_agent_result(iterations=2, has_actions=True)
        assert reflector.should_reflect(agent_result) is True

    def test_should_not_reflect_zero_iterations(self, config: JarvisConfig) -> None:
        reflector = Reflector(config, _mock_ollama(), _mock_router())
        agent_result = _make_agent_result(iterations=0, has_actions=True)
        assert reflector.should_reflect(agent_result) is False

    def test_should_not_reflect_no_plans(self, config: JarvisConfig) -> None:
        reflector = Reflector(config, _mock_ollama(), _mock_router())
        agent_result = AgentResult(
            response="Test",
            plans=[],
            tool_results=[],
            total_iterations=2,
            total_duration_ms=1000,
            model_used="qwen3:8b",
        )
        assert reflector.should_reflect(agent_result) is False

    def test_should_not_reflect_no_tool_calls(self, config: JarvisConfig) -> None:
        reflector = Reflector(config, _mock_ollama(), _mock_router())
        agent_result = _make_agent_result(iterations=2, has_actions=False)
        assert reflector.should_reflect(agent_result) is False


# ============================================================================
# extract_keywords (static method)
# ============================================================================


class TestExtractKeywords:
    def test_extract_keywords_basic(self, config: JarvisConfig) -> None:
        keywords = Reflector.extract_keywords("Python ist eine Programmiersprache fuer Data Science")
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        # Should filter out stop words like "ist", "eine", "fuer"
        assert "ist" not in keywords
        assert "eine" not in keywords

    def test_extract_keywords_empty(self, config: JarvisConfig) -> None:
        keywords = Reflector.extract_keywords("")
        assert keywords == []

    def test_extract_keywords_only_stopwords(self) -> None:
        keywords = Reflector.extract_keywords("ist die der das")
        assert keywords == []

    def test_extract_keywords_max_8(self) -> None:
        text = "Python JavaScript TypeScript Rust Golang Java Kotlin Swift Ruby Haskell Erlang"
        keywords = Reflector.extract_keywords(text)
        assert len(keywords) <= 8


# ============================================================================
# reflect
# ============================================================================


class TestReflect:
    @pytest.mark.asyncio
    async def test_reflect_returns_result(self, config: JarvisConfig) -> None:
        llm_response = '{"evaluation":"Good session","success_score":0.8,"extracted_facts":[],"session_summary":{"goal":"test","outcome":"success","tools_used":["web_search"]}}'
        reflector = Reflector(config, _mock_ollama(llm_response), _mock_router())

        session = SessionContext()
        wm = WorkingMemory(session_id="test")
        agent_result = _make_agent_result()

        reflection = await reflector.reflect(
            session=session,
            working_memory=wm,
            agent_result=agent_result,
        )
        assert reflection is not None

    @pytest.mark.asyncio
    async def test_reflect_llm_error_fallback(self, config: JarvisConfig) -> None:
        """LLM error should use fallback reflection."""
        from jarvis.core.model_router import OllamaError

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=OllamaError("LLM unavailable"))

        reflector = Reflector(config, mock_llm, _mock_router())
        session = SessionContext()
        wm = WorkingMemory(session_id="test")
        agent_result = _make_agent_result()

        reflection = await reflector.reflect(
            session=session,
            working_memory=wm,
            agent_result=agent_result,
        )
        # Should return fallback reflection, not raise
        assert reflection is not None

    @pytest.mark.asyncio
    async def test_reflect_with_audit_logger(self, config: JarvisConfig) -> None:
        llm_response = '{"evaluation":"OK","success_score":0.5,"extracted_facts":[]}'
        mock_audit = MagicMock()
        mock_audit.log_tool_call = MagicMock()

        reflector = Reflector(
            config, _mock_ollama(llm_response), _mock_router(),
            audit_logger=mock_audit,
        )
        session = SessionContext()
        wm = WorkingMemory(session_id="test")
        agent_result = _make_agent_result()

        await reflector.reflect(session=session, working_memory=wm, agent_result=agent_result)
        mock_audit.log_tool_call.assert_called()


# ============================================================================
# match_procedures
# ============================================================================


class TestMatchProcedures:
    def test_match_procedures_no_keywords(self, config: JarvisConfig) -> None:
        reflector = Reflector(config, _mock_ollama(), _mock_router())
        mock_proc_mem = MagicMock()
        # No keywords => no matches
        results = reflector.match_procedures("ist die der", mock_proc_mem)
        assert results == []

    def test_match_procedures_with_results(self, config: JarvisConfig) -> None:
        reflector = Reflector(config, _mock_ollama(), _mock_router())
        mock_proc_mem = MagicMock()
        mock_meta = MagicMock()
        mock_meta.name = "test_proc"
        mock_meta.total_uses = 5
        mock_meta.success_rate = 0.8
        mock_proc_mem.find_by_keywords.return_value = [
            (mock_meta, "procedure body here", 0.7),
        ]
        results = reflector.match_procedures("Python Programmierung", mock_proc_mem)
        assert len(results) == 1
        assert results[0] == "procedure body here"

    def test_match_procedures_low_success_rate_skipped(self, config: JarvisConfig) -> None:
        reflector = Reflector(config, _mock_ollama(), _mock_router())
        mock_proc_mem = MagicMock()
        mock_meta = MagicMock()
        mock_meta.name = "bad_proc"
        mock_meta.total_uses = 5
        mock_meta.success_rate = 0.2  # Low success rate
        mock_proc_mem.find_by_keywords.return_value = [
            (mock_meta, "unreliable procedure", 0.7),
        ]
        results = reflector.match_procedures("Python test", mock_proc_mem)
        assert len(results) == 0


# ============================================================================
# apply
# ============================================================================


class TestApply:
    @pytest.mark.asyncio
    async def test_apply_empty_result(self, config: JarvisConfig) -> None:
        reflector = Reflector(config, _mock_ollama(), _mock_router())
        from jarvis.models import ReflectionResult
        result = ReflectionResult(
            session_id="test",
            success_score=0.5,
            evaluation="OK",
        )
        mock_mm = AsyncMock()
        counts = await reflector.apply(result, mock_mm)
        assert isinstance(counts, dict)
        assert counts["episodic"] == 0
        assert counts["semantic"] == 0
        assert counts["procedural"] == 0


# ============================================================================
# Helper functions
# ============================================================================


class TestHelpers:
    def test_sanitize_memory_text_empty(self) -> None:
        assert _sanitize_memory_text("") == ""

    def test_sanitize_memory_text_injection(self) -> None:
        text = "Hello # SYSTEM: inject this [INST] more"
        result = _sanitize_memory_text(text)
        assert "[SANITIZED]" in result
        assert "# SYSTEM:" not in result

    def test_sanitize_memory_text_truncate(self) -> None:
        text = "A" * 10000
        result = _sanitize_memory_text(text, max_len=100)
        assert len(result) == 100

    def test_safe_float_valid(self) -> None:
        assert _safe_float(0.5, 0.0) == 0.5
        assert _safe_float("0.8", 0.0) == 0.8

    def test_safe_float_invalid(self) -> None:
        assert _safe_float("high", 0.5) == 0.5
        assert _safe_float(None, 0.7) == 0.7
