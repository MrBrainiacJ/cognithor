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

    def _execute_cluster_click(
        self,
        initial_grid: np.ndarray,
        target_color: int | None,
        max_actions: int,
    ) -> StrategyOutcome:
        """Cluster-based click strategy: find clusters, try subsets via arcade.make()."""
        import itertools

        from arcengine.enums import GameState

        from jarvis.arc.cluster_solver import ClusterSolver

        outcome = StrategyOutcome()

        if target_color is None:
            return outcome

        solver = ClusterSolver(target_color=target_color, max_skip=6)
        centers = solver.find_clusters(initial_grid)

        if not centers:
            return outcome

        n = len(centers)
        max_skip = min(n, 6)
        combos_tried = 0

        for skip in range(max_skip + 1):
            for skip_combo in itertools.combinations(range(n), skip):
                if combos_tried >= max_actions:
                    outcome.budget_ratio = 1.0
                    return outcome

                click_idx = [i for i in range(n) if i not in skip_combo]
                combos_tried += 1

                # Test this combo in a fresh env
                env = self._arcade.make(self._profile.game_id)
                obs = env.reset()

                won = False
                for idx in click_idx:
                    cx, cy = centers[idx]
                    obs = env.step(6, data={"x": cx, "y": cy})
                    outcome.steps += 1

                    if obs.state == GameState.WIN:
                        won = True
                        break
                    if obs.state == GameState.GAME_OVER:
                        break

                if won:
                    outcome.won = True
                    outcome.levels_solved = 1
                    outcome.budget_ratio = combos_tried / max_actions
                    return outcome

        outcome.budget_ratio = 1.0
        return outcome

    def _execute_strategy(
        self, env: Any, strategy: str, max_actions: int
    ) -> StrategyOutcome:
        """Execute a single strategy with a given action budget."""
        from arcengine.enums import GameState

        # Special handling for cluster_click: uses arcade.make() per combo
        if strategy == "cluster_click":
            target_color = self._profile.target_colors[0] if self._profile.target_colors else None
            obs = env.reset()
            last_grid = safe_frame_extract(obs)
            return self._execute_cluster_click(last_grid, target_color, max_actions)

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

    def solve(
        self,
        max_levels: int = 10,
        timeout_s: float = 300.0,
        base_dir: Any | None = None,
    ) -> SolveResult:
        """Solve the game level by level with budget-based strategy mix."""
        import time

        from arcengine.enums import GameState

        env = self._arcade.make(self._profile.game_id)
        obs = env.reset()

        result = SolveResult(
            game_id=self._profile.game_id,
            levels_completed=0,
            total_steps=0,
            strategy_log=[],
            score=0.0,
        )

        start_time = time.monotonic()
        max_resets = 3

        for level_num in range(max_levels):
            if time.monotonic() - start_time > timeout_s:
                log.info("arc.solver_timeout", game_id=self._profile.game_id)
                break

            level_result = self._solve_level(env, level_num, max_resets, start_time, timeout_s)
            result.total_steps += level_result["steps"]
            result.strategy_log.append(level_result)

            if level_result["won"]:
                result.levels_completed += 1
                # Update profile metrics for the winning strategy
                self._profile.update_metrics(
                    level_result["strategy"],
                    won=True,
                    levels_solved=1,
                    steps=level_result["steps"],
                    budget_ratio=level_result.get("budget_ratio", 1.0),
                )
            else:
                # Update metrics for failed strategies
                for failed in level_result.get("tried", []):
                    self._profile.update_metrics(
                        failed,
                        won=False,
                        levels_solved=0,
                        steps=level_result["steps"],
                        budget_ratio=1.0,
                    )

        self._profile.update_run(score=result.levels_completed)
        self._profile.save(base_dir=base_dir)
        result.score = float(result.levels_completed)
        return result

    def _solve_level(
        self,
        env: Any,
        level_num: int,
        max_resets: int,
        start_time: float,
        timeout_s: float,
    ) -> dict:
        """Try all budget slots on one level."""
        import time

        from arcengine.enums import GameState

        slots = self._allocate_budget(level_num)
        total_steps = 0
        tried: list[str] = []
        resets_used = 0

        for slot in slots:
            if time.monotonic() - start_time > timeout_s:
                break

            tried.append(slot.strategy)
            outcome = self._execute_strategy(env, slot.strategy, slot.max_actions)
            total_steps += outcome.steps

            if outcome.won:
                return {
                    "level": level_num,
                    "strategy": slot.strategy,
                    "won": True,
                    "steps": total_steps,
                    "budget_ratio": outcome.budget_ratio,
                    "tried": tried,
                }

            if outcome.game_over:
                resets_used += 1
                if resets_used >= max_resets:
                    break
                # Reset level
                try:
                    env.reset()
                except Exception:
                    break

        return {
            "level": level_num,
            "strategy": tried[-1] if tried else "none",
            "won": False,
            "steps": total_steps,
            "tried": tried,
        }

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
