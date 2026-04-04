"""ARC-AGI-3 Hybrid Solver — fast cluster detection + subset search.

Click games: ndimage.label() finds clusters instantly (no SDK calls),
then subset search validates on SDK. This is the approach that solved
ft09 Level 1 (17 clicks, 60s) and Level 2 (9 clicks).

Keyboard games: epsilon-greedy with pixel reward (200 steps).

Mixed games: try click approach first, keyboard fallback.
"""

from __future__ import annotations

import itertools
import random
import time
from typing import Any

import numpy as np
from scipy import ndimage

from jarvis.utils.logging import get_logger

__all__ = ["HybridSolver", "run_all_games"]

log = get_logger(__name__)


class HybridSolver:
    """Fast solver using cluster detection for clicks, exploration for keyboard."""

    def __init__(self, max_skip: int = 6, max_keyboard_steps: int = 200) -> None:
        self.max_skip = max_skip
        self.max_keyboard_steps = max_keyboard_steps

    def solve_game(self, game_id: str) -> dict[str, Any]:
        """Play one game with the best strategy."""
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

        if has_click:
            result = self._solve_click(arcade, game_id)
            if result["levels_completed"] > 0 or not has_keyboard:
                result["elapsed_s"] = round(time.monotonic() - t0, 1)
                result["game_id"] = game_id.split("-")[0]
                return result

        # Keyboard fallback
        result = self._solve_keyboard(arcade, game_id)
        result["elapsed_s"] = round(time.monotonic() - t0, 1)
        result["game_id"] = game_id.split("-")[0]
        return result

    def _find_clusters(self, grid: np.ndarray) -> dict[int, list[tuple[int, int]]]:
        """Find cluster centers for each non-background color. Pure numpy, no SDK."""
        if grid.ndim == 3:
            grid = grid[0]

        # Background = most common color
        colors, counts = np.unique(grid, return_counts=True)
        bg = colors[np.argmax(counts)]

        result: dict[int, list[tuple[int, int]]] = {}
        for c in colors:
            if c == bg:
                continue
            mask = grid == c
            labeled, n = ndimage.label(mask)
            if n > 0:
                centers = []
                for i in range(1, n + 1):
                    ys, xs = np.where(labeled == i)
                    centers.append((int(np.mean(xs)), int(np.mean(ys))))
                result[int(c)] = centers

        return result

    def _solve_click(self, arcade: Any, game_id: str) -> dict[str, Any]:
        """Solve click game using cluster detection + subset search."""
        from arcengine.enums import GameState

        all_solutions: list[list[tuple[int, int]]] = []
        levels = 0

        for _level_attempt in range(10):
            # Get current grid state
            env = arcade.make(game_id)
            obs = env.reset()
            for sol in all_solutions:
                for cx, cy in sol:
                    obs = env.step(6, data={"x": cx, "y": cy})

            grid = np.array(obs.frame)
            if grid.ndim == 3:
                grid = grid[0]

            # Find all non-bg clusters
            color_clusters = self._find_clusters(grid)

            if not color_clusters:
                break

            # Try each color's clusters as click targets
            solved = False
            for color, centers in sorted(
                color_clusters.items(), key=lambda x: len(x[1]), reverse=True
            ):
                n = len(centers)
                if n == 0:
                    continue

                # Try subsets: click all, skip 1, skip 2, ...
                for skip in range(min(n + 1, self.max_skip + 1)):
                    if solved:
                        break
                    for combo in itertools.combinations(range(n), skip):
                        click_idx = [i for i in range(n) if i not in combo]
                        clicks = [centers[i] for i in click_idx]

                        # Validate on fresh env
                        env_t = arcade.make(game_id)
                        obs_t = env_t.reset()

                        ok = True
                        for prev in all_solutions:
                            for cx, cy in prev:
                                obs_t = env_t.step(6, data={"x": cx, "y": cy})
                                if obs_t.state == GameState.GAME_OVER:
                                    ok = False
                                    break
                            if not ok:
                                break
                        if not ok:
                            continue

                        for cx, cy in clicks:
                            obs_t = env_t.step(6, data={"x": cx, "y": cy})
                            if obs_t.state != GameState.NOT_FINISHED:
                                break

                        if obs_t.levels_completed > levels:
                            all_solutions.append(clicks)
                            levels = obs_t.levels_completed
                            log.info(
                                "hybrid_click_solved",
                                game=game_id.split("-")[0],
                                level=levels,
                                color=color,
                                clicks=len(clicks),
                                skipped=skip,
                                total_clusters=n,
                            )
                            solved = True
                            break

                        if obs_t.state == GameState.GAME_OVER:
                            break
                if solved:
                    break

            if not solved:
                break

        return {
            "levels_completed": levels,
            "total_actions": sum(len(s) for s in all_solutions),
            "method": "click",
        }

    def _solve_keyboard(self, arcade: Any, game_id: str) -> dict[str, Any]:
        """Solve keyboard game with epsilon-greedy exploration."""
        from arcengine.enums import GameState

        env = arcade.make(game_id)
        obs = env.reset()

        actions = [
            a.value if hasattr(a, "value") else int(a)
            for a in (obs.available_actions or [1, 2, 3, 4])
        ]

        levels = 0
        total_steps = 0
        prev_grid = np.array(obs.frame)
        if prev_grid.ndim == 3:
            prev_grid = prev_grid[0]

        action_reward: dict[int, float] = {a: 1.0 for a in actions}

        for _step in range(self.max_keyboard_steps):
            # 30% random, 70% best
            if random.random() < 0.3:
                action = random.choice(actions)
            else:
                action = max(action_reward, key=lambda a: action_reward[a])

            obs = env.step(action)
            total_steps += 1

            cur = np.array(obs.frame)
            if cur.ndim == 3:
                cur = cur[0]
            changed = int(np.sum(cur != prev_grid))
            prev_grid = cur

            action_reward[action] = action_reward.get(action, 0) * 0.9 + changed * 0.1

            if obs.levels_completed > levels:
                levels = obs.levels_completed
                log.info(
                    "hybrid_keyboard_level",
                    game=game_id.split("-")[0],
                    level=levels,
                    step=total_steps,
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


def run_all_games() -> list[dict]:
    """Run hybrid solver on all available games."""
    import arc_agi

    arcade = arc_agi.Arcade()
    envs = arcade.get_environments()

    results = []
    total_levels = 0
    t0 = time.monotonic()

    for e in envs:
        gid = e.game_id
        short = gid.split("-")[0]

        solver = HybridSolver()
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
            results.append({"game_id": short, "levels_completed": 0, "error": str(exc)[:100]})

    elapsed = time.monotonic() - t0
    print(f"\nTOTAL: {total_levels} levels across {len(envs)} games in {elapsed:.0f}s", flush=True)
    return results
