"""ARC-AGI-3 Hybrid Solver — runs all solver strategies per game.

Strategy priority:
1. ClusterSolver (click-toggle games) — fast, proven on ft09
2. Keyboard explorer (directional games) — epsilon-greedy with pixel reward
3. Random baseline — fallback

Runs each game for a limited budget, reports results.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from jarvis.utils.logging import get_logger

__all__ = ["HybridSolver", "run_all_games"]

log = get_logger(__name__)


class HybridSolver:
    """Attempts multiple strategies per game to maximize score."""

    def __init__(self, max_actions_per_level: int = 40) -> None:
        self.max_actions = max_actions_per_level

    def solve_game(self, game_id: str) -> dict[str, Any]:
        """Play one game with the best available strategy."""
        import arc_agi

        arcade = arc_agi.Arcade()
        env = arcade.make(game_id)
        obs = env.reset()

        actions = [
            a.value if hasattr(a, "value") else int(a) for a in (obs.available_actions or [])
        ]
        has_click = 6 in actions
        has_keyboard = any(a in [1, 2, 3, 4] for a in actions)

        t0 = time.monotonic()

        if has_click and not has_keyboard:
            # Pure click game → ClusterSolver
            result = self._solve_click(arcade, game_id, env, obs)
        elif has_keyboard and not has_click:
            # Pure keyboard game → Keyboard explorer
            result = self._solve_keyboard(arcade, game_id, env, obs)
        else:
            # Mixed → try click first, then keyboard
            result = self._solve_click(arcade, game_id, env, obs)
            if result["levels_completed"] == 0:
                # Retry with keyboard
                env2 = arcade.make(game_id)
                obs2 = env2.reset()
                result = self._solve_keyboard(arcade, game_id, env2, obs2)

        result["elapsed_s"] = round(time.monotonic() - t0, 1)
        result["game_id"] = game_id.split("-")[0]
        return result

    def _solve_click(self, arcade: Any, game_id: str, env: Any, obs: Any) -> dict[str, Any]:
        """Solve a click-based game using cluster detection + subset search."""
        import itertools

        from arcengine.enums import GameState

        levels = 0
        total_clicks = 0
        all_solutions: list[list[tuple[int, int]]] = []

        for _level in range(10):
            grid = np.array(obs.frame)
            if grid.ndim == 3:
                grid = grid[0]

            # Find ALL clickable regions by scanning
            hot_spots = self._find_hot_spots(arcade, game_id, all_solutions, grid)

            if not hot_spots:
                break

            n = len(hot_spots)
            solved = False

            # Try subsets: skip 0, 1, 2, ... clusters
            for skip in range(min(n + 1, 8)):
                if solved:
                    break
                for combo in itertools.combinations(range(n), skip):
                    click_idx = [i for i in range(n) if i not in combo]
                    clicks = [hot_spots[i] for i in click_idx]

                    # Test on fresh env
                    env_t = arcade.make(game_id)
                    obs_t = env_t.reset()

                    # Replay previous solutions
                    ok = True
                    for prev_sol in all_solutions:
                        for cx, cy in prev_sol:
                            obs_t = env_t.step(6, data={"x": cx, "y": cy})
                            if obs_t.state == GameState.GAME_OVER:
                                ok = False
                                break
                        if not ok:
                            break
                    if not ok:
                        continue

                    # Test this combination
                    for cx, cy in clicks:
                        obs_t = env_t.step(6, data={"x": cx, "y": cy})
                        if obs_t.state != GameState.NOT_FINISHED:
                            break

                    if obs_t.levels_completed > levels:
                        # Apply to real env
                        for cx, cy in clicks:
                            obs = env.step(6, data={"x": cx, "y": cy})
                            total_clicks += 1
                        levels = obs.levels_completed
                        all_solutions.append(clicks)
                        log.info(
                            "hybrid_click_level",
                            game=game_id.split("-")[0],
                            level=levels,
                            clicks=len(clicks),
                        )
                        solved = True
                        break

                    if obs_t.state == GameState.GAME_OVER:
                        break

            if not solved:
                break
            if obs.state == GameState.WIN:
                break

        return {
            "levels_completed": levels,
            "total_actions": total_clicks,
            "method": "click",
        }

    def _find_hot_spots(
        self,
        arcade: Any,
        game_id: str,
        prev_solutions: list[list[tuple[int, int]]],
        grid: np.ndarray,
    ) -> list[tuple[int, int]]:
        """Find clickable positions that cause >5px change."""

        # Get base state
        env = arcade.make(game_id)
        obs = env.reset()
        for sol in prev_solutions:
            for cx, cy in sol:
                obs = env.step(6, data={"x": cx, "y": cy})
        base = np.array(obs.frame)
        if base.ndim == 3:
            base = base[0]

        spots = []
        seen = set()
        for y in range(0, 64, 2):
            for x in range(0, 64, 2):
                env2 = arcade.make(game_id)
                obs2 = env2.reset()
                for sol in prev_solutions:
                    for cx, cy in sol:
                        obs2 = env2.step(6, data={"x": cx, "y": cy})
                obs2 = env2.step(6, data={"x": x, "y": y})
                g2 = np.array(obs2.frame)
                if g2.ndim == 3:
                    g2 = g2[0]
                ch = int(np.sum(g2 != base))
                if ch > 5:
                    # Deduplicate by region
                    key = (x // 8, y // 8)
                    if key not in seen:
                        seen.add(key)
                        spots.append((x, y))

        return spots

    def _solve_keyboard(self, arcade: Any, game_id: str, env: Any, obs: Any) -> dict[str, Any]:
        """Solve a keyboard game using systematic action sequences."""
        import random

        from arcengine.enums import GameState

        actions = [
            a.value if hasattr(a, "value") else int(a)
            for a in (obs.available_actions or [1, 2, 3, 4])
        ]

        levels = 0
        total_steps = 0
        prev_grid = np.array(obs.frame)
        if prev_grid.ndim == 3:
            prev_grid = prev_grid[0]

        # Simple strategy: cycle through actions, prefer ones that cause change
        action_reward: dict[int, float] = {a: 0.0 for a in actions}

        for _step in range(self.max_actions * 5):
            # Pick action: 30% random, 70% best reward
            if random.random() < 0.3 or not any(action_reward.values()):
                action = random.choice(actions)
            else:
                action = max(action_reward, key=lambda a: action_reward[a])

            obs = env.step(action)
            total_steps += 1

            cur_grid = np.array(obs.frame)
            if cur_grid.ndim == 3:
                cur_grid = cur_grid[0]
            changed = int(np.sum(cur_grid != prev_grid))
            prev_grid = cur_grid

            # Update reward
            action_reward[action] = action_reward.get(action, 0) * 0.9 + changed * 0.1

            if obs.levels_completed > levels:
                levels = obs.levels_completed
                log.info(
                    "hybrid_keyboard_level",
                    game=game_id.split("-")[0],
                    level=levels,
                    steps=total_steps,
                )

            if obs.state == GameState.WIN:
                break
            if obs.state == GameState.GAME_OVER:
                obs = env.reset()
                prev_grid = np.array(obs.frame)
                if prev_grid.ndim == 3:
                    prev_grid = prev_grid[0]

        return {
            "levels_completed": levels,
            "total_actions": total_steps,
            "method": "keyboard",
        }


def run_all_games(max_time_per_game: int = 120) -> list[dict]:
    """Run hybrid solver on all available games."""
    import arc_agi

    arcade = arc_agi.Arcade()
    envs = arcade.get_environments()

    results = []
    total_levels = 0

    for e in envs:
        gid = e.game_id
        short = gid.split("-")[0]

        solver = HybridSolver(max_actions_per_level=40)
        try:
            result = solver.solve_game(gid)
            total_levels += result["levels_completed"]
            results.append(result)

            status = "WIN" if result["levels_completed"] > 0 else "---"
            print(
                f"{short:5s}: {status} levels={result['levels_completed']} "
                f"actions={result['total_actions']} method={result['method']} "
                f"{result['elapsed_s']}s",
                flush=True,
            )
        except Exception as exc:
            print(f"{short:5s}: ERROR {str(exc)[:60]}", flush=True)
            results.append(
                {
                    "game_id": short,
                    "levels_completed": 0,
                    "error": str(exc)[:100],
                }
            )

    print(f"\nTOTAL: {total_levels} levels across {len(envs)} games", flush=True)
    return results
