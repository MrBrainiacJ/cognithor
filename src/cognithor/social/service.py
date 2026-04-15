"""RedditLeadService — orchestrates scanning, storing, and replying."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from cognithor.social.models import Lead, LeadStats, LeadStatus, ScanResult
from cognithor.social.refiner import ReplyRefiner
from cognithor.social.reply import ReplyMode, ReplyPoster, ReplyResult
from cognithor.social.scanner import RedditScanner, ScanConfig
from cognithor.social.store import LeadStore
from cognithor.social.templates import TemplateManager
from cognithor.utils.logging import get_logger

log = get_logger(__name__)


class RedditLeadService:
    """Orchestrates Reddit lead scanning, persistence, and reply posting."""

    _hn_scanner: Any = None  # Set by gateway
    _discord_scanner: Any = None  # Set by gateway
    _rss_scanner: Any = None  # Set by gateway

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
        auto_post_whitelist: list[str] | None = None,
        min_auto_score: int = 85,
    ) -> None:
        self._store = LeadStore(db_path)
        self._scanner = RedditScanner(llm_fn=llm_fn)
        self._poster = ReplyPoster(browser_agent=browser_agent)
        self._refiner = ReplyRefiner(llm_fn=llm_fn)
        self._template_mgr = TemplateManager(self._store)
        self._notification_cb = notification_callback
        self._default_subreddits = default_subreddits or []
        # Auto-post guardrails: mode="auto" is rejected unless the subreddit is on
        # this whitelist AND the lead's intent_score is at least min_auto_score.
        # Empty whitelist (default) = auto-post globally disabled.
        self._auto_post_whitelist: set[str] = {
            s.strip().lower() for s in (auto_post_whitelist or []) if s.strip()
        }
        self._min_auto_score = min_auto_score
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

                # Fetch learning context for this subreddit
                style_profile = self._store.get_profile(sub)
                few_shot = self._store.get_top_performers(sub, limit=3) if style_profile else []

                # 4. Reply-Draft with learning context + intent score for link gating
                draft = await self._scanner.draft_reply(
                    post,
                    config,
                    style_profile=style_profile,
                    few_shot_examples=few_shot,
                    intent_score=score,
                )
                # LLM self-veto: if draft is empty ("SKIP"), archive the lead.
                if not draft.strip():
                    log.info(
                        "lead_skipped_by_llm",
                        subreddit=sub,
                        score=score,
                        title=post.get("title", "")[:60],
                    )
                    self._store.save_lead(
                        Lead(
                            post_id=post_id,
                            subreddit=sub,
                            title=post.get("title", ""),
                            url=f"https://reddit.com{post.get('permalink', '')}",
                            intent_score=score,
                            score_reason=reasoning + " [LLM skipped: nothing useful to add]",
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

    async def scan_hackernews(
        self, categories: list[str] | None = None, min_score: int = 60
    ) -> dict[str, Any]:
        """Delegate scan to HN scanner (set by gateway)."""
        if not self._hn_scanner:
            return {"error": "HN scanner not initialized", "leads_found": 0, "posts_checked": 0}
        product = self._scan_config.product_name
        desc = self._scan_config.product_description
        return await self._hn_scanner.scan(product, desc, categories, min_score)

    async def scan_discord(
        self, channel_ids: list[str] | None = None, min_score: int = 60
    ) -> dict[str, Any]:
        """Delegate scan to Discord scanner (set by gateway)."""
        if not self._discord_scanner:
            return {
                "error": "Discord scanner not initialized",
                "leads_found": 0,
                "posts_checked": 0,
            }
        product = self._scan_config.product_name
        desc = self._scan_config.product_description
        return await self._discord_scanner.scan(channel_ids or [], product, desc, min_score)

    async def scan_rss(self, feeds: list[str] | None = None, min_score: int = 60) -> dict[str, Any]:
        """Delegate scan to RSS/Atom feed scanner (set by gateway)."""
        if not self._rss_scanner:
            return {
                "error": "RSS scanner not initialized",
                "leads_found": 0,
                "posts_checked": 0,
            }
        product = self._scan_config.product_name
        desc = self._scan_config.product_description
        return await self._rss_scanner.scan(feeds or [], product, desc, min_score)

    def get_leads(
        self,
        status: LeadStatus | str | None = None,
        min_score: int = 0,
        limit: int = 50,
        offset: int = 0,
        platform: str | None = None,
    ) -> list[Lead]:
        return self._store.get_leads(
            status=status, min_score=min_score, limit=limit, offset=offset, platform=platform
        )

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

        # Auto-post safety gate: downgrade to clipboard unless the subreddit is
        # explicitly whitelisted AND the lead passes the intent threshold. This
        # prevents accidental drive-by posting on sensitive subs like LocalLLaMA
        # where AI-slop replies get torched.
        if reply_mode == ReplyMode.AUTO:
            sub = (lead.subreddit or "").lower()
            if sub not in self._auto_post_whitelist:
                log.warning(
                    "auto_post_blocked_not_whitelisted",
                    lead_id=lead_id,
                    subreddit=lead.subreddit,
                )
                reply_mode = ReplyMode.CLIPBOARD
            elif lead.intent_score < self._min_auto_score:
                log.warning(
                    "auto_post_blocked_low_score",
                    lead_id=lead_id,
                    score=lead.intent_score,
                    threshold=self._min_auto_score,
                )
                reply_mode = ReplyMode.CLIPBOARD

        result = self._poster.post(lead, mode=reply_mode)
        if result.success:
            self._store.update_lead(lead_id, status=LeadStatus.REPLIED)
        return result

    def get_stats(self) -> LeadStats:
        return self._store.get_stats()

    def get_scan_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._store.get_scan_history(limit=limit)

    async def refine_reply(self, lead_id: str, hint: str = "", variants: int = 0) -> Any:
        """Refine an existing reply draft or generate variants."""
        lead = self._store.get_lead(lead_id)
        if not lead:
            return None
        post = {"title": lead.title, "selftext": lead.body, "subreddit": lead.subreddit}
        profile = self._store.get_profile(lead.subreddit)
        few_shot = self._store.get_top_performers(lead.subreddit, limit=3)

        if variants > 0:
            return await self._refiner.generate_variants(
                post,
                self._scan_config.product_name,
                count=variants,
                style_profile=profile,
            )
        return await self._refiner.refine(
            post,
            lead.reply_final or lead.reply_draft,
            self._scan_config.product_name,
            user_hint=hint,
            style_profile=profile,
            few_shot_examples=few_shot,
        )

    def get_templates(self, subreddit: str = "") -> list[dict[str, Any]]:
        """List reply templates, optionally filtered by subreddit."""
        return self._template_mgr.list_for_subreddit(subreddit)

    def apply_template(self, template_id: str, **variables: str) -> str:
        """Apply a template with variable substitution."""
        return self._template_mgr.apply(template_id, **variables)

    def create_template(self, name: str, text: str, subreddit: str = "", style: str = "") -> str:
        """Create a new reply template."""
        return self._template_mgr.create(name, text, subreddit, style)

    def delete_template(self, template_id: str) -> None:
        """Delete a reply template."""
        self._template_mgr.delete(template_id)

    def set_feedback(self, lead_id: str, tag: str, note: str = "") -> None:
        """Set feedback on a replied lead for learning."""
        self._store.set_feedback(lead_id, tag, note)

    def get_performance(self, lead_id: str) -> dict[str, Any] | None:
        """Get performance metrics for a replied lead."""
        return self._store.get_performance(lead_id)
