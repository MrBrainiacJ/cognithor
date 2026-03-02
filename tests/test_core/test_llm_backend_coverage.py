"""Coverage-Tests fuer llm_backend.py -- fehlende Zeilen."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.config import JarvisConfig, ensure_directory_structure
from jarvis.core.llm_backend import (
    AnthropicBackend,
    ChatResponse,
    EmbedResponse,
    GeminiBackend,
    LLMBackendError,
    LLMBackendType,
    OllamaBackend,
    OpenAIBackend,
    create_backend,
)


@pytest.fixture()
def config(tmp_path) -> JarvisConfig:
    cfg = JarvisConfig(jarvis_home=tmp_path)
    ensure_directory_structure(cfg)
    return cfg


# ============================================================================
# Data classes
# ============================================================================


class TestDataClasses:
    def test_chat_response(self) -> None:
        resp = ChatResponse(content="Hello", model="gpt-4")
        assert resp.content == "Hello"
        assert resp.model == "gpt-4"
        assert resp.tool_calls is None
        assert resp.usage is None
        assert resp.raw is None

    def test_chat_response_with_tools(self) -> None:
        tools = [{"function": {"name": "search", "arguments": {}}}]
        resp = ChatResponse(content="", tool_calls=tools, model="gpt-4")
        assert resp.tool_calls == tools

    def test_embed_response(self) -> None:
        resp = EmbedResponse(embedding=[0.1, 0.2, 0.3], model="embed-v1")
        assert resp.embedding == [0.1, 0.2, 0.3]
        assert resp.model == "embed-v1"

    def test_llm_backend_error(self) -> None:
        err = LLMBackendError("test error", status_code=500)
        assert str(err) == "test error"
        assert err.status_code == 500

    def test_llm_backend_type_enum(self) -> None:
        assert LLMBackendType.OLLAMA == "ollama"
        assert LLMBackendType.OPENAI == "openai"
        assert LLMBackendType.ANTHROPIC == "anthropic"
        assert LLMBackendType.GEMINI == "gemini"
        assert LLMBackendType.LMSTUDIO == "lmstudio"


# ============================================================================
# create_backend factory
# ============================================================================


class TestCreateBackend:
    def test_create_ollama_default(self, config: JarvisConfig) -> None:
        """Default backend type is ollama."""
        backend = create_backend(config)
        assert isinstance(backend, OllamaBackend)
        assert backend.backend_type == LLMBackendType.OLLAMA

    def test_create_openai(self, config: JarvisConfig) -> None:
        config.llm_backend_type = "openai"
        config.openai_api_key = "sk-test"
        config.openai_base_url = "https://api.openai.com/v1"
        backend = create_backend(config)
        assert isinstance(backend, OpenAIBackend)
        assert backend.backend_type == LLMBackendType.OPENAI

    def test_create_anthropic(self, config: JarvisConfig) -> None:
        config.llm_backend_type = "anthropic"
        config.anthropic_api_key = "sk-ant-test"
        backend = create_backend(config)
        assert isinstance(backend, AnthropicBackend)
        assert backend.backend_type == LLMBackendType.ANTHROPIC

    def test_create_gemini(self, config: JarvisConfig) -> None:
        config.llm_backend_type = "gemini"
        config.gemini_api_key = "test-key"
        backend = create_backend(config)
        assert isinstance(backend, GeminiBackend)
        assert backend.backend_type == LLMBackendType.GEMINI

    def test_create_lmstudio(self, config: JarvisConfig) -> None:
        config.llm_backend_type = "lmstudio"
        backend = create_backend(config)
        assert isinstance(backend, OpenAIBackend)

    def test_create_groq(self, config: JarvisConfig) -> None:
        config.llm_backend_type = "groq"
        config.groq_api_key = "gsk-test"
        backend = create_backend(config)
        assert isinstance(backend, OpenAIBackend)

    def test_create_deepseek(self, config: JarvisConfig) -> None:
        config.llm_backend_type = "deepseek"
        config.deepseek_api_key = "sk-test"
        backend = create_backend(config)
        assert isinstance(backend, OpenAIBackend)


# ============================================================================
# OpenAIBackend
# ============================================================================


class TestOpenAIBackend:
    def _make_backend(self) -> OpenAIBackend:
        return OpenAIBackend(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            timeout=30,
        )

    def test_backend_type(self) -> None:
        backend = self._make_backend()
        assert backend.backend_type == LLMBackendType.OPENAI

    def test_is_reasoning_model(self) -> None:
        backend = self._make_backend()
        assert backend._is_reasoning_model("o1") is True
        assert backend._is_reasoning_model("o1-mini") is True
        assert backend._is_reasoning_model("o3-preview") is True
        assert backend._is_reasoning_model("o4-mini") is True
        assert backend._is_reasoning_model("gpt-5") is True
        assert backend._is_reasoning_model("gpt-5.1-mini") is True
        assert backend._is_reasoning_model("gpt-5.2-pro") is True
        assert backend._is_reasoning_model("gpt-4") is False
        assert backend._is_reasoning_model("gpt-4o") is False
        assert backend._is_reasoning_model("claude-3-opus") is False

    @pytest.mark.asyncio
    async def test_chat(self) -> None:
        backend = self._make_backend()
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {"role": "assistant", "content": "Hello!", "tool_calls": None},
            }],
            "model": "gpt-4",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.object(backend, "_ensure_client", return_value=mock_client):
            result = await backend.chat(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hi"}],
            )
        assert isinstance(result, ChatResponse)
        assert result.content == "Hello!"
        assert result.model == "gpt-4"

    @pytest.mark.asyncio
    async def test_chat_with_tools(self) -> None:
        backend = self._make_backend()
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"function": {"name": "web_search", "arguments": '{"q":"test"}'}},
                    ],
                },
            }],
            "model": "gpt-4",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.object(backend, "_ensure_client", return_value=mock_client):
            result = await backend.chat(
                model="gpt-4",
                messages=[{"role": "user", "content": "Search"}],
                tools=[{"function": {"name": "web_search"}}],
            )
        assert isinstance(result, ChatResponse)
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1

    @pytest.mark.asyncio
    async def test_chat_http_error(self) -> None:
        backend = self._make_backend()
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.object(backend, "_ensure_client", return_value=mock_client):
            with pytest.raises(LLMBackendError, match="OpenAI HTTP 500"):
                await backend.chat(
                    model="gpt-4",
                    messages=[{"role": "user", "content": "Hi"}],
                )

    @pytest.mark.asyncio
    async def test_chat_reasoning_model_no_temperature(self) -> None:
        """Reasoning models (o1, o3, gpt-5) should not send temperature/top_p."""
        backend = self._make_backend()
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Hi"}}],
            "model": "o3-mini",
            "usage": {},
        }
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.object(backend, "_ensure_client", return_value=mock_client):
            result = await backend.chat(
                model="o3-mini",
                messages=[{"role": "user", "content": "Hi"}],
            )
        assert isinstance(result, ChatResponse)
        # Check that post was called without temperature in payload
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert "temperature" not in payload

    @pytest.mark.asyncio
    async def test_is_available_true(self) -> None:
        backend = self._make_backend()
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(backend, "_ensure_client", return_value=mock_client):
            result = await backend.is_available()
        assert result is True

    @pytest.mark.asyncio
    async def test_embed(self) -> None:
        backend = self._make_backend()
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3]}],
        }
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.object(backend, "_ensure_client", return_value=mock_client):
            result = await backend.embed("text-embedding-3-small", "Hello")
        assert isinstance(result, EmbedResponse)
        assert result.embedding == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        backend = self._make_backend()
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        backend._client = mock_client

        await backend.close()
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_already_closed(self) -> None:
        backend = self._make_backend()
        backend._client = None
        await backend.close()  # Should not raise


# ============================================================================
# AnthropicBackend
# ============================================================================


class TestAnthropicBackend:
    def _make_backend(self) -> AnthropicBackend:
        return AnthropicBackend(
            api_key="sk-ant-test",
            timeout=30,
            max_tokens=4096,
        )

    def test_backend_type(self) -> None:
        backend = self._make_backend()
        assert backend.backend_type == LLMBackendType.ANTHROPIC

    @pytest.mark.asyncio
    async def test_embed_not_supported(self) -> None:
        backend = self._make_backend()
        with pytest.raises(LLMBackendError, match="Embedding"):
            await backend.embed("model", "text")

    @pytest.mark.asyncio
    async def test_list_models(self) -> None:
        backend = self._make_backend()
        models = await backend.list_models()
        assert isinstance(models, list)
        assert len(models) > 0

    @pytest.mark.asyncio
    async def test_chat(self) -> None:
        backend = self._make_backend()
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "Hello!"}],
            "model": "claude-3-opus",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.object(backend, "_ensure_client", return_value=mock_client):
            result = await backend.chat(
                model="claude-3-opus",
                messages=[
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hi"},
                ],
            )
        assert isinstance(result, ChatResponse)
        assert "Hello!" in result.content

    def test_convert_tools_to_anthropic(self) -> None:
        tools = [
            {"function": {"name": "search", "description": "Search the web", "parameters": {"type": "object"}}},
            {"name": "read", "description": "Read a file", "inputSchema": {"type": "object"}},
        ]
        converted = AnthropicBackend._convert_tools_to_anthropic(tools)
        assert len(converted) == 2
        assert converted[0]["name"] == "search"
        assert converted[1]["name"] == "read"


# ============================================================================
# GeminiBackend
# ============================================================================


class TestGeminiBackend:
    def _make_backend(self) -> GeminiBackend:
        return GeminiBackend(api_key="test-key", timeout=30)

    def test_backend_type(self) -> None:
        backend = self._make_backend()
        assert backend.backend_type == LLMBackendType.GEMINI

    def test_convert_messages(self) -> None:
        messages = [
            {"role": "system", "content": "You are a helper."},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        system_text, contents = GeminiBackend._convert_messages(messages)
        assert "helper" in system_text
        assert len(contents) == 2
        assert contents[0]["role"] == "user"
        assert contents[1]["role"] == "model"

    def test_convert_tools_to_gemini(self) -> None:
        tools = [
            {"function": {"name": "search", "description": "Search", "parameters": {"type": "object"}}},
            {"name": "read", "description": "Read file", "inputSchema": {"type": "object"}},
        ]
        declarations = GeminiBackend._convert_tools_to_gemini(tools)
        assert len(declarations) == 2
        assert declarations[0]["name"] == "search"
        assert declarations[1]["name"] == "read"


# ============================================================================
# OllamaBackend
# ============================================================================


class TestOllamaBackend:
    def _make_backend(self) -> OllamaBackend:
        return OllamaBackend(
            base_url="http://localhost:11434",
            timeout=30,
        )

    def test_backend_type(self) -> None:
        backend = self._make_backend()
        assert backend.backend_type == LLMBackendType.OLLAMA

    @pytest.mark.asyncio
    async def test_close_no_client(self) -> None:
        backend = self._make_backend()
        backend._client = None
        await backend.close()  # Should not raise
