"""Observer Audit Layer — LLM-based response quality check.

See design spec: docs/superpowers/specs/2026-04-19-observer-audit-layer-design.md

Runs after the Executor and after the regex-based ResponseValidator. Checks
the final response against four dimensions — Hallucination, Sycophancy,
Laziness, Tool-Ignorance — with per-dimension retry strategies.

The class is additive: it never replaces existing validators and fails open
(returns a pass result) on any internal failure so the core agent is never
blocked by a broken observer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class DimensionResult:
    """Per-dimension audit outcome."""

    name: Literal["hallucination", "sycophancy", "laziness", "tool_ignorance"]
    passed: bool
    reason: str
    evidence: str
    fix_suggestion: str


@dataclass(frozen=True)
class AuditResult:
    """Aggregate audit outcome for one observer call."""

    overall_passed: bool
    dimensions: dict[str, DimensionResult]
    retry_count: int
    final_action: Literal["pass", "rejected_with_retry", "delivered_with_warning"]
    retry_strategy: Literal["response_regen", "pge_reloop", "deliver", "deliver_with_warning"]
    model: str
    duration_ms: int
    degraded_mode: bool
    error_type: str | None


@dataclass(frozen=True)
class PGEReloopDirective:
    """Observer signal requesting a full PGE re-loop (not just response regen)."""

    reason: Literal["tool_ignorance"]
    missing_data: str
    suggested_tools: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResponseEnvelope:
    """Return type of Planner.formulate_response().

    A plain content payload plus an optional directive. Directive=None means
    'deliver content to user as-is'. Otherwise the Gateway catches the
    directive and re-enters the PGE loop.
    """

    content: str
    directive: PGEReloopDirective | None
