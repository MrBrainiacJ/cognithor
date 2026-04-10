"""Tests for v2 store tables: reply_performance, reply_templates, subreddit_profiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cognithor.social.store import LeadStore

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def store(tmp_path: Path) -> LeadStore:
    return LeadStore(str(tmp_path / "leads.db"))


class TestReplyPerformance:
    def test_save_and_get_performance(self, store: LeadStore):
        store.save_performance(
            lead_id="lead1",
            reply_text="Great post! Check out Cognithor",
            subreddit="LocalLLaMA",
        )
        perf = store.get_performance("lead1")
        assert perf is not None
        assert perf["reply_text"] == "Great post! Check out Cognithor"
        assert perf["reply_upvotes"] == 0
        assert perf["feedback_tag"] == ""

    def test_update_performance_metrics(self, store: LeadStore):
        store.save_performance(lead_id="lead2", reply_text="text", subreddit="SaaS")
        store.update_performance("lead2", reply_upvotes=5, reply_replies=2, author_replied=True)
        perf = store.get_performance("lead2")
        assert perf["reply_upvotes"] == 5
        assert perf["reply_replies"] == 2
        assert perf["author_replied"] == 1

    def test_set_feedback(self, store: LeadStore):
        store.save_performance(lead_id="lead3", reply_text="text", subreddit="SaaS")
        store.set_feedback("lead3", tag="converted", note="User signed up")
        perf = store.get_performance("lead3")
        assert perf["feedback_tag"] == "converted"
        assert perf["feedback_note"] == "User signed up"

    def test_get_top_performers(self, store: LeadStore):
        for i in range(5):
            store.save_performance(lead_id=f"p{i}", reply_text=f"Reply {i}", subreddit="SaaS")
            store.update_performance(f"p{i}", reply_upvotes=i * 3, reply_replies=i)
        top = store.get_top_performers("SaaS", limit=3)
        assert len(top) == 3
        assert top[0]["reply_upvotes"] >= top[1]["reply_upvotes"]

    def test_get_replied_leads_for_tracking(self, store: LeadStore):
        import time

        from cognithor.social.models import Lead, LeadStatus

        lead = Lead(
            post_id="tr1",
            subreddit="SaaS",
            title="T",
            url="u",
            intent_score=70,
            status=LeadStatus.REPLIED,
            replied_at=time.time(),
        )
        store.save_lead(lead)
        replied = store.get_replied_leads_for_tracking(max_age_days=7)
        assert len(replied) == 1


class TestReplyTemplates:
    def test_save_and_list(self, store: LeadStore):
        store.save_template(
            name="Technical Intro",
            template_text="Hey, {product_name} does exactly this...",
            subreddit="LocalLLaMA",
            style="technical",
        )
        templates = store.list_templates()
        assert len(templates) == 1
        assert templates[0]["name"] == "Technical Intro"

    def test_list_by_subreddit(self, store: LeadStore):
        store.save_template(name="Generic", template_text="text", subreddit="", style="casual")
        store.save_template(
            name="LLaMA-specific",
            template_text="text",
            subreddit="LocalLLaMA",
            style="technical",
        )
        llama = store.list_templates(subreddit="LocalLLaMA")
        assert len(llama) == 2  # specific + universal (empty subreddit)

    def test_delete_template(self, store: LeadStore):
        tid = store.save_template(name="ToDelete", template_text="x", subreddit="", style="")
        store.delete_template(tid)
        assert len(store.list_templates()) == 0

    def test_increment_use_count(self, store: LeadStore):
        tid = store.save_template(name="Used", template_text="x", subreddit="", style="")
        store.increment_template_use(tid)
        store.increment_template_use(tid)
        templates = store.list_templates()
        assert templates[0]["use_count"] == 2


class TestSubredditProfiles:
    def test_save_and_get_profile(self, store: LeadStore):
        store.save_profile(
            subreddit="LocalLLaMA",
            what_works="Technical depth, code examples",
            what_fails="Sales pitch, generic advice",
            optimal_length=120,
            optimal_tone="technically detailed",
            best_openings='["Your point about...", "Have you tried..."]',
            avoid_patterns='["Check out my...", "I built..."]',
            sample_size=15,
        )
        profile = store.get_profile("LocalLLaMA")
        assert profile is not None
        assert profile["what_works"] == "Technical depth, code examples"
        assert profile["optimal_length"] == 120
        assert profile["sample_size"] == 15

    def test_get_nonexistent_profile(self, store: LeadStore):
        assert store.get_profile("NonExistent") is None

    def test_update_profile(self, store: LeadStore):
        store.save_profile(
            subreddit="SaaS",
            what_works="v1",
            what_fails="v1",
            optimal_length=100,
            optimal_tone="casual",
            sample_size=5,
        )
        store.save_profile(
            subreddit="SaaS",
            what_works="v2 updated",
            what_fails="v2",
            optimal_length=150,
            optimal_tone="detailed",
            sample_size=20,
        )
        profile = store.get_profile("SaaS")
        assert profile["what_works"] == "v2 updated"
        assert profile["sample_size"] == 20
