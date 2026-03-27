"""Core Memory · Tier 1 -- Identity, rules, preferences. [B§4.2]

ALWAYS loaded. In every session. Completely.
Changes only by user or explicit command.
No recency decay.
"""

from __future__ import annotations

import re
from pathlib import Path


class CoreMemory:
    """Manage the CORE.md file -- Jarvis' identity.

    Source of Truth: ~/.jarvis/memory/CORE.md
    """

    def __init__(self, core_file: str | Path) -> None:
        """Initialize CoreMemory with the path to CORE.md."""
        self._path = Path(core_file)
        self._content: str = ""
        self._sections: dict[str, str] = {}

    @property
    def path(self) -> Path:
        """Return the path to CORE.md."""
        return self._path

    @property
    def content(self) -> str:
        """Complete CORE.md content."""
        return self._content

    @property
    def sections(self) -> dict[str, str]:
        """Parsed sections as {header: content}."""
        return dict(self._sections)

    def load(self) -> str:
        """Load CORE.md from disk. Create default if not found.

        Returns:
            Complete content as string.
        """
        if not self._path.exists():
            self._content = ""
            self._sections = {}
            return ""

        self._content = self._path.read_text(encoding="utf-8")
        self._sections = self._parse_sections(self._content)
        return self._content

    def get_section(self, name: str) -> str:
        """Return the content of a section.

        Args:
            name: Section name (case-insensitive, without '#').

        Returns:
            Section content or empty string.
        """
        name_lower = name.lower().strip()
        for key, value in self._sections.items():
            if key.lower().strip() == name_lower:
                return value
        return ""

    def save(self, content: str | None = None) -> None:
        """Save CORE.md to disk.

        Args:
            content: New content. If None, current content is saved.
        """
        if content is not None:
            self._content = content
            self._sections = self._parse_sections(content)

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(self._content, encoding="utf-8")

    def create_default(self) -> str:
        """Create a default CORE.md and return its content."""
        default = (
            "# Identität\n"
            "Ich bin Jarvis, ein lokaler AI-Assistent.\n\n"
            "# Regeln\n"
            "- Kundendaten NIEMALS in Logs schreiben\n"
            "- E-Mails IMMER zur Bestätigung vorlegen\n\n"
            "# Präferenzen\n"
            "- Codesprache: Python\n"
            "- Kommunikation: Direkt, keine Floskeln\n"
            "- Zeitzone: Europe/Berlin\n"
        )
        self.save(default)
        return default

    @staticmethod
    def _parse_sections(text: str) -> dict[str, str]:
        """Parse Markdown into sections based on H1/H2 headers.

        Returns:
            Dict of {header_name: content_text}.
        """
        sections: dict[str, str] = {}
        current_header: str | None = None
        current_lines: list[str] = []

        for line in text.split("\n"):
            match = re.match(r"^(#{1,2})\s+(.+)$", line)
            if match:
                # Save previous section
                if current_header is not None:
                    sections[current_header] = "\n".join(current_lines).strip()
                current_header = match.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        # Last section
        if current_header is not None:
            sections[current_header] = "\n".join(current_lines).strip()

        return sections
