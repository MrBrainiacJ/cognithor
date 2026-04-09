"""Tests for Priority enum and IngestResult fields in knowledge_ingest.py."""

from __future__ import annotations

from jarvis.learning.knowledge_ingest import IngestResult, Priority

# ---------------------------------------------------------------------------
# Priority enum
# ---------------------------------------------------------------------------


class TestPriorityEnum:
    def test_ordering_high_less_than_normal(self):
        assert Priority.HIGH < Priority.NORMAL

    def test_ordering_normal_less_than_low(self):
        assert Priority.NORMAL < Priority.LOW

    def test_ordering_high_less_than_low(self):
        assert Priority.HIGH < Priority.LOW

    def test_int_values(self):
        assert int(Priority.HIGH) == 0
        assert int(Priority.NORMAL) == 1
        assert int(Priority.LOW) == 2

    def test_from_string_high(self):
        assert Priority.from_string("high") == Priority.HIGH

    def test_from_string_normal(self):
        assert Priority.from_string("normal") == Priority.NORMAL

    def test_from_string_low(self):
        assert Priority.from_string("low") == Priority.LOW

    def test_from_string_uppercase(self):
        assert Priority.from_string("HIGH") == Priority.HIGH

    def test_from_string_mixed_case(self):
        assert Priority.from_string("Normal") == Priority.NORMAL

    def test_from_string_invalid_returns_normal(self):
        assert Priority.from_string("bogus") == Priority.NORMAL

    def test_from_string_empty_returns_normal(self):
        assert Priority.from_string("") == Priority.NORMAL


# ---------------------------------------------------------------------------
# IngestResult dataclass
# ---------------------------------------------------------------------------


class TestIngestResult:
    def _make(self, **kwargs) -> IngestResult:
        defaults = dict(id="test-id", source_type="file", source_name="test.txt", status="success")
        defaults.update(kwargs)
        return IngestResult(**defaults)

    def test_default_priority_is_normal(self):
        result = self._make()
        assert result.priority == Priority.NORMAL

    def test_explicit_priority_high(self):
        result = self._make(priority=Priority.HIGH)
        assert result.priority == Priority.HIGH

    def test_explicit_priority_low(self):
        result = self._make(priority=Priority.LOW)
        assert result.priority == Priority.LOW

    def test_chunks_alias_returns_chunks_created(self):
        result = self._make(chunks_created=42)
        assert result.chunks == 42

    def test_chunks_alias_zero(self):
        result = self._make(chunks_created=0)
        assert result.chunks == 0

    def test_chunks_alias_mirrors_chunks_created(self):
        result = self._make(chunks_created=7)
        result.chunks_created = 99
        assert result.chunks == 99

    def test_deep_learn_status_default_is_pending(self):
        result = self._make()
        assert result.deep_learn_status == "pending"

    def test_deep_learn_status_can_be_set(self):
        for status in ("queued", "skipped", "completed", "failed"):
            result = self._make(deep_learn_status=status)
            assert result.deep_learn_status == status
