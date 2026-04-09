"""SQLite-backed lead persistence with encryption support."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from jarvis.social.models import Lead, LeadStats, LeadStatus, ScanResult
from jarvis.utils.logging import get_logger

try:
    from jarvis.security.encrypted_db import compatible_row_factory as _row_factory_fn
except ImportError:

    def _row_factory_fn() -> type:  # type: ignore[misc]
        return sqlite3.Row

log = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id            TEXT PRIMARY KEY,
    post_id       TEXT UNIQUE NOT NULL,
    subreddit     TEXT NOT NULL,
    title         TEXT NOT NULL,
    body          TEXT DEFAULT '',
    url           TEXT NOT NULL,
    author        TEXT DEFAULT '',
    created_utc   REAL DEFAULT 0,
    upvotes       INTEGER DEFAULT 0,
    num_comments  INTEGER DEFAULT 0,
    intent_score  INTEGER DEFAULT 0,
    score_reason  TEXT DEFAULT '',
    reply_draft   TEXT DEFAULT '',
    reply_final   TEXT DEFAULT '',
    status        TEXT DEFAULT 'new',
    replied_at    REAL DEFAULT 0,
    detected_at   REAL NOT NULL,
    content_hash  TEXT DEFAULT '',
    scan_id       TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS lead_scans (
    id              TEXT PRIMARY KEY,
    started_at      REAL NOT NULL,
    finished_at     REAL DEFAULT 0,
    posts_checked   INTEGER DEFAULT 0,
    leads_found     INTEGER DEFAULT 0,
    subreddits      TEXT DEFAULT '',
    trigger         TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(intent_score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_post_id ON leads(post_id);
"""


class LeadStore:
    """SQLite-backed lead storage with encryption."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        try:
            from jarvis.security.encrypted_db import encrypted_connect

            self._conn = encrypted_connect(str(self._db_path), check_same_thread=False)
        except ImportError:
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = _row_factory_fn()
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        return self._conn

    def save_lead(self, lead: Lead) -> None:
        """Insert or update a lead (upsert on post_id)."""
        self.conn.execute(
            """INSERT INTO leads
                (id, post_id, subreddit, title, body, url, author, created_utc,
                 upvotes, num_comments, intent_score, score_reason, reply_draft,
                 reply_final, status, replied_at, detected_at, content_hash, scan_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(post_id) DO UPDATE SET
                intent_score=excluded.intent_score,
                score_reason=excluded.score_reason,
                reply_draft=excluded.reply_draft,
                title=excluded.title,
                body=excluded.body,
                upvotes=excluded.upvotes,
                num_comments=excluded.num_comments
            """,
            (
                lead.id,
                lead.post_id,
                lead.subreddit,
                lead.title,
                lead.body,
                lead.url,
                lead.author,
                lead.created_utc,
                lead.upvotes,
                lead.num_comments,
                lead.intent_score,
                lead.score_reason,
                lead.reply_draft,
                lead.reply_final,
                lead.status.value if isinstance(lead.status, LeadStatus) else lead.status,
                lead.replied_at,
                lead.detected_at,
                lead.content_hash,
                lead.scan_id,
            ),
        )
        self.conn.commit()

    def get_lead(self, lead_id: str) -> Lead | None:
        """Fetch a single lead by its UUID."""
        row = self.conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_lead(row)

    def get_leads(
        self,
        status: LeadStatus | None = None,
        min_score: int = 0,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        """Return leads ordered by detected_at DESC with optional filters."""
        query = "SELECT * FROM leads WHERE intent_score >= ?"
        params: list[Any] = [min_score]
        if status is not None:
            query += " AND status = ?"
            params.append(status.value if isinstance(status, LeadStatus) else status)
        query += " ORDER BY detected_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_lead(r) for r in rows]

    def update_lead(
        self,
        lead_id: str,
        status: LeadStatus | None = None,
        reply_final: str | None = None,
    ) -> Lead | None:
        """Update lead status and/or reply_final. Returns updated lead."""
        sets: list[str] = []
        params: list[Any] = []
        if status is not None:
            sets.append("status = ?")
            params.append(status.value if isinstance(status, LeadStatus) else status)
            if status == LeadStatus.REPLIED:
                sets.append("replied_at = ?")
                params.append(time.time())
        if reply_final is not None:
            sets.append("reply_final = ?")
            params.append(reply_final)
        if not sets:
            return self.get_lead(lead_id)
        params.append(lead_id)
        self.conn.execute(f"UPDATE leads SET {', '.join(sets)} WHERE id = ?", params)
        self.conn.commit()
        return self.get_lead(lead_id)

    def already_seen(self, post_id: str) -> bool:
        """Return True if a lead with this post_id already exists."""
        row = self.conn.execute("SELECT 1 FROM leads WHERE post_id = ?", (post_id,)).fetchone()
        return row is not None

    def get_stats(self) -> LeadStats:
        """Return aggregate statistics over all leads and scans."""
        total = self.conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        new = self.conn.execute("SELECT COUNT(*) FROM leads WHERE status = 'new'").fetchone()[0]
        reviewed = self.conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status = 'reviewed'"
        ).fetchone()[0]
        replied = self.conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status = 'replied'"
        ).fetchone()[0]
        archived = self.conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status = 'archived'"
        ).fetchone()[0]
        avg_row = self.conn.execute("SELECT AVG(intent_score) FROM leads").fetchone()
        avg_score = avg_row[0] if avg_row[0] is not None else 0.0
        sub_rows = self.conn.execute(
            "SELECT subreddit, COUNT(*) as cnt FROM leads"
            " GROUP BY subreddit ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        top_subs = {r[0]: r[1] for r in sub_rows}
        scan_count = self.conn.execute("SELECT COUNT(*) FROM lead_scans").fetchone()[0]
        return LeadStats(
            total=total,
            new=new,
            reviewed=reviewed,
            replied=replied,
            archived=archived,
            avg_score=round(avg_score, 1),
            top_subreddits=top_subs,
            total_scans=scan_count,
        )

    def save_scan(self, scan: ScanResult) -> None:
        """Persist a completed ScanResult."""
        self.conn.execute(
            """INSERT INTO lead_scans
                (id, started_at, finished_at, posts_checked, leads_found, subreddits, trigger)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                scan.id,
                scan.started_at,
                scan.finished_at,
                scan.posts_checked,
                scan.leads_found,
                json.dumps(scan.subreddits_scanned),
                scan.trigger,
            ),
        )
        self.conn.commit()

    def get_scan_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent scan records as plain dicts."""
        rows = self.conn.execute(
            "SELECT * FROM lead_scans ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @staticmethod
    def _row_to_lead(row: Any) -> Lead:
        """Convert a sqlite3.Row to a Lead dataclass."""
        return Lead(
            id=row["id"],
            post_id=row["post_id"],
            subreddit=row["subreddit"],
            title=row["title"],
            body=row["body"],
            url=row["url"],
            author=row["author"],
            created_utc=row["created_utc"],
            upvotes=row["upvotes"],
            num_comments=row["num_comments"],
            intent_score=row["intent_score"],
            score_reason=row["score_reason"],
            reply_draft=row["reply_draft"],
            reply_final=row["reply_final"],
            status=LeadStatus(row["status"]),
            replied_at=row["replied_at"],
            detected_at=row["detected_at"],
            content_hash=row["content_hash"],
            scan_id=row["scan_id"],
        )
