"""Tests for social.discovery — smart subreddit discovery."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cognithor.social.discovery import SubredditDiscovery, SubredditSuggestion


class TestSubredditDiscovery:
    @pytest.mark.asyncio
    async def test_discover_returns_suggestions(self):
        llm_fn = AsyncMock(
            return_value={
                "message": {
                    "content": (
                        '["LocalLLaMA", "SaaS", "Python", "agentframework", "MachineLearning"]'
                    )
                }
            }
        )
        discovery = SubredditDiscovery(llm_fn=llm_fn)

        mock_about = MagicMock()
        mock_about.status_code = 200
        mock_about.json.return_value = {
            "data": {"subscribers": 50000, "active_user_count": 200, "display_name": "LocalLLaMA"}
        }

        with patch.object(discovery._http, "get", return_value=mock_about):
            results = await discovery.discover("Cognithor", "Open-source Agent OS")

        assert len(results) > 0
        assert all(isinstance(r, SubredditSuggestion) for r in results)

    @pytest.mark.asyncio
    async def test_discover_handles_nonexistent_subreddit(self):
        llm_fn = AsyncMock(return_value={"message": {"content": '["NonExistentSub12345"]'}})
        discovery = SubredditDiscovery(llm_fn=llm_fn)

        with patch.object(discovery._http, "get", side_effect=Exception("404")):
            results = await discovery.discover("X", "Y")

        assert len(results) == 0

    def test_suggestion_model(self):
        s = SubredditSuggestion(
            name="LocalLLaMA",
            subscribers=50000,
            posts_per_day=25.0,
            relevance_score=85,
            reasoning="Active LLM community",
            sample_posts=["Post 1", "Post 2"],
        )
        assert s.name == "LocalLLaMA"
        assert s.relevance_score == 85
