"""Tests for social.models — Lead, ScanResult, LeadStats."""

from __future__ import annotations

from cognithor.social.models import Lead, LeadStats, LeadStatus, ScanResult


class TestLead:
    def test_create_minimal(self):
        lead = Lead(
            post_id="abc123",
            subreddit="LocalLLaMA",
            title="Test post",
            url="https://reddit.com/r/LocalLLaMA/abc123",
            intent_score=75,
        )
        assert lead.id  # auto-generated UUID
        assert lead.status == LeadStatus.NEW
        assert lead.content_hash  # auto-generated SHA256
        assert lead.detected_at > 0

    def test_content_hash_deterministic(self):
        a = Lead(post_id="x", subreddit="s", title="t", url="u", intent_score=50)
        b = Lead(post_id="x", subreddit="s", title="t", url="u", intent_score=50)
        assert a.content_hash == b.content_hash

    def test_content_hash_changes_with_title(self):
        a = Lead(post_id="x", subreddit="s", title="t1", url="u", intent_score=50)
        b = Lead(post_id="x", subreddit="s", title="t2", url="u", intent_score=50)
        assert a.content_hash != b.content_hash

    def test_status_enum_values(self):
        assert LeadStatus.NEW == "new"
        assert LeadStatus.REVIEWED == "reviewed"
        assert LeadStatus.REPLIED == "replied"
        assert LeadStatus.ARCHIVED == "archived"

    def test_to_dict(self):
        lead = Lead(
            post_id="abc",
            subreddit="SaaS",
            title="Looking for AI tool",
            url="https://reddit.com/r/SaaS/abc",
            intent_score=80,
            score_reason="Direct search",
            reply_draft="Try Cognithor",
        )
        d = lead.to_dict()
        assert d["post_id"] == "abc"
        assert d["intent_score"] == 80
        assert d["status"] == "new"
        assert "id" in d
        assert "content_hash" in d

    def test_notification_text(self):
        lead = Lead(
            post_id="abc",
            subreddit="SaaS",
            title="Need AI assistant",
            url="https://reddit.com/r/SaaS/abc",
            intent_score=85,
            score_reason="Active search",
            reply_draft="Check Cognithor",
            author="test_user",
            upvotes=10,
            num_comments=5,
        )
        text = lead.to_notification_text()
        assert "85" in text
        assert "SaaS" in text
        assert "Need AI assistant" in text
        assert "test_user" in text


class TestScanResult:
    def test_create(self):
        result = ScanResult(
            subreddits_scanned=["LocalLLaMA", "SaaS"],
            posts_checked=20,
            leads_found=3,
        )
        assert result.id
        assert result.started_at > 0
        assert result.finished_at == 0

    def test_summary(self):
        result = ScanResult(
            subreddits_scanned=["LocalLLaMA"],
            posts_checked=50,
            leads_found=5,
            posts_skipped_duplicate=10,
            posts_skipped_low_score=35,
        )
        s = result.summary()
        assert "50" in s
        assert "5" in s


class TestLeadStats:
    def test_from_counts(self):
        stats = LeadStats(
            total=20,
            new=10,
            reviewed=5,
            replied=3,
            archived=2,
            avg_score=72.5,
            top_subreddits={"LocalLLaMA": 12, "SaaS": 8},
            total_scans=15,
        )
        assert stats.total == 20
        assert stats.avg_score == 72.5
