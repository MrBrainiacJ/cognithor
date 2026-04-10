"""MCP tools for Reddit Lead Hunter — exposes scan, leads, reply to the Planner."""

from __future__ import annotations

import json
from typing import Any

from jarvis.utils.logging import get_logger

log = get_logger(__name__)


def register_reddit_tools(mcp_client: Any, lead_service: Any) -> None:
    """Register Reddit Lead Hunter MCP tools."""

    async def _reddit_scan(
        subreddits: str = "",
        product: str = "",
        min_score: int = 0,
    ) -> str:
        """Scan Reddit for leads. Subreddits as comma-separated string."""
        if lead_service is None:
            return json.dumps({"error": "Reddit Lead Service not initialized"})

        # Allow overriding product from tool call
        if product:
            lead_service._scan_config.product_name = product

        if not lead_service._scan_config.product_name:
            return json.dumps(
                {
                    "error": "Reddit product not configured. Set social.reddit_product_name in config or Flutter UI (Administration > Social).",
                }
            )

        subs = [s.strip() for s in subreddits.split(",") if s.strip()] if subreddits else None
        effective_min = min_score if min_score > 0 else lead_service._scan_config.min_score

        result = await lead_service.scan(
            subreddits=subs,
            min_score=effective_min,
            trigger="chat",
        )

        leads_summary = []
        for lead in lead_service.get_leads(min_score=effective_min, limit=10):
            if lead.scan_id == result.id:
                leads_summary.append(
                    {
                        "score": lead.intent_score,
                        "subreddit": lead.subreddit,
                        "title": lead.title[:80],
                        "url": lead.url,
                        "author": lead.author,
                    }
                )

        return json.dumps(
            {
                "summary": result.summary(),
                "leads_found": result.leads_found,
                "posts_checked": result.posts_checked,
                "leads": leads_summary,
            },
            ensure_ascii=False,
        )

    async def _reddit_leads(
        status: str = "",
        min_score: int = 0,
        limit: int = 20,
    ) -> str:
        """List current Reddit leads with optional filters."""
        if lead_service is None:
            return json.dumps({"error": "Reddit Lead Service not initialized"})

        from jarvis.social.models import LeadStatus

        status_filter = (
            LeadStatus(status) if status and status in LeadStatus.__members__.values() else None
        )
        leads = lead_service.get_leads(status=status_filter, min_score=min_score, limit=limit)

        return json.dumps(
            {
                "count": len(leads),
                "leads": [
                    {
                        "id": l.id,
                        "score": l.intent_score,
                        "subreddit": l.subreddit,
                        "title": l.title[:80],
                        "status": l.status.value if hasattr(l.status, "value") else l.status,
                        "url": l.url,
                        "reply_draft": l.reply_draft[:100] + "..."
                        if len(l.reply_draft) > 100
                        else l.reply_draft,
                    }
                    for l in leads
                ],
            },
            ensure_ascii=False,
        )

    async def _reddit_reply(
        lead_id: str = "",
        mode: str = "clipboard",
    ) -> str:
        """Post a reply to a Reddit lead. Mode: clipboard, browser, or auto."""
        if lead_service is None:
            return json.dumps({"error": "Reddit Lead Service not initialized"})

        if not lead_id:
            return json.dumps({"error": "lead_id is required"})

        result = lead_service.post_reply(lead_id, mode=mode)
        return json.dumps(
            {
                "success": result.success,
                "mode": result.mode.value,
                "error": result.error,
            }
        )

    mcp_client.register_builtin_handler(
        "reddit_scan",
        _reddit_scan,
        description=(
            "Reddit nach Leads scannen. Scannt Subreddits nach Posts mit hohem Intent "
            "und erstellt Reply-Drafts. Kein API-Key noetig (nutzt oeffentliche JSON-Feeds)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "subreddits": {
                    "type": "string",
                    "description": "Kommagetrennte Subreddit-Namen, z.B. 'LocalLLaMA,SaaS'",
                },
                "product": {
                    "type": "string",
                    "description": "Produktname nach dem gesucht wird, z.B. 'Cognithor'",
                },
                "min_score": {
                    "type": "integer",
                    "description": "Minimum Intent-Score 0-100 (Default: 60)",
                    "default": 0,
                },
            },
            "required": ["subreddits", "product"],
        },
    )
    mcp_client.register_builtin_handler(
        "reddit_leads",
        _reddit_leads,
        description="Gespeicherte Reddit-Leads auflisten mit optionalen Filtern.",
        input_schema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter: new, reviewed, replied, archived",
                },
                "min_score": {"type": "integer", "description": "Minimum Score Filter"},
                "limit": {
                    "type": "integer",
                    "description": "Max Ergebnisse (Default: 20)",
                    "default": 20,
                },
            },
        },
    )
    mcp_client.register_builtin_handler(
        "reddit_reply",
        _reddit_reply,
        description="Antwort auf einen Reddit-Lead erstellen. Kopiert in Zwischenablage und oeffnet Browser.",
        input_schema={
            "type": "object",
            "properties": {
                "lead_id": {"type": "string", "description": "Lead-ID zum Antworten"},
                "mode": {
                    "type": "string",
                    "description": "clipboard (Default), browser, oder auto",
                    "default": "clipboard",
                },
            },
            "required": ["lead_id"],
        },
    )

    async def _reddit_refine(lead_id: str = "", hint: str = "", variants: int = 0) -> str:
        if lead_service is None:
            return json.dumps({"error": "Reddit Lead Service not initialized"})
        if not lead_id:
            return json.dumps({"error": "lead_id is required"})
        result = await lead_service.refine_reply(lead_id, hint=hint, variants=variants)
        if result is None:
            return json.dumps({"error": "Lead not found"})
        if isinstance(result, list):
            return json.dumps(
                {"variants": [{"text": r.text, "style": r.style} for r in result]},
                ensure_ascii=False,
            )
        return json.dumps(
            {"text": result.text, "style": result.style, "changes": result.changes_summary},
            ensure_ascii=False,
        )

    async def _reddit_discover_subreddits(
        product_name: str = "", product_description: str = ""
    ) -> str:
        if lead_service is None:
            return json.dumps({"error": "Reddit Lead Service not initialized"})
        from jarvis.social.discovery import SubredditDiscovery

        discovery = SubredditDiscovery(llm_fn=lead_service._scanner._llm_fn)
        name = product_name or lead_service._scan_config.product_name
        desc = product_description or lead_service._scan_config.product_description
        results = await discovery.discover(name, desc)
        discovery.close()
        return json.dumps(
            {
                "suggestions": [
                    {
                        "name": s.name,
                        "subscribers": s.subscribers,
                        "posts_per_day": s.posts_per_day,
                        "relevance_score": s.relevance_score,
                        "reasoning": s.reasoning,
                        "sample_posts": s.sample_posts,
                    }
                    for s in results
                ]
            },
            ensure_ascii=False,
        )

    async def _reddit_templates(
        action: str = "list",
        subreddit: str = "",
        name: str = "",
        text: str = "",
        template_id: str = "",
    ) -> str:
        if lead_service is None:
            return json.dumps({"error": "Reddit Lead Service not initialized"})
        if action == "list":
            return json.dumps(
                {"templates": lead_service.get_templates(subreddit)}, ensure_ascii=False
            )
        elif action == "create":
            tid = lead_service.create_template(name, text, subreddit)
            return json.dumps({"id": tid, "status": "created"})
        elif action == "delete":
            lead_service.delete_template(template_id)
            return json.dumps({"status": "deleted"})
        return json.dumps({"error": f"Unknown action: {action}"})

    mcp_client.register_builtin_handler(
        "reddit_refine",
        _reddit_refine,
        description="Reply-Draft per LLM verbessern. variants>0 erzeugt mehrere Optionen.",
        input_schema={
            "type": "object",
            "properties": {
                "lead_id": {"type": "string", "description": "Lead-ID"},
                "hint": {"type": "string", "description": "Optional: Richtung fuer Verbesserung"},
                "variants": {
                    "type": "integer",
                    "description": "Anzahl Varianten (0=nur verfeinern)",
                    "default": 0,
                },
            },
            "required": ["lead_id"],
        },
    )
    mcp_client.register_builtin_handler(
        "reddit_discover_subreddits",
        _reddit_discover_subreddits,
        description="Relevante Subreddits fuer ein Produkt entdecken via LLM + Reddit-Validierung.",
        input_schema={
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Produktname (Default: Config)",
                },
                "product_description": {
                    "type": "string",
                    "description": "Produktbeschreibung (Default: Config)",
                },
            },
        },
    )
    mcp_client.register_builtin_handler(
        "reddit_templates",
        _reddit_templates,
        description="Reply-Templates verwalten. Aktionen: list, create, delete.",
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "list, create, oder delete"},
                "subreddit": {
                    "type": "string",
                    "description": "Filtern nach Subreddit (list) oder zuweisen (create)",
                },
                "name": {"type": "string", "description": "Template-Name (create)"},
                "text": {"type": "string", "description": "Template-Text (create)"},
                "template_id": {"type": "string", "description": "Template-ID (delete)"},
            },
        },
    )
    log.info("reddit_tools_registered", tools=6)
