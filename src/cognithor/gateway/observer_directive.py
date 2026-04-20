"""Gateway-side handling of Observer-issued PGE re-loop directives.

The Observer audit may return a ``PGEReloopDirective`` when it detects that a
tool call was missed (``tool_ignorance`` failure). The Gateway catches this
signal after ``Planner.formulate_response()`` and decides whether to:

- re-enter the full PGE loop with the Observer feedback injected, OR
- downgrade to response-regen only (when the directive is a duplicate of one
  already seen this session, or when the PGE iteration budget is exhausted).

This module is pure — no gateway state is touched here, only the per-session
state dict passed in by the caller.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from cognithor.config import JarvisConfig
    from cognithor.core.observer import PGEReloopDirective


@dataclass(frozen=True)
class ObserverDirectiveDecision:
    """Outcome of handle_observer_directive()."""

    action: Literal["reenter_pge", "downgrade_to_regen"]
    planner_feedback: str  # empty when downgrading


def handle_observer_directive(
    *,
    directive: PGEReloopDirective,
    session_state: dict,
    config: JarvisConfig,
) -> ObserverDirectiveDecision:
    """Decide how to act on an Observer-issued PGE directive.

    Returns ``reenter_pge`` when a fresh re-loop is warranted, or
    ``downgrade_to_regen`` when the directive is a duplicate or the PGE
    budget is exhausted (in which case Planner falls back to response
    regen).
    """
    hash_input = f"{directive.reason}|{directive.missing_data}"
    fb_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    seen: set[str] = session_state.setdefault("seen_observer_feedback_hashes", set())
    pge_count: int = session_state.get("pge_iteration_count", 0)
    max_iter = config.security.max_iterations

    if fb_hash in seen or pge_count >= max_iter:
        return ObserverDirectiveDecision(action="downgrade_to_regen", planner_feedback="")

    seen.add(fb_hash)
    # Bounded memory: prune to last 50 when above 100.
    if len(seen) > 100:
        keep = list(seen)[-50:]
        session_state["seen_observer_feedback_hashes"] = set(keep)

    tools_text = ", ".join(directive.suggested_tools) or "(none)"
    feedback = (
        f"Observer detected tool_ignorance: missing data = {directive.missing_data}. "
        f"Suggested tools: {tools_text}. "
        "Re-plan the task and call the appropriate tools."
    )
    return ObserverDirectiveDecision(action="reenter_pge", planner_feedback=feedback)
