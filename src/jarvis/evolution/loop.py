"""Evolution Loop — orchestrates Scout/Research/Build/Reflect cycles during idle time."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from jarvis.utils.logging import get_logger

if TYPE_CHECKING:
    from jarvis.evolution.idle_detector import IdleDetector

log = get_logger(__name__)

__all__ = ["EvolutionLoop", "EvolutionCycleResult"]


@dataclass
class EvolutionCycleResult:
    """Result of one evolution cycle."""

    cycle_id: int = 0
    skipped: bool = False
    reason: str = ""
    gaps_found: int = 0
    research_topic: str = ""
    skill_created: str = ""
    duration_ms: int = 0
    steps_completed: list[str] = field(default_factory=list)


class EvolutionLoop:
    """Orchestrates autonomous learning during idle time.

    Cycle: Scout (find gaps) -> Research (deep_research) -> Build (create skill) -> Reflect
    Each step checks idle_detector — aborts immediately if user returns.
    """

    def __init__(
        self,
        idle_detector: IdleDetector,
        curiosity_engine: Any = None,
        skill_generator: Any = None,
        memory_manager: Any = None,
        config: Any = None,
    ) -> None:
        self._idle = idle_detector
        self._curiosity = curiosity_engine
        self._skill_gen = skill_generator
        self._memory = memory_manager
        self._config = config
        self._running = False
        self._task: asyncio.Task | None = None
        self._cycles_today = 0
        self._last_cycle_day = ""
        self._total_cycles = 0
        self._total_skills_created = 0
        self._results: list[EvolutionCycleResult] = []

    async def start(self) -> None:
        """Start the evolution background loop."""
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="evolution-loop")
        log.info("evolution_loop_started")

    def stop(self) -> None:
        """Stop the evolution loop."""
        self._running = False
        if self._task:
            self._task.cancel()
        log.info("evolution_loop_stopped")

    async def run_cycle(self) -> EvolutionCycleResult:
        """Run one Scout->Research->Build->Reflect cycle."""
        t0 = time.monotonic()
        self._total_cycles += 1
        result = EvolutionCycleResult(cycle_id=self._total_cycles)

        # Pre-check: still idle?
        if not self._idle.is_idle:
            result.skipped = True
            result.reason = "not_idle"
            return result

        # Step 1: Scout — find knowledge gaps
        gaps = await self._scout()
        result.steps_completed.append("scout")
        if not gaps:
            result.skipped = True
            result.reason = "no_gaps"
            result.duration_ms = int((time.monotonic() - t0) * 1000)
            return result
        result.gaps_found = len(gaps)

        if not self._idle.is_idle:
            result.skipped = True
            result.reason = "interrupted_after_scout"
            result.duration_ms = int((time.monotonic() - t0) * 1000)
            return result

        # Step 2: Research — investigate the top gap
        top_gap = gaps[0]
        result.research_topic = getattr(top_gap, "question", str(top_gap))[:100]
        research_text = await self._research(top_gap)
        result.steps_completed.append("research")

        if not research_text or not self._idle.is_idle:
            result.reason = "research_empty_or_interrupted"
            result.duration_ms = int((time.monotonic() - t0) * 1000)
            return result

        # Step 3: Build — create a skill from the research
        skill_name = await self._build(top_gap, research_text)
        result.steps_completed.append("build")
        if skill_name:
            result.skill_created = skill_name
            self._total_skills_created += 1

        # Step 4: Reflect — log what was learned
        result.steps_completed.append("reflect")
        result.duration_ms = int((time.monotonic() - t0) * 1000)

        log.info(
            "evolution_cycle_complete",
            cycle=result.cycle_id,
            gaps=result.gaps_found,
            topic=result.research_topic[:50],
            skill=result.skill_created or "none",
            duration_ms=result.duration_ms,
        )

        return result

    # -- Internal steps --------------------------------------------------

    async def _scout(self) -> list[Any]:
        """Find knowledge gaps via CuriosityEngine."""
        if not self._curiosity:
            return []
        try:
            if self._memory and hasattr(self._memory, "semantic"):
                entities = self._memory.semantic.list_entities(limit=50)
                await self._curiosity.detect_gaps("", entities)
            tasks = self._curiosity.propose_exploration(max_tasks=3)
            return tasks
        except Exception:
            log.debug("evolution_scout_failed", exc_info=True)
            return []

    async def _research(self, gap: Any) -> str:
        """Research a knowledge gap. Returns research text."""
        query = getattr(gap, "query", getattr(gap, "question", str(gap)))
        # Use memory search as lightweight research
        if self._memory:
            try:
                results = self._memory.search_memory_sync(query=query, top_k=5)
                if results:
                    return "\n".join(getattr(r, "text", str(r))[:200] for r in results[:3])
            except Exception:
                pass
        return ""

    async def _build(self, gap: Any, research: str) -> str:
        """Build a skill from research results. Returns skill name or empty."""
        if not self._skill_gen:
            return ""
        try:
            from jarvis.skills.generator import SkillGap, SkillGapType

            skill_gap = SkillGap(
                gap_type=SkillGapType.NO_SKILL_MATCH,
                description=getattr(gap, "query", str(gap))[:200],
                context=research[:500],
            )
            result = await self._skill_gen.process_gap(skill_gap)
            if result and hasattr(result, "name"):
                return result.name
        except Exception:
            log.debug("evolution_build_failed", exc_info=True)
        return ""

    # -- Loop control ----------------------------------------------------

    def _can_run_cycle(self) -> bool:
        """Check daily limit and cooldown."""
        today = time.strftime("%Y-%m-%d")
        if today != self._last_cycle_day:
            self._cycles_today = 0
            self._last_cycle_day = today
        max_cycles = 10
        if self._config and hasattr(self._config, "max_cycles_per_day"):
            max_cycles = self._config.max_cycles_per_day
        return self._cycles_today < max_cycles

    async def _loop(self) -> None:
        """Background loop: wait for idle -> run cycle -> cooldown."""
        cooldown = 300
        if self._config and hasattr(self._config, "cycle_cooldown_seconds"):
            cooldown = self._config.cycle_cooldown_seconds
        while self._running:
            try:
                if self._idle.is_idle and self._can_run_cycle():
                    result = await self.run_cycle()
                    self._cycles_today += 1
                    self._results.append(result)
                    if len(self._results) > 100:
                        self._results = self._results[-50:]
                    await asyncio.sleep(cooldown)
                else:
                    await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception:
                log.debug("evolution_loop_error", exc_info=True)
                await asyncio.sleep(60)

    def stats(self) -> dict[str, Any]:
        """Return evolution statistics."""
        return {
            "running": self._running,
            "is_idle": self._idle.is_idle,
            "idle_seconds": round(self._idle.idle_seconds),
            "total_cycles": self._total_cycles,
            "cycles_today": self._cycles_today,
            "total_skills_created": self._total_skills_created,
            "recent_results": [
                {
                    "cycle": r.cycle_id,
                    "skipped": r.skipped,
                    "reason": r.reason,
                    "topic": r.research_topic[:50],
                    "skill": r.skill_created,
                    "steps": r.steps_completed,
                    "duration_ms": r.duration_ms,
                }
                for r in self._results[-10:]
            ],
        }
