"""REST endpoints for Skill Performance Tracking.

Provides health inspection and manual reset of degraded skills.
Integrates into the FastAPI Control Center on port 8741.
"""

from __future__ import annotations

from typing import Any

from cognithor.utils.logging import get_logger

log = get_logger(__name__)


def create_skill_performance_routes(app: Any, deps: dict[str, Any]) -> None:
    """Register skill-performance endpoints on *app*.

    ``deps`` should contain a ``"performance_tracker"`` key holding
    a :class:`~jarvis.skills.performance_tracker.SkillPerformanceTracker`
    instance.  If the key is missing the routes are still registered but
    will return 503.
    """
    try:
        from fastapi import HTTPException
        from fastapi.responses import JSONResponse
    except ImportError:
        log.warning("fastapi_not_available_for_performance_routes")
        return

    def _get_tracker() -> Any:
        tracker = deps.get("performance_tracker")
        if tracker is None:
            raise HTTPException(status_code=503, detail="Performance tracker not initialised")
        return tracker

    @app.get("/api/v1/skills/health", tags=["skills"])
    async def get_all_skill_health() -> JSONResponse:
        """Return health stats for every tracked skill."""
        tracker = _get_tracker()
        healths = await tracker.get_all_health()
        payload = {}
        for name, h in healths.items():
            payload[name] = {
                "skill_name": h.skill_name,
                "total_executions": h.total_executions,
                "window_executions": h.window_executions,
                "failure_rate": h.failure_rate,
                "avg_score": h.avg_score,
                "avg_duration_ms": h.avg_duration_ms,
                "is_degraded": h.is_degraded,
                "degraded_since": h.degraded_since,
                "cooldown_remaining_seconds": h.cooldown_remaining_seconds,
            }
        return JSONResponse(content=payload)

    @app.post("/api/v1/skills/{name}/reset", tags=["skills"])
    async def reset_skill(name: str) -> JSONResponse:
        """Manually re-enable a degraded skill."""
        tracker = _get_tracker()
        await tracker.reset_skill(name)
        health = await tracker.get_skill_health(name)
        return JSONResponse(
            content={
                "status": "ok",
                "skill_name": health.skill_name,
                "is_degraded": health.is_degraded,
            }
        )
