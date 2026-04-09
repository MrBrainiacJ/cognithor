"""Reply template management — save, match, apply successful reply patterns."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jarvis.utils.logging import get_logger

if TYPE_CHECKING:
    from jarvis.social.store import LeadStore

log = get_logger(__name__)

AUTO_SAVE_THRESHOLD = 85
PROMPT_SAVE_THRESHOLD = 70


class TemplateManager:
    """Manages reply templates with auto-save from high-performing replies."""

    def __init__(self, store: LeadStore) -> None:
        self._store = store

    def create(
        self,
        name: str,
        template_text: str,
        subreddit: str = "",
        style: str = "",
        created_from_lead: str = "",
    ) -> str:
        return self._store.save_template(
            name=name,
            template_text=template_text,
            subreddit=subreddit,
            style=style,
            created_from_lead=created_from_lead,
        )

    def list_for_subreddit(self, subreddit: str) -> list[dict[str, Any]]:
        return self._store.list_templates(subreddit=subreddit or None)

    def apply(self, template_id: str, **variables: str) -> str:
        templates = self._store.list_templates()
        for t in templates:
            if t["id"] == template_id:
                self._store.increment_template_use(template_id)
                text = t["template_text"]
                for key, val in variables.items():
                    text = text.replace(f"{{{key}}}", val)
                return text
        return ""

    def delete(self, template_id: str) -> None:
        self._store.delete_template(template_id)

    @staticmethod
    def should_auto_save(engagement_score: int) -> bool:
        return engagement_score >= AUTO_SAVE_THRESHOLD

    @staticmethod
    def should_prompt_save(engagement_score: int) -> bool:
        return PROMPT_SAVE_THRESHOLD <= engagement_score < AUTO_SAVE_THRESHOLD
