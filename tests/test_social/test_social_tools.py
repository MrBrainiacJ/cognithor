"""Tests for mcp.social_tools — unified social_scan and social_leads."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

import pytest

from cognithor.mcp.social_tools import register_social_tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeScanResult:
    leads_found: int = 2
    posts_checked: int = 10
    id: str = "scan-1"

    def summary(self) -> str:
        return f"{self.leads_found}/{self.posts_checked}"


@dataclass
class _FakeLead:
    id: str = "lead-1"
    platform: str = "reddit"
    intent_score: int = 85
    title: str = "Need an AI assistant"
    status: str = "new"
    url: str = "https://reddit.com/r/test/1"
    platform_url: str = ""


class _FakeMCPClient:
    def __init__(self) -> None:
        self.handlers: dict[str, Any] = {}

    def register_builtin_handler(self, name, fn, **kwargs) -> None:
        self.handlers[name] = fn


def _make_service(
    *,
    has_hn: bool = False,
    has_discord: bool = False,
    leads: list | None = None,
) -> MagicMock:
    svc = MagicMock()
    svc._scan_config = MagicMock()
    svc._scan_config.product_name = "Cognithor"
    svc._scan_config.product_description = "AI assistant"
    svc.scan = AsyncMock(return_value=_FakeScanResult())
    svc.scan_hackernews = AsyncMock(return_value={"leads_found": 1, "posts_checked": 5})
    svc.scan_discord = AsyncMock(return_value={"leads_found": 3, "posts_checked": 8})
    svc.get_leads = MagicMock(return_value=leads if leads is not None else [])

    if has_hn:
        svc._hn_scanner = MagicMock()
    else:
        svc._hn_scanner = None

    if has_discord:
        svc._discord_scanner = MagicMock()
    else:
        svc._discord_scanner = None

    return svc


from typing import Any


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSocialScan:
    @pytest.mark.asyncio
    async def test_social_scan_reddit(self):
        """platform='reddit' only calls reddit scan."""
        svc = _make_service(has_hn=True, has_discord=True)
        client = _FakeMCPClient()
        register_social_tools(client, svc)

        handler = client.handlers["social_scan"]
        raw = await handler(platform="reddit", subreddits="LocalLLaMA,SaaS")
        data = json.loads(raw)

        assert "reddit" in data
        assert data["reddit"]["leads_found"] == 2
        assert "hackernews" not in data
        assert "discord" not in data
        svc.scan.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_social_scan_hackernews(self):
        """platform='hackernews' calls hn scanner."""
        svc = _make_service(has_hn=True)
        client = _FakeMCPClient()
        register_social_tools(client, svc)

        handler = client.handlers["social_scan"]
        raw = await handler(platform="hackernews", categories="top,new")
        data = json.loads(raw)

        assert "hackernews" in data
        assert data["hackernews"]["leads_found"] == 1
        assert "reddit" not in data
        svc.scan_hackernews.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_social_scan_discord(self):
        """platform='discord' calls discord scanner."""
        svc = _make_service(has_discord=True)
        client = _FakeMCPClient()
        register_social_tools(client, svc)

        handler = client.handlers["social_scan"]
        raw = await handler(platform="discord", channel_ids="123,456")
        data = json.loads(raw)

        assert "discord" in data
        assert data["discord"]["leads_found"] == 3
        assert "reddit" not in data
        svc.scan_discord.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_social_scan_all(self):
        """Empty platform scans all enabled platforms."""
        svc = _make_service(has_hn=True, has_discord=True)
        client = _FakeMCPClient()
        register_social_tools(client, svc)

        handler = client.handlers["social_scan"]
        raw = await handler(platform="")
        data = json.loads(raw)

        assert "reddit" in data
        assert "hackernews" in data
        assert "discord" in data

    @pytest.mark.asyncio
    async def test_social_scan_none_service(self):
        """Returns error when service is None."""
        client = _FakeMCPClient()
        register_social_tools(client, None)

        handler = client.handlers["social_scan"]
        raw = await handler()
        data = json.loads(raw)
        assert "error" in data


class TestSocialLeads:
    @pytest.mark.asyncio
    async def test_social_leads_with_filter(self):
        """platform filter returns correct leads."""
        leads = [
            _FakeLead(id="l1", platform="hackernews", title="HN post"),
        ]
        svc = _make_service(leads=leads)
        client = _FakeMCPClient()
        register_social_tools(client, svc)

        handler = client.handlers["social_leads"]
        raw = await handler(platform="hackernews")
        data = json.loads(raw)

        assert data["count"] == 1
        assert data["leads"][0]["platform"] == "hackernews"
        svc.get_leads.assert_called_once_with(
            platform="hackernews", status=None, min_score=0, limit=20
        )

    @pytest.mark.asyncio
    async def test_social_leads_all(self):
        """Empty platform returns all leads."""
        leads = [
            _FakeLead(id="l1", platform="reddit"),
            _FakeLead(id="l2", platform="hackernews"),
            _FakeLead(id="l3", platform="discord"),
        ]
        svc = _make_service(leads=leads)
        client = _FakeMCPClient()
        register_social_tools(client, svc)

        handler = client.handlers["social_leads"]
        raw = await handler()
        data = json.loads(raw)

        assert data["count"] == 3
        svc.get_leads.assert_called_once_with(platform=None, status=None, min_score=0, limit=20)

    @pytest.mark.asyncio
    async def test_social_leads_none_service(self):
        """Returns error when service is None."""
        client = _FakeMCPClient()
        register_social_tools(client, None)

        handler = client.handlers["social_leads"]
        raw = await handler()
        data = json.loads(raw)
        assert "error" in data


class TestRegistration:
    def test_registers_both_tools(self):
        """Both social_scan and social_leads are registered."""
        client = _FakeMCPClient()
        svc = _make_service()
        register_social_tools(client, svc)
        assert "social_scan" in client.handlers
        assert "social_leads" in client.handlers
