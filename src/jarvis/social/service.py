"""RedditLeadService — orchestrates scanning, storing, and replying."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from jarvis.social.models import Lead, LeadStats, LeadStatus, ScanResult
from jarvis.social.reply import ReplyMode, ReplyPoster, ReplyResult
from jarvis.social.scanner import RedditScanner, ScanConfig
from jarvis.social.store import LeadStore
from jarvis.utils.logging import get_logger

log = get_logger(__name__)


class RedditLeadService:
    """Orchestrates Reddit lead scanning, persistence, and reply posting."""

    def __init__(
        self,
        db_path: str,
        llm_fn: Callable[..., Awaitable[dict[str, Any]]] | None = None,
        product_name: str = "",
        product_description: str = "",
        reply_tone: str = "helpful, technically credible, no sales pitch",
        default_subreddits: list[str] | None = None,
        min_score: int = 60,
        browser_agent: Any = None,
        notification_callback: Callable[[Lead], None] | None = None,
    ) -> None:
        self._store = LeadStore(db_path)
        self._scanner = RedditScanner(llm_fn=llm_fn)
        self._poster = ReplyPoster(browser_agent=browser_agent)
        self._notification_cb = notification_callback
        self._default_subreddits = default_subreddits or []
        self._scan_config = ScanConfig(
            product_name=product_name,
            min_score=min_score,
            product_description=product_description,
            reply_tone=reply_tone,
        )

    async def scan(
        self,
        subreddits: list[str] | None = None,
        min_score: int = 60,
        trigger: str = "chat",
    ) -> ScanResult:
        """Run a full scan cycle: fetch -> score -> draft -> store."""
        subs = subreddits or self._default_subreddits
        config = ScanConfig(
            product_name=self._scan_config.product_name,
            product_description=self._scan_config.product_description,
            reply_tone=self._scan_config.reply_tone,
            min_score=min_score,
        )

        result = ScanResult(subreddits_scanned=subs, trigger=trigger)
        leads_created: list[Lead] = []

        for sub in subs:
            posts = self._scanner.fetch_posts(sub, limit=100)

            # Rate limit between subreddits
            if posts:
                await asyncio.sleep(1.0)

            for post in posts:
                result.posts_checked += 1
                post_id = post.get("id", "")

                # Duplicate check
                if self._store.already_seen(post_id):
                    result.posts_skipped_duplicate += 1
                    continue

                # Quick filter
                if len(post.get("title", "")) < 15:
                    result.posts_skipped_low_score += 1
                    continue

                # LLM scoring
                score, reasoning = await self._scanner.score_post(post, config)

                if score < min_score:
                    result.posts_skipped_low_score += 1
                    # Still save to prevent re-scoring
                    self._store.save_lead(
                        Lead(
                            post_id=post_id,
                            subreddit=sub,
                            title=post.get("title", ""),
                            url=f"https://reddit.com{post.get('permalink', '')}",
                            intent_score=score,
                            score_reason=reasoning,
                            status=LeadStatus.ARCHIVED,
                            scan_id=result.id,
                            author=post.get("author", ""),
                            body=(post.get("selftext") or "")[:500],
                            created_utc=post.get("created_utc", 0),
                            upvotes=post.get("score", 0),
                            num_comments=post.get("num_comments", 0),
                        )
                    )
                    continue

                # Draft reply
                draft = await self._scanner.draft_reply(post, config)

                # Create and save lead
                lead = Lead(
                    post_id=post_id,
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
                    reply_draft=draft,
                    scan_id=result.id,
                )
                self._store.save_lead(lead)
                leads_created.append(lead)
                result.leads_found += 1

                log.info(
                    "lead_found",
                    subreddit=sub,
                    score=score,
                    title=post.get("title", "")[:60],
                )

                # Notification callback
                if self._notification_cb:
                    try:
                        self._notification_cb(lead)
                    except Exception as exc:
                        log.warning("notification_failed", error=str(exc))

        result.finished_at = time.time()
        self._store.save_scan(result)
        log.info("scan_complete", summary=result.summary())
        return result

    def get_leads(
        self,
        status: LeadStatus | None = None,
        min_score: int = 0,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        return self._store.get_leads(status=status, min_score=min_score, limit=limit, offset=offset)

    def get_lead(self, lead_id: str) -> Lead | None:
        return self._store.get_lead(lead_id)

    def update_lead(
        self,
        lead_id: str,
        status: LeadStatus | None = None,
        reply_final: str | None = None,
    ) -> Lead | None:
        return self._store.update_lead(lead_id, status=status, reply_final=reply_final)

    def post_reply(self, lead_id: str, mode: str = "clipboard") -> ReplyResult:
        lead = self._store.get_lead(lead_id)
        if lead is None:
            return ReplyResult(success=False, mode=ReplyMode(mode), error="Lead not found")
        reply_mode = ReplyMode(mode)
        result = self._poster.post(lead, mode=reply_mode)
        if result.success:
            self._store.update_lead(lead_id, status=LeadStatus.REPLIED)
        return result

    def get_stats(self) -> LeadStats:
        return self._store.get_stats()

    def get_scan_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._store.get_scan_history(limit=limit)
