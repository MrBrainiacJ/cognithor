"""Tests for social.service — RedditLeadService orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from jarvis.social.models import LeadStatus
from jarvis.social.service import RedditLeadService


@pytest.fixture()
def service(tmp_path: Path) -> RedditLeadService:
    return RedditLeadService(
        db_path=str(tmp_path / "leads.db"),
        llm_fn=AsyncMock(),
        product_name="TestProduct",
        product_description="A test product",
    )


class TestRedditLeadService:
    @pytest.mark.asyncio
    async def test_scan_returns_result(self, service: RedditLeadService):
        mock_posts = [
            {
                "id": "p1",
                "title": "Looking for AI tool with local deployment",
                "selftext": "Need something private",
                "subreddit": "SaaS",
                "permalink": "/r/SaaS/p1",
                "author": "user1",
                "created_utc": 1700000000,
                "score": 10,
                "num_comments": 5,
            },
        ]
        with patch.object(service._scanner, "fetch_posts", return_value=mock_posts):
            with patch.object(
                service._scanner,
                "score_post",
                new_callable=AsyncMock,
                return_value=(75, "Direct match"),
            ):
                with patch.object(
                    service._scanner,
                    "draft_reply",
                    new_callable=AsyncMock,
                    return_value="Try TestProduct",
                ):
                    result = await service.scan(["SaaS"], min_score=60, trigger="test")

        assert result.posts_checked == 1
        assert result.leads_found == 1
        leads = service.get_leads()
        assert len(leads) == 1
        assert leads[0].intent_score == 75

    @pytest.mark.asyncio
    async def test_scan_skips_duplicates(self, service: RedditLeadService):
        mock_posts = [
            {
                "id": "dup1",
                "title": "Some post about tools",
                "selftext": "text",
                "subreddit": "SaaS",
                "permalink": "/r/SaaS/dup1",
                "author": "u",
                "created_utc": 1700000000,
                "score": 5,
                "num_comments": 1,
            },
        ]
        with patch.object(service._scanner, "fetch_posts", return_value=mock_posts):
            with patch.object(
                service._scanner,
                "score_post",
                new_callable=AsyncMock,
                return_value=(80, "Match"),
            ):
                with patch.object(
                    service._scanner,
                    "draft_reply",
                    new_callable=AsyncMock,
                    return_value="Reply",
                ):
                    await service.scan(["SaaS"], min_score=60, trigger="test")
                    result = await service.scan(["SaaS"], min_score=60, trigger="test")

        assert result.posts_skipped_duplicate == 1
        assert result.leads_found == 0

    @pytest.mark.asyncio
    async def test_scan_skips_low_score(self, service: RedditLeadService):
        mock_posts = [
            {
                "id": "low1",
                "title": "Random discussion about nothing",
                "selftext": "",
                "subreddit": "SaaS",
                "permalink": "/r/SaaS/low1",
                "author": "u",
                "created_utc": 1700000000,
                "score": 2,
                "num_comments": 0,
            },
        ]
        with patch.object(service._scanner, "fetch_posts", return_value=mock_posts):
            with patch.object(
                service._scanner,
                "score_post",
                new_callable=AsyncMock,
                return_value=(20, "No match"),
            ):
                result = await service.scan(["SaaS"], min_score=60, trigger="test")

        assert result.posts_skipped_low_score == 1
        assert result.leads_found == 0

    def test_get_stats(self, service: RedditLeadService):
        stats = service.get_stats()
        assert stats.total == 0

    def test_update_lead(self, service: RedditLeadService):
        from jarvis.social.models import Lead

        lead = Lead(post_id="x", subreddit="S", title="T", url="u", intent_score=70)
        service._store.save_lead(lead)
        updated = service.update_lead(lead.id, status=LeadStatus.REVIEWED)
        assert updated is not None
        assert updated.status == LeadStatus.REVIEWED
