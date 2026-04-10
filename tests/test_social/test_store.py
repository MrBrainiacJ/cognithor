"""Tests for social.store — SQLite lead persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from cognithor.social.models import Lead, LeadStatus, ScanResult
from cognithor.social.store import LeadStore


@pytest.fixture()
def store(tmp_path: Path) -> LeadStore:
    return LeadStore(str(tmp_path / "leads.db"))


class TestLeadStore:
    def test_save_and_get(self, store: LeadStore):
        lead = Lead(
            post_id="abc",
            subreddit="SaaS",
            title="Test",
            url="https://reddit.com/abc",
            intent_score=75,
        )
        store.save_lead(lead)
        loaded = store.get_lead(lead.id)
        assert loaded is not None
        assert loaded.post_id == "abc"
        assert loaded.intent_score == 75
        assert loaded.status == LeadStatus.NEW

    def test_duplicate_post_id_updates(self, store: LeadStore):
        lead1 = Lead(
            post_id="dup",
            subreddit="SaaS",
            title="First",
            url="https://reddit.com/dup",
            intent_score=60,
        )
        store.save_lead(lead1)
        lead2 = Lead(
            post_id="dup",
            subreddit="SaaS",
            title="Updated",
            url="https://reddit.com/dup",
            intent_score=80,
        )
        store.save_lead(lead2)
        leads = store.get_leads()
        dup_leads = [l for l in leads if l.post_id == "dup"]
        assert len(dup_leads) == 1
        assert dup_leads[0].intent_score == 80

    def test_get_leads_filter_status(self, store: LeadStore):
        for i in range(3):
            store.save_lead(
                Lead(
                    post_id=f"p{i}",
                    subreddit="S",
                    title=f"T{i}",
                    url=f"u{i}",
                    intent_score=70,
                )
            )
        store.update_lead(store.get_leads()[0].id, status=LeadStatus.REVIEWED)
        new_leads = store.get_leads(status=LeadStatus.NEW)
        assert len(new_leads) == 2

    def test_get_leads_filter_min_score(self, store: LeadStore):
        store.save_lead(Lead(post_id="low", subreddit="S", title="Low", url="u", intent_score=30))
        store.save_lead(Lead(post_id="high", subreddit="S", title="High", url="u", intent_score=90))
        high_leads = store.get_leads(min_score=60)
        assert len(high_leads) == 1
        assert high_leads[0].post_id == "high"

    def test_update_lead_status(self, store: LeadStore):
        lead = Lead(post_id="up", subreddit="S", title="T", url="u", intent_score=70)
        store.save_lead(lead)
        updated = store.update_lead(lead.id, status=LeadStatus.REPLIED, reply_final="Done")
        assert updated is not None
        assert updated.status == LeadStatus.REPLIED
        assert updated.reply_final == "Done"

    def test_already_seen(self, store: LeadStore):
        assert not store.already_seen("new_post")
        store.save_lead(
            Lead(post_id="new_post", subreddit="S", title="T", url="u", intent_score=50)
        )
        assert store.already_seen("new_post")

    def test_get_stats(self, store: LeadStore):
        store.save_lead(Lead(post_id="a", subreddit="X", title="T", url="u", intent_score=80))
        store.save_lead(Lead(post_id="b", subreddit="X", title="T", url="u", intent_score=60))
        store.save_lead(Lead(post_id="c", subreddit="Y", title="T", url="u", intent_score=70))
        stats = store.get_stats()
        assert stats.total == 3
        assert stats.new == 3
        assert stats.avg_score == pytest.approx(70.0)
        assert stats.top_subreddits["X"] == 2

    def test_save_scan(self, store: LeadStore):
        scan = ScanResult(subreddits_scanned=["X", "Y"], posts_checked=50, leads_found=3)
        store.save_scan(scan)
        history = store.get_scan_history(limit=10)
        assert len(history) == 1
        assert history[0]["posts_checked"] == 50

    def test_get_lead_not_found_returns_none(self, store: LeadStore):
        result = store.get_lead("nonexistent-id")
        assert result is None
