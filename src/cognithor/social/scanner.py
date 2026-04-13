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

# Minimum intent_score to include the GitHub link in a reply. Below this, replies
# are link-free so we don't look like a drive-by marketer.
MIN_LINK_SCORE = 75

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

# Shared anti-patterns used by scanner and refiner to kill "AI slop" tone.
# Anything in this list triggers instant downvotes on r/LocalLLaMA and similar subs.
ANTI_PATTERNS = """
NEVER do ANY of this (instant AI-slop detection):
- Do not start with "Great question", "I understand", "You might want to",
  "Have you considered", or "Thanks for sharing"
- Use em-dashes (—). Use a comma or period instead.
- Use bullet-point lists in a conversational reply
- End with "Hope this helps!", "Let me know if...", "Good luck!", "Cheers!"
- Use words like "leverage", "seamlessly", "robust", "streamline",
  "powerful tool", "game-changer", or "empower"
- Sound cheerful, enthusiastic, or customer-support-y
- Pretend to be a brand or support agent
- Pad answers with context the OP already stated
- Refer to "the user" or "your needs"
""".strip()

# Per-subreddit persona hints — the LLM matches the culture of each sub.
SUBREDDIT_PERSONAS: dict[str, str] = {
    "LocalLLaMA": (
        "This is r/LocalLLaMA: extremely AI-literate, skeptical of hype, benchmark-obsessed. "
        "They care about VRAM, tokens/sec, quant levels, context length. They hate marketing. "
        "Lowercase is common. Sarcasm is common. They will downvote anything that smells like "
        "an LLM output or a product pitch. Reply like a tired dev with strong opinions."
    ),
    "selfhosted": (
        "This is r/selfhosted: pragmatic, docker-native, values stability and simplicity over "
        "features. They distrust cloud-first tools. They ask about backups, resource usage, "
        "and 'what happens when this project dies'. Blunt, no fluff."
    ),
    "ollama": (
        "This is r/ollama: practical users focused on which model+quant fits their hardware. "
        "Short replies. Casual. Often just a command or a model name."
    ),
    "homelab": (
        "This is r/homelab: hardware-focused, loves actual specs and setups. Blunt, no fluff. "
        "Will ask 'why not just use X' if you suggest something overengineered."
    ),
    "MachineLearning": (
        "This is r/MachineLearning: academic-leaning, cites papers, values rigor. "
        "They hate marketing even more than LocalLLaMA. Mention only if genuinely on-topic."
    ),
}

DEFAULT_PERSONA = (
    "You're a regular redditor. Informal. No marketing tone. "
    "Answer like you're typing from your phone on the couch."
)

REPLY_PROMPT = """
You are a redditor who happens to use {product_name}.
You are NOT a marketer, brand, or support agent.
You scroll r/{subreddit}, see a post, and reply only if you have
something actually useful to say.

{persona_hint}

POST:
Title: {title}
Text: {body}

{style_context}
{few_shot_context}

TASK: Write a Reddit reply.

Rules:
- Answer the ACTUAL question first. If someone else's tool is
  obviously better for their case, say that instead.
- Mention {product_name} ONLY if it's genuinely the best fit.
  One sentence, in passing. Never as a pitch.
- {link_instruction}
- Max {max_words} words. Usually half that is better.
- Lowercase is fine. Typos are fine. Incomplete sentences are fine.
- Be specific: numbers, version names, actual commands, real tradeoffs.
- If you have nothing useful to add, reply with exactly: SKIP

{anti_patterns}

Output ONLY the reply text. No preamble, no sign-off, no meta-commentary.
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
        intent_score: int = 0,
    ) -> str:
        """Draft a reply for a post via LLM.

        The reply is intentionally terse and reddit-native. The GitHub link is only
        included for high-intent posts (score >= MIN_LINK_SCORE) — low-intent posts
        get a link-free answer so we don't look like a drive-by marketer.
        """
        if not self._llm_fn:
            return "[No LLM available for reply drafting]"

        subreddit = post.get("subreddit", "") or ""
        persona_hint = SUBREDDIT_PERSONAS.get(subreddit, DEFAULT_PERSONA)

        # TONE EXAMPLES (not content templates): match the vibe, don't copy the words.
        few_shot_ctx = ""
        if few_shot_examples:
            lines = [
                "TONE EXAMPLES from this subreddit (match the VIBE, not the content — "
                "do not copy phrasing, only the register/length/rhythm):"
            ]
            for i, ex in enumerate(few_shot_examples[:3], 1):
                upv = ex.get("reply_upvotes", 0)
                txt = ex.get("reply_text", "")[:150]
                lines.append(f'{i}. [{upv} upvotes] "{txt}"')
            few_shot_ctx = "\n".join(lines)

        style_ctx = ""
        if style_profile:
            works = style_profile.get("what_works", "")
            fails = style_profile.get("what_fails", "")
            if works or fails:
                style_ctx = f"SUBREDDIT NOTES:\n- What lands: {works}\n- What flops: {fails}"

        # Shorter is better — cap optimal_length aggressively.
        raw_len = style_profile.get("optimal_length", 80) if style_profile else 80
        max_words = min(raw_len, 120)

        # Link-gating: only high-intent posts get the GitHub link, and never as markdown.
        if intent_score >= MIN_LINK_SCORE:
            link_instruction = (
                "If — and only if — the OP is explicitly asking for tool recommendations, "
                "you may mention 'github.com/Alex8791-cyber/cognithor' in plain text (no "
                "markdown link, no 'check out', no 'you should try'). If they're not asking, "
                "skip the link entirely."
            )
        else:
            link_instruction = (
                "Do NOT include any link. Do NOT mention GitHub. "
                "Your Reddit profile bio has the link if anyone cares to look."
            )

        prompt = REPLY_PROMPT.format(
            product_name=config.product_name,
            subreddit=subreddit,
            persona_hint=persona_hint,
            title=post.get("title", ""),
            body=(post.get("selftext") or "")[:1000],
            style_context=style_ctx,
            few_shot_context=few_shot_ctx,
            link_instruction=link_instruction,
            anti_patterns=ANTI_PATTERNS,
            max_words=max_words,
        )
        try:
            response = await self._llm_fn(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.85,  # high variance — predictability is what gets caught
            )
            text = response.get("message", {}).get("content", "").strip()
            # LLM self-veto: return empty string so caller can skip archiving this lead
            if text.strip().upper() == "SKIP":
                return ""
            return text
        except Exception as exc:
            log.warning("draft_failed", post_id=post.get("id"), error=str(exc))
            return "[Reply draft failed]"

    def close(self) -> None:
        self._http.close()
