"""Tests for social.refiner — LLM reply refinement + variants."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from cognithor.social.refiner import RefinedReply, ReplyRefiner


@pytest.fixture()
def refiner():
    llm_fn = AsyncMock(
        return_value={"message": {"content": "Improved reply with more technical depth."}}
    )
    return ReplyRefiner(llm_fn=llm_fn)


def _extract_prompt(call_args) -> str:
    """Helper to extract the prompt text from llm_fn call_args."""
    if call_args[1].get("messages"):
        messages = call_args[1]["messages"]
    elif call_args[0]:
        messages = call_args[0][0]
    else:
        messages = call_args[1]["messages"]
    return messages[0]["content"]


class TestReplyRefiner:
    @pytest.mark.asyncio
    async def test_refine_returns_refined_reply(self, refiner: ReplyRefiner):
        result = await refiner.refine(
            post={
                "title": "Need local AI",
                "selftext": "Looking for tools",
                "subreddit": "LocalLLaMA",
            },
            current_draft="Check out Cognithor",
            product_name="Cognithor",
        )
        assert isinstance(result, RefinedReply)
        assert result.text == "Improved reply with more technical depth."
        assert result.style == "refined"

    @pytest.mark.asyncio
    async def test_refine_with_hint(self, refiner: ReplyRefiner):
        result = await refiner.refine(
            post={"title": "T", "selftext": "", "subreddit": "SaaS"},
            current_draft="Draft",
            product_name="X",
            user_hint="make it shorter",
        )
        assert result.text  # LLM was called
        prompt_text = _extract_prompt(refiner._llm_fn.call_args)
        assert "shorter" in prompt_text

    @pytest.mark.asyncio
    async def test_generate_variants(self):
        call_count = 0

        async def mock_llm(**kwargs):
            nonlocal call_count
            call_count += 1
            styles = ["Technical deep-dive reply", "Short casual reply", "Question-based reply"]
            content = styles[call_count - 1] if call_count <= 3 else "fallback"
            return {"message": {"content": content}}

        refiner = ReplyRefiner(llm_fn=mock_llm)
        variants = await refiner.generate_variants(
            post={"title": "T", "selftext": "", "subreddit": "SaaS"},
            product_name="X",
            count=3,
        )
        assert len(variants) == 3
        assert variants[0].text != variants[1].text

    @pytest.mark.asyncio
    async def test_refine_with_style_profile(self, refiner: ReplyRefiner):
        profile = {
            "what_works": "Technical depth",
            "what_fails": "Sales pitch",
            "optimal_length": 120,
        }
        result = await refiner.refine(
            post={"title": "T", "selftext": "", "subreddit": "LLaMA"},
            current_draft="Draft",
            product_name="X",
            style_profile=profile,
        )
        assert result.text
        prompt_text = _extract_prompt(refiner._llm_fn.call_args)
        assert "Technical depth" in prompt_text

    @pytest.mark.asyncio
    async def test_refine_with_few_shot(self, refiner: ReplyRefiner):
        few_shot = [
            {"reply_text": "Great example reply", "reply_upvotes": 8},
        ]
        result = await refiner.refine(
            post={"title": "T", "selftext": "", "subreddit": "X"},
            current_draft="Draft",
            product_name="X",
            few_shot_examples=few_shot,
        )
        assert result.text
        prompt_text = _extract_prompt(refiner._llm_fn.call_args)
        assert "Great example reply" in prompt_text
