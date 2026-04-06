"""Human Investigation Module (HIM) — OSINT research and trust scoring."""

from jarvis.osint.him_agent import HIMAgent
from jarvis.osint.models import (
    ClaimResult,
    ClaimType,
    Evidence,
    Finding,
    GDPRScope,
    GDPRViolationError,
    HIMReport,
    HIMRequest,
    TrustScore,
    VerificationStatus,
)

__all__ = [
    "ClaimResult",
    "ClaimType",
    "Evidence",
    "Finding",
    "GDPRScope",
    "GDPRViolationError",
    "HIMAgent",
    "HIMReport",
    "HIMRequest",
    "TrustScore",
    "VerificationStatus",
]
