# Copyright 2024-2026 Cognithor Contributors
# Licensed under the Apache License, Version 2.0
"""Integration mit Cognithors SHA-256 Audit Chain."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis.utils.logging import get_logger

if TYPE_CHECKING:
    from jarvis.hashline.models import EditIntent, EditResult

log = get_logger(__name__)


class HashlineAuditor:
    """Append-only JSONL audit log for hashline operations.

    Writes audit entries to ``~/.jarvis/hashline_audit.jsonl``. Each entry
    is a single JSON line containing timestamp, file, operation, hashes,
    and agent ID. Entries are never modified or deleted.

    Args:
        data_dir: Base directory for audit files (defaults to ~/.jarvis).
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or Path.home() / ".jarvis"
        self._audit_file = self._data_dir / "hashline_audit.jsonl"
        self._lock = threading.Lock()

        # Ensure directory exists
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def log_edit(
        self,
        result: EditResult,
        intent: EditIntent,
        agent_id: str,
    ) -> str:
        """Log an edit operation to the audit trail.

        Args:
            result: The result of the edit operation.
            intent: The original edit intent.
            agent_id: Identifier of the agent that performed the edit.

        Returns:
            SHA-256 hash of the audit entry.
        """
        entry = {
            "timestamp": time.time(),
            "type": "edit",
            "file": str(result.file_path),
            "line": result.line_number,
            "operation": result.operation,
            "old_hash": intent.target_hash,
            "new_hash": result.audit_hash,
            "agent_id": agent_id,
            "success": result.success,
            "error": result.error,
            "retry_count": result.retry_count,
        }
        return self._append(entry)

    def log_read(
        self,
        path: Path,
        line_count: int,
        agent_id: str,
    ) -> str:
        """Log a file read operation to the audit trail.

        Args:
            path: Path to the file that was read.
            line_count: Number of lines read.
            agent_id: Identifier of the agent that read the file.

        Returns:
            SHA-256 hash of the audit entry.
        """
        entry = {
            "timestamp": time.time(),
            "type": "read",
            "file": str(path),
            "line_count": line_count,
            "agent_id": agent_id,
        }
        return self._append(entry)

    def get_file_history(
        self,
        path: Path,
        limit: int = 50,
    ) -> list[dict]:
        """Retrieve audit history for a specific file.

        Args:
            path: Path to the file (matched as substring).
            limit: Maximum number of entries to return.

        Returns:
            List of audit entry dicts, newest first.
        """
        path_str = str(path)
        entries: list[dict] = []

        with self._lock:
            if not self._audit_file.exists():
                return []

            try:
                with open(self._audit_file, encoding="utf-8") as f:
                    for raw_line in f:
                        raw_line = raw_line.strip()
                        if not raw_line:
                            continue
                        try:
                            entry = json.loads(raw_line)
                            if entry.get("file", "").endswith(path_str) or path_str in entry.get(
                                "file", ""
                            ):
                                entries.append(entry)
                        except json.JSONDecodeError:
                            continue
            except OSError:
                log.debug("audit_read_failed", path=str(self._audit_file), exc_info=True)

        # Newest first, limited
        entries.reverse()
        return entries[:limit]

    def _append(self, entry: dict) -> str:
        """Append an entry to the audit file and return its SHA-256 hash.

        Args:
            entry: Dict to serialize as JSON and append.

        Returns:
            SHA-256 hex digest of the JSON line.
        """
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        entry_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()

        with self._lock:
            with open(self._audit_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        log.debug("audit_logged", type=entry.get("type"), file=entry.get("file"))
        return entry_hash
