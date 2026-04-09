"""LLM-based reply refinement and variant generation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from jarvis.utils.logging import get_logger

log = get_logger(__name__)

LLMFn = Callable[..., Awaitable[dict[str, Any]]]

REFINE_PROMPT = """
You are an expert Reddit reply editor. Improve this draft reply.

PRODUCT: {product_name}
SUBREDDIT: r/{subreddit}

ORIGINAL POST:
Title: {title}
Text: {body}

CURRENT DRAFT:
{current_draft}

{style_context}
{few_shot_context}
{hint_context}

Rewrite the reply to be more effective. Keep it under {max_words} words.
Maintain a {tone} tone. No meta-commentary, output ONLY the improved reply.
""".strip()

VARIANT_PROMPT = """
You are an expert Reddit reply writer. Write a {style_name} reply.

PRODUCT: {product_name}
SUBREDDIT: r/{subreddit}

ORIGINAL POST:
Title: {title}
Text: {body}

Style: {style_description}
Max length: {max_words} words.
Tone: {tone}

{style_context}

Output ONLY the reply text, no meta-commentary.
""".strip()

VARIANT_STYLES = [
    (
        "technical",
        "Technically detailed with specific features, code examples or architecture details",
    ),
    (
        "casual",
        "Short, casual, reddit-native. Conversational tone, like talking to a friend",
    ),
    (
        "question",
        "Start with a question that shows understanding, then suggest the product as one option",
    ),
]


@dataclass
class RefinedReply:
    text: str
    style: str
    changes_summary: str = ""


class ReplyRefiner:
    """Refines reply drafts via LLM with style profile and few-shot context."""

    def __init__(self, llm_fn: LLMFn | None = None) -> None:
        self._llm_fn = llm_fn

    async def refine(
        self,
        post: dict[str, Any],
        current_draft: str,
        product_name: str,
        *,
        user_hint: str = "",
        style_profile: dict[str, Any] | None = None,
        few_shot_examples: list[dict[str, Any]] | None = None,
        tone: str = "helpful, technically credible",
        max_words: int = 150,
    ) -> RefinedReply:
        if not self._llm_fn:
            return RefinedReply(
                text=current_draft, style="original", changes_summary="No LLM available"
            )

        style_ctx = ""
        if style_profile:
            style_ctx = (
                f"STYLE PROFILE for r/{post.get('subreddit', '')}:\n"
                f"- What works: {style_profile.get('what_works', '')}\n"
                f"- What fails: {style_profile.get('what_fails', '')}\n"
                f"- Optimal length: ~{style_profile.get('optimal_length', 150)} words"
            )
            max_words = style_profile.get("optimal_length", max_words)

        few_shot_ctx = ""
        if few_shot_examples:
            lines = ["TOP PERFORMING REPLIES in this subreddit:"]
            for i, ex in enumerate(few_shot_examples[:3], 1):
                upvotes = ex.get("reply_upvotes", 0)
                snippet = ex.get("reply_text", "")[:200]
                lines.append(f'{i}. [{upvotes} upvotes] "{snippet}"')
            few_shot_ctx = "\n".join(lines)

        hint_ctx = f"USER REQUEST: {user_hint}" if user_hint else ""

        prompt = REFINE_PROMPT.format(
            product_name=product_name,
            subreddit=post.get("subreddit", ""),
            title=post.get("title", ""),
            body=(post.get("selftext") or "")[:500],
            current_draft=current_draft,
            style_context=style_ctx,
            few_shot_context=few_shot_ctx,
            hint_context=hint_ctx,
            max_words=max_words,
            tone=tone,
        )

        try:
            response = await self._llm_fn(
                messages=[{"role": "user", "content": prompt}], temperature=0.4
            )
            text = response.get("message", {}).get("content", "").strip()
            return RefinedReply(
                text=text or current_draft,
                style="refined",
                changes_summary=hint_ctx or "General improvement",
            )
        except Exception as exc:
            log.warning("refine_failed", error=str(exc))
            return RefinedReply(
                text=current_draft,
                style="original",
                changes_summary=f"Refinement failed: {exc}",
            )

    async def generate_variants(
        self,
        post: dict[str, Any],
        product_name: str,
        count: int = 3,
        *,
        style_profile: dict[str, Any] | None = None,
        tone: str = "helpful, technically credible",
        max_words: int = 150,
    ) -> list[RefinedReply]:
        if not self._llm_fn:
            return []

        style_ctx = ""
        if style_profile:
            style_ctx = (
                f"STYLE PROFILE:\n"
                f"- What works: {style_profile.get('what_works', '')}\n"
                f"- Avoid: {style_profile.get('what_fails', '')}"
            )

        variants = []
        for i in range(min(count, len(VARIANT_STYLES))):
            style_name, style_desc = VARIANT_STYLES[i]
            prompt = VARIANT_PROMPT.format(
                product_name=product_name,
                subreddit=post.get("subreddit", ""),
                title=post.get("title", ""),
                body=(post.get("selftext") or "")[:500],
                style_name=style_name,
                style_description=style_desc,
                max_words=max_words,
                tone=tone,
                style_context=style_ctx,
            )
            try:
                response = await self._llm_fn(
                    messages=[{"role": "user", "content": prompt}], temperature=0.6
                )
                text = response.get("message", {}).get("content", "").strip()
                if text:
                    variants.append(RefinedReply(text=text, style=style_name))
            except Exception as exc:
                log.warning("variant_failed", style=style_name, error=str(exc))

        return variants
