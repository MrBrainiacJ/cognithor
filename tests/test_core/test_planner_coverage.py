"""Coverage-Tests fuer planner.py -- fehlende Zeilen."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.config import JarvisConfig, ensure_directory_structure
from jarvis.core.planner import Planner
from jarvis.models import ActionPlan, WorkingMemory


@pytest.fixture()
def config(tmp_path) -> JarvisConfig:
    cfg = JarvisConfig(jarvis_home=tmp_path)
    ensure_directory_structure(cfg)
    return cfg


def _mock_ollama(response_content: str) -> AsyncMock:
    mock = AsyncMock()
    mock.chat = AsyncMock(return_value={
        "message": {"role": "assistant", "content": response_content}
    })
    mock.is_available = AsyncMock(return_value=True)
    return mock


def _mock_router() -> MagicMock:
    router = MagicMock()
    router.select_model.return_value = "qwen3:32b"
    router.get_model_config.return_value = {"temperature": 0.7, "top_p": 0.9}
    return router


# ============================================================================
# Planner.plan -- edge cases
# ============================================================================


class TestPlannerEdgeCases:
    @pytest.mark.asyncio
    async def test_plan_with_think_tags(self, config: JarvisConfig) -> None:
        """LLM returns response with <think> tags (qwen3 behavior)."""
        content = '<think>Let me think about this...</think>\nDas ist eine einfache Frage.'
        ollama = _mock_ollama(content)
        planner = Planner(config, ollama, _mock_router())
        wm = WorkingMemory(session_id="test")

        plan = await planner.plan(
            user_message="Was ist Python?",
            working_memory=wm,
            tool_schemas={},
        )
        assert isinstance(plan, ActionPlan)
        assert plan.direct_response

    @pytest.mark.asyncio
    async def test_plan_json_in_code_block(self, config: JarvisConfig) -> None:
        """LLM returns JSON in a code block."""
        content = '```json\n{"goal":"test","steps":[{"tool":"read_file","params":{"path":"/tmp/x"},"rationale":"test"}],"confidence":0.9}\n```'
        ollama = _mock_ollama(content)
        planner = Planner(config, ollama, _mock_router())
        wm = WorkingMemory(session_id="test")

        plan = await planner.plan(
            user_message="Lies /tmp/x",
            working_memory=wm,
            tool_schemas={"read_file": {"description": "reads a file"}},
        )
        assert isinstance(plan, ActionPlan)

    @pytest.mark.asyncio
    async def test_plan_invalid_json(self, config: JarvisConfig) -> None:
        """LLM returns invalid JSON -- should fallback to direct response."""
        content = 'Das ist keine JSON-Antwort sondern normaler Text.'
        ollama = _mock_ollama(content)
        planner = Planner(config, ollama, _mock_router())
        wm = WorkingMemory(session_id="test")

        plan = await planner.plan(
            user_message="test",
            working_memory=wm,
            tool_schemas={},
        )
        assert isinstance(plan, ActionPlan)
        assert plan.direct_response

    @pytest.mark.asyncio
    async def test_plan_with_empty_steps(self, config: JarvisConfig) -> None:
        """LLM returns JSON with empty steps list."""
        content = '```json\n{"goal":"test","steps":[],"confidence":0.9}\n```'
        ollama = _mock_ollama(content)
        planner = Planner(config, ollama, _mock_router())
        wm = WorkingMemory(session_id="test")

        plan = await planner.plan(
            user_message="test",
            working_memory=wm,
            tool_schemas={},
        )
        assert isinstance(plan, ActionPlan)


# ============================================================================
# Planner.replan
# ============================================================================


class TestPlannerReplan:
    @pytest.mark.asyncio
    async def test_replan_after_tool_results(self, config: JarvisConfig) -> None:
        content = 'Die Antwort basierend auf den Tool-Ergebnissen ist: 42.'
        ollama = _mock_ollama(content)
        planner = Planner(config, ollama, _mock_router())
        wm = WorkingMemory(session_id="test")

        from jarvis.models import ToolResult
        results = [ToolResult(tool_name="calc", content="42", is_error=False)]

        plan = await planner.replan(
            original_goal="Was ist 6*7?",
            results=results,
            working_memory=wm,
            tool_schemas={},
        )
        assert isinstance(plan, ActionPlan)


# ============================================================================
# Planner.formulate_response
# ============================================================================


class TestFormulateResponse:
    @pytest.mark.asyncio
    async def test_formulate_response(self, config: JarvisConfig) -> None:
        content = "Hier ist die zusammengefasste Antwort."
        ollama = _mock_ollama(content)
        planner = Planner(config, ollama, _mock_router())

        from jarvis.models import ToolResult
        results = [ToolResult(tool_name="web_search", content="Python ist toll", is_error=False)]
        wm = WorkingMemory(session_id="test")

        response = await planner.formulate_response(
            user_message="Was ist Python?",
            results=results,
            working_memory=wm,
        )
        assert isinstance(response, str)
        assert len(response) > 0


# ============================================================================
# Planner.generate_escalation
# ============================================================================


class TestGenerateEscalation:
    @pytest.mark.asyncio
    async def test_generate_escalation(self, config: JarvisConfig) -> None:
        content = "Der Befehl wurde aus Sicherheitsgruenden blockiert."
        ollama = _mock_ollama(content)
        planner = Planner(config, ollama, _mock_router())
        wm = WorkingMemory(session_id="test")

        response = await planner.generate_escalation(
            tool="exec_command",
            reason="Dangerous command blocked",
            working_memory=wm,
        )
        assert isinstance(response, str)
