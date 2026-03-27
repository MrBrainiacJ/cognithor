"""Tests for Evolution Engine — IdleDetector + EvolutionLoop."""

import asyncio
import time

import pytest


class TestIdleDetector:
    def test_not_idle_initially(self):
        from jarvis.evolution.idle_detector import IdleDetector

        d = IdleDetector(idle_threshold_seconds=5)
        assert d.is_idle is False

    def test_idle_after_threshold(self):
        from jarvis.evolution.idle_detector import IdleDetector

        d = IdleDetector(idle_threshold_seconds=0)
        # Threshold 0 = immediately idle
        assert d.is_idle is True

    def test_activity_resets_idle(self):
        from jarvis.evolution.idle_detector import IdleDetector

        d = IdleDetector(idle_threshold_seconds=0)
        d._last_activity = time.time() - 100  # Force old
        assert d.is_idle is True
        d.notify_activity()
        # After activity with threshold 0, need to wait
        # But with very small threshold it should flip back quickly
        assert d.idle_seconds < 1

    def test_idle_seconds(self):
        from jarvis.evolution.idle_detector import IdleDetector

        d = IdleDetector(idle_threshold_seconds=10)
        d._last_activity = time.time() - 30
        assert d.idle_seconds >= 29


class TestEvolutionLoop:
    @pytest.fixture
    def idle_detector(self):
        from jarvis.evolution.idle_detector import IdleDetector

        d = IdleDetector(idle_threshold_seconds=0)
        d._last_activity = time.time() - 100  # Force idle
        return d

    @pytest.fixture
    def loop(self, idle_detector):
        from jarvis.evolution.loop import EvolutionLoop

        return EvolutionLoop(idle_detector=idle_detector)

    @pytest.mark.asyncio
    async def test_cycle_skips_when_not_idle(self):
        from jarvis.evolution.idle_detector import IdleDetector
        from jarvis.evolution.loop import EvolutionLoop

        d = IdleDetector(idle_threshold_seconds=9999)
        loop = EvolutionLoop(idle_detector=d)
        result = await loop.run_cycle()
        assert result.skipped is True
        assert result.reason == "not_idle"

    @pytest.mark.asyncio
    async def test_cycle_runs_when_idle(self, loop):
        result = await loop.run_cycle()
        # Without curiosity engine, should skip with no_gaps
        assert result.skipped is True
        assert result.reason == "no_gaps"
        assert "scout" in result.steps_completed

    @pytest.mark.asyncio
    async def test_daily_limit(self, loop):
        import time

        loop._cycles_today = 100
        loop._last_cycle_day = time.strftime("%Y-%m-%d")
        assert loop._can_run_cycle() is False

    def test_stats(self, loop):
        stats = loop.stats()
        assert "running" in stats
        assert "total_cycles" in stats
        assert "is_idle" in stats

    @pytest.mark.asyncio
    async def test_start_stop(self, loop):
        await loop.start()
        assert loop._running is True
        loop.stop()
        assert loop._running is False
        await asyncio.sleep(0.1)  # Let cancellation propagate
