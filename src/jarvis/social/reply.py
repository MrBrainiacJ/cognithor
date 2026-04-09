"""Hybrid reply posting — clipboard, browser, or auto (Playwright)."""

from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from jarvis.utils.logging import get_logger

if TYPE_CHECKING:
    from jarvis.social.models import Lead

log = get_logger(__name__)


class ReplyMode(StrEnum):
    CLIPBOARD = "clipboard"
    BROWSER = "browser"
    AUTO = "auto"


@dataclass
class ReplyResult:
    success: bool
    mode: ReplyMode
    error: str = ""


def _copy_to_clipboard(text: str) -> None:
    """Copy text to system clipboard (cross-platform)."""
    try:
        import subprocess
        import sys

        if sys.platform == "win32":
            process = subprocess.Popen(
                ["clip"],
                stdin=subprocess.PIPE,
                shell=True,
            )
            process.communicate(text.encode("utf-16-le"))
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
    except Exception as exc:
        log.warning("clipboard_copy_failed", error=str(exc))
        # Fallback: try pyperclip
        try:
            import pyperclip

            pyperclip.copy(text)
        except ImportError:
            raise RuntimeError(f"Cannot copy to clipboard: {exc}") from exc


class ReplyPoster:
    """Posts replies to Reddit leads via clipboard, browser, or Playwright."""

    def __init__(self, browser_agent: Any = None) -> None:
        self._browser_agent = browser_agent

    def post(self, lead: Lead, mode: ReplyMode = ReplyMode.CLIPBOARD) -> ReplyResult:
        """Post a reply to a lead."""
        reply_text = lead.reply_final or lead.reply_draft

        if not reply_text.strip():
            return ReplyResult(success=False, mode=mode, error="Reply text is empty")

        try:
            if mode == ReplyMode.CLIPBOARD:
                _copy_to_clipboard(reply_text)
                webbrowser.open(lead.url)
                log.info("reply_clipboard", lead_id=lead.id, url=lead.url)
                return ReplyResult(success=True, mode=mode)

            elif mode == ReplyMode.BROWSER:
                _copy_to_clipboard(reply_text)
                webbrowser.open(lead.url)
                log.info("reply_browser", lead_id=lead.id, url=lead.url)
                return ReplyResult(success=True, mode=mode)

            elif mode == ReplyMode.AUTO:
                return self._auto_post(lead, reply_text)

            return ReplyResult(success=False, mode=mode, error=f"Unknown mode: {mode}")
        except Exception as exc:
            log.error("reply_failed", lead_id=lead.id, error=str(exc))
            return ReplyResult(success=False, mode=mode, error=str(exc))

    def _auto_post(self, lead: Lead, reply_text: str) -> ReplyResult:
        """Auto-post via Playwright browser agent."""
        if self._browser_agent is None:
            # Fallback to clipboard mode
            log.warning("auto_post_no_browser_agent_falling_back_to_clipboard")
            _copy_to_clipboard(reply_text)
            webbrowser.open(lead.url)
            return ReplyResult(
                success=True,
                mode=ReplyMode.CLIPBOARD,
                error="Browser agent not available, used clipboard fallback",
            )

        # Playwright auto-posting will be wired when BrowserAgent is available
        # For now, this is a placeholder that falls back to clipboard
        log.info("auto_post_placeholder", lead_id=lead.id)
        _copy_to_clipboard(reply_text)
        webbrowser.open(lead.url)
        return ReplyResult(
            success=True,
            mode=ReplyMode.CLIPBOARD,
            error="Auto-post not yet wired, used clipboard",
        )
