"""Tests for social.tracker — performance re-scanning."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cognithor.social.tracker import PerformanceTracker, engagement_score

if TYPE_CHECKING:
    from pathlib import Path

    from cognithor.social.store import LeadStore


@pytest.fixture()
def store(tmp_path: Path) -> LeadStore:
    from cognithor.social.store import LeadStore

    return LeadStore(str(tmp_path / "leads.db"))


class TestEngagementScore:
    def test_zero_engagement(self):
        assert engagement_score(0, 0, False, "") == 0

    def test_upvotes_only(self):
        assert engagement_score(5, 0, False, "") == 15  # 5*3

    def test_full_engagement(self):
        score = engagement_score(5, 2, True, "converted")
        assert score == 15 + 10 + 10 + 20  # 5*3 + 2*5 + 10 + 20 = 55

    def test_capped_at_100(self):
        score = engagement_score(50, 20, True, "converted")
        assert score <= 100


class TestPerformanceTracker:
    def test_create(self, store: LeadStore):
        tracker = PerformanceTracker(store=store)
        assert tracker is not None

    def test_find_reply_in_comments(self):
        comments = [
            {
                "data": {
                    "body": "Some random comment",
                    "author": "user1",
                    "score": 2,
                    "replies": "",
                }
            },
            {
                "data": {
                    "body": "Check out Cognithor \u2014 it does exactly this",
                    "author": "our_user",
                    "score": 5,
                    "replies": {"data": {"children": [{"data": {}}]}},
                }
            },
        ]
        from cognithor.social.tracker import _find_our_reply

        match = _find_our_reply(comments, "Check out Cognithor")
        assert match is not None
        assert match["score"] == 5

    def test_find_reply_fuzzy_match(self):
        comments = [
            {
                "data": {
                    "body": "Check out Cognithor - it does exactly this thing",
                    "author": "u",
                    "score": 3,
                    "replies": "",
                }
            },
        ]
        from cognithor.social.tracker import _find_our_reply

        match = _find_our_reply(comments, "Check out Cognithor \u2014 it does exactly this")
        assert match is not None  # fuzzy match should find it
