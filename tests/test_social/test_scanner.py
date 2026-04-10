"""Tests for social.scanner — Reddit JSON fetch + LLM scoring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cognithor.social.scanner import RedditScanner, ScanConfig


class TestRedditScanner:
    def test_create(self):
        scanner = RedditScanner(llm_fn=AsyncMock())
        assert scanner is not None

    @pytest.mark.asyncio
    async def test_fetch_posts_returns_list(self):
        scanner = RedditScanner(llm_fn=AsyncMock())
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc",
                            "title": "Test post",
                            "selftext": "body",
                            "subreddit": "LocalLLaMA",
                            "permalink": "/r/LocalLLaMA/abc",
                            "author": "user1",
                            "created_utc": 1700000000,
                            "score": 10,
                            "num_comments": 5,
                        }
                    },
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.Client.get", return_value=mock_response):
            posts = scanner.fetch_posts("LocalLLaMA", limit=10)
        assert len(posts) == 1
        assert posts[0]["id"] == "abc"
        assert posts[0]["subreddit"] == "LocalLLaMA"

    @pytest.mark.asyncio
    async def test_score_post(self):
        llm_fn = AsyncMock(
            return_value={"message": {"content": '{"score": 75, "reasoning": "Direct match"}'}}
        )
        scanner = RedditScanner(llm_fn=llm_fn)
        config = ScanConfig(product_name="Cognithor", product_description="AI OS")
        score, reason = await scanner.score_post(
            {
                "title": "Need local AI agent",
                "selftext": "Looking for tools",
                "subreddit": "LocalLLaMA",
            },
            config,
        )
        assert score == 75
        assert "Direct match" in reason

    @pytest.mark.asyncio
    async def test_score_post_invalid_json_returns_zero(self):
        llm_fn = AsyncMock(return_value={"message": {"content": "I cannot score this post"}})
        scanner = RedditScanner(llm_fn=llm_fn)
        config = ScanConfig(product_name="X", product_description="Y")
        score, reason = await scanner.score_post(
            {"title": "Random", "selftext": "", "subreddit": "test"},
            config,
        )
        assert score == 0

    @pytest.mark.asyncio
    async def test_draft_reply(self):
        llm_fn = AsyncMock(
            return_value={"message": {"content": "Check out Cognithor — it does exactly this."}}
        )
        scanner = RedditScanner(llm_fn=llm_fn)
        config = ScanConfig(
            product_name="Cognithor",
            product_description="AI OS",
            reply_tone="helpful, no sales pitch",
        )
        draft = await scanner.draft_reply(
            {"title": "Need tool", "selftext": "Help", "subreddit": "SaaS"},
            config,
        )
        assert "Cognithor" in draft

    def test_fetch_posts_handles_error(self):
        scanner = RedditScanner(llm_fn=AsyncMock())
        with patch("httpx.Client.get", side_effect=Exception("Network error")):
            posts = scanner.fetch_posts("NonExistent", limit=10)
        assert posts == []
