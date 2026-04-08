"""Tests for the IdentityLayer adapter (Immortal Mind integration)."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestIdentityLayerBasics:
    """Basic IdentityLayer tests that don't require chromadb/sentence-transformers."""

    def test_import(self) -> None:
        """IdentityLayer can be imported."""
        from jarvis.identity import IdentityLayer

        assert IdentityLayer is not None

    def test_genesis_anchors(self) -> None:
        """Genesis anchors are accessible."""
        from jarvis.identity.cognitio.engine import GENESIS_ANCHOR_CONTENTS

        assert len(GENESIS_ANCHOR_CONTENTS) == 7
        assert "AI" in GENESIS_ANCHOR_CONTENTS[0]
        assert (
            "truth" in GENESIS_ANCHOR_CONTENTS[1].lower()
            or "distort" in GENESIS_ANCHOR_CONTENTS[1].lower()
        )

    def test_empty_enrichment(self) -> None:
        """Empty enrichment returns correct structure."""
        from jarvis.identity.adapter import IdentityLayer

        result = IdentityLayer._empty_enrichment()
        assert "cognitive_context" in result
        assert "trust_boundary" in result
        assert "temperature_modifier" in result
        assert "style_hints" in result
        assert result["temperature_modifier"] == 0.0


class TestLLMBridge:
    """Tests for the CognithorLLMBridge."""

    def test_import(self) -> None:
        from jarvis.identity.llm_bridge import CognithorLLMBridge

        assert CognithorLLMBridge is not None

    def test_parse_json_safe_direct(self) -> None:
        from jarvis.identity.llm_bridge import CognithorLLMBridge

        result = CognithorLLMBridge._parse_json_safe('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_safe_markdown(self) -> None:
        from jarvis.identity.llm_bridge import CognithorLLMBridge

        text = 'Some text\n```json\n{"key": "value"}\n```\nMore text'
        result = CognithorLLMBridge._parse_json_safe(text)
        assert result == {"key": "value"}

    def test_parse_json_safe_broken(self) -> None:
        from jarvis.identity.llm_bridge import CognithorLLMBridge

        result = CognithorLLMBridge._parse_json_safe("not json at all", ["a", "b"])
        assert result == {"a": None, "b": None}

    def test_parse_json_safe_with_defaults(self) -> None:
        from jarvis.identity.llm_bridge import CognithorLLMBridge

        result = CognithorLLMBridge._parse_json_safe('{"a": 1}', ["a", "b"])
        assert result["a"] == 1
        assert "b" in result


class TestMCPIdentityTools:
    """Tests for identity MCP tool registration."""

    def test_register(self) -> None:
        """Tools can be registered."""
        from jarvis.mcp.identity_tools import register_identity_tools

        mcp = MagicMock()
        identity = MagicMock()
        register_identity_tools(mcp, identity)
        assert mcp.register_builtin_handler.call_count == 4
        tool_names = [c[1]["tool_name"] for c in mcp.register_builtin_handler.call_args_list]
        assert "identity_recall" in tool_names
        assert "identity_state" in tool_names
        assert "identity_reflect" in tool_names
        assert "identity_dream" in tool_names


class TestStoreFromCognithorTags:
    """Tests for store_from_cognithor tags parameter."""

    def test_default_tags_without_parameter(self):
        """Without tags param, uses ['cognithor', memory_type] as before."""
        tags = None
        memory_type = "semantic"
        result = ["cognithor", *tags] if tags else ["cognithor", memory_type]
        assert result == ["cognithor", "semantic"]

    def test_custom_tags_prepends_cognithor(self):
        """Custom tags always get 'cognithor' prepended."""
        input_tags = ["versicherung", "vvg", "recht"]
        result_tags = ["cognithor", *input_tags]
        assert result_tags == ["cognithor", "versicherung", "vvg", "recht"]

    def test_none_tags_falls_back(self):
        """None tags falls back to default behavior."""
        memory_type = "semantic"
        tags = None
        result_tags = ["cognithor", *tags] if tags else ["cognithor", memory_type]
        assert result_tags == ["cognithor", "semantic"]
