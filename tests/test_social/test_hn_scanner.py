"""Tests for social.hn_scanner — Hacker News fetch + LLM scoring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from cognithor.social.hn_scanner import HackerNewsScanner


def _mock_async_response(json_data, status_code=200):
    """Create a mock httpx.Response for async client."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


class TestHackerNewsScanner:
    def test_create(self):
        scanner = HackerNewsScanner(llm_fn=AsyncMock())
        assert scanner is not None

    @pytest.mark.asyncio
    async def test_fetch_stories(self):
        scanner = HackerNewsScanner()

        story_ids_resp = _mock_async_response([101, 102])
        story_101 = _mock_async_response(
            {
                "id": 101,
                "type": "story",
                "title": "Show HN: My AI tool",
                "url": "https://example.com/ai",
                "score": 42,
                "descendants": 10,
                "time": 1700000000,
                "by": "hacker1",
            }
        )
        story_102 = _mock_async_response(
            {
                "id": 102,
                "type": "story",
                "title": "Ask HN: Best local LLM?",
                "url": "",
                "score": 15,
                "descendants": 25,
                "time": 1700000100,
                "by": "hacker2",
            }
        )

        responses = [story_ids_resp, story_101, story_102]
        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        with patch("cognithor.social.hn_scanner.asyncio.sleep", new_callable=AsyncMock):
            with patch("httpx.AsyncClient.get", side_effect=mock_get):
                stories = await scanner.fetch_stories(category="top", limit=5)

        assert len(stories) == 2
        assert stories[0]["id"] == 101
        assert stories[0]["title"] == "Show HN: My AI tool"
        assert stories[1]["by"] == "hacker2"

    @pytest.mark.asyncio
    async def test_search_stories(self):
        scanner = HackerNewsScanner()

        algolia_resp = _mock_async_response(
            {
                "hits": [
                    {
                        "objectID": "999",
                        "title": "Local AI agents",
                        "url": "https://example.com",
                        "points": 50,
                        "num_comments": 12,
                        "author": "searcher1",
                    }
                ]
            }
        )

        async def mock_get(url, **kwargs):
            return algolia_resp

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            results = await scanner.search_stories("local AI agent", limit=10)

        assert len(results) == 1
        assert results[0]["objectID"] == "999"
        assert results[0]["points"] == 50

    @pytest.mark.asyncio
    async def test_score_story(self):
        llm_fn = AsyncMock(
            return_value={
                "message": {"content": '{"score": 82, "reasoning": "Direct match for AI tooling"}'}
            }
        )
        scanner = HackerNewsScanner(llm_fn=llm_fn)
        score, reason = await scanner.score_story(
            {
                "title": "Need local AI agent",
                "url": "https://example.com",
                "score": 50,
                "descendants": 20,
            },
            product_name="Cognithor",
            product_description="AI OS",
        )
        assert score == 82
        assert "Direct match" in reason
        llm_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_score_story_no_llm(self):
        scanner = HackerNewsScanner(llm_fn=None)
        score, reason = await scanner.score_story({"title": "Test"}, product_name="Cognithor")
        assert score == 0
        assert "No LLM" in reason

    @pytest.mark.asyncio
    async def test_scan_lifecycle(self):
        """Full scan: fetch stories, deduplicate, score, return leads."""
        llm_fn = AsyncMock(
            return_value={"message": {"content": '{"score": 75, "reasoning": "Good match"}'}}
        )
        scanner = HackerNewsScanner(llm_fn=llm_fn)

        # Mock fetch_stories to return controlled data
        async def mock_fetch(category="top", limit=30):
            if category == "top":
                return [
                    {
                        "id": 1,
                        "title": "Story A",
                        "url": "https://a.com",
                        "score": 10,
                        "descendants": 5,
                        "time": 0,
                        "by": "a",
                    },
                    {
                        "id": 2,
                        "title": "Story B",
                        "url": "https://b.com",
                        "score": 20,
                        "descendants": 3,
                        "time": 0,
                        "by": "b",
                    },
                ]
            return [
                {
                    "id": 2,
                    "title": "Story B",
                    "url": "https://b.com",
                    "score": 20,
                    "descendants": 3,
                    "time": 0,
                    "by": "b",
                },
                {
                    "id": 3,
                    "title": "Story C",
                    "url": "https://c.com",
                    "score": 5,
                    "descendants": 1,
                    "time": 0,
                    "by": "c",
                },
            ]

        with patch.object(scanner, "fetch_stories", side_effect=mock_fetch):
            result = await scanner.scan(
                product_name="Cognithor",
                product_description="AI OS",
                categories=["top", "new"],
                min_score=60,
            )

        # 3 unique stories (id 2 deduplicated)
        assert result["posts_checked"] == 3
        # All score 75 which is >= 60
        assert result["leads_found"] == 3
        assert len(result["leads"]) == 3
        # LLM called once per unique story
        assert llm_fn.call_count == 3

    @pytest.mark.asyncio
    async def test_fetch_stories_error_returns_empty(self):
        scanner = HackerNewsScanner()

        async def mock_get(url, **kwargs):
            raise httpx.ConnectError("Connection failed")

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            stories = await scanner.fetch_stories()

        assert stories == []

    @pytest.mark.asyncio
    async def test_search_stories_error_returns_empty(self):
        scanner = HackerNewsScanner()

        async def mock_get(url, **kwargs):
            raise httpx.ConnectError("Connection failed")

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            results = await scanner.search_stories("test")

        assert results == []
