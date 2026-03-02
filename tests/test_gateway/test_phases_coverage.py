"""Coverage-Tests fuer gateway/phases/ -- alle 8 Phasen-Module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.config import JarvisConfig, ensure_directory_structure


@pytest.fixture()
def config(tmp_path) -> JarvisConfig:
    cfg = JarvisConfig(jarvis_home=tmp_path)
    ensure_directory_structure(cfg)
    return cfg


# ============================================================================
# phases/core.py
# ============================================================================


class TestCorePhase:
    def test_declare_core_attrs(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.core import declare_core_attrs
        result = declare_core_attrs(config)
        assert "ollama" in result
        assert "llm" in result
        assert "model_router" in result
        assert "session_store" in result
        assert all(v is None for v in result.values())

    @pytest.mark.asyncio
    async def test_init_core_llm_available(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.core import init_core

        mock_llm = MagicMock()
        mock_llm._ollama = MagicMock()
        mock_llm._backend = None
        mock_llm.is_available = AsyncMock(return_value=True)
        mock_llm.backend_type = "ollama"

        mock_router = MagicMock()
        mock_router.initialize = AsyncMock()

        with (
            patch("jarvis.core.unified_llm.UnifiedLLMClient.create", return_value=mock_llm),
            patch("jarvis.core.model_router.ModelRouter", return_value=mock_router),
            patch("jarvis.gateway.session_store.SessionStore") as MockStore,
        ):
            MockStore.return_value = MagicMock(count_sessions=MagicMock(return_value=0))

            result = await init_core(config)
            assert result["__llm_ok"] is True
            assert result["llm"] is mock_llm

    @pytest.mark.asyncio
    async def test_init_core_llm_not_available_ollama(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.core import init_core

        mock_llm = MagicMock()
        mock_llm._ollama = MagicMock()
        mock_llm._backend = None
        mock_llm.is_available = AsyncMock(return_value=False)
        mock_llm.backend_type = "ollama"

        with (
            patch("jarvis.core.unified_llm.UnifiedLLMClient.create", return_value=mock_llm),
            patch("jarvis.core.model_router.ModelRouter") as MockRouter,
            patch("jarvis.gateway.session_store.SessionStore") as MockStore,
        ):
            MockRouter.return_value = MagicMock()
            MockStore.return_value = MagicMock(count_sessions=MagicMock(return_value=0))

            result = await init_core(config)
            assert result["__llm_ok"] is False

    @pytest.mark.asyncio
    async def test_init_core_llm_not_available_lmstudio(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.core import init_core

        mock_llm = MagicMock()
        mock_llm._ollama = MagicMock()
        mock_llm._backend = None
        mock_llm.is_available = AsyncMock(return_value=False)
        mock_llm.backend_type = "lmstudio"

        with (
            patch("jarvis.core.unified_llm.UnifiedLLMClient.create", return_value=mock_llm),
            patch("jarvis.core.model_router.ModelRouter") as MockRouter,
            patch("jarvis.gateway.session_store.SessionStore") as MockStore,
        ):
            MockRouter.return_value = MagicMock()
            MockStore.return_value = MagicMock(count_sessions=MagicMock(return_value=0))

            result = await init_core(config)
            assert result["__llm_ok"] is False

    @pytest.mark.asyncio
    async def test_init_core_llm_not_available_other(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.core import init_core

        mock_llm = MagicMock()
        mock_llm._ollama = MagicMock()
        mock_llm._backend = MagicMock()  # has backend
        mock_llm.is_available = AsyncMock(return_value=False)
        mock_llm.backend_type = "openai"

        mock_router = MagicMock()

        with (
            patch("jarvis.core.unified_llm.UnifiedLLMClient.create", return_value=mock_llm),
            patch("jarvis.core.model_router.ModelRouter") as MockRouter,
            patch("jarvis.gateway.session_store.SessionStore") as MockStore,
        ):
            MockRouter.from_backend.return_value = mock_router
            MockStore.return_value = MagicMock(count_sessions=MagicMock(return_value=0))

            result = await init_core(config)
            assert result["__llm_ok"] is False

    @pytest.mark.asyncio
    async def test_init_core_with_backend(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.core import init_core

        mock_llm = MagicMock()
        mock_llm._ollama = None
        mock_llm._backend = MagicMock()
        mock_llm.is_available = AsyncMock(return_value=True)
        mock_llm.backend_type = "openai"

        mock_router = MagicMock()
        mock_router.initialize = AsyncMock()

        with (
            patch("jarvis.core.unified_llm.UnifiedLLMClient.create", return_value=mock_llm),
            patch("jarvis.core.model_router.ModelRouter") as MockRouter,
            patch("jarvis.gateway.session_store.SessionStore") as MockStore,
        ):
            MockRouter.from_backend.return_value = mock_router
            MockStore.return_value = MagicMock(count_sessions=MagicMock(return_value=0))

            result = await init_core(config)
            assert result["__llm_ok"] is True


# ============================================================================
# phases/security.py
# ============================================================================


class TestSecurityPhase:
    def test_declare_security_attrs(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.security import declare_security_attrs
        result = declare_security_attrs(config)
        assert "audit_logger" in result
        assert "gatekeeper" in result

    @pytest.mark.asyncio
    async def test_init_security(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.security import init_security
        result = await init_security(config)
        assert "audit_logger" in result
        assert "gatekeeper" in result


# ============================================================================
# phases/memory.py
# ============================================================================


class TestMemoryPhase:
    def test_declare_memory_attrs(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.memory import declare_memory_attrs
        result = declare_memory_attrs(config)
        assert "memory_manager" in result

    @pytest.mark.asyncio
    async def test_init_memory(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.memory import init_memory

        mock_audit = MagicMock()
        mock_mm = MagicMock()
        mock_mm.initialize = AsyncMock(return_value={"chunks": 0, "entities": 0})

        with patch("jarvis.memory.manager.MemoryManager", return_value=mock_mm):
            result = await init_memory(config, audit_logger=mock_audit)
            assert "memory_manager" in result

    @pytest.mark.asyncio
    async def test_init_memory_failure(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.memory import init_memory

        mock_mm = MagicMock()
        mock_mm.initialize = AsyncMock(side_effect=Exception("DB error"))

        with patch("jarvis.memory.manager.MemoryManager", return_value=mock_mm):
            result = await init_memory(config, audit_logger=MagicMock())
            assert "memory_manager" in result


# ============================================================================
# phases/tools.py
# ============================================================================


class TestToolsPhase:
    def test_declare_tools_attrs(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.tools import declare_tools_attrs
        result = declare_tools_attrs(config)
        assert "mcp_client" in result

    @pytest.mark.asyncio
    async def test_init_tools(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.tools import init_tools

        mock_mcp = MagicMock()
        mock_mm = MagicMock()
        result = await init_tools(config, mcp_client=mock_mcp, memory_manager=mock_mm)
        assert isinstance(result, dict)


# ============================================================================
# phases/pge.py
# ============================================================================


class TestPGEPhase:
    def test_declare_pge_attrs(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.pge import declare_pge_attrs
        result = declare_pge_attrs(config)
        assert "planner" in result
        assert "executor" in result
        assert "reflector" in result

    @pytest.mark.asyncio
    async def test_init_pge_with_llm(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.pge import init_pge

        mock_llm = MagicMock()
        mock_llm._ollama = MagicMock()
        mock_mcp = MagicMock()
        mock_router = MagicMock()

        result = await init_pge(
            config,
            llm=mock_llm,
            mcp_client=mock_mcp,
            model_router=mock_router,
            runtime_monitor=MagicMock(),
            audit_logger=MagicMock(),
        )
        assert result["planner"] is not None
        assert result["executor"] is not None

    @pytest.mark.asyncio
    async def test_init_pge_no_llm(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.pge import init_pge

        result = await init_pge(
            config,
            llm=None,
            mcp_client=None,
            model_router=None,
            runtime_monitor=None,
            audit_logger=None,
        )
        # PGE always creates Planner/Executor/Reflector (even without LLM)
        assert "planner" in result
        assert "executor" in result
        assert "reflector" in result


# ============================================================================
# phases/agents.py
# ============================================================================


class TestAgentsPhase:
    def test_declare_agents_attrs(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.agents import declare_agents_attrs
        result = declare_agents_attrs(config)
        assert "agent_router" in result

    @pytest.mark.asyncio
    async def test_init_agents(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.agents import init_agents

        result = await init_agents(
            config,
            memory_manager=MagicMock(),
            mcp_client=MagicMock(),
            audit_logger=MagicMock(),
            jarvis_home=config.jarvis_home,
        )
        assert "agent_router" in result


# ============================================================================
# phases/advanced.py
# ============================================================================


class TestAdvancedPhase:
    def test_declare_advanced_attrs(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.advanced import declare_advanced_attrs
        result = declare_advanced_attrs(config)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_init_advanced(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.advanced import init_advanced
        result = await init_advanced(config)
        assert isinstance(result, dict)


# ============================================================================
# phases/compliance.py
# ============================================================================


class TestCompliancePhase:
    def test_declare_compliance_attrs(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.compliance import declare_compliance_attrs
        result = declare_compliance_attrs(config)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_init_compliance(self, config: JarvisConfig) -> None:
        from jarvis.gateway.phases.compliance import init_compliance
        result = await init_compliance(config)
        assert isinstance(result, dict)
