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
