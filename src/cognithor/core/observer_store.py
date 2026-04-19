"""SQLite persistence for Observer audit records.

Plain sqlite3 (not SQLCipher) — audit data is telemetry, not sensitive.
Responses and user messages are sha256-hashed before storage so the DB
does not contain verbatim content.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import asdict
from typing import TYPE_CHECKING

from cognithor.utils.logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from cognithor.core.observer import AuditResult

log = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audits (
    audit_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    timestamp         INTEGER NOT NULL,
    user_message_hash TEXT NOT NULL,
    response_hash     TEXT NOT NULL,
    model             TEXT NOT NULL,
    dimensions_json   TEXT NOT NULL,
    overall_passed    INTEGER NOT NULL,
    retry_count       INTEGER NOT NULL,
    final_action      TEXT NOT NULL,
    retry_strategy    TEXT,
    duration_ms       INTEGER NOT NULL,
    degraded_mode     INTEGER NOT NULL,
    error_type        TEXT
);
CREATE INDEX IF NOT EXISTS idx_session   ON audits(session_id);
CREATE INDEX IF NOT EXISTS idx_timestamp ON audits(timestamp);
CREATE INDEX IF NOT EXISTS idx_passed    ON audits(overall_passed);
"""


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class AuditStore:
    """Append-only SQLite store for Observer audit records."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._initialized = False

    def _ensure_ready(self) -> None:
        if self._initialized:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript(_SCHEMA)
        self._initialized = True

    def record(
        self,
        *,
        session_id: str,
        user_message: str,
        response: str,
        result: AuditResult,
    ) -> None:
        """Write one audit record. Fail-open on any I/O error."""
        self._ensure_ready()
        dims_serialized = json.dumps(
            {name: asdict(dim) for name, dim in result.dimensions.items()},
            ensure_ascii=False,
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO audits (session_id, timestamp, user_message_hash, "
                "response_hash, model, dimensions_json, overall_passed, retry_count, "
                "final_action, retry_strategy, duration_ms, degraded_mode, error_type) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    int(time.time() * 1000),
                    _sha256(user_message),
                    _sha256(response),
                    result.model,
                    dims_serialized,
                    int(result.overall_passed),
                    result.retry_count,
                    result.final_action,
                    result.retry_strategy,
                    result.duration_ms,
                    int(result.degraded_mode),
                    result.error_type,
                ),
            )
