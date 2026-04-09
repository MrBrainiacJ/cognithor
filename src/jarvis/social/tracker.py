"""Reply performance tracking — re-scans Reddit for engagement metrics."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

import httpx

from jarvis.utils.logging import get_logger

if TYPE_CHECKING:
    from jarvis.social.store import LeadStore

log = get_logger(__name__)

_USER_AGENT = "cognithor:reply_tracker:v1.0 (by u/cognithor-bot)"


def engagement_score(
    upvotes: int,
    replies: int,
    author_replied: bool,
    feedback_tag: str,
) -> int:
    raw = (
        upvotes * 3
        + replies * 5
        + (10 if author_replied else 0)
        + (20 if feedback_tag == "converted" else 0)
    )
    return min(100, raw)


def _find_our_reply(
    comments: list[dict[str, Any]],
    reply_text: str,
    threshold: float = 0.75,
) -> dict[str, Any] | None:
    """Find our reply in a list of Reddit comments using fuzzy matching."""
    reply_lower = reply_text.lower()[:200]
    for comment in comments:
        data = comment.get("data", {})
        body = (data.get("body") or "").lower()[:200]
        if not body:
            continue
        ratio = SequenceMatcher(None, reply_lower, body).ratio()
        # Also match when our stored text is a prefix/substring of the posted body
        # (body may have been extended after storage)
        contained = reply_lower in body or body in reply_lower
        if ratio >= threshold or contained:
            # Count direct replies to our comment
            reply_data = data.get("replies")
            reply_count = 0
            if isinstance(reply_data, dict):
                children = reply_data.get("data", {}).get("children", [])
                reply_count = len(children)
            replies_list = children if isinstance(reply_data, dict) else []
            return {
                "score": data.get("score", 0),
                "reply_count": reply_count,
                "author": data.get("author", ""),
                "ratio": ratio,
                "replies_data": replies_list,
            }
    return None


class PerformanceTracker:
    """Tracks reply performance by re-scanning Reddit posts."""

    def __init__(self, store: LeadStore) -> None:
        self._store = store
        self._http = httpx.Client(
            timeout=15,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )

    async def track_all(self, max_age_days: int = 7) -> dict[str, Any]:
        """Re-scan all replied leads for engagement metrics."""
        import asyncio

        leads = self._store.get_replied_leads_for_tracking(max_age_days=max_age_days)
        tracked = 0
        errors = 0

        for lead_dict in leads:
            lead_id = lead_dict.get("id", "")
            post_id = lead_dict.get("post_id", "")
            subreddit = lead_dict.get("subreddit", "")

            perf = self._store.get_performance(lead_id)
            if perf is None:
                # First tracking — save initial record
                self._store.save_performance(
                    lead_id=lead_id,
                    reply_text=lead_dict.get("reply_final") or lead_dict.get("reply_draft", ""),
                    subreddit=subreddit,
                )
                perf = self._store.get_performance(lead_id)

            try:
                # Fetch post comments
                url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
                resp = self._http.get(url, params={"raw_json": 1, "limit": 100})
                resp.raise_for_status()
                data = resp.json()

                # Post data
                post_data = data[0]["data"]["children"][0]["data"] if data else {}

                # Comments
                comments = data[1]["data"]["children"] if len(data) > 1 else []
                reply_text = perf.get("reply_text", "") if perf else ""

                match = _find_our_reply(comments, reply_text)

                if match:
                    # Check if post author replied to our comment
                    post_author = post_data.get("author", "")
                    replies_data = match.get("replies_data")
                    author_replied = any(
                        c.get("data", {}).get("author") == post_author
                        for c in (replies_data if isinstance(replies_data, list) else [])
                    )

                    self._store.update_performance(
                        lead_id,
                        reply_upvotes=match["score"],
                        reply_replies=match["reply_count"],
                        author_replied=author_replied,
                    )
                    tracked += 1
                    log.info(
                        "tracked_reply",
                        lead_id=lead_id,
                        upvotes=match["score"],
                        replies=match["reply_count"],
                    )
                else:
                    tracked += 1  # Still counts as tracked even if reply not found

                # Rate limit
                await asyncio.sleep(1.0)

            except Exception as exc:
                errors += 1
                log.debug("tracking_failed", lead_id=lead_id, error=str(exc))

        return {"tracked": tracked, "errors": errors, "total": len(leads)}

    def close(self) -> None:
        self._http.close()
