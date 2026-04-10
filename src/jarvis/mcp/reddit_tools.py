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
        min_score: int = 0,
    ) -> str:
        """Scan Reddit for leads. Subreddits as comma-separated string."""
        if lead_service is None:
            return json.dumps({"error": "Reddit Lead Service not initialized"})

        if not lead_service._scan_config.product_name:
            return json.dumps(
                {
                    "error": "Reddit product not configured. Set social.reddit_product_name in config or Flutter UI (Administration > Social).",
                }
            )

        subs = [s.strip() for s in subreddits.split(",") if s.strip()] if subreddits else None
        # subs=None → service falls back to default_subreddits from config
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
            "Scan Reddit subreddits for high-intent leads. Returns scored posts with reply drafts."
        ),
        input_schema={
            "subreddits": {
                "type": "string",
                "description": "Comma-separated subreddit names (default: config)",
            },
            "min_score": {
                "type": "integer",
                "description": "Minimum intent score 0-100 (default: config)",
            },
        },
    )
    mcp_client.register_builtin_handler(
        "reddit_leads",
        _reddit_leads,
        description="List current Reddit leads with filters.",
        input_schema={
            "status": {
                "type": "string",
                "description": "Filter: new, reviewed, replied, archived",
            },
            "min_score": {"type": "integer", "description": "Minimum score filter"},
            "limit": {"type": "integer", "description": "Max results (default 20)"},
        },
    )
    mcp_client.register_builtin_handler(
        "reddit_reply",
        _reddit_reply,
        description="Post a reply to a Reddit lead. Copies to clipboard and opens browser.",
        input_schema={
            "lead_id": {"type": "string", "description": "Lead ID to reply to"},
            "mode": {
                "type": "string",
                "description": "clipboard (default), browser, or auto",
            },
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
        description="Refine a reply draft via LLM. Set variants>0 to generate multiple options.",
        input_schema={
            "lead_id": {"type": "string", "description": "Lead ID"},
            "hint": {"type": "string", "description": "Optional: direction for refinement"},
            "variants": {
                "type": "integer",
                "description": "Generate N variants (0=refine only)",
            },
        },
    )
    mcp_client.register_builtin_handler(
        "reddit_discover_subreddits",
        _reddit_discover_subreddits,
        description="Discover relevant subreddits for a product via LLM + Reddit validation.",
        input_schema={
            "product_name": {
                "type": "string",
                "description": "Product name (default: config)",
            },
            "product_description": {
                "type": "string",
                "description": "Product description (default: config)",
            },
        },
    )
    mcp_client.register_builtin_handler(
        "reddit_templates",
        _reddit_templates,
        description="Manage reply templates. Actions: list, create, delete.",
        input_schema={
            "action": {"type": "string", "description": "list, create, or delete"},
            "subreddit": {
                "type": "string",
                "description": "Filter by subreddit (list) or assign (create)",
            },
            "name": {"type": "string", "description": "Template name (create)"},
            "text": {"type": "string", "description": "Template text (create)"},
            "template_id": {"type": "string", "description": "Template ID (delete)"},
        },
    )
    log.info("reddit_tools_registered", tools=6)
