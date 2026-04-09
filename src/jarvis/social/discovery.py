"""Smart subreddit discovery via LLM + Reddit JSON validation."""

from __future__ import annotations

import json
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from jarvis.utils.logging import get_logger

log = get_logger(__name__)

LLMFn = Callable[..., Awaitable[dict[str, Any]]]

_USER_AGENT = "cognithor:subreddit_discovery:v1.0 (by u/cognithor-bot)"

DISCOVER_PROMPT = """
You are an expert in Reddit communities. Given a product, suggest 15-20 subreddits
where potential users might discuss related problems.

PRODUCT: {product_name}
DESCRIPTION: {product_description}

Rules:
- Include both large (>100k) and niche (<50k) subreddits
- Focus on subreddits where people ask for help, not just news
- Include technology-specific and use-case-specific subreddits
- NO NSFW subreddits

Reply ONLY with a JSON array of subreddit names (without r/ prefix):
["SubredditName1", "SubredditName2", ...]
""".strip()


@dataclass
class SubredditSuggestion:
    name: str
    subscribers: int = 0
    posts_per_day: float = 0.0
    relevance_score: int = 0
    reasoning: str = ""
    sample_posts: list[str] = field(default_factory=list)


class SubredditDiscovery:
    """Discovers relevant subreddits for a product via LLM + Reddit validation."""

    def __init__(self, llm_fn: LLMFn | None = None) -> None:
        self._llm_fn = llm_fn
        self._http = httpx.Client(
            timeout=15,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )

    async def discover(
        self,
        product_name: str,
        product_description: str,
        max_results: int = 10,
    ) -> list[SubredditSuggestion]:
        if not self._llm_fn:
            return []

        # Step 1: LLM generates candidates
        prompt = DISCOVER_PROMPT.format(
            product_name=product_name,
            product_description=product_description,
        )
        try:
            response = await self._llm_fn(
                messages=[{"role": "user", "content": prompt}], temperature=0.3
            )
            raw = response.get("message", {}).get("content", "")
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start == -1 or end == 0:
                return []
            candidates = json.loads(raw[start:end])
        except Exception as exc:
            log.warning("discovery_llm_failed", error=str(exc))
            return []

        # Step 2: Validate each candidate via Reddit JSON
        suggestions = []
        for name in candidates[:20]:
            try:
                about = self._http.get(
                    f"https://www.reddit.com/r/{name}/about.json",
                    params={"raw_json": 1},
                )
                about.raise_for_status()
                data = about.json().get("data", {})

                subscribers = data.get("subscribers", 0)
                active = data.get("active_user_count", 0)

                # Estimate posts per day from active users
                posts_per_day = max(1.0, active * 0.1)

                # Get sample posts
                sample_posts = []
                try:
                    posts_resp = self._http.get(
                        f"https://www.reddit.com/r/{name}/new.json",
                        params={"limit": 5, "raw_json": 1},
                    )
                    if posts_resp.status_code == 200:
                        children = posts_resp.json().get("data", {}).get("children", [])
                        sample_posts = [c["data"]["title"] for c in children[:3]]
                except Exception:
                    pass

                # Rank score: relevance × posts × log(subscribers)
                posts_per_day_val = posts_per_day  # noqa: F841 (used in sort key)

                suggestions.append(
                    SubredditSuggestion(
                        name=name,
                        subscribers=subscribers,
                        posts_per_day=round(posts_per_day, 1),
                        relevance_score=0,  # Set after sorting
                        reasoning=f"{subscribers:,} subscribers, ~{posts_per_day:.0f} posts/day",
                        sample_posts=sample_posts,
                    )
                )

                import asyncio

                await asyncio.sleep(0.5)  # Rate limit

            except Exception as exc:
                log.debug("discovery_validation_failed", subreddit=name, error=str(exc))

        # Sort by rank, assign relevance scores
        suggestions.sort(
            key=lambda s: s.posts_per_day * math.log(max(s.subscribers, 1)),
            reverse=True,
        )
        for i, s in enumerate(suggestions[:max_results]):
            s.relevance_score = max(10, 100 - i * 8)

        return suggestions[:max_results]

    def close(self) -> None:
        self._http.close()
