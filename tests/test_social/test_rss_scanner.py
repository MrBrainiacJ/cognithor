"""Tests for social.rss_scanner — feed parsing + LLM scoring."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from cognithor.social.rss_scanner import RssFeedScanner, parse_feed

RSS_2_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example News</title>
    <link>https://example.com</link>
    <description>A test feed</description>
    <item>
      <title>Startup struggles with local LLM costs</title>
      <link>https://example.com/post1</link>
      <description>Company X is looking for cheaper alternatives to OpenAI.</description>
      <guid>post-1</guid>
      <pubDate>Mon, 14 Apr 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Weather report</title>
      <link>https://example.com/post2</link>
      <description>Sunny with clouds.</description>
      <guid>post-2</guid>
      <pubDate>Mon, 14 Apr 2026 13:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

ATOM_SAMPLE = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Example</title>
  <entry>
    <title>Atom Entry One</title>
    <link href="https://example.org/one"/>
    <id>tag:example.org,2026:one</id>
    <updated>2026-04-14T12:00:00Z</updated>
    <summary>Summary text for entry one.</summary>
  </entry>
</feed>
"""


class TestParseFeed:
    def test_parses_rss_2(self):
        entries = parse_feed(RSS_2_SAMPLE)
        assert len(entries) == 2
        assert entries[0]["title"] == "Startup struggles with local LLM costs"
        assert entries[0]["url"] == "https://example.com/post1"
        assert "OpenAI" in entries[0]["summary"]
        assert entries[0]["id"] == "post-1"

    def test_parses_atom(self):
        entries = parse_feed(ATOM_SAMPLE)
        assert len(entries) == 1
        assert entries[0]["title"] == "Atom Entry One"
        assert entries[0]["url"] == "https://example.org/one"
        assert entries[0]["id"] == "tag:example.org,2026:one"

    def test_malformed_returns_empty(self):
        assert parse_feed(b"<not-xml") == []

    def test_empty_channel(self):
        assert parse_feed(b"<?xml version='1.0'?><rss><channel></channel></rss>") == []


class TestRssFeedScannerScoring:
    @pytest.mark.asyncio
    async def test_score_entry_uses_llm(self):
        llm = AsyncMock(
            return_value={
                "message": {
                    "content": '{"score": 82, "reasoning": "Direct pain point for local LLM cost"}'
                }
            }
        )
        scanner = RssFeedScanner(llm_fn=llm)
        score, reason = await scanner.score_entry(
            {
                "title": "Startup struggles with local LLM costs",
                "url": "https://example.com/post1",
                "summary": "Looking for cheaper alternatives",
            },
            product_name="Cognithor",
            product_description="Local-first AI assistant",
        )
        assert score == 82
        assert "pain point" in reason.lower()
        llm.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_score_entry_without_llm_returns_zero(self):
        scanner = RssFeedScanner(llm_fn=None)
        score, reason = await scanner.score_entry({"title": "X"}, product_name="P")
        assert score == 0
        assert "No LLM" in reason

    @pytest.mark.asyncio
    async def test_score_entry_handles_bad_json(self):
        llm = AsyncMock(return_value={"message": {"content": "not json at all"}})
        scanner = RssFeedScanner(llm_fn=llm)
        score, _ = await scanner.score_entry({"title": "X"}, product_name="P")
        assert score == 0

    @pytest.mark.asyncio
    async def test_scan_filters_by_min_score(self, monkeypatch):
        scanner = RssFeedScanner(llm_fn=AsyncMock())

        async def fake_fetch(url, limit=30):
            return [
                {"id": "a", "title": "A", "url": "u", "summary": "", "entry_hash": "a"},
                {"id": "b", "title": "B", "url": "u", "summary": "", "entry_hash": "b"},
            ]

        scores = iter([(90, "high"), (20, "low")])

        async def fake_score(entry, product_name, product_description=""):
            return next(scores)

        monkeypatch.setattr(scanner, "fetch_feed", fake_fetch)
        monkeypatch.setattr(scanner, "score_entry", fake_score)

        result = await scanner.scan(["https://example.com/feed"], "Cognithor", min_score=60)
        assert result["posts_checked"] == 2
        assert result["leads_found"] == 1
        assert result["leads"][0]["intent_score"] == 90
