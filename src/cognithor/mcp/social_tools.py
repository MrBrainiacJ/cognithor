"""Unified MCP tools for cross-platform social listening."""

from __future__ import annotations

import json
from typing import Any

from cognithor.utils.logging import get_logger

log = get_logger(__name__)


def register_social_tools(mcp_client: Any, lead_service: Any) -> None:
    """Register social_scan and social_leads MCP tools."""

    async def _social_scan(
        platform: str = "",
        product: str = "",
        subreddits: str = "",
        categories: str = "",
        channel_ids: str = "",
        min_score: int = 0,
    ) -> str:
        """Scan social platforms for leads. platform: reddit|hackernews|discord|'' (all enabled)"""
        if lead_service is None:
            return json.dumps({"error": "Social listening not initialized"})

        results: dict[str, Any] = {}
        _product = product or lead_service._scan_config.product_name

        if platform in ("", "reddit"):
            try:
                subs = (
                    [s.strip() for s in subreddits.split(",") if s.strip()] if subreddits else None
                )
                r = await lead_service.scan(subreddits=subs, min_score=min_score or 60)
                results["reddit"] = {
                    "leads_found": r.leads_found,
                    "posts_checked": r.posts_checked,
                }
            except Exception as e:
                results["reddit"] = {"error": str(e)}

        if platform in ("", "hackernews"):
            hn = getattr(lead_service, "_hn_scanner", None)
            if hn:
                try:
                    cats = (
                        [c.strip() for c in categories.split(",") if c.strip()]
                        if categories
                        else None
                    )
                    r = await lead_service.scan_hackernews(
                        categories=cats, min_score=min_score or 60
                    )
                    results["hackernews"] = r
                except Exception as e:
                    results["hackernews"] = {"error": str(e)}

        if platform in ("", "discord"):
            dc = getattr(lead_service, "_discord_scanner", None)
            if dc:
                try:
                    cids = (
                        [c.strip() for c in channel_ids.split(",") if c.strip()]
                        if channel_ids
                        else None
                    )
                    r = await lead_service.scan_discord(channel_ids=cids, min_score=min_score or 60)
                    results["discord"] = r
                except Exception as e:
                    results["discord"] = {"error": str(e)}

        return json.dumps(results, ensure_ascii=False)

    async def _social_leads(
        platform: str = "",
        status: str = "",
        min_score: int = 0,
        limit: int = 20,
    ) -> str:
        """List leads from all platforms with optional filters."""
        if lead_service is None:
            return json.dumps({"error": "Social listening not initialized"})
        leads = lead_service.get_leads(
            platform=platform or None,
            status=status or None,
            min_score=min_score,
            limit=limit,
        )
        return json.dumps(
            {
                "count": len(leads),
                "leads": [
                    {
                        "id": l.id,
                        "platform": l.platform,
                        "score": l.intent_score,
                        "title": l.title[:80],
                        "status": l.status.value if hasattr(l.status, "value") else l.status,
                        "url": l.platform_url or l.url,
                    }
                    for l in leads
                ],
            },
            ensure_ascii=False,
        )

    # Register with proper JSON Schema
    mcp_client.register_builtin_handler(
        "social_scan",
        _social_scan,
        description="Scanne soziale Plattformen nach Leads (Reddit, Hacker News, Discord)",
        input_schema={
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "reddit, hackernews, discord, oder leer fuer alle",
                },
                "product": {"type": "string", "description": "Produktname"},
                "subreddits": {
                    "type": "string",
                    "description": "Reddit: kommagetrennte Subreddit-Namen",
                },
                "categories": {
                    "type": "string",
                    "description": "HN: top,new,best",
                },
                "channel_ids": {
                    "type": "string",
                    "description": "Discord: kommagetrennte Channel-IDs",
                },
                "min_score": {
                    "type": "integer",
                    "description": "Minimum Score 0-100",
                },
            },
        },
    )

    mcp_client.register_builtin_handler(
        "social_leads",
        _social_leads,
        description="Leads von allen Plattformen auflisten mit optionalen Filtern",
        input_schema={
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "Filter: reddit, hackernews, discord",
                },
                "status": {
                    "type": "string",
                    "description": "Filter: new, reviewed, replied, archived",
                },
                "min_score": {
                    "type": "integer",
                    "description": "Minimum Score",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max Ergebnisse (Default: 20)",
                },
            },
        },
    )
    log.info("social_tools_registered", tools=2)
