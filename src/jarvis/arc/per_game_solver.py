"""ARC-AGI-3 PerGameSolver -- budget-based strategy execution per game."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from jarvis.arc.error_handler import safe_frame_extract
from jarvis.arc.game_profile import GameProfile
from jarvis.utils.logging import get_logger

__all__ = ["BudgetSlot", "PerGameSolver", "SolveResult", "StrategyOutcome"]

log = get_logger(__name__)

# Default total budget per game type
_BUDGET_BY_TYPE = {"click": 20, "keyboard": 200, "mixed": 100}

_STAGNATION_WINDOW = 5
_STAGNATION_THRESHOLD = 10  # pixels


@dataclass
class BudgetSlot:
    """One strategy with its allocated action budget."""

    strategy: str
    max_actions: int
    priority: int


@dataclass
class StrategyOutcome:
    """Result of executing one strategy on one level."""

    won: bool = False
    game_over: bool = False
    stagnated: bool = False
    steps: int = 0
    levels_solved: int = 0
    budget_ratio: float = 0.0


@dataclass
class SolveResult:
    """Outcome of solving a game."""

    game_id: str
    levels_completed: int
    total_steps: int
    strategy_log: list[dict]
    score: float


class PerGameSolver:
    """Budget-based solver that combines strategies from a GameProfile."""

    def __init__(self, profile: GameProfile, arcade: Any):
        self._profile = profile
        self._arcade = arcade

    def _allocate_budget(self, level_num: int) -> list[BudgetSlot]:
        """Allocate action budget across strategies."""
        total = _BUDGET_BY_TYPE.get(self._profile.game_type, 100)

        ranked = self._profile.ranked_strategies()
        if ranked:
            # Use learned ranking: top 3 with 50/30/20 split
            top3 = ranked[:3]
            ratios = [0.5, 0.3, 0.2]
        else:
            # Use defaults for this game type
            defaults = self._profile.default_strategies()
            top3 = [name for name, _ in defaults]
            ratios = [ratio for _, ratio in defaults]

        slots = []
        for i, strategy in enumerate(top3):
            ratio = ratios[i] if i < len(ratios) else 0.1
            slots.append(BudgetSlot(
                strategy=strategy,
                max_actions=int(total * ratio),
                priority=i,
            ))

        return slots

    def _execute_strategy(
        self, env: Any, strategy: str, max_actions: int
    ) -> StrategyOutcome:
        """Execute a single strategy with a given action budget."""
        from arcengine.enums import GameState

        outcome = StrategyOutcome()
        frame_history: list[np.ndarray] = []
        initial_levels = 0

        for step in range(max_actions):
            action_id, data = self._pick_action(strategy, frame_history)
            obs = env.step(action_id, data=data)
            grid = safe_frame_extract(obs)
            frame_history.append(grid)
            outcome.steps += 1

            if hasattr(obs, "levels_completed"):
                initial_levels = initial_levels or obs.levels_completed

            # Check terminal states
            if obs.state == GameState.WIN:
                outcome.won = True
                outcome.levels_solved = (
                    getattr(obs, "levels_completed", 0) - initial_levels + 1
                )
                outcome.budget_ratio = outcome.steps / max_actions
                return outcome

            if obs.state == GameState.GAME_OVER:
                outcome.game_over = True
                outcome.budget_ratio = outcome.steps / max_actions
                return outcome

            # Check stagnation
            if self._detect_stagnation(frame_history):
                outcome.stagnated = True
                outcome.budget_ratio = outcome.steps / max_actions
                return outcome

        outcome.budget_ratio = 1.0
        return outcome

    def _pick_action(
        self, strategy: str, frame_history: list[np.ndarray]
    ) -> tuple[int, dict | None]:
        """Pick next action based on strategy."""
        profile = self._profile

        if strategy == "cluster_click" or strategy == "targeted_click":
            # Click on known zones from profile
            if profile.click_zones:
                idx = len(frame_history) % len(profile.click_zones)
                x, y = profile.click_zones[idx]
                return 6, {"x": x, "y": y}
            # Fallback: center position
            return 6, {"x": 32, "y": 32}

        if strategy == "keyboard_explore":
            # Cycle through directions
            directions = [a for a in profile.available_actions if a in (1, 2, 3, 4)]
            if directions:
                idx = len(frame_history) % len(directions)
                return directions[idx], None
            return 1, None

        if strategy == "keyboard_sequence":
            # Use directions in order, repeat
            directions = [a for a in profile.available_actions if a in (1, 2, 3, 4)]
            if directions:
                idx = len(frame_history) % len(directions)
                return directions[idx], None
            return 5, None  # interact as fallback

        if strategy == "hybrid":
            # Alternate: keyboard for first 3/4, click for 1/4
            if profile.click_zones and len(frame_history) % 4 == 3:
                idx = len(frame_history) % len(profile.click_zones)
                x, y = profile.click_zones[idx]
                return 6, {"x": x, "y": y}
            directions = [a for a in profile.available_actions if a in (1, 2, 3, 4)]
            if directions:
                idx = len(frame_history) % len(directions)
                return directions[idx], None
            return 5, None

        # Unknown strategy -> interact
        return 5, None

    def _detect_stagnation(self, frame_history: list[np.ndarray]) -> bool:
        """Check if recent frames show no meaningful change."""
        if len(frame_history) < _STAGNATION_WINDOW:
            return False

        window = frame_history[-_STAGNATION_WINDOW:]
        for i in range(1, len(window)):
            diff = int(np.sum(window[i] != window[i - 1]))
            if diff >= _STAGNATION_THRESHOLD:
                return False

        return True
