"""Autonomous Evolution Engine — self-improving idle-time learning."""

from jarvis.evolution.autonomous_learner import AutonomousLearner
from jarvis.evolution.cron_scheduler import EvolutionScheduler
from jarvis.evolution.deep_learner import DeepLearner
from jarvis.evolution.goal_index import GoalScopedIndex
from jarvis.evolution.idle_detector import IdleDetector
from jarvis.evolution.loop import EvolutionLoop
from jarvis.evolution.meta_learner import MetaLearner
from jarvis.evolution.models import LearningPlan, SubGoal
from jarvis.evolution.rag_pipeline import EvolutionRAG
from jarvis.evolution.resume import EvolutionResumer, ResumeState
from jarvis.evolution.strategy_planner import StrategyPlanner

__all__ = [
    "AutonomousLearner",
    "DeepLearner",
    "EvolutionLoop",
    "EvolutionRAG",
    "EvolutionResumer",
    "EvolutionScheduler",
    "GoalScopedIndex",
    "IdleDetector",
    "LearningPlan",
    "MetaLearner",
    "ResumeState",
    "StrategyPlanner",
    "SubGoal",
]
