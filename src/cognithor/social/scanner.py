"""Reddit JSON feed scanner with LLM-based intent scoring and reply drafting."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

from cognithor.utils.logging import get_logger

log = get_logger(__name__)

_USER_AGENT = "cognithor:reddit_lead_hunter:v1.0 (by u/cognithor-bot)"

SCORE_PROMPT = """
You are a B2B lead qualification expert. Score this Reddit post for purchase intent.

PRODUCT: {product_name}
DESCRIPTION: {product_description}

REDDIT POST:
Subreddit: r/{subreddit}
Title: {title}
Text: {body}

Score 0-100:
- 0-20: No relation to product
- 21-40: Weak relation, no concrete problem
- 41-60: Relevant topic, no clear buying signal
- 61-80: Clear problem that our product solves
- 81-100: Active search for exactly this solution

Reply ONLY in this JSON format:
{{"score": <int 0-100>, "reasoning": "<max 1 sentence>"}}
""".strip()

REPLY_PROMPT = """
You are a helpful expert replying on Reddit.

PRODUCT: {product_name}
YOUR TONE: {reply_tone}

REDDIT POST:
Subreddit: r/{subreddit}
Title: {title}
Text: {body}

{style_context}
{few_shot_context}

Write a short, helpful Reddit reply (max {max_words} words):
- Acknowledge the user's problem
- Briefly explain how {product_name} can help
- No hard sales pitch
- Subreddit-native tone (informal, direct)
- End with the GitHub link: github.com/Alex8791-cyber/cognithor

Reply ONLY with the response text, no meta-comments.
""".strip()


@dataclass
class ScanConfig:
    """Configuration for a scan cycle."""

    product_name: str = "Cognithor"
    product_description: str = ""
    reply_tone: str = "helpful, technically credible, no sales pitch"
    min_score: int = 60


# Type alias for the LLM function (matches Cognithor's UnifiedLLMClient.chat signature)
LLMFn = Callable[..., Awaitable[dict[str, Any]]]


class RedditScanner:
    """Fetches Reddit posts via public JSON and scores them via LLM."""

    def __init__(self, llm_fn: LLMFn | None = None) -> None:
        self._llm_fn = llm_fn
        self._http = httpx.Client(
            timeout=30,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )

    def fetch_posts(self, subreddit: str, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch new posts from a subreddit via public JSON feed."""
        url = f"https://www.reddit.com/r/{subreddit}/new.json"
        try:
            resp = self._http.get(url, params={"limit": min(limit, 100), "raw_json": 1})
            resp.raise_for_status()
            children = resp.json().get("data", {}).get("children", [])
            return [
                {
                    "id": p.get("id", ""),
                    "title": p.get("title", ""),
                    "selftext": p.get("selftext", ""),
                    "subreddit": p.get("subreddit", subreddit),
                    "permalink": p.get("permalink", ""),
                    "author": p.get("author", "[deleted]"),
                    "created_utc": p.get("created_utc", 0),
                    "score": p.get("score", 0),
                    "num_comments": p.get("num_comments", 0),
                }
                for child in children
                for p in [child.get("data", {})]
                if p.get("id")
            ]
        except Exception as exc:
            log.warning("reddit_fetch_failed", subreddit=subreddit, error=str(exc))
            return []

    async def score_post(
        self,
        post: dict[str, Any],
        config: ScanConfig,
    ) -> tuple[int, str]:
        """Score a post for intent 0-100 via LLM. Returns (score, reasoning)."""
        if not self._llm_fn:
            return 0, "No LLM available"

        prompt = SCORE_PROMPT.format(
            product_name=config.product_name,
            product_description=config.product_description,
            subreddit=post.get("subreddit", ""),
            title=post.get("title", ""),
            body=(post.get("selftext") or "")[:1000],
        )
        try:
            response = await self._llm_fn(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            raw = response.get("message", {}).get("content", "")
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                return 0, "No JSON in LLM response"
            data = json.loads(raw[start:end])
            score = max(0, min(100, int(data.get("score", 0))))
            reasoning = str(data.get("reasoning", ""))
            return score, reasoning
        except Exception as exc:
            log.warning("score_failed", post_id=post.get("id"), error=str(exc))
            return 0, "Scoring failed"

    async def draft_reply(
        self,
        post: dict[str, Any],
        config: ScanConfig,
        *,
        style_profile: dict[str, Any] | None = None,
        few_shot_examples: list[dict[str, Any]] | None = None,
    ) -> str:
        """Draft a reply for a post via LLM."""
        if not self._llm_fn:
            return "[No LLM available for reply drafting]"

        style_ctx = ""
        if style_profile:
            style_ctx = (
                f"STYLE PROFILE for r/{post.get('subreddit', '')}:\n"
                f"- What works: {style_profile.get('what_works', '')}\n"
                f"- Avoid: {style_profile.get('what_fails', '')}\n"
                f"- Optimal tone: {style_profile.get('optimal_tone', config.reply_tone)}"
            )

        few_shot_ctx = ""
        if few_shot_examples:
            lines = ["PROVEN REPLIES that performed well in this subreddit:"]
            for i, ex in enumerate(few_shot_examples[:3], 1):
                upv = ex.get("reply_upvotes", 0)
                txt = ex.get("reply_text", "")[:150]
                lines.append(f'{i}. [{upv} upvotes] "{txt}"')
            few_shot_ctx = "\n".join(lines)

        max_words = style_profile.get("optimal_length", 150) if style_profile else 150

        prompt = REPLY_PROMPT.format(
            product_name=config.product_name,
            reply_tone=(
                style_profile.get("optimal_tone", config.reply_tone)
                if style_profile
                else config.reply_tone
            ),
            subreddit=post.get("subreddit", ""),
            title=post.get("title", ""),
            body=(post.get("selftext") or "")[:1000],
            style_context=style_ctx,
            few_shot_context=few_shot_ctx,
            max_words=max_words,
        )
        try:
            response = await self._llm_fn(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
            )
            return response.get("message", {}).get("content", "").strip()
        except Exception as exc:
            log.warning("draft_failed", post_id=post.get("id"), error=str(exc))
            return "[Reply draft failed]"

    def close(self) -> None:
        self._http.close()
