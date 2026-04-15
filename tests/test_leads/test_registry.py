"""Tests for cognithor.leads.registry — SourceRegistry."""

from __future__ import annotations

from typing import Any

import pytest

from cognithor.leads.models import Lead
from cognithor.leads.registry import SourceRegistry
from cognithor.leads.source import LeadSource


def _make_source(source_id: str) -> LeadSource:
    """Create a concrete LeadSource subclass with the given id for registry tests."""

    class _Concrete(LeadSource):
        pass

    _Concrete.source_id = source_id
    _Concrete.display_name = source_id.upper()
    _Concrete.icon = "forum"
    _Concrete.color = "#123456"
    _Concrete.capabilities = frozenset({"scan"})

    async def _scan(
        self,
        *,
        config: dict[str, Any],
        product: str,
        product_description: str,
        min_score: int,
    ) -> list[Lead]:
        return []

    _Concrete.scan = _scan  # type: ignore[assignment]
    return _Concrete()


class TestSourceRegistry:
    def test_register_and_list(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source("reddit"))
        reg.register(_make_source("hn"))
        ids = {s.source_id for s in reg.list()}
        assert ids == {"reddit", "hn"}

    def test_get_by_id(self) -> None:
        reg = SourceRegistry()
        src = _make_source("rss")
        reg.register(src)
        assert reg.get("rss") is src
        assert reg.get("nonexistent") is None

    def test_register_duplicate_raises(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source("reddit"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_make_source("reddit"))

    def test_unregister(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source("reddit"))
        reg.unregister("reddit")
        assert reg.get("reddit") is None
        assert reg.list() == []

    def test_unregister_nonexistent_is_noop(self) -> None:
        reg = SourceRegistry()
        reg.unregister("nothing")  # must not raise

    def test_contains(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source("hn"))
        assert "hn" in reg
        assert "reddit" not in reg

    def test_len(self) -> None:
        reg = SourceRegistry()
        assert len(reg) == 0
        reg.register(_make_source("a"))
        reg.register(_make_source("b"))
        assert len(reg) == 2
        reg.unregister("a")
        assert len(reg) == 1
