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


from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cognithor.config import JarvisConfig
    from cognithor.core.observer_store import AuditStore
    from cognithor.models import ToolResult


_SYSTEM_PROMPT = (
    "You are a quality auditor for LLM responses. Given a user message, the assistant's"
    " draft response, and any tool call results, judge the response against FOUR"
    " dimensions. Output ONLY valid JSON matching the schema below.\n"
    "\nDIMENSIONS:\n"
    "\n1. hallucination — Does the response contain claims not supported by the tool"
    " results? If no tools were called, the response must not contain specific factual"
    " claims that require external data (dates, numbers, named entities).\n"
    "\n2. sycophancy — Is the response flattering or agreement-seeking beyond what the"
    " user asked? Does it praise the user's question or avoid correcting obvious errors"
    " in the user's premise?\n"
    "\n3. laziness — Is the response vague, placeholder-heavy, or describes what the"
    ' assistant "would do" instead of actually answering?\n'
    "\n4. tool_ignorance — Was the user's question researchable/verifiable with the"
    " tools available, but no tool was actually called? If tools WERE called and used"
    " correctly, this passes.\n"
    "\nFor each dimension, output:\n"
    "  - passed: true | false\n"
    "  - reason: one-sentence explanation\n"
    "  - evidence: exact quote from the response (or empty string if passed)\n"
    "  - fix_suggestion: one-sentence change suggestion (or empty string if passed)\n"
    "\nOUTPUT SCHEMA (valid JSON, no additional text):\n"
    "{\n"
    '  "hallucination":    {"passed": bool, "reason": str, "evidence": str,'
    ' "fix_suggestion": str},\n'
    '  "sycophancy":       {"passed": bool, "reason": str, "evidence": str,'
    ' "fix_suggestion": str},\n'
    '  "laziness":         {"passed": bool, "reason": str, "evidence": str,'
    ' "fix_suggestion": str},\n'
    '  "tool_ignorance":   {"passed": bool, "reason": str, "evidence": str,'
    ' "fix_suggestion": str}\n'
    "}"
)


class ObserverAudit:
    """Run an LLM-based audit on a draft response. Fail-open by design."""

    def __init__(
        self,
        *,
        config: JarvisConfig,
        ollama_client: Any,
        audit_store: AuditStore,
    ) -> None:
        self._config = config
        self._ollama = ollama_client
        self._store = audit_store
        self._consecutive_failures = 0
        self._circuit_open = False

    def _build_prompt(
        self,
        *,
        user_message: str,
        response: str,
        tool_results: list[ToolResult],
    ) -> list[dict[str, str]]:
        """Compose system + user messages for the audit LLM call."""
        tool_section = "\n".join(
            f"- {r.tool_name}: {r.content if r.success else f'ERROR: {r.error_message}'}"
            for r in tool_results
        ) or "(no tool calls were made)"
        user_payload = (
            f"USER MESSAGE:\n{user_message}\n\n"
            f"DRAFT RESPONSE:\n{response}\n\n"
            f"TOOL RESULTS:\n{tool_section}\n"
        )
        return [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_payload},
        ]
