"""Tests for PerGameSolver -- budget-based strategy execution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from jarvis.arc.game_profile import GameProfile, StrategyMetrics
from jarvis.arc.per_game_solver import (
    BudgetSlot,
    PerGameSolver,
    SolveResult,
    StrategyOutcome,
)


def _make_profile(game_type="click", metrics=None) -> GameProfile:
    return GameProfile(
        game_id="test_game",
        game_type=game_type,
        available_actions=[5, 6] if game_type == "click" else [1, 2, 3, 4, 5],
        click_zones=[(10, 10), (30, 30)] if game_type == "click" else [],
        target_colors=[3] if game_type == "click" else [],
        movement_effects={1: "moves_player", 2: "moves_player"} if game_type != "click" else {},
        win_condition="clear_board",
        vision_description="test",
        vision_strategy="test",
        strategy_metrics=metrics or {},
        analyzed_at="2026-04-04",
    )


class TestBudgetAllocation:
    def test_default_click_allocation(self):
        profile = _make_profile("click")
        solver = PerGameSolver(profile, arcade=MagicMock())
        slots = solver._allocate_budget(level_num=0)

        assert len(slots) == 3
        assert slots[0].strategy == "cluster_click"
        assert slots[0].max_actions == 10  # 50% of 20
        assert slots[1].strategy == "targeted_click"
        assert slots[1].max_actions == 6   # 30% of 20
        assert slots[2].strategy == "hybrid"
        assert slots[2].max_actions == 4   # 20% of 20

    def test_default_keyboard_allocation(self):
        profile = _make_profile("keyboard")
        solver = PerGameSolver(profile, arcade=MagicMock())
        slots = solver._allocate_budget(level_num=0)

        assert len(slots) == 3
        assert slots[0].strategy == "keyboard_explore"
        assert slots[0].max_actions == 100  # 50% of 200

    def test_default_mixed_allocation(self):
        profile = _make_profile("mixed")
        solver = PerGameSolver(profile, arcade=MagicMock())
        slots = solver._allocate_budget(level_num=0)

        assert slots[0].strategy == "hybrid"
        assert slots[0].max_actions == 50  # 50% of 100

    def test_ranked_allocation_overrides_defaults(self):
        metrics = {
            "keyboard_explore": StrategyMetrics(attempts=10, wins=8),
            "cluster_click": StrategyMetrics(attempts=10, wins=2),
            "hybrid": StrategyMetrics(attempts=5, wins=1),
        }
        profile = _make_profile("click", metrics=metrics)
        solver = PerGameSolver(profile, arcade=MagicMock())
        slots = solver._allocate_budget(level_num=0)

        # keyboard_explore has highest win_rate -> gets 50%
        assert slots[0].strategy == "keyboard_explore"
        assert slots[1].strategy == "cluster_click"
        assert slots[2].strategy == "hybrid"


class TestStagnationDetection:
    def test_no_stagnation_with_changes(self):
        solver = PerGameSolver(_make_profile(), arcade=MagicMock())
        grids = [np.random.randint(0, 10, (64, 64)) for _ in range(5)]
        assert solver._detect_stagnation(grids) is False

    def test_stagnation_with_identical_frames(self):
        solver = PerGameSolver(_make_profile(), arcade=MagicMock())
        same = np.zeros((64, 64), dtype=np.int8)
        grids = [same.copy() for _ in range(5)]
        assert solver._detect_stagnation(grids) is True

    def test_stagnation_with_tiny_changes(self):
        solver = PerGameSolver(_make_profile(), arcade=MagicMock())
        base = np.zeros((64, 64), dtype=np.int8)
        grids = []
        for i in range(5):
            g = base.copy()
            g[0, i] = 1  # only 1 pixel changes per frame
            grids.append(g)
        # Max diff between consecutive = 2 pixels (one removed, one added)
        # Under threshold of 10 -> stagnation
        assert solver._detect_stagnation(grids) is True

    def test_no_stagnation_with_short_history(self):
        solver = PerGameSolver(_make_profile(), arcade=MagicMock())
        same = np.zeros((64, 64), dtype=np.int8)
        assert solver._detect_stagnation([same, same]) is False  # < 5 frames


class TestSolveResult:
    def test_defaults(self):
        r = SolveResult(game_id="test", levels_completed=0, total_steps=0, strategy_log=[], score=0.0)
        assert r.game_id == "test"


def _make_mock_game_state(name):
    state = MagicMock()
    state.name = name
    state.__eq__ = lambda self, other: getattr(other, "name", other) == name
    return state


def _make_mock_obs(grid=None, state_name="NOT_FINISHED", levels=0, actions=None):
    if grid is None:
        grid = np.zeros((1, 64, 64), dtype=np.int8)
    obs = MagicMock()
    obs.frame = grid
    obs.state = _make_mock_game_state(state_name)
    obs.levels_completed = levels
    obs.available_actions = actions or []
    obs.win_levels = 0
    return obs


class TestStrategyExecution:
    def test_execute_targeted_click_win(self):
        """targeted_click strategy clicks on known zones and wins."""
        profile = _make_profile("click")

        mock_env = MagicMock()
        step_count = [0]

        def mock_step(action, data=None):
            step_count[0] += 1
            if step_count[0] >= 2:
                return _make_mock_obs(state_name="WIN", levels=1)
            return _make_mock_obs()

        mock_env.step = mock_step

        solver = PerGameSolver(profile, arcade=MagicMock())
        outcome = solver._execute_strategy(mock_env, "targeted_click", max_actions=10)

        assert isinstance(outcome, StrategyOutcome)
        assert outcome.won is True
        assert outcome.steps > 0

    def test_execute_keyboard_explore(self):
        """keyboard_explore strategy runs actions without error."""
        profile = _make_profile("keyboard")
        mock_env = MagicMock()
        call_count = [0]

        def varied_step(action, data=None):
            call_count[0] += 1
            grid = np.full((1, 64, 64), call_count[0] % 256, dtype=np.int8)
            return _make_mock_obs(grid=grid)

        mock_env.step = varied_step

        solver = PerGameSolver(profile, arcade=MagicMock())
        outcome = solver._execute_strategy(mock_env, "keyboard_explore", max_actions=20)

        assert isinstance(outcome, StrategyOutcome)
        assert outcome.steps == 20  # used full budget

    def test_execute_stops_on_game_over(self):
        """Strategy stops when GAME_OVER is received."""
        profile = _make_profile("click")
        mock_env = MagicMock()
        mock_env.step.return_value = _make_mock_obs(state_name="GAME_OVER")

        solver = PerGameSolver(profile, arcade=MagicMock())
        outcome = solver._execute_strategy(mock_env, "targeted_click", max_actions=10)

        assert outcome.won is False
        assert outcome.game_over is True

    def test_execute_stops_on_stagnation(self):
        """Strategy switches on stagnation (identical frames)."""
        profile = _make_profile("keyboard")
        same_grid = np.zeros((1, 64, 64), dtype=np.int8)
        mock_env = MagicMock()
        mock_env.step.return_value = _make_mock_obs(grid=same_grid)

        solver = PerGameSolver(profile, arcade=MagicMock())
        outcome = solver._execute_strategy(mock_env, "keyboard_explore", max_actions=50)

        # Should stop early due to stagnation (after ~5 identical frames)
        assert outcome.steps < 50
        assert outcome.stagnated is True


class TestSolve:
    def test_solve_single_level_win(self):
        """solve() wins a single level and returns SolveResult."""
        profile = _make_profile("click")

        mock_env = MagicMock()
        step_count = [0]

        def mock_step(action, data=None):
            step_count[0] += 1
            if step_count[0] >= 2:
                return _make_mock_obs(state_name="WIN", levels=1)
            return _make_mock_obs()

        mock_env.step = mock_step
        mock_env.reset.return_value = _make_mock_obs()

        mock_arcade = MagicMock()
        mock_arcade.make.return_value = mock_env

        solver = PerGameSolver(profile, arcade=mock_arcade)
        result = solver.solve(max_levels=1)

        assert isinstance(result, SolveResult)
        assert result.levels_completed >= 1
        assert result.total_steps > 0
        assert len(result.strategy_log) >= 1

    def test_solve_skips_failed_level(self):
        """solve() moves to next level after all strategies fail."""
        profile = _make_profile("click")

        mock_env = MagicMock()
        # Always return same grid -> stagnation -> all strategies fail
        same_grid = np.zeros((1, 64, 64), dtype=np.int8)
        mock_env.step.return_value = _make_mock_obs(grid=same_grid)
        mock_env.reset.return_value = _make_mock_obs(grid=same_grid)

        mock_arcade = MagicMock()
        mock_arcade.make.return_value = mock_env

        solver = PerGameSolver(profile, arcade=mock_arcade)
        result = solver.solve(max_levels=2)

        assert result.levels_completed == 0

    def test_solve_updates_profile_metrics(self, tmp_path):
        """solve() updates strategy metrics in the profile."""
        profile = _make_profile("click")

        mock_env = MagicMock()
        step_count = [0]

        def mock_step(action, data=None):
            step_count[0] += 1
            if step_count[0] >= 2:
                return _make_mock_obs(state_name="WIN", levels=1)
            return _make_mock_obs()

        mock_env.step = mock_step
        mock_env.reset.return_value = _make_mock_obs()

        mock_arcade = MagicMock()
        mock_arcade.make.return_value = mock_env

        solver = PerGameSolver(profile, arcade=mock_arcade)
        solver.solve(max_levels=1, base_dir=tmp_path)

        # Profile should have been updated
        assert profile.total_runs == 1
        assert len(profile.strategy_metrics) > 0

    def test_solve_respects_timeout(self):
        """solve() respects the timeout per game."""
        profile = _make_profile("keyboard")

        mock_env = MagicMock()
        # Return varied grids so stagnation doesn't trigger
        call_count = [0]
        def varied_step(action, data=None):
            call_count[0] += 1
            grid = np.full((1, 64, 64), call_count[0] % 16, dtype=np.int8)
            return _make_mock_obs(grid=grid)

        mock_env.step = varied_step
        mock_env.reset.return_value = _make_mock_obs()

        mock_arcade = MagicMock()
        mock_arcade.make.return_value = mock_env

        solver = PerGameSolver(profile, arcade=mock_arcade)
        # With a tiny timeout, should return quickly
        result = solver.solve(max_levels=10, timeout_s=0.1)

        assert isinstance(result, SolveResult)


class TestClusterClickStrategy:
    def test_cluster_click_uses_subset_search(self):
        """cluster_click should find clusters and try subsets via arcade.make()."""
        profile = _make_profile("click")
        profile.target_colors = [3]

        # Initial grid with 3 clusters of color 3
        grid = np.zeros((64, 64), dtype=np.int8)
        grid[10:15, 10:15] = 3
        grid[30:35, 30:35] = 3
        grid[50:55, 50:55] = 3

        make_count = [0]

        def mock_make(game_id):
            make_count[0] += 1
            env = MagicMock()
            click_count = [0]

            def env_step(action, data=None):
                click_count[0] += 1
                # Win when clicking exactly 2 of the 3 clusters
                if click_count[0] == 2:
                    return _make_mock_obs(state_name="WIN", levels=1)
                return _make_mock_obs(grid=np.expand_dims(grid, 0))

            env.step = env_step
            env.reset.return_value = _make_mock_obs(grid=np.expand_dims(grid, 0))
            return env

        mock_arcade = MagicMock()
        mock_arcade.make = mock_make

        solver = PerGameSolver(profile, arcade=mock_arcade)
        outcome = solver._execute_cluster_click(
            initial_grid=grid, target_color=3, max_actions=20
        )

        assert outcome.won is True
        assert make_count[0] > 0  # Used arcade.make for subset search

    def test_cluster_click_no_target_color_returns_empty(self):
        """cluster_click with no target color returns no-win outcome."""
        profile = _make_profile("click")
        profile.target_colors = []

        solver = PerGameSolver(profile, arcade=MagicMock())
        grid = np.zeros((64, 64), dtype=np.int8)
        outcome = solver._execute_cluster_click(grid, target_color=None, max_actions=10)

        assert outcome.won is False
        assert outcome.steps == 0
