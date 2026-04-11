"""Data models for the Social Lead Hunter."""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class LeadStatus(StrEnum):
    NEW = "new"
    REVIEWED = "reviewed"
    REPLIED = "replied"
    ARCHIVED = "archived"


@dataclass
class Lead:
    """A scored Reddit post identified as a potential lead."""

    post_id: str
    subreddit: str
    title: str
    url: str
    intent_score: int

    # Optional enrichment
    body: str = ""
    author: str = ""
    created_utc: float = 0.0
    upvotes: int = 0
    num_comments: int = 0
    score_reason: str = ""
    reply_draft: str = ""
    reply_final: str = ""
    status: LeadStatus = LeadStatus.NEW
    replied_at: float = 0.0
    scan_id: str = ""

    # Platform fields
    platform: str = "reddit"  # "reddit" | "hackernews" | "discord"
    platform_id: str = ""  # Original ID on the platform
    platform_url: str = ""  # Direct link

    # Auto-generated
    id: str = field(default_factory=lambda: str(uuid4()))
    detected_at: float = field(default_factory=time.time)
    content_hash: str = field(default="")

    def __post_init__(self) -> None:
        if not self.content_hash:
            raw = f"{self.post_id}:{self.title}:{self.body}"
            self.content_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, LeadStatus) else self.status
        return d

    def to_notification_text(self) -> str:
        stars = self.intent_score // 20
        star_str = "*" * stars + "." * (5 - stars)
        return (
            f"[{star_str} {self.intent_score}/100] r/{self.subreddit}\n"
            f"{self.title}\n"
            f"{self.url}\n"
            f"u/{self.author} | {self.upvotes} upvotes | {self.num_comments} comments\n"
            f"Reason: {self.score_reason}\n"
            f"Draft: {self.reply_draft[:100]}..."
        )


@dataclass
class ScanResult:
    """Result of a single scan cycle."""

    subreddits_scanned: list[str]
    posts_checked: int = 0
    leads_found: int = 0
    posts_skipped_duplicate: int = 0
    posts_skipped_low_score: int = 0
    trigger: str = ""  # "chat", "cron", "ui"

    id: str = field(default_factory=lambda: str(uuid4()))
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0

    def summary(self) -> str:
        return (
            f"Scan: {self.posts_checked} posts checked, "
            f"{self.posts_skipped_duplicate} duplicates, "
            f"{self.posts_skipped_low_score} below threshold, "
            f"{self.leads_found} leads found."
        )


@dataclass
class LeadStats:
    """Aggregate lead statistics."""

    total: int = 0
    new: int = 0
    reviewed: int = 0
    replied: int = 0
    archived: int = 0
    avg_score: float = 0.0
    top_subreddits: dict[str, int] = field(default_factory=dict)
    total_scans: int = 0
