"""End-to-End scenario tests -- simulate REAL user interactions through the PGE pipeline.

These tests validate the full Gateway.handle_message() flow with mocked LLM
responses that simulate realistic German-language interactions. They test
BEHAVIOR, not implementation details.

Scenarios:
  1.  Greeting -- direct response, no tool calls
  2.  Factual question -- triggers web search tool
  3.  File operations -- read_file / write_file
  4.  Code generation -- autonomous write + run + fix loop
  5.  Memory operations -- search/save memory
  6.  Response quality -- German, no JSON leakage, no meta text
  7.  Edge cases -- empty, long, unicode, ambiguous
  8.  Multi-step tool chains -- multiple tools in sequence
  9.  Streaming events -- tool_start / tool_result callbacks
  10. Session persistence -- context across messages
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.config import JarvisConfig, ensure_directory_structure
from jarvis.core.executor import Executor
from jarvis.core.gatekeeper import Gatekeeper
from jarvis.core.planner import Planner
from jarvis.gateway.gateway import Gateway
from jarvis.models import IncomingMessage

# =============================================================================
# Helpers
# =============================================================================


@dataclass
class MockCallToolResult:
    """Lightweight mock for MCP call_tool return values."""

    content: str = "tool output"
    is_error: bool = False


def _llm_response(text: str) -> dict[str, Any]:
    """Build an Ollama-style chat response dict."""
    return {"message": {"role": "assistant", "content": text}}


def _plan_json(
    steps: list[dict[str, Any]],
    goal: str = "Testaufgabe",
    reasoning: str = "Schritte geplant",
    confidence: float = 0.9,
) -> str:
    """Return a plan as a JSON code block, the way the LLM emits it."""
    plan = {
        "goal": goal,
        "reasoning": reasoning,
        "steps": steps,
        "confidence": confidence,
    }
    return f"```json\n{json.dumps(plan, ensure_ascii=False)}\n```"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def gateway_with_mocks(tmp_path):
    """Creates a fully wired Gateway with mocked LLM + tools.

    Returns (gateway, mock_ollama, mock_mcp, tmp_path) so tests can configure
    LLM responses and tool results per-scenario.
    """
    from jarvis.config import SecurityConfig

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    cfg = JarvisConfig(
        jarvis_home=tmp_path / ".jarvis",
        security=SecurityConfig(
            allowed_paths=[
                str(tmp_path / ".jarvis"),
                str(sandbox),
                str(tmp_path),
            ],
        ),
    )
    ensure_directory_structure(cfg)
    gw = Gateway(cfg)

    mock_ollama = AsyncMock()
    mock_ollama.is_available = AsyncMock(return_value=True)

    mock_router = MagicMock()
    mock_router.select_model.return_value = "test-model"
    mock_router.get_model_config.return_value = {
        "temperature": 0.7,
        "top_p": 0.9,
        "context_window": 32768,
    }
    mock_router.initialize = AsyncMock()
    mock_router.set_coding_override = MagicMock()
    mock_router.clear_coding_override = MagicMock()

    mock_mcp = MagicMock()
    mock_mcp.get_tool_schemas.return_value = {
        "read_file": {"description": "Read a file"},
        "web_search": {"description": "Search the web"},
        "search_and_read": {"description": "Search and read web pages"},
        "write_file": {"description": "Write a file"},
        "run_python": {"description": "Run Python code"},
        "search_memory": {"description": "Search memory"},
        "save_to_memory": {"description": "Save to memory"},
    }
    mock_mcp.get_tool_list.return_value = [
        "read_file",
        "web_search",
        "search_and_read",
        "write_file",
        "run_python",
        "search_memory",
        "save_to_memory",
    ]
    mock_mcp.call_tool = AsyncMock(return_value=MockCallToolResult())
    mock_mcp.disconnect_all = AsyncMock()

    gw._planner = Planner(cfg, mock_ollama, mock_router)
    gw._gatekeeper = Gatekeeper(cfg)
    gw._gatekeeper.initialize()
    gw._executor = Executor(cfg, mock_mcp)
    gw._mcp_client = mock_mcp
    gw._ollama = mock_ollama
    gw._model_router = mock_router
    gw._running = True

    return gw, mock_ollama, mock_mcp, tmp_path


# =============================================================================
# 1. Greeting -- Direct Response (no tools)
# =============================================================================


class TestGreeting:
    """User says hello -- Jarvis responds warmly, no tool calls."""

    @pytest.mark.asyncio
    async def test_simple_greeting_german(self, gateway_with_mocks):
        """'Hallo' produces a friendly German response, no JSON plan."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Hey! Was kann ich fuer dich tun?"),
        )

        msg = IncomingMessage(text="Hallo!", channel="webui", user_id="alex")
        response = await gw.handle_message(msg)

        assert response.text, "Response must not be empty"
        assert response.is_final
        assert len(response.text) < 500, "Greeting should be short"
        # No tools should have been called
        mock_mcp.call_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_greeting_not_json(self, gateway_with_mocks):
        """Greeting must return plain text, never a JSON plan."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Guten Morgen! Wie kann ich dir heute helfen?"),
        )

        msg = IncomingMessage(text="Guten Morgen!", channel="cli", user_id="alex")
        response = await gw.handle_message(msg)

        assert response.text
        assert not response.text.strip().startswith("```json"), (
            "Greeting must not be a JSON code block"
        )
        assert '"steps"' not in response.text
        assert '"tool"' not in response.text

    @pytest.mark.asyncio
    async def test_goodbye_message(self, gateway_with_mocks):
        """'Tschuess' produces a farewell, no tool calls."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Bis bald! Melde dich jederzeit."),
        )

        msg = IncomingMessage(text="Tschuess!", channel="webui", user_id="alex")
        response = await gw.handle_message(msg)

        assert response.text
        assert response.is_final
        mock_mcp.call_tool.assert_not_called()


# =============================================================================
# 2. Factual Question -- Web Search
# =============================================================================


class TestFactualQuestion:
    """User asks about current events -- Jarvis uses search_and_read."""

    @pytest.mark.asyncio
    async def test_current_event_triggers_search(self, gateway_with_mocks):
        """'Was ist heute passiert?' produces a plan with search_and_read."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: Planner returns a search plan
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "search_and_read",
                                "params": {"query": "aktuelle Nachrichten heute"},
                                "rationale": "Web-Recherche fuer aktuelle Ereignisse",
                            }
                        ],
                        goal="Aktuelle Nachrichten recherchieren",
                        reasoning="User fragt nach aktuellen Ereignissen",
                    )
                )
            # Subsequent calls: formulate response from results
            return _llm_response(
                "Heute gab es folgende wichtige Ereignisse: Die EU hat neue Klimaziele beschlossen."
            )

        mock_ollama.chat = mock_chat
        mock_mcp.call_tool = AsyncMock(
            return_value=MockCallToolResult(
                content="Breaking: EU beschliesst neue Klimaziele fuer 2030."
            ),
        )

        msg = IncomingMessage(
            text="Was ist heute in der Welt passiert?",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        assert response.is_final
        assert mock_mcp.call_tool.called, "search_and_read tool must be invoked"

    @pytest.mark.asyncio
    async def test_factual_answer_uses_search_content(self, gateway_with_mocks):
        """The LLM response should incorporate search results."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "web_search",
                                "params": {"query": "Hauptstadt Australien"},
                                "rationale": "Faktencheck",
                            }
                        ],
                        goal="Hauptstadt von Australien finden",
                    )
                )
            return _llm_response("Die Hauptstadt von Australien ist Canberra.")

        mock_ollama.chat = mock_chat
        mock_mcp.call_tool = AsyncMock(
            return_value=MockCallToolResult(content="Canberra ist die Hauptstadt von Australien."),
        )

        msg = IncomingMessage(
            text="Was ist die Hauptstadt von Australien?",
            channel="cli",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        assert "Canberra" in response.text


# =============================================================================
# 3. File Operations -- Read + Write
# =============================================================================


class TestFileOperation:
    """User asks to read or write files -- Jarvis plans read_file/write_file."""

    @pytest.mark.asyncio
    async def test_read_file_request(self, gateway_with_mocks):
        """User asks to see a file -- plan uses read_file, response includes content."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        # Use a relative path -- Gatekeeper resolves it to workspace under jarvis_home
        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "read_file",
                                "params": {"path": "notes.txt"},
                                "rationale": "Datei lesen wie angefragt",
                            }
                        ],
                        goal="Datei notes.txt lesen",
                    )
                )
            return _llm_response(
                "Die Datei notes.txt enthaelt folgende Notizen:\n"
                "- Einkaufen gehen\n- Zahnarzt Termin"
            )

        mock_ollama.chat = mock_chat
        mock_mcp.call_tool = AsyncMock(
            return_value=MockCallToolResult(content="- Einkaufen gehen\n- Zahnarzt Termin"),
        )

        msg = IncomingMessage(
            text="Zeig mir den Inhalt von notes.txt",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        assert mock_mcp.call_tool.called
        # The response should mention the file content
        assert "Einkaufen" in response.text or "notes" in response.text.lower()

    @pytest.mark.asyncio
    async def test_write_file_request(self, gateway_with_mocks):
        """User asks to create a file -- plan uses write_file with correct content."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "write_file",
                                "params": {
                                    "path": "todo.txt",
                                    "content": "Milch kaufen\nBrot kaufen",
                                },
                                "rationale": "Datei schreiben wie angefragt",
                            }
                        ],
                        goal="Todo-Datei erstellen",
                    )
                )
            return _llm_response("Ich habe die Datei todo.txt mit deiner Einkaufsliste erstellt.")

        mock_ollama.chat = mock_chat
        mock_mcp.call_tool = AsyncMock(
            return_value=MockCallToolResult(content="File written successfully"),
        )

        msg = IncomingMessage(
            text="Erstelle eine Datei todo.txt mit: Milch kaufen, Brot kaufen",
            channel="cli",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        assert response.is_final
        assert mock_mcp.call_tool.called


# =============================================================================
# 4. Code Generation -- Autonomous Loop
# =============================================================================


class TestCodeGeneration:
    """User wants code -- Jarvis writes, tests, and fixes autonomously."""

    @pytest.mark.asyncio
    async def test_simple_python_script(self, gateway_with_mocks):
        """User asks for a script -- plan: write_file + run_python, success."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "write_file",
                                "params": {
                                    "path": "hello.py",
                                    "content": "print('Hello World')",
                                },
                                "rationale": "Python-Script schreiben",
                            },
                            {
                                "tool": "run_python",
                                "params": {"code": "print('Hello World')"},
                                "rationale": "Script testen",
                                "depends_on": [0],
                            },
                        ],
                        goal="Python Hello-World Script erstellen und testen",
                    )
                )
            return _llm_response(
                "Ich habe das Script hello.py erstellt und getestet. Es gibt 'Hello World' aus."
            )

        mock_ollama.chat = mock_chat
        mock_mcp.call_tool = AsyncMock(
            return_value=MockCallToolResult(content="Hello World"),
        )

        msg = IncomingMessage(
            text="Schreib mir ein Python-Script das Hello World ausgibt",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        assert response.is_final
        assert mock_mcp.call_tool.call_count >= 1

    @pytest.mark.asyncio
    async def test_code_with_error_triggers_replan(self, gateway_with_mocks):
        """First run_python fails -- LLM replans -- second run succeeds."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Initial plan: run code
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "run_python",
                                "params": {"code": "print(1/0)"},
                                "rationale": "Code ausfuehren",
                            }
                        ],
                        goal="Code ausfuehren",
                    )
                )
            if call_count == 2:
                # Replan: fix the code
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "run_python",
                                "params": {"code": "print(42)"},
                                "rationale": "Code korrigiert und erneut ausfuehren",
                            }
                        ],
                        goal="Code-Fehler korrigieren",
                        reasoning="ZeroDivisionError behoben",
                    )
                )
            # Final response formulation
            return _llm_response(
                "Der Code hatte einen ZeroDivisionError. "
                "Ich habe ihn korrigiert und er gibt jetzt 42 aus."
            )

        mock_ollama.chat = mock_chat

        tool_call_count = 0

        async def mock_call_tool(tool_name, arguments=None, **kwargs):
            nonlocal tool_call_count
            tool_call_count += 1
            if tool_call_count == 1:
                return MockCallToolResult(
                    content="ZeroDivisionError: division by zero",
                    is_error=True,
                )
            return MockCallToolResult(content="42")

        mock_mcp.call_tool = mock_call_tool

        msg = IncomingMessage(
            text="Fuehre diesen Python-Code aus: print(1/0)",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        # The replan should have triggered at least 2 tool calls
        assert tool_call_count >= 2, "Error should trigger a replan with retry"


# =============================================================================
# 5. Memory Operations
# =============================================================================


class TestMemoryOperations:
    """User asks about something -- Jarvis checks or saves to memory."""

    @pytest.mark.asyncio
    async def test_memory_lookup(self, gateway_with_mocks):
        """'Was weisst du ueber Projekt X?' triggers search_memory."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "search_memory",
                                "params": {"query": "Projekt Phoenix"},
                                "rationale": "Erinnerung an Projekt durchsuchen",
                            }
                        ],
                        goal="Informationen zu Projekt Phoenix finden",
                    )
                )
            return _llm_response(
                "Zu Projekt Phoenix habe ich folgende Informationen: "
                "Es ist ein Web-Projekt mit React-Frontend."
            )

        mock_ollama.chat = mock_chat
        mock_mcp.call_tool = AsyncMock(
            return_value=MockCallToolResult(
                content="Projekt Phoenix: Web-Projekt, React-Frontend, gestartet Q1 2026"
            ),
        )

        msg = IncomingMessage(
            text="Was weisst du ueber Projekt Phoenix?",
            channel="cli",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        assert mock_mcp.call_tool.called

    @pytest.mark.asyncio
    async def test_save_to_memory(self, gateway_with_mocks):
        """'Merk dir dass...' triggers save_to_memory."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "save_to_memory",
                                "params": {
                                    "content": "Alexanders Lieblingsfarbe ist blau",
                                    "category": "personal",
                                },
                                "rationale": "Information speichern wie angefragt",
                            }
                        ],
                        goal="Information in Erinnerung speichern",
                    )
                )
            return _llm_response(
                "Alles klar, ich habe mir gemerkt dass deine Lieblingsfarbe blau ist."
            )

        mock_ollama.chat = mock_chat
        mock_mcp.call_tool = AsyncMock(
            return_value=MockCallToolResult(content="Memory saved successfully"),
        )

        msg = IncomingMessage(
            text="Merk dir dass meine Lieblingsfarbe blau ist",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        assert mock_mcp.call_tool.called


# =============================================================================
# 6. Response Quality Validation
# =============================================================================


class TestResponseQuality:
    """Validate response characteristics regardless of content."""

    @pytest.mark.asyncio
    async def test_response_is_german(self, gateway_with_mocks):
        """Response to a German question should be in German."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Das Wetter in Berlin ist heute sonnig mit 22 Grad."),
        )

        msg = IncomingMessage(
            text="Wie ist das Wetter heute?",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        # Check for common German words/patterns
        german_indicators = ["ist", "das", "der", "die", "ein", "und", "mit", "heute"]
        has_german = any(word in response.text.lower() for word in german_indicators)
        assert has_german, f"Response should contain German text, got: {response.text[:200]}"

    @pytest.mark.asyncio
    async def test_response_not_json_plan(self, gateway_with_mocks):
        """Direct answer must never contain a raw JSON plan."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response(
                "Python ist eine vielseitige Programmiersprache, "
                "die fuer Webentwicklung, Data Science und KI eingesetzt wird."
            ),
        )

        msg = IncomingMessage(
            text="Was ist Python?",
            channel="cli",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        assert "```json" not in response.text, "Response must not contain JSON code blocks"
        assert '"steps"' not in response.text
        assert '"confidence"' not in response.text

    @pytest.mark.asyncio
    async def test_response_not_too_long(self, gateway_with_mocks):
        """Simple question should produce a concise answer (< 1000 chars)."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("2 + 2 = 4."),
        )

        msg = IncomingMessage(
            text="Was ist 2 + 2?",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        assert len(response.text) < 1000, (
            f"Simple question answer too long: {len(response.text)} chars"
        )

    @pytest.mark.asyncio
    async def test_response_not_empty(self, gateway_with_mocks):
        """Every message must get a non-empty response."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Hallo! Wie kann ich helfen?"),
        )

        msg = IncomingMessage(text="Hi", channel="webui", user_id="alex")
        response = await gw.handle_message(msg)

        assert response.text, "Response must never be empty"
        assert len(response.text.strip()) > 0

    @pytest.mark.asyncio
    async def test_no_meta_planning_text(self, gateway_with_mocks):
        """Response must not contain internal planning markers."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Hier ist eine kurze Zusammenfassung der aktuellen Lage."),
        )

        msg = IncomingMessage(
            text="Was gibt es Neues?",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        forbidden_markers = [
            "REPLAN-GRUND:",
            "KORRIGIERTER PLAN:",
            "BETROFFENE SCHRITTE:",
            "AKTUALISIERTE RISIKOBEWERTUNG:",
            "CORRECTED PLAN:",
        ]
        for marker in forbidden_markers:
            assert marker not in response.text, f"Response leaked internal planning text: {marker}"

    @pytest.mark.asyncio
    async def test_no_english_system_leakage(self, gateway_with_mocks):
        """Response should not contain system prompt fragments."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Klar, ich helfe dir gerne!"),
        )

        msg = IncomingMessage(
            text="Hilf mir bitte!",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        leakage_fragments = [
            "You are Jarvis",
            "SYSTEM_PROMPT",
            "REPLAN_PROMPT",
            "system prompt",
            "I am an AI assistant",
        ]
        for fragment in leakage_fragments:
            assert fragment not in response.text, f"System prompt leaked: {fragment}"


# =============================================================================
# 7. Edge Cases
# =============================================================================


class TestEdgeCases:
    """Unusual inputs that should be handled gracefully."""

    @pytest.mark.asyncio
    async def test_empty_message(self, gateway_with_mocks):
        """Empty string should produce a polite prompt, not crash."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response(
                "Ich habe keine Nachricht erhalten. Wie kann ich dir helfen?"
            ),
        )

        msg = IncomingMessage(text="", channel="webui", user_id="alex")
        response = await gw.handle_message(msg)

        # Must not crash, must return something
        assert response is not None
        assert response.is_final

    @pytest.mark.asyncio
    async def test_very_long_message(self, gateway_with_mocks):
        """10000 character message should not crash."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response(
                "Das ist eine sehr lange Nachricht. "
                "Ich habe sie verarbeitet. Wie kann ich weiterhelfen?"
            ),
        )

        long_text = "Bitte hilf mir. " * 625  # ~10000 chars
        msg = IncomingMessage(text=long_text, channel="webui", user_id="alex")
        response = await gw.handle_message(msg)

        assert response is not None
        assert response.text
        assert response.is_final

    @pytest.mark.asyncio
    async def test_unicode_message(self, gateway_with_mocks):
        """Emojis, CJK, Arabic -- handled correctly without crash."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response(
                "Ich sehe verschiedene Zeichen in deiner Nachricht. Alles klar!"
            ),
        )

        msg = IncomingMessage(
            text="Hallo! \U0001f44b \u4f60\u597d \u0645\u0631\u062d\u0628\u0627 \U0001f600",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response is not None
        assert response.text
        assert response.is_final

    @pytest.mark.asyncio
    async def test_ambiguous_request(self, gateway_with_mocks):
        """Vague request like 'Mach das' should produce a clarification."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response(
                "Was genau moechtest du? Bitte beschreibe genauer, was ich fuer dich tun soll."
            ),
        )

        msg = IncomingMessage(text="Mach das", channel="webui", user_id="alex")
        response = await gw.handle_message(msg)

        assert response.text
        assert response.is_final

    @pytest.mark.asyncio
    async def test_special_characters_in_message(self, gateway_with_mocks):
        """SQL injection / shell injection patterns should not crash."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Ich kann diese Anfrage leider nicht verarbeiten."),
        )

        msg = IncomingMessage(
            text="'; DROP TABLE users; --",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response is not None
        assert response.is_final


# =============================================================================
# 8. Multi-Step Tool Chain
# =============================================================================


class TestMultiStepPlan:
    """Complex tasks requiring multiple tools in sequence."""

    @pytest.mark.asyncio
    async def test_search_then_summarize(self, gateway_with_mocks):
        """search_and_read then formulate -- both tools called in order."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "search_and_read",
                                "params": {"query": "Python 3.13 neue Features"},
                                "rationale": "Recherche zu Python 3.13",
                            },
                            {
                                "tool": "search_and_read",
                                "params": {"query": "Python 3.13 performance"},
                                "rationale": "Performance-Verbesserungen recherchieren",
                                "depends_on": [],
                            },
                        ],
                        goal="Python 3.13 Features recherchieren und zusammenfassen",
                    )
                )
            return _llm_response(
                "Python 3.13 bringt folgende Neuerungen:\n"
                "1. Verbesserte Fehlermeldungen\n"
                "2. Performance-Optimierungen\n"
                "3. Neues typing-Modul"
            )

        mock_ollama.chat = mock_chat
        mock_mcp.call_tool = AsyncMock(
            return_value=MockCallToolResult(
                content="Python 3.13 features: improved error messages, "
                "faster startup, new typing features"
            ),
        )

        msg = IncomingMessage(
            text="Recherchiere was es Neues in Python 3.13 gibt und fasse zusammen",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        assert response.is_final
        # Both search_and_read calls should execute
        assert mock_mcp.call_tool.call_count >= 2, (
            f"Expected at least 2 tool calls, got {mock_mcp.call_tool.call_count}"
        )

    @pytest.mark.asyncio
    async def test_read_then_write(self, gateway_with_mocks):
        """Read a file then write a modified version."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "read_file",
                                "params": {"path": "config.yaml"},
                                "rationale": "Aktuelle Config lesen",
                            },
                            {
                                "tool": "write_file",
                                "params": {
                                    "path": "config.yaml",
                                    "content": "debug: true\nport: 8080",
                                },
                                "rationale": "Config aktualisieren",
                                "depends_on": [0],
                            },
                        ],
                        goal="Config-Datei aktualisieren",
                    )
                )
            return _llm_response("Ich habe die Config gelesen und den Debug-Modus aktiviert.")

        mock_ollama.chat = mock_chat
        mock_mcp.call_tool = AsyncMock(
            return_value=MockCallToolResult(content="debug: false\nport: 8080"),
        )

        msg = IncomingMessage(
            text="Oeffne config.yaml und aktiviere den Debug-Modus",
            channel="cli",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        assert mock_mcp.call_tool.call_count >= 2


# =============================================================================
# 9. Streaming Events
# =============================================================================


class TestStreaming:
    """Verify streaming callback sends correct events."""

    @pytest.mark.asyncio
    async def test_tool_events_sent(self, gateway_with_mocks):
        """With stream_callback, tool_start and tool_result events are emitted."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "web_search",
                                "params": {"query": "test"},
                                "rationale": "Suche",
                            }
                        ],
                        goal="Websuche durchfuehren",
                    )
                )
            return _llm_response("Hier sind die Suchergebnisse.")

        mock_ollama.chat = mock_chat
        mock_mcp.call_tool = AsyncMock(
            return_value=MockCallToolResult(content="Search results: test page"),
        )

        events: list[tuple[str, dict]] = []

        async def capture_callback(event_type, data):
            events.append((event_type, data))

        msg = IncomingMessage(
            text="Suche nach test",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg, stream_callback=capture_callback)

        assert response.text

        tool_starts = [e for e in events if e[0] == "tool_start"]
        tool_results = [e for e in events if e[0] == "tool_result"]
        assert len(tool_starts) >= 1, f"Expected tool_start events, got: {[e[0] for e in events]}"
        assert len(tool_results) >= 1, f"Expected tool_result events, got: {[e[0] for e in events]}"

    @pytest.mark.asyncio
    async def test_tool_start_contains_tool_name(self, gateway_with_mocks):
        """tool_start event data must include the tool name."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "read_file",
                                "params": {"path": "test.txt"},
                                "rationale": "Lesen",
                            }
                        ],
                        goal="Datei lesen",
                    )
                )
            return _llm_response("Datei gelesen.")

        mock_ollama.chat = mock_chat
        mock_mcp.call_tool = AsyncMock(
            return_value=MockCallToolResult(content="file content"),
        )

        events: list[tuple[str, dict]] = []

        async def capture_callback(event_type, data):
            events.append((event_type, data))

        msg = IncomingMessage(
            text="Lies test.txt",
            channel="webui",
            user_id="alex",
        )
        await gw.handle_message(msg, stream_callback=capture_callback)

        tool_starts = [e for e in events if e[0] == "tool_start"]
        assert len(tool_starts) >= 1
        assert "tool" in tool_starts[0][1], "tool_start event must contain 'tool' key"
        assert tool_starts[0][1]["tool"] == "read_file"

    @pytest.mark.asyncio
    async def test_tool_result_contains_success_flag(self, gateway_with_mocks):
        """tool_result event data must include the success flag."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "web_search",
                                "params": {"query": "test query"},
                                "rationale": "Suche",
                            }
                        ],
                        goal="Suche",
                    )
                )
            return _llm_response("Ergebnisse gefunden.")

        mock_ollama.chat = mock_chat
        mock_mcp.call_tool = AsyncMock(
            return_value=MockCallToolResult(content="results"),
        )

        events: list[tuple[str, dict]] = []

        async def capture_callback(event_type, data):
            events.append((event_type, data))

        msg = IncomingMessage(
            text="Suche nach test query",
            channel="webui",
            user_id="alex",
        )
        await gw.handle_message(msg, stream_callback=capture_callback)

        tool_results = [e for e in events if e[0] == "tool_result"]
        assert len(tool_results) >= 1
        assert "success" in tool_results[0][1], "tool_result event must contain 'success' key"


# =============================================================================
# 10. Session Persistence
# =============================================================================


class TestSessionPersistence:
    """Verify session state is maintained across messages."""

    @pytest.mark.asyncio
    async def test_second_message_reuses_session(self, gateway_with_mocks):
        """Two messages from the same user/channel share a session."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Antwort eins."),
        )

        msg1 = IncomingMessage(text="Erste Nachricht", channel="webui", user_id="alex")
        resp1 = await gw.handle_message(msg1)

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Antwort zwei."),
        )

        msg2 = IncomingMessage(text="Zweite Nachricht", channel="webui", user_id="alex")
        resp2 = await gw.handle_message(msg2)

        assert resp1.session_id == resp2.session_id, (
            "Same user+channel should reuse the same session"
        )

    @pytest.mark.asyncio
    async def test_different_users_get_different_sessions(self, gateway_with_mocks):
        """Different user_ids get separate sessions."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Hallo!"),
        )

        msg1 = IncomingMessage(text="Hi", channel="webui", user_id="alice")
        resp1 = await gw.handle_message(msg1)

        msg2 = IncomingMessage(text="Hi", channel="webui", user_id="bob")
        resp2 = await gw.handle_message(msg2)

        assert resp1.session_id != resp2.session_id, "Different users must get different sessions"

    @pytest.mark.asyncio
    async def test_working_memory_persists_across_messages(self, gateway_with_mocks):
        """Working memory should contain history from previous messages."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Hallo Alex!"),
        )

        msg1 = IncomingMessage(
            text="Ich heisse Alexander",
            channel="webui",
            user_id="alex",
        )
        await gw.handle_message(msg1)

        # Retrieve the working memory for this session
        session = gw._get_or_create_session("webui", "alex")
        wm = gw._get_or_create_working_memory(session)

        # Working memory should contain the user's first message
        history_texts = [m.content for m in wm.chat_history]
        has_user_msg = any("Alexander" in t for t in history_texts)
        assert has_user_msg, (
            f"Working memory should contain first user message. History: {history_texts}"
        )

    @pytest.mark.asyncio
    async def test_different_channels_separate_sessions(self, gateway_with_mocks):
        """Same user on different channels gets separate sessions."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Hallo!"),
        )

        msg1 = IncomingMessage(text="Hi", channel="webui", user_id="alex")
        resp1 = await gw.handle_message(msg1)

        msg2 = IncomingMessage(text="Hi", channel="telegram", user_id="alex")
        resp2 = await gw.handle_message(msg2)

        assert resp1.session_id != resp2.session_id, (
            "Same user on different channels should get separate sessions"
        )


# =============================================================================
# 11. Gatekeeper Blocking
# =============================================================================


class TestGatekeeperBlocking:
    """Verify dangerous operations are blocked by the Gatekeeper."""

    @pytest.mark.asyncio
    async def test_blocked_tool_returns_error_message(self, gateway_with_mocks):
        """A plan with a RED-risk tool should be blocked and explained."""
        gw, mock_ollama, mock_mcp, _sandbox = gateway_with_mocks

        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _llm_response(
                    _plan_json(
                        [
                            {
                                "tool": "exec_command",
                                "params": {"command": "rm -rf /"},
                                "rationale": "System loeschen",
                            }
                        ],
                        goal="System loeschen",
                    )
                )
            return _llm_response("Aktion blockiert.")

        mock_ollama.chat = mock_chat

        msg = IncomingMessage(
            text="Loesche alles auf dem System",
            channel="webui",
            user_id="alex",
        )
        response = await gw.handle_message(msg)

        assert response.text
        assert response.is_final
        # The tool should NOT have been executed
        mock_mcp.call_tool.assert_not_called()


# =============================================================================
# 12. Response Channel Metadata
# =============================================================================


class TestResponseMetadata:
    """Verify OutgoingMessage has correct metadata."""

    @pytest.mark.asyncio
    async def test_response_channel_matches_request(self, gateway_with_mocks):
        """Response channel must match the incoming message channel."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Test response"),
        )

        for channel in ["webui", "cli", "telegram", "api"]:
            msg = IncomingMessage(
                text="Test",
                channel=channel,
                user_id="alex",
            )
            response = await gw.handle_message(msg)
            assert response.channel == channel, (
                f"Response channel {response.channel} != request channel {channel}"
            )

    @pytest.mark.asyncio
    async def test_response_always_final(self, gateway_with_mocks):
        """handle_message always returns is_final=True."""
        gw, mock_ollama, _, _sandbox = gateway_with_mocks

        mock_ollama.chat = AsyncMock(
            return_value=_llm_response("Antwort"),
        )

        msg = IncomingMessage(text="Test", channel="webui", user_id="alex")
        response = await gw.handle_message(msg)

        assert response.is_final is True
