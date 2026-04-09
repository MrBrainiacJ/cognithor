"""Tests for social.reply — hybrid reply posting."""

from __future__ import annotations

from unittest.mock import patch

from jarvis.social.models import Lead
from jarvis.social.reply import ReplyMode, ReplyPoster


class TestReplyPoster:
    def test_clipboard_mode(self):
        lead = Lead(
            post_id="abc",
            subreddit="SaaS",
            title="Test",
            url="https://reddit.com/r/SaaS/abc",
            intent_score=80,
            reply_draft="Try Cognithor",
        )
        poster = ReplyPoster()
        with patch("jarvis.social.reply._copy_to_clipboard") as mock_clip:
            with patch("webbrowser.open") as mock_browser:
                result = poster.post(lead, mode=ReplyMode.CLIPBOARD)
        assert result.success
        assert result.mode == ReplyMode.CLIPBOARD
        mock_clip.assert_called_once_with("Try Cognithor")
        mock_browser.assert_called_once()

    def test_browser_mode(self):
        lead = Lead(
            post_id="abc",
            subreddit="SaaS",
            title="Test",
            url="https://reddit.com/r/SaaS/abc",
            intent_score=80,
            reply_draft="Draft text",
        )
        poster = ReplyPoster()
        with patch("jarvis.social.reply._copy_to_clipboard") as mock_clip:
            with patch("webbrowser.open") as mock_browser:
                result = poster.post(lead, mode=ReplyMode.BROWSER)
        assert result.success
        mock_browser.assert_called_once()
        mock_clip.assert_called_once()

    def test_uses_reply_final_over_draft(self):
        lead = Lead(
            post_id="abc",
            subreddit="SaaS",
            title="Test",
            url="https://reddit.com/r/SaaS/abc",
            intent_score=80,
            reply_draft="Draft",
            reply_final="Final edited version",
        )
        poster = ReplyPoster()
        with patch("jarvis.social.reply._copy_to_clipboard") as mock_clip:
            with patch("webbrowser.open"):
                poster.post(lead, mode=ReplyMode.CLIPBOARD)
        mock_clip.assert_called_once_with("Final edited version")

    def test_empty_reply_fails(self):
        lead = Lead(
            post_id="abc",
            subreddit="SaaS",
            title="Test",
            url="https://reddit.com/r/SaaS/abc",
            intent_score=80,
        )
        poster = ReplyPoster()
        result = poster.post(lead, mode=ReplyMode.CLIPBOARD)
        assert not result.success
        assert "empty" in result.error.lower()
