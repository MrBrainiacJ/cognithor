"""User-friendly error messages for Jarvis channels.

Replaces generic error messages with contextual, empathetic error descriptions.
Used across all channels. Supports German (default) and English.
"""

from __future__ import annotations

import os

# ── Language Detection ─────────────────────────────────────────
# Set JARVIS_LANGUAGE=en (or COGNITHOR_LANGUAGE=en) to switch to English.
# Default: "de" (German).

_LANG = os.environ.get(
    "JARVIS_LANGUAGE",
    os.environ.get("COGNITHOR_LANGUAGE", "de"),
).lower()[:2]


def _t(de: str, en: str) -> str:
    """Returns the German or English string based on the configured language."""
    return en if _LANG == "en" else de


# ── Tool-Friendly-Names ─────────────────────────────────────────
# Maps internal MCP tool names to human-readable names.

_TOOL_FRIENDLY_NAMES_DE: dict[str, str] = {
    "exec_command": "Shell-Befehl",
    "write_file": "Datei schreiben",
    "read_file": "Datei lesen",
    "edit_file": "Datei bearbeiten",
    "list_directory": "Verzeichnis auflisten",
    "run_python": "Python-Code",
    "web_search": "Web-Suche",
    "web_news_search": "Nachrichten-Suche",
    "web_fetch": "Webseite abrufen",
    "search_and_read": "Web-Recherche",
    "search_memory": "Wissens-Suche",
    "save_to_memory": "Wissen speichern",
    "document_export": "Dokument erstellen",
    "media_analyze_image": "Bildanalyse",
    "media_transcribe_audio": "Audio-Transkription",
    "media_extract_text": "Text-Extraktion",
    "media_tts": "Sprachausgabe",
    "vault_search": "Vault-Suche",
    "vault_write": "Vault-Eintrag",
    "analyze_code": "Code-Analyse",
    "browser_navigate": "Browser-Navigation",
    "browser_screenshot": "Browser-Screenshot",
}

_TOOL_FRIENDLY_NAMES_EN: dict[str, str] = {
    "exec_command": "shell command",
    "write_file": "write file",
    "read_file": "read file",
    "edit_file": "edit file",
    "list_directory": "list directory",
    "run_python": "Python code",
    "web_search": "web search",
    "web_news_search": "news search",
    "web_fetch": "fetch webpage",
    "search_and_read": "web research",
    "search_memory": "knowledge search",
    "save_to_memory": "save knowledge",
    "document_export": "create document",
    "media_analyze_image": "image analysis",
    "media_transcribe_audio": "audio transcription",
    "media_extract_text": "text extraction",
    "media_tts": "text-to-speech",
    "vault_search": "vault search",
    "vault_write": "vault entry",
    "analyze_code": "code analysis",
    "browser_navigate": "browser navigation",
    "browser_screenshot": "browser screenshot",
}


def _friendly_tool_name(tool: str) -> str:
    """Returns a user-friendly name for a tool."""
    names = _TOOL_FRIENDLY_NAMES_EN if _LANG == "en" else _TOOL_FRIENDLY_NAMES_DE
    return names.get(tool, tool)


# ── Error Classification ────────────────────────────────────────

def classify_error_for_user(exc: BaseException) -> str:
    """Classifies an exception into a user-friendly error message.

    Used by all channels instead of generic error messages.
    Language depends on JARVIS_LANGUAGE / COGNITHOR_LANGUAGE env var.
    """
    exc_type = type(exc).__name__
    exc_str = str(exc)[:200]

    if exc_type in ("TimeoutError", "asyncio.TimeoutError") or "timeout" in exc_str.lower():
        return _t(
            "Die Verarbeitung hat leider zu lange gedauert. "
            "Das kann an einem langsamen Netzwerk oder einem überlasteten Dienst liegen. "
            "Bitte versuch es gleich noch einmal.",
            "The request timed out. This may be due to a slow network or an overloaded "
            "service. Please try again in a moment.",
        )

    if exc_type in ("ConnectionError", "ConnectError", "OSError") or "connection" in exc_str.lower():
        return _t(
            "Es gab ein Verbindungsproblem. "
            "Bitte prüfe deine Internetverbindung und versuch es erneut.",
            "There was a connection problem. "
            "Please check your internet connection and try again.",
        )

    if exc_type in ("PermissionError", "AuthenticationError") or "permission" in exc_str.lower():
        return _t(
            "Mir fehlt die Berechtigung für diese Aktion. "
            "Bitte prüfe die Zugriffsrechte oder wende dich an den Administrator.",
            "I don't have permission for this action. "
            "Please check the access rights or contact the administrator.",
        )

    if exc_type == "FileNotFoundError" or "not found" in exc_str.lower():
        return _t(
            "Die angeforderte Datei oder Ressource wurde nicht gefunden. "
            "Bitte prüfe den Pfad und versuch es erneut.",
            "The requested file or resource was not found. "
            "Please check the path and try again.",
        )

    if "rate limit" in exc_str.lower() or "429" in exc_str:
        return _t(
            "Der Dienst ist gerade überlastet (Rate-Limit erreicht). "
            "Bitte warte einen Moment und versuch es dann erneut.",
            "The service is currently overloaded (rate limit reached). "
            "Please wait a moment and try again.",
        )

    if "memory" in exc_str.lower() or exc_type == "MemoryError":
        return _t(
            "Es ist ein Speicherproblem aufgetreten. "
            "Bitte versuch es mit einer kleineren Anfrage.",
            "A memory problem occurred. "
            "Please try again with a smaller request.",
        )

    # Generic fallback -- still friendlier than raw exception
    return _t(
        "Bei der Verarbeitung ist ein unerwarteter Fehler aufgetreten. "
        "Bitte versuch es erneut. Wenn das Problem weiterhin besteht, "
        "formuliere deine Anfrage etwas anders.",
        "An unexpected error occurred during processing. "
        "Please try again. If the problem persists, "
        "try rephrasing your request.",
    )


# ── Gatekeeper Block Messages ───────────────────────────────────

def gatekeeper_block_message(tool: str, reason: str) -> str:
    """Creates a user-friendly message when the Gatekeeper blocks an action.

    Instead of a generic "action blocked" message, explains what happened
    and what the user can do.
    """
    friendly = _friendly_tool_name(tool)
    return _t(
        f"Ich wollte \"{friendly}\" ausführen, aber das wurde aus Sicherheitsgründen "
        f"blockiert: {reason}\n"
        f"Du kannst mir die Berechtigung erteilen oder eine alternative Vorgehensweise vorschlagen.",
        f"I wanted to execute \"{friendly}\", but it was blocked for security reasons: "
        f"{reason}\n"
        f"You can grant me permission or suggest an alternative approach.",
    )


# ── Retry Exhausted Messages ────────────────────────────────────

def retry_exhausted_message(tool: str, attempts: int, error: str) -> str:
    """Creates a user-friendly message when all retries are exhausted."""
    friendly = _friendly_tool_name(tool)

    # Classify the error for a friendlier sub-message
    error_lower = error.lower()
    if "timeout" in error_lower:
        cause = _t(
            "Der Dienst hat nicht rechtzeitig geantwortet.",
            "The service did not respond in time.",
        )
    elif "connection" in error_lower:
        cause = _t(
            "Die Verbindung konnte nicht hergestellt werden.",
            "The connection could not be established.",
        )
    elif "rate" in error_lower or "429" in error:
        cause = _t(
            "Der Dienst ist gerade überlastet.",
            "The service is currently overloaded.",
        )
    else:
        cause = _t(
            f"Technischer Fehler: {error[:100]}",
            f"Technical error: {error[:100]}",
        )

    return _t(
        f"Ich habe \"{friendly}\" {attempts}-mal versucht, aber es hat leider nicht geklappt. "
        f"{cause} "
        f"Ich versuche einen anderen Ansatz oder du kannst mir helfen, das Problem zu lösen.",
        f"I tried \"{friendly}\" {attempts} times, but it didn't work. "
        f"{cause} "
        f"I'll try a different approach, or you can help me resolve the issue.",
    )


# ── All-Blocked Message ─────────────────────────────────────────

def all_actions_blocked_message(
    steps: list,
    decisions: list,
) -> str:
    """Creates a specific message when all planned actions are blocked."""
    reasons: list[str] = []
    for step, decision in zip(steps, decisions, strict=False):
        friendly = _friendly_tool_name(step.tool)
        reasons.append(f"- {friendly}: {decision.reason}")

    reasons_text = "\n".join(reasons) if reasons else _t(
        "Keine Details verfügbar.",
        "No details available.",
    )
    return _t(
        "Ich konnte keinen meiner geplanten Schritte ausführen, da sie alle "
        "aus Sicherheitsgründen blockiert wurden:\n"
        f"{reasons_text}\n\n"
        "Du kannst mir die Berechtigungen erteilen oder mir eine andere "
        "Herangehensweise vorschlagen.",
        "None of my planned steps could be executed because they were all "
        "blocked for security reasons:\n"
        f"{reasons_text}\n\n"
        "You can grant me the required permissions or suggest a different approach.",
    )
