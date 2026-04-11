"""Tests for social.discord_scanner — Discord channel fetch + LLM scoring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from cognithor.social.discord_scanner import DiscordScanner


def _mock_async_response(json_data, status_code=200):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


class TestDiscordScanner:
    def test_no_token_raises(self):
        with pytest.raises(ValueError, match="Discord bot token required"):
            DiscordScanner(bot_token="")

    def test_create(self):
        scanner = DiscordScanner(bot_token="test-token", llm_fn=AsyncMock())
        assert scanner is not None

    @pytest.mark.asyncio
    async def test_fetch_messages(self):
        scanner = DiscordScanner(bot_token="test-token")

        api_resp = _mock_async_response(
            [
                {
                    "id": "msg1",
                    "content": "Looking for an AI assistant tool",
                    "author": {"username": "user1"},
                    "timestamp": "2026-01-01T00:00:00Z",
                },
                {
                    "id": "msg2",
                    "content": "Has anyone tried local LLM agents?",
                    "author": {"username": "user2"},
                    "timestamp": "2026-01-01T01:00:00Z",
                },
                {
                    "id": "msg3",
                    "content": "",
                    "author": {"username": "bot"},
                    "timestamp": "2026-01-01T02:00:00Z",
                },
            ]
        )

        async def mock_get(url, **kwargs):
            return api_resp

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            messages = await scanner.fetch_messages("chan123", limit=50)

        # Empty content message filtered out
        assert len(messages) == 2
        assert messages[0]["id"] == "msg1"
        assert messages[0]["author"] == "user1"
        assert messages[1]["content"] == "Has anyone tried local LLM agents?"

    @pytest.mark.asyncio
    async def test_score_message(self):
        llm_fn = AsyncMock(
            return_value={
                "message": {"content": '{"score": 68, "reasoning": "Asking about AI agents"}'}
            }
        )
        scanner = DiscordScanner(bot_token="test-token", llm_fn=llm_fn)
        score, reason = await scanner.score_message(
            {"author": "user1", "content": "Need a local AI agent for automation"},
            product_name="Cognithor",
            product_description="AI OS",
        )
        assert score == 68
        assert "AI agents" in reason
        llm_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_score_message_no_llm(self):
        scanner = DiscordScanner(bot_token="test-token", llm_fn=None)
        score, reason = await scanner.score_message(
            {"author": "u", "content": "test"}, product_name="X"
        )
        assert score == 0
        assert "No LLM" in reason

    @pytest.mark.asyncio
    async def test_scan_channels(self):
        llm_fn = AsyncMock(
            return_value={"message": {"content": '{"score": 80, "reasoning": "Strong intent"}'}}
        )
        scanner = DiscordScanner(bot_token="test-token", llm_fn=llm_fn)

        async def mock_fetch(channel_id, limit=100):
            if channel_id == "c1":
                return [
                    {"id": "m1", "content": "Need AI tool", "author": "u1", "timestamp": "t1"},
                ]
            return [
                {"id": "m2", "content": "Any LLM recs?", "author": "u2", "timestamp": "t2"},
                {"id": "m3", "content": "Hello world", "author": "u3", "timestamp": "t3"},
            ]

        with patch.object(scanner, "fetch_messages", side_effect=mock_fetch):
            with patch("cognithor.social.discord_scanner.asyncio.sleep", new_callable=AsyncMock):
                result = await scanner.scan(
                    channel_ids=["c1", "c2"],
                    product_name="Cognithor",
                    min_score=60,
                )

        assert result["posts_checked"] == 3
        assert result["leads_found"] == 3
        assert len(result["leads"]) == 3
        assert llm_fn.call_count == 3

    @pytest.mark.asyncio
    async def test_empty_channel(self):
        scanner = DiscordScanner(bot_token="test-token", llm_fn=AsyncMock())

        async def mock_fetch(channel_id, limit=100):
            return []

        with patch.object(scanner, "fetch_messages", side_effect=mock_fetch):
            result = await scanner.scan(
                channel_ids=["empty1"],
                product_name="Cognithor",
                min_score=60,
            )

        assert result["posts_checked"] == 0
        assert result["leads_found"] == 0
        assert result["leads"] == []

    @pytest.mark.asyncio
    async def test_fetch_messages_error_returns_empty(self):
        scanner = DiscordScanner(bot_token="test-token")

        async def mock_get(url, **kwargs):
            raise httpx.ConnectError("Connection failed")

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            messages = await scanner.fetch_messages("bad_channel")

        assert messages == []
