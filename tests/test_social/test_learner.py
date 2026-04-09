"""Tests for social.learner — feedback learning loop."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from jarvis.social.learner import ReplyLearner
from jarvis.social.store import LeadStore

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def store(tmp_path: Path) -> LeadStore:
    return LeadStore(str(tmp_path / "leads.db"))


class TestReplyLearner:
    @pytest.mark.asyncio
    async def test_analyze_subreddit(self, store: LeadStore):
        # Seed performance data
        for i in range(6):
            store.save_performance(
                lead_id=f"l{i}",
                reply_text=f"Reply {i} about technical details",
                subreddit="LocalLLaMA",
            )
            store.update_performance(f"l{i}", reply_upvotes=i * 2, reply_replies=i)

        llm_fn = AsyncMock(
            return_value={
                "message": {
                    "content": (
                        '{"what_works": "Technical depth", "what_fails": "Generic advice",'
                        ' "optimal_length": 120, "optimal_tone": "technically detailed",'
                        ' "best_openings": ["Your point about..."],'
                        ' "avoid_patterns": ["Check out my..."]}'
                    )
                }
            }
        )
        learner = ReplyLearner(store=store, llm_fn=llm_fn)
        profile = await learner.analyze_subreddit("LocalLLaMA")

        assert profile is not None
        assert "Technical depth" in profile["what_works"]

    @pytest.mark.asyncio
    async def test_run_learning_cycle(self, store: LeadStore):
        # Seed data for 2 subreddits
        for sub in ["LocalLLaMA", "SaaS"]:
            for i in range(5):
                store.save_performance(
                    lead_id=f"{sub}_{i}",
                    reply_text=f"Reply {i}",
                    subreddit=sub,
                )
                store.update_performance(f"{sub}_{i}", reply_upvotes=i * 3)

        llm_fn = AsyncMock(
            return_value={
                "message": {
                    "content": (
                        '{"what_works": "X", "what_fails": "Y", "optimal_length": 100,'
                        ' "optimal_tone": "casual", "best_openings": [], "avoid_patterns": []}'
                    )
                }
            }
        )
        learner = ReplyLearner(store=store, llm_fn=llm_fn)
        result = await learner.run_learning_cycle(min_sample_size=3)

        assert result["subreddits_analyzed"] == 2
        # Profiles should be saved
        assert store.get_profile("LocalLLaMA") is not None
        assert store.get_profile("SaaS") is not None

    def test_get_few_shot_examples(self, store: LeadStore):
        for i in range(5):
            store.save_performance(lead_id=f"fs{i}", reply_text=f"Reply {i}", subreddit="X")
            store.update_performance(f"fs{i}", reply_upvotes=i * 5)

        learner = ReplyLearner(store=store, llm_fn=AsyncMock())
        examples = learner.get_few_shot_examples("X", limit=3)
        assert len(examples) == 3
        assert examples[0]["reply_upvotes"] >= examples[1]["reply_upvotes"]
