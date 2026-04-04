"""CognithorArcAgent — ARC-AGI-3 agent using DSL + LLM hybrid solver."""

from __future__ import annotations

from typing import Any

from jarvis.arc.audit import ArcAuditTrail
from jarvis.arc.episode_memory import EpisodeMemory
from jarvis.arc.solver import ArcSolver
from jarvis.arc.task_parser import ArcTask, GameResult
from jarvis.utils.logging import get_logger

__all__ = ["CognithorArcAgent"]

log = get_logger(__name__)


class CognithorArcAgent:
    """ARC-AGI-3 Agent using DSL search + LLM code-generation.

    Args:
        game_id: The ARC-AGI-3 task/environment identifier.
        llm_fn: Optional async LLM function for code generation.
    """

    def __init__(
        self,
        game_id: str,
        llm_fn: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self.game_id = game_id
        self.solver = ArcSolver(llm_fn=llm_fn)
        self.memory = EpisodeMemory()
        self.audit_trail = ArcAuditTrail(game_id)

    def run(self) -> dict[str, Any]:
        """Synchronous entry point (wraps async solve)."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, self._run_async()).result()
        else:
            result = asyncio.run(self._run_async())

        return {
            "game_id": self.game_id,
            "win": result.win,
            "attempts": result.attempts,
            "levels_completed": 1 if result.win else 0,
            "total_steps": result.attempts,
            "score": 1.0 if result.win else 0.0,
        }

    async def _run_async(self) -> GameResult:
        """Async entry point: load task, solve, return result."""
        task = self._load_task()
        if task is None:
            return GameResult(win=False, attempts=0, task_id=self.game_id)

        self.audit_trail.log_game_start()

        solutions = await self.solver.solve(task)

        for i, solution in enumerate(solutions[:3]):
            self.audit_trail.log_step(
                level=0,
                step=i,
                action=solution.description,
                game_state="solving",
                pixels_changed=0,
            )

        result = GameResult(
            win=len(solutions) > 0,
            attempts=len(solutions),
            task_id=task.task_id,
            solutions_tried=solutions,
        )

        self.audit_trail.log_game_end(1.0 if result.win else 0.0)

        return result

    def _load_task(self) -> ArcTask | None:
        """Try to load a task from local ARC dataset files or adapter."""
        # Try adapter first
        try:
            from jarvis.arc.adapter import ArcEnvironmentAdapter

            adapter = ArcEnvironmentAdapter(self.game_id)
            if hasattr(adapter, "load_as_arc_task"):
                return adapter.load_as_arc_task()
        except Exception:
            pass

        # Fallback: load from JSON file
        import json
        from pathlib import Path

        for base in [
            Path.home() / ".jarvis" / "arc" / "tasks",
            Path("data") / "arc",
        ]:
            task_file = base / f"{self.game_id}.json"
            if task_file.exists():
                try:
                    data = json.loads(task_file.read_text())
                    examples = [(ex["input"], ex["output"]) for ex in data.get("train", [])]
                    test_input = data.get("test", [{}])[0].get("input", [[]])
                    return ArcTask(
                        task_id=self.game_id,
                        examples=examples,
                        test_input=test_input,
                    )
                except Exception:
                    pass

        log.warning("arc_task_not_found", game=self.game_id)
        return None
