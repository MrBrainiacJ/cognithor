"""DeepLearner — orchestrates learning plans via StrategyPlanner and plan CRUD."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, List, Optional

from jarvis.evolution.models import LearningPlan, SeedSource, SubGoal
from jarvis.evolution.strategy_planner import StrategyPlanner
from jarvis.utils.logging import get_logger

log = get_logger(__name__)


class DeepLearner:
    """High-level orchestrator for autonomous deep-learning plans.

    Delegates plan creation to StrategyPlanner and provides CRUD
    operations on persisted LearningPlan instances.
    """

    def __init__(
        self,
        llm_fn: Callable,
        plans_dir: str | None = None,
        mcp_client=None,
        memory_manager=None,
        skill_registry=None,
        skill_generator=None,
        cron_engine=None,
        cost_tracker=None,
        resource_monitor=None,
        checkpoint_store=None,
        config=None,
        idle_detector=None,
        operation_mode: str = "offline",
    ) -> None:
        if plans_dir is None:
            self._plans_dir = Path.home() / ".jarvis" / "evolution" / "plans"
        else:
            self._plans_dir = Path(plans_dir)
        self._plans_dir.mkdir(parents=True, exist_ok=True)

        self._strategy_planner = StrategyPlanner(llm_fn=llm_fn)

        self._llm_fn = llm_fn
        self._mcp_client = mcp_client
        self._memory_manager = memory_manager
        self._skill_registry = skill_registry
        self._skill_generator = skill_generator
        self._cron_engine = cron_engine
        self._cost_tracker = cost_tracker
        self._resource_monitor = resource_monitor
        self._checkpoint_store = checkpoint_store
        self._config = config
        self._idle_detector = idle_detector
        self._operation_mode = operation_mode

    # ------------------------------------------------------------------
    # Plan CRUD
    # ------------------------------------------------------------------

    async def create_plan(
        self,
        goal: str,
        seed_sources: list[SeedSource] | None = None,
    ) -> LearningPlan:
        """Create a new learning plan via StrategyPlanner, persist to disk."""
        plan = await self._strategy_planner.create_plan(
            goal, seed_sources=seed_sources
        )
        plan.status = "active"
        plan.save(str(self._plans_dir))
        log.info("Created plan %s for goal: %s", plan.id, goal)
        return plan

    def list_plans(self) -> List[LearningPlan]:
        """Return all persisted learning plans."""
        return LearningPlan.list_plans(str(self._plans_dir))

    def get_plan(self, plan_id: str) -> LearningPlan | None:
        """Load a single plan by ID, or None if not found."""
        plan_dir = self._plans_dir / plan_id
        if not (plan_dir / "plan.json").exists():
            return None
        try:
            return LearningPlan.load(str(plan_dir))
        except Exception:
            log.warning("Failed to load plan %s", plan_id)
            return None

    def update_plan_status(self, plan_id: str, status: str) -> bool:
        """Update a plan's status and re-persist."""
        plan = self.get_plan(plan_id)
        if plan is None:
            return False
        plan.status = status
        plan.save(str(self._plans_dir))
        log.info("Plan %s status -> %s", plan_id, status)
        return True

    def delete_plan(self, plan_id: str) -> bool:
        """Remove plan directory entirely."""
        plan_dir = self._plans_dir / plan_id
        if not plan_dir.exists():
            return False
        shutil.rmtree(plan_dir)
        log.info("Deleted plan %s", plan_id)
        return True

    def get_next_subgoal(self, plan_id: str) -> SubGoal | None:
        """Return highest-priority pending SubGoal, or None if all done."""
        plan = self.get_plan(plan_id)
        if plan is None:
            return None
        pending = [sg for sg in plan.sub_goals if sg.status == "pending"]
        if not pending:
            return None
        # Sub-goals are already sorted by priority from StrategyPlanner;
        # return the first pending one (lowest priority number = highest priority).
        pending.sort(key=lambda sg: sg.priority)
        return pending[0]

    def has_active_plans(self) -> bool:
        """Return True if any plan is active with pending sub_goals."""
        for plan in self.list_plans():
            if plan.status == "active":
                if any(sg.status == "pending" for sg in plan.sub_goals):
                    return True
        return False

    def is_complex_goal(self, goal: str) -> bool:
        """Delegate complexity check to StrategyPlanner."""
        return self._strategy_planner.is_complex_goal(goal)

    # ------------------------------------------------------------------
    # Future methods (not yet implemented)
    # ------------------------------------------------------------------
    # async def run_subgoal(self, plan_id, subgoal_id) -> SubGoal: ...
    # async def process_scheduled_update(self, plan_id, schedule_name) -> None: ...
    # async def run_quality_test(self, plan_id) -> dict: ...
    # async def run_horizon_scan(self, plan_id) -> dict: ...
