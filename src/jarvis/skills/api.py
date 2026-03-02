"""REST API fuer den Skill Marketplace.

Endpoints fuer Browse, Search, Install, Publish und Reviews.
Integriert sich in den FastAPI Control Center auf Port 8741
als APIRouter unter ``/api/v1/skills``.

Architektur-Bibel: SS14 (Skills & Ecosystem)
"""

import sqlite3
from pathlib import Path
from typing import Any, Optional

from jarvis.utils.logging import get_logger

log = get_logger(__name__)

# Lazy-initialisierter Store -- wird beim ersten Request erzeugt.
_store_holder: dict[str, Any] = {"store": None}


def _get_store() -> Any:
    """Gibt den globalen MarketplaceStore zurueck (Lazy-Init)."""
    if _store_holder["store"] is None:
        from jarvis.skills.persistence import MarketplaceStore

        # Pfad aus Config lesen, Fallback auf Standard
        try:
            from jarvis.config import load_config
            cfg = load_config()
            db_path = getattr(cfg, "marketplace", None)
            if db_path and hasattr(db_path, "db_path") and db_path.db_path:
                store_path = Path(db_path.db_path)
            else:
                store_path = cfg.jarvis_home / "marketplace.db"
        except Exception:
            store_path = Path.home() / ".jarvis" / "marketplace.db"

        _store_holder["store"] = MarketplaceStore(store_path)
    return _store_holder["store"]


def set_store(store: Any) -> None:
    """Setzt den Store manuell (fuer Tests)."""
    _store_holder["store"] = store


# ------------------------------------------------------------------
# Request/Response Models (module-level fuer FastAPI-Kompatibilitaet)
# ------------------------------------------------------------------

try:
    from pydantic import BaseModel as _BaseModel

    class ReviewRequest(_BaseModel):
        """Payload fuer eine Review-Einreichung."""
        rating: int
        comment: str = ""
        reviewer_id: str = "anonymous"

    class InstallRequest(_BaseModel):
        """Payload fuer eine Installation."""
        user_id: str = "default"
        version: str = ""

except ImportError:
    ReviewRequest = None  # type: ignore[assignment,misc]
    InstallRequest = None  # type: ignore[assignment,misc]


def _build_router() -> Any:
    """Erstellt den FastAPI APIRouter mit allen Marketplace-Endpoints."""
    try:
        from fastapi import APIRouter, HTTPException, Query
    except ImportError:
        # FastAPI nicht installiert -- leerer Platzhalter
        log.warning("fastapi_not_available_for_skills_api")
        return None

    router = APIRouter(prefix="/api/v1/skills", tags=["skills"])

    # ------------------------------------------------------------------
    # Search & Browse
    # ------------------------------------------------------------------

    @router.get("/search")
    async def search_skills(
        query: str = "",
        category: str = "",
        sort: str = "relevance",
        min_rating: float = 0.0,
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict:
        """Durchsucht den Skill-Marketplace.

        Query-Parameter:
          - query: Volltextsuche
          - category: Kategorie-Filter
          - sort: relevance | newest | rating | installs | popularity
          - min_rating: Mindestbewertung (0.0 - 5.0)
          - limit: Max Ergebnisse (1-100)
        """
        store = _get_store()
        results = store.search_listings(
            query=query, category=category,
            min_rating=min_rating, sort=sort, limit=limit,
        )
        return {"results": results, "count": len(results)}

    @router.get("/featured")
    async def get_featured(
        limit: int = Query(default=10, ge=1, le=50),
    ) -> dict:
        """Kuratierte Featured-Skills."""
        store = _get_store()
        return {"featured": store.get_featured(limit=limit)}

    @router.get("/trending")
    async def get_trending(
        days: int = Query(default=7, ge=1, le=90),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> dict:
        """Trending-Skills der letzten N Tage."""
        store = _get_store()
        return {"trending": store.get_trending(days=days, limit=limit)}

    @router.get("/categories")
    async def get_categories() -> dict:
        """Alle verfuegbaren Kategorien mit Metadaten."""
        from jarvis.skills.marketplace import CATEGORY_INFOS
        categories = []
        for cat, info in CATEGORY_INFOS.items():
            categories.append({
                "value": cat.value,
                "display_name": info.display_name,
                "icon": info.icon,
                "description": info.description,
            })
        return {"categories": categories}

    @router.get("/installed")
    async def list_installed(
        user_id: str = "default",
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict:
        """Liste der installierten Skills eines Users."""
        store = _get_store()
        history = store.get_install_history(user_id=user_id, limit=limit)
        return {"installed": history, "count": len(history)}

    @router.get("/stats")
    async def get_marketplace_stats() -> dict:
        """Aggregierte Marketplace-Statistiken."""
        store = _get_store()
        return store.get_stats()

    # ------------------------------------------------------------------
    # Skill Detail
    # ------------------------------------------------------------------

    @router.get("/{package_id}")
    async def get_skill_detail(package_id: str) -> dict:
        """Detail-Ansicht eines einzelnen Skills."""
        store = _get_store()
        listing = store.get_listing(package_id)
        if listing is None:
            raise HTTPException(status_code=404, detail="Skill nicht gefunden")
        return listing

    # ------------------------------------------------------------------
    # Install / Uninstall
    # ------------------------------------------------------------------

    @router.post("/{package_id}/install")
    async def install_skill(
        package_id: str, body: Optional[InstallRequest] = None,
    ) -> dict:
        """Installiert einen Skill (zeichnet Installation auf)."""
        store = _get_store()
        listing = store.get_listing(package_id)
        if listing is None:
            raise HTTPException(status_code=404, detail="Skill nicht gefunden")

        user_id = body.user_id if body else "default"
        version = body.version if body else listing.get("version", "")

        store.increment_install_count(package_id)
        store.record_install(
            package_id=package_id, version=version, user_id=user_id,
        )
        log.info(
            "skill_installed",
            package_id=package_id, user_id=user_id, version=version,
        )
        return {"status": "installed", "package_id": package_id}

    @router.delete("/{package_id}")
    async def uninstall_skill(package_id: str) -> dict:
        """Deinstalliert einen Skill (markiert als recalled)."""
        store = _get_store()
        listing = store.get_listing(package_id)
        if listing is None:
            raise HTTPException(status_code=404, detail="Skill nicht gefunden")
        # Recall-Mechanismus fuer Uninstall
        store.recall_listing(package_id, reason="user_uninstall")
        return {"status": "uninstalled", "package_id": package_id}

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    @router.get("/{package_id}/reviews")
    async def get_reviews(
        package_id: str,
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict:
        """Reviews fuer einen Skill."""
        store = _get_store()
        reviews = store.get_reviews(package_id, limit=limit)
        avg = store.get_average_rating(package_id)
        return {"reviews": reviews, "count": len(reviews), "average_rating": avg}

    @router.post("/{package_id}/reviews")
    async def submit_review(
        package_id: str, body: ReviewRequest,
    ) -> dict:
        """Review fuer einen Skill einreichen."""
        store = _get_store()
        listing = store.get_listing(package_id)
        if listing is None:
            raise HTTPException(status_code=404, detail="Skill nicht gefunden")

        try:
            review_id = store.save_review(
                package_id=package_id,
                reviewer_id=body.reviewer_id,
                rating=body.rating,
                comment=body.comment,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=409,
                detail="Du hast diesen Skill bereits bewertet",
            )

        return {
            "status": "created",
            "review_id": review_id,
            "package_id": package_id,
        }

    return router


# Erstelle den Router beim Import (None falls FastAPI fehlt)
router = _build_router()
