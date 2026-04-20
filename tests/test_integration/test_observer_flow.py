"""End-to-end integration tests for the Observer flow."""

from __future__ import annotations

from cognithor.config import JarvisConfig
from cognithor.core.observer import PGEReloopDirective


class TestPGEReloopDirectiveHandling:
    async def test_directive_triggers_planner_reentry(self, tmp_path):
        """A ResponseEnvelope with directive causes the PGE phase to re-enter planning."""
        from cognithor.gateway.observer_directive import handle_observer_directive

        cfg = JarvisConfig(jarvis_home=tmp_path / ".cognithor")
        session_state: dict = {
            "seen_observer_feedback_hashes": set(),
            "pge_iteration_count": 0,
        }

        directive = PGEReloopDirective(
            reason="tool_ignorance",
            missing_data="weather data",
            suggested_tools=["web_search"],
        )

        # First time seeing this directive: should allow re-entry.
        decision = handle_observer_directive(
            directive=directive, session_state=session_state, config=cfg,
        )
        assert decision.action == "reenter_pge"
        assert "weather data" in decision.planner_feedback

        # Second time same directive: dedupe kicks in.
        decision = handle_observer_directive(
            directive=directive, session_state=session_state, config=cfg,
        )
        assert decision.action == "downgrade_to_regen"

    async def test_pge_budget_exhausted_downgrades(self, tmp_path):
        from cognithor.gateway.observer_directive import handle_observer_directive

        cfg = JarvisConfig(jarvis_home=tmp_path / ".cognithor")
        cfg.security.max_iterations = 3
        session_state: dict = {
            "seen_observer_feedback_hashes": set(),
            "pge_iteration_count": 3,  # already at cap
        }
        directive = PGEReloopDirective(
            reason="tool_ignorance", missing_data="x", suggested_tools=[],
        )
        decision = handle_observer_directive(
            directive=directive, session_state=session_state, config=cfg,
        )
        assert decision.action == "downgrade_to_regen"

    async def test_seen_hashes_set_is_pruned_when_over_100(self, tmp_path):
        from cognithor.gateway.observer_directive import handle_observer_directive

        cfg = JarvisConfig(jarvis_home=tmp_path / ".cognithor")
        session_state: dict = {
            "seen_observer_feedback_hashes": {f"hash_{i}" for i in range(100)},
            "pge_iteration_count": 0,
        }
        directive = PGEReloopDirective(
            reason="tool_ignorance", missing_data="fresh", suggested_tools=[],
        )
        handle_observer_directive(
            directive=directive, session_state=session_state, config=cfg,
        )
        # After handling: new hash added, but set pruned to at most 51 items.
        assert len(session_state["seen_observer_feedback_hashes"]) <= 51
