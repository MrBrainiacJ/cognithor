"""Tests for MCP Reddit tools."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestRedditMcpTools:
    @pytest.mark.asyncio
    async def test_register_tools(self):
        from jarvis.mcp.reddit_tools import register_reddit_tools

        mcp = MagicMock()
        svc = MagicMock()
        register_reddit_tools(mcp, svc)
        assert mcp.register_builtin_handler.call_count == 6
        tool_names = [call[0][0] for call in mcp.register_builtin_handler.call_args_list]
        assert "reddit_scan" in tool_names
        assert "reddit_leads" in tool_names
        assert "reddit_reply" in tool_names
        assert "reddit_refine" in tool_names
        assert "reddit_discover_subreddits" in tool_names
        assert "reddit_templates" in tool_names
