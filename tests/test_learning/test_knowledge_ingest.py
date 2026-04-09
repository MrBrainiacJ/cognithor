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


# ---------------------------------------------------------------------------
# IngestQueue
# ---------------------------------------------------------------------------


class TestIngestQueue:
    def test_enqueue_dequeue_priority_order(self):
        from jarvis.learning.knowledge_ingest import IngestQueue, _QueueItem

        q = IngestQueue()
        q.enqueue(
            _QueueItem(
                result_id="low1", text="low", source="f1.pdf", priority=Priority.LOW, page_images=[]
            )
        )
        q.enqueue(
            _QueueItem(
                result_id="high1",
                text="high",
                source="f2.pdf",
                priority=Priority.HIGH,
                page_images=[],
            )
        )
        q.enqueue(
            _QueueItem(
                result_id="norm1",
                text="norm",
                source="f3.pdf",
                priority=Priority.NORMAL,
                page_images=[],
            )
        )
        assert not q.empty
        assert q.dequeue().result_id == "high1"
        assert q.dequeue().result_id == "norm1"
        assert q.dequeue().result_id == "low1"
        assert q.empty

    def test_queue_size(self):
        from jarvis.learning.knowledge_ingest import IngestQueue, _QueueItem

        q = IngestQueue()
        assert len(q) == 0
        q.enqueue(
            _QueueItem(
                result_id="x", text="t", source="s", priority=Priority.NORMAL, page_images=[]
            )
        )
        assert len(q) == 1

    def test_pending_returns_sorted_list(self):
        from jarvis.learning.knowledge_ingest import IngestQueue, _QueueItem

        q = IngestQueue()
        q.enqueue(
            _QueueItem(
                result_id="a", text="t", source="s1", priority=Priority.NORMAL, page_images=[]
            )
        )
        q.enqueue(
            _QueueItem(result_id="b", text="t", source="s2", priority=Priority.HIGH, page_images=[])
        )
        pending = q.pending()
        assert len(pending) == 2
        assert pending[0]["id"] == "b"  # HIGH first
        assert pending[0]["priority"] == "HIGH"
        assert pending[1]["id"] == "a"
