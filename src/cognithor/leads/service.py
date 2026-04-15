"""Source-agnostic lead service — orchestrates scan, persist, query.

Replaces the Reddit-only ``RedditLeadService``. All lead sources (Reddit,
HN, Discord, RSS, future Twitter/LinkedIn/…) register with the internal
``SourceRegistry`` and the service delegates scan calls by ``source_id``.

Called from:

- Gateway REST routes (``POST /api/v1/leads/scan``, ``GET /api/v1/leads``).
- Cron jobs (``cognithor.leads.sdk.LeadService.scan()``).
- CLI commands (``cognithor leads scan``).
- MCP tools registered by packs.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from cognithor.leads.models import LeadStats, LeadStatus, ScanResult
from cognithor.leads.registry import SourceRegistry
from cognithor.utils.logging import get_logger

if TYPE_CHECKING:
    from cognithor.leads.models import Lead
    from cognithor.leads.source import LeadSource
    from cognithor.leads.store import LeadStore

log = get_logger(__name__)


class LeadService:
    def __init__(
        self,
        store: LeadStore,
        llm_fn: Any | None = None,
    ) -> None:
        self._store = store
        self._llm_fn = llm_fn
        self._registry = SourceRegistry()

    # ---------- source registration ----------

    def register_source(self, source: LeadSource) -> None:
        log.info("lead_source_registered", source_id=source.source_id)
        self._registry.register(source)

    def unregister_source(self, source_id: str) -> None:
        log.info("lead_source_unregistered", source_id=source_id)
        self._registry.unregister(source_id)

    def list_sources(self) -> list[LeadSource]:
        return self._registry.list()

    def get_source(self, source_id: str) -> LeadSource | None:
        return self._registry.get(source_id)

    # ---------- scanning ----------

    async def scan(
        self,
        *,
        source_id: str | None = None,
        min_score: int = 60,
        product: str = "",
        product_description: str = "",
        trigger: str = "cli",
        config: dict[str, Any] | None = None,
    ) -> ScanResult:
        """Run a scan on one source (by id) or all registered sources.

        Returns an aggregated ``ScanResult`` with counts across all scanned
        sources. Individual per-source errors are logged and do not abort
        the overall scan when ``source_id`` is None.
        """
        result = ScanResult(trigger=trigger)
        cfg = config or {}

        targets: list[LeadSource]
        if source_id is not None:
            src = self._registry.get(source_id)
            if src is None:
                raise ValueError(f"unknown source {source_id!r}")
            targets = [src]
        else:
            targets = self._registry.list()

        for source in targets:
            try:
                scanned_leads = await source.scan(
                    config=cfg.get(source.source_id, {}),
                    product=product,
                    product_description=product_description,
                    min_score=min_score,
                )
            except Exception as exc:
                log.warning(
                    "source_scan_failed",
                    source_id=source.source_id,
                    error=str(exc),
                    exc_info=True,
                )
                continue

            for lead in scanned_leads:
                result.posts_checked += 1

                if self._store.already_seen(lead.post_id):
                    result.posts_skipped_duplicate += 1
                    continue

                if lead.intent_score < min_score:
                    result.posts_skipped_low_score += 1
                    continue

                lead.scan_id = result.id
                self._store.save_lead(lead)
                result.leads_found += 1

        result.finished_at = time.time()
        log.info("scan_complete", summary=result.summary(), trigger=trigger)
        return result

    # ---------- queries ----------

    def get_leads(
        self,
        status: LeadStatus | str | None = None,
        min_score: int = 0,
        limit: int = 50,
        offset: int = 0,
        source_id: str | None = None,
    ) -> list[Lead]:
        return self._store.get_leads(
            status=status,
            min_score=min_score,
            limit=limit,
            offset=offset,
            source_id=source_id,
        )

    def get_stats(self) -> LeadStats:
        return self._store.get_stats()
