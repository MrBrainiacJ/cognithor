"""Feedback learning loop — analyzes reply performance and builds style profiles."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from cognithor.utils.logging import get_logger

if TYPE_CHECKING:
    from cognithor.social.store import LeadStore

log = get_logger(__name__)

LLMFn = Callable[..., Awaitable[dict[str, Any]]]

ANALYZE_PROMPT = """
You are an expert at analyzing Reddit engagement patterns. Analyze these replies and their
performance.

SUBREDDIT: r/{subreddit}

TOP PERFORMING REPLIES (high engagement):
{top_replies}

WORST PERFORMING REPLIES (low engagement):
{bottom_replies}

Analyze what makes replies successful vs unsuccessful in this subreddit.
Reply in this exact JSON format:
{{
    "what_works": "<2-3 sentence summary of successful patterns>",
    "what_fails": "<2-3 sentence summary of unsuccessful patterns>",
    "optimal_length": <int, average word count of top performers>,
    "optimal_tone": "<tone description, e.g. 'technically detailed, with code examples'>",
    "best_openings": ["<opening phrase 1>", "<opening phrase 2>"],
    "avoid_patterns": ["<pattern to avoid 1>", "<pattern to avoid 2>"]
}}
""".strip()


class ReplyLearner:
    """Learns from reply engagement data to improve future drafts."""

    def __init__(self, store: LeadStore, llm_fn: LLMFn | None = None) -> None:
        self._store = store
        self._llm_fn = llm_fn

    def get_few_shot_examples(self, subreddit: str, limit: int = 3) -> list[dict[str, Any]]:
        """Get top performing replies for a subreddit as few-shot examples."""
        return self._store.get_top_performers(subreddit, limit=limit)

    async def analyze_subreddit(
        self, subreddit: str, min_samples: int = 5
    ) -> dict[str, Any] | None:
        """Analyze top vs bottom replies for a subreddit, generate style profile."""
        if not self._llm_fn:
            return None

        top = self._store.get_top_performers(subreddit, limit=5)
        # Get bottom performers
        all_perf = self._store.conn.execute(
            """SELECT * FROM reply_performance WHERE subreddit = ?
            ORDER BY (reply_upvotes * 3 + reply_replies * 5 + author_replied * 10) ASC
            LIMIT 5""",
            (subreddit,),
        ).fetchall()
        bottom = [dict(r) for r in all_perf]

        if len(top) + len(bottom) < min_samples:
            log.debug("insufficient_data", subreddit=subreddit, samples=len(top) + len(bottom))
            return None

        def format_replies(replies: list[dict[str, Any]]) -> str:
            lines = []
            for r in replies:
                lines.append(
                    f"- [{r.get('reply_upvotes', 0)} upvotes, {r.get('reply_replies', 0)} replies] "
                    f'"{r.get("reply_text", "")[:200]}"'
                )
            return "\n".join(lines) or "(none)"

        prompt = ANALYZE_PROMPT.format(
            subreddit=subreddit,
            top_replies=format_replies(top),
            bottom_replies=format_replies(bottom),
        )

        try:
            response = await self._llm_fn(
                messages=[{"role": "user", "content": prompt}], temperature=0.3
            )
            raw = response.get("message", {}).get("content", "")
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                return None
            profile_data = json.loads(raw[start:end])

            # Save to store
            self._store.save_profile(
                subreddit=subreddit,
                what_works=profile_data.get("what_works", ""),
                what_fails=profile_data.get("what_fails", ""),
                optimal_length=profile_data.get("optimal_length", 0),
                optimal_tone=profile_data.get("optimal_tone", ""),
                best_openings=json.dumps(profile_data.get("best_openings", [])),
                avoid_patterns=json.dumps(profile_data.get("avoid_patterns", [])),
                sample_size=len(top) + len(bottom),
            )

            log.info("profile_updated", subreddit=subreddit, sample_size=len(top) + len(bottom))
            return profile_data

        except Exception as exc:
            log.warning("analysis_failed", subreddit=subreddit, error=str(exc))
            return None

    async def run_learning_cycle(self, min_sample_size: int = 5) -> dict[str, Any]:
        """Run the weekly learning cycle across all tracked subreddits."""
        # Find all subreddits with enough data
        rows = self._store.conn.execute(
            """SELECT subreddit, COUNT(*) as cnt FROM reply_performance
            GROUP BY subreddit HAVING cnt >= ?""",
            (min_sample_size,),
        ).fetchall()

        analyzed = 0
        for row in rows:
            sub = row[0] if isinstance(row, tuple) else row["subreddit"]
            profile = await self.analyze_subreddit(sub, min_samples=min_sample_size)
            if profile:
                analyzed += 1

        log.info("learning_cycle_complete", subreddits_analyzed=analyzed)
        return {"subreddits_analyzed": analyzed, "total_subreddits": len(rows)}
