"""Legacy LeadSource adapters that wrap the existing social scanner classes.

These exist only during Phase 1-3 of the agent pack extraction. Phase 4
moves them into the four actual pack repos and deletes this file.
"""

from __future__ import annotations

import os
from typing import Any

from cognithor.leads.models import Lead, LeadStatus
from cognithor.leads.source import LeadSource
from cognithor.social.discord_scanner import DiscordScanner
from cognithor.social.hn_scanner import HackerNewsScanner
from cognithor.social.rss_scanner import RssFeedScanner
from cognithor.social.scanner import RedditScanner, ScanConfig


class LegacyRedditSource(LeadSource):
    source_id = "reddit"
    display_name = "Reddit"
    icon = "forum"
    color = "#FF4500"
    capabilities = frozenset({"scan", "draft_reply", "refine_reply", "auto_post"})

    def __init__(self, llm_fn: Any = None, browser_agent: Any = None) -> None:
        self._scanner = RedditScanner(llm_fn=llm_fn)
        self._browser_agent = browser_agent

    async def scan(
        self,
        *,
        config: dict[str, Any],
        product: str,
        product_description: str,
        min_score: int,
    ) -> list[Lead]:
        subreddits: list[str] = list(config.get("subreddits") or [])
        if not subreddits:
            return []

        scan_cfg = ScanConfig(
            product_name=product,
            product_description=product_description,
            min_score=min_score,
        )
        leads: list[Lead] = []
        for sub in subreddits:
            # fetch_posts is synchronous per the existing implementation.
            posts = self._scanner.fetch_posts(sub, limit=100)
            for post in posts:
                if len(post.get("title", "")) < 15:
                    continue
                score, reasoning = await self._scanner.score_post(post, scan_cfg)
                leads.append(
                    Lead(
                        post_id=post.get("id", ""),
                        source_id="reddit",
                        subreddit=sub,
                        title=post.get("title", ""),
                        body=(post.get("selftext") or "")[:500],
                        url=f"https://reddit.com{post.get('permalink', '')}",
                        author=post.get("author", "[deleted]"),
                        created_utc=post.get("created_utc", 0),
                        upvotes=post.get("score", 0),
                        num_comments=post.get("num_comments", 0),
                        intent_score=score,
                        score_reason=reasoning,
                        status=LeadStatus.NEW,
                    )
                )
        return leads


class LegacyHnSource(LeadSource):
    source_id = "hn"
    display_name = "Hacker News"
    icon = "article"
    color = "#FF6600"
    capabilities = frozenset({"scan"})

    def __init__(self, llm_fn: Any = None) -> None:
        self._scanner = HackerNewsScanner(llm_fn=llm_fn)

    async def scan(
        self,
        *,
        config: dict[str, Any],
        product: str,
        product_description: str,
        min_score: int,
    ) -> list[Lead]:
        categories = config.get("categories") or ["top", "new"]
        # HackerNewsScanner.scan() takes positional product_name, product_description,
        # then categories and min_score as keyword args.
        raw = await self._scanner.scan(
            product,
            product_description,
            categories=categories,
            min_score=min_score,
        )
        return [
            Lead(
                post_id=f"hn-{entry.get('id', '')}",
                source_id="hn",
                title=entry.get("title", ""),
                url=entry.get("url", "")
                or f"https://news.ycombinator.com/item?id={entry.get('id', '')}",
                intent_score=entry.get("intent_score", 0),
                score_reason=entry.get("score_reason", ""),
            )
            for entry in raw.get("leads", [])
        ]


class LegacyDiscordSource(LeadSource):
    source_id = "discord"
    display_name = "Discord"
    icon = "tag"
    color = "#5865F2"
    capabilities = frozenset({"scan"})

    def __init__(self, llm_fn: Any = None) -> None:
        token = os.environ.get("COGNITHOR_DISCORD_TOKEN", "")
        self._scanner: DiscordScanner | None = (
            DiscordScanner(bot_token=token, llm_fn=llm_fn) if token else None
        )

    async def scan(
        self,
        *,
        config: dict[str, Any],
        product: str,
        product_description: str,
        min_score: int,
    ) -> list[Lead]:
        if self._scanner is None:
            return []
        channel_ids = list(config.get("channel_ids") or [])
        # DiscordScanner.scan() takes: channel_ids, product_name, product_description, min_score
        raw = await self._scanner.scan(
            channel_ids,
            product,
            product_description,
            min_score,
        )
        return [
            Lead(
                post_id=f"discord-{entry.get('id', '')}",
                source_id="discord",
                title=entry.get("content", "")[:200],
                url=entry.get("url", ""),
                intent_score=entry.get("intent_score", 0),
                score_reason=entry.get("score_reason", ""),
                body=entry.get("content", "")[:500],
                author=entry.get("author", ""),
            )
            for entry in raw.get("leads", [])
        ]


class LegacyRssSource(LeadSource):
    source_id = "rss"
    display_name = "RSS Feeds"
    icon = "rss_feed"
    color = "#FFA500"
    capabilities = frozenset({"scan"})

    def __init__(self, llm_fn: Any = None) -> None:
        self._scanner = RssFeedScanner(llm_fn=llm_fn)

    async def scan(
        self,
        *,
        config: dict[str, Any],
        product: str,
        product_description: str,
        min_score: int,
    ) -> list[Lead]:
        feeds = list(config.get("feeds") or [])
        if not feeds:
            return []
        # RssFeedScanner.scan() takes: feeds, product_name, product_description, min_score
        raw = await self._scanner.scan(
            feeds,
            product,
            product_description,
            min_score,
        )
        return [
            Lead(
                post_id=entry.get("entry_hash") or entry.get("id") or entry.get("url", ""),
                source_id="rss",
                title=entry.get("title", ""),
                url=entry.get("url", ""),
                intent_score=entry.get("intent_score", 0),
                score_reason=entry.get("score_reason", ""),
                body=(entry.get("summary") or "")[:500],
            )
            for entry in raw.get("leads", [])
        ]
