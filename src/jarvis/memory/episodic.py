"""Episodic Memory · Tier 2 -- Daily log. [B§4.3]

What happened when? Chronologically ordered entries.
Append-only: entries are never modified, only added.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from jarvis.security.encrypted_file import efile as _efile
except ImportError:  # encryption module not available
    _efile = None  # type: ignore[assignment]


class EpisodicMemory:
    """Manage daily log files under ~/.jarvis/memory/episodes/.

    Format: episodes/YYYY-MM-DD.md
    Eintraege: ## HH:MM · Thema
    """

    def __init__(self, episodes_dir: str | Path) -> None:
        """Initialize EpisodicMemory with the episodes directory."""
        self._dir = Path(episodes_dir)

    @property
    def directory(self) -> Path:
        """Return the episodes directory."""
        return self._dir

    def _file_for_date(self, d: date) -> Path:
        """Return the path to the daily log file."""
        return self._dir / f"{d.isoformat()}.md"

    def ensure_directory(self) -> None:
        """Create the episodes directory if needed."""
        self._dir.mkdir(parents=True, exist_ok=True)

    def append_entry(
        self,
        topic: str,
        content: str,
        *,
        timestamp: datetime | None = None,
    ) -> str:
        """Fuegt einen Eintrag zum Tageslog hinzu. Append-only.

        Args:
            topic: Short title of the entry.
            content: Detail text (can be multiline).
            timestamp: Timestamp (default: now).

        Returns:
            The written entry as string.
        """
        if timestamp is None:
            timestamp = datetime.now()

        self.ensure_directory()

        file_path = self._file_for_date(timestamp.date())
        time_str = timestamp.strftime("%H:%M")

        entry = f"\n## {time_str} · {topic}\n{content}\n"

        # Create file if not present (with daily header)
        if not file_path.exists():
            header = f"# {timestamp.date().isoformat()}\n"
            full_content = header + entry
            if _efile is not None:
                _efile.write(file_path, full_content)
            else:
                file_path.write_text(full_content, encoding="utf-8")
        else:
            # Append: efile doesn't support append, so read + append + write
            if _efile is not None:
                existing = _efile.read(file_path)
                _efile.write(file_path, existing + entry)
            else:
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(entry)

        return entry.strip()

    def get_today(self) -> str:
        """Return today's daily log."""
        return self.get_date(date.today())

    def get_date(self, d: date) -> str:
        """Return the daily log for a specific date.

        Args:
            d: Das gewuenschte Datum.

        Returns:
            File content or empty string.
        """
        file_path = self._file_for_date(d)
        if not file_path.exists():
            return ""
        if _efile is not None:
            return _efile.read(file_path)
        return file_path.read_text(encoding="utf-8")

    def get_recent(self, days: int = 2) -> list[tuple[date, str]]:
        """Return the last N days.

        Args:
            days: Number of days (default: 2 = today + yesterday).

        Returns:
            List of (date, content) tuples, most recent first.
        """
        results: list[tuple[date, str]] = []
        today = date.today()

        for i in range(days):
            d = today - timedelta(days=i)
            content = self.get_date(d)
            if content:
                results.append((d, content))

        return results

    def list_dates(self) -> list[date]:
        """List all available daily log dates.

        Returns:
            Sorted list of dates (most recent first).
        """
        if not self._dir.exists():
            return []

        dates: list[date] = []
        for f in self._dir.glob("????-??-??.md"):
            try:
                d = date.fromisoformat(f.stem)
                dates.append(d)
            except ValueError:
                continue  # Filename doesn't match date format, skip

        return sorted(dates, reverse=True)

    # ------------------------------------------------------------------
    # Retention / Pruning
    #
    # Um eine unkontrollierte Ansammlung alter Episoden zu verhindern,
    # kann die Anzahl der gespeicherten Tageslogs zeitlich begrenzt werden.
    # Der MemoryManager ruft diese Methode beim Initialisieren auf.
    # Alte Dateien werden geloescht, wenn sie aelter als ``retention_days`` sind.
    def prune_old(self, retention_days: int) -> int:
        """Delete episode files older than ``retention_days``.

        Args:
            retention_days: Maximales Alter in Tagen. Dateien, die aelter
                sind, werden entfernt. Wenn ``retention_days`` <= 0,
                passiert nichts.

        Returns:
            Anzahl der geloeschten Dateien.
        """
        if retention_days <= 0:
            return 0
        if not self._dir.exists():
            return 0
        deleted = 0
        today = date.today()
        threshold = today - timedelta(days=retention_days)
        for f in self._dir.glob("????-??-??.md"):
            try:
                d = date.fromisoformat(f.stem)
            except ValueError:
                continue  # Filename doesn't match date format, skip
            if d < threshold:
                try:
                    f.unlink()
                    deleted += 1
                except OSError:
                    pass  # Best-effort deletion, file may be locked
        return deleted
