"""Tests for social.templates — reply template management."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.social.templates import TemplateManager

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def manager(tmp_path: Path) -> TemplateManager:
    from jarvis.social.store import LeadStore

    store = LeadStore(str(tmp_path / "leads.db"))
    return TemplateManager(store=store)


class TestTemplateManager:
    def test_create_template(self, manager: TemplateManager):
        tid = manager.create(
            name="Tech Intro",
            template_text="Hey, {product_name} solves this — it has {feature}.",
            subreddit="LocalLLaMA",
            style="technical",
        )
        assert tid
        templates = manager.list_for_subreddit("LocalLLaMA")
        assert len(templates) == 1
        assert templates[0]["name"] == "Tech Intro"

    def test_apply_template(self, manager: TemplateManager):
        manager.create(name="T", template_text="Check out {product_name} for r/{subreddit}!")
        templates = manager.list_for_subreddit("SaaS")
        applied = manager.apply(templates[0]["id"], product_name="Cognithor", subreddit="SaaS")
        assert applied == "Check out Cognithor for r/SaaS!"

    def test_should_auto_save(self, manager: TemplateManager):
        assert manager.should_auto_save(engagement_score=90) is True
        assert manager.should_auto_save(engagement_score=50) is False
        assert manager.should_prompt_save(engagement_score=75) is True
        assert manager.should_prompt_save(engagement_score=60) is False

    def test_delete(self, manager: TemplateManager):
        tid = manager.create(name="X", template_text="text")
        manager.delete(tid)
        assert len(manager.list_for_subreddit("")) == 0
