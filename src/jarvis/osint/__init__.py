"""Human Investigation Module (HIM) — OSINT research and trust scoring."""

from jarvis.osint.him_agent import HIMAgent
from jarvis.osint.models import (
    ClaimType,
    ClaimResult,
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
    "HIMAgent",
    "ClaimType",
    "ClaimResult",
    "Evidence",
    "Finding",
    "GDPRScope",
    "GDPRViolationError",
    "HIMReport",
    "HIMRequest",
    "TrustScore",
    "VerificationStatus",
]
