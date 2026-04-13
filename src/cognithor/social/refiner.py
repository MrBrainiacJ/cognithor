"""LLM-based reply refinement and variant generation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from cognithor.social.scanner import (
    ANTI_PATTERNS,
    DEFAULT_PERSONA,
    SUBREDDIT_PERSONAS,
)
from cognithor.utils.logging import get_logger

log = get_logger(__name__)

LLMFn = Callable[..., Awaitable[dict[str, Any]]]

REFINE_PROMPT = """
You are rewriting a Reddit reply to sound less like an LLM and more like a real redditor.

{persona_hint}

ORIGINAL POST:
Title: {title}
Text: {body}

CURRENT DRAFT (probably too formal, too long, or too AI-sounding):
{current_draft}

{style_context}
{few_shot_context}
{hint_context}

TASK: Rewrite the draft. Keep what's factually useful, strip everything else.
- Max {max_words} words. Usually half that is better.
- Answer the question first. Everything else is optional.
- Mention {product_name} in passing only if the draft did so helpfully; otherwise drop it.
- Lowercase, typos, and fragments are all fine.

{anti_patterns}

Output ONLY the rewritten reply. No meta-commentary, no "Here's the improved version:".
""".strip()

VARIANT_PROMPT = """
You are writing a Reddit reply in a specific style: "{style_name}".

{persona_hint}

POST:
Title: {title}
Text: {body}

STYLE BRIEF: {style_description}

Max length: {max_words} words.
Product to mention (only if genuinely relevant): {product_name}

{style_context}

{anti_patterns}

Output ONLY the reply text. No preamble, no sign-off.
""".strip()

# Reddit-native variants — these are the patterns that actually get upvotes on
# tech subs, not the generic "technical / casual / question" framings.
VARIANT_STYLES = [
    (
        "one_liner",
        "A single sentence, max 15 words. Blunt, direct, like a dismissive power-user "
        "reply. Example tone: 'just use llama.cpp with q4, ollama adds nothing here'",
    ),
    (
        "specific",
        "Two or three sentences with concrete numbers, version names, or actual commands. "
        "Zero fluff. The kind of reply someone screenshots and saves.",
    ),
    (
        "contrarian",
        "Start by partially pushing back on the OP's framing ('fwiw that's not really "
        "the bottleneck'), then give your actual take. Skeptical but not rude.",
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
        del tone  # tone is now baked into persona_hint + ANTI_PATTERNS
        if not self._llm_fn:
            return RefinedReply(
                text=current_draft, style="original", changes_summary="No LLM available"
            )

        subreddit = post.get("subreddit", "") or ""
        persona_hint = SUBREDDIT_PERSONAS.get(subreddit, DEFAULT_PERSONA)

        style_ctx = ""
        if style_profile:
            works = style_profile.get("what_works", "")
            fails = style_profile.get("what_fails", "")
            if works or fails:
                style_ctx = f"SUBREDDIT NOTES:\n- What lands: {works}\n- What flops: {fails}"
            max_words = min(style_profile.get("optimal_length", max_words), 120)
        else:
            max_words = min(max_words, 120)

        few_shot_ctx = ""
        if few_shot_examples:
            lines = ["TONE EXAMPLES from this subreddit (match the VIBE, not the content):"]
            for i, ex in enumerate(few_shot_examples[:3], 1):
                upvotes = ex.get("reply_upvotes", 0)
                snippet = ex.get("reply_text", "")[:200]
                lines.append(f'{i}. [{upvotes} upvotes] "{snippet}"')
            few_shot_ctx = "\n".join(lines)

        hint_ctx = f"USER REQUEST: {user_hint}" if user_hint else ""

        prompt = REFINE_PROMPT.format(
            product_name=product_name,
            persona_hint=persona_hint,
            title=post.get("title", ""),
            body=(post.get("selftext") or "")[:500],
            current_draft=current_draft,
            style_context=style_ctx,
            few_shot_context=few_shot_ctx,
            hint_context=hint_ctx,
            max_words=max_words,
            anti_patterns=ANTI_PATTERNS,
        )

        try:
            response = await self._llm_fn(
                messages=[{"role": "user", "content": prompt}], temperature=0.75
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
        del tone  # tone is now baked into persona_hint + ANTI_PATTERNS
        if not self._llm_fn:
            return []

        subreddit = post.get("subreddit", "") or ""
        persona_hint = SUBREDDIT_PERSONAS.get(subreddit, DEFAULT_PERSONA)

        style_ctx = ""
        if style_profile:
            works = style_profile.get("what_works", "")
            fails = style_profile.get("what_fails", "")
            if works or fails:
                style_ctx = f"SUBREDDIT NOTES:\n- What lands: {works}\n- What flops: {fails}"

        # Cap variants at a tight reddit-friendly length regardless of input.
        capped_max = min(max_words, 100)

        variants = []
        for i in range(min(count, len(VARIANT_STYLES))):
            style_name, style_desc = VARIANT_STYLES[i]
            prompt = VARIANT_PROMPT.format(
                product_name=product_name,
                persona_hint=persona_hint,
                title=post.get("title", ""),
                body=(post.get("selftext") or "")[:500],
                style_name=style_name,
                style_description=style_desc,
                max_words=capped_max,
                style_context=style_ctx,
                anti_patterns=ANTI_PATTERNS,
            )
            try:
                response = await self._llm_fn(
                    messages=[{"role": "user", "content": prompt}], temperature=0.9
                )
                text = response.get("message", {}).get("content", "").strip()
                if text:
                    variants.append(RefinedReply(text=text, style=style_name))
            except Exception as exc:
                log.warning("variant_failed", style=style_name, error=str(exc))

        return variants
