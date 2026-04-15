"""Abstract base class for lead sources.

A ``LeadSource`` represents one origin for leads (Reddit, Hacker News,
Discord, RSS, etc.). Source implementations live in agent packs and
register with the ``SourceRegistry`` via ``PackContext.leads.register_source``
during ``AgentPack.register()``.

Required metadata (ClassVars on concrete subclasses):

- ``source_id`` — stable short identifier, used as a key in the registry and
  persisted on every ``Lead`` record. Must be unique across all registered
  sources.
- ``display_name`` — human-friendly name for UI.
- ``icon`` — Material icon name (e.g. ``"forum"``, ``"rss_feed"``) OR data URL.
- ``color`` — hex color string for UI accents (e.g. ``"#FF4500"`` for Reddit).
- ``capabilities`` — frozen set of capability strings. Known values:
  ``"scan"`` (always required), ``"draft_reply"``, ``"refine_reply"``,
  ``"auto_post"``, ``"discover_targets"``.

Required methods:

- ``scan(config, product, product_description, min_score)`` — fetch posts from
  the source, score them via LLM, return ``list[Lead]``.

Optional methods (default to ``NotImplementedError``; callers check
``capabilities`` before invoking):

- ``draft_reply(lead, tone)`` — generate a reply draft for a lead.
- ``refine_reply(lead, draft)`` — refine an existing reply draft.
- ``post_reply(lead, text)`` — actually post the reply (e.g. via browser
  automation).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from cognithor.leads.models import Lead


class LeadSource(ABC):
    """Abstract lead source — one per origin (Reddit, HN, Discord, RSS, ...)."""

    source_id: ClassVar[str]
    display_name: ClassVar[str]
    icon: ClassVar[str]
    color: ClassVar[str]
    capabilities: ClassVar[frozenset[str]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # ``__abstractmethods__`` is set by ABCMeta *after* __init_subclass__
        # returns, so we cannot rely on it here to detect abstract subclasses.
        # Instead, check whether ``scan`` is still the abstract base version
        # (i.e. not overridden in any class between LeadSource and cls).
        # A subclass is "abstract" (not yet concrete) if it hasn't provided its
        # own ``scan`` implementation anywhere in the MRO above LeadSource.
        scan_impl = cls.__dict__.get("scan")
        if scan_impl is None:
            # Not in cls.__dict__ — check parent chain excluding LeadSource
            for base in cls.__mro__[1:]:
                if base is LeadSource:
                    break
                if "scan" in base.__dict__:
                    scan_impl = base.__dict__["scan"]
                    break
        if scan_impl is None:
            # No concrete scan found — subclass is still abstract; skip validation.
            return
        required = ("source_id", "display_name", "icon", "color", "capabilities")
        for attr in required:
            if not hasattr(cls, attr) or getattr(cls, attr) is None:
                raise TypeError(f"LeadSource subclass {cls.__name__} must set class attr {attr!r}")

    def __new__(cls, *args: Any, **kwargs: Any) -> "LeadSource":
        # Allow instantiation when ``scan`` has been monkey-patched onto the
        # class as a plain attribute after class-body execution (e.g. in test
        # helpers). ``__abstractmethods__`` is computed at class-creation time
        # and is not updated on later attribute assignment, so we reconcile it
        # here at instantiation time.
        # Only do this for concrete subclasses — not LeadSource itself.
        if cls is not LeadSource:
            abstract = frozenset(getattr(cls, "__abstractmethods__", ()) or ())
            if "scan" in abstract and "scan" in cls.__dict__:
                cls.__abstractmethods__ = abstract - {"scan"}
        return super().__new__(cls)

    @abstractmethod
    async def scan(
        self,
        *,
        config: dict[str, Any],
        product: str,
        product_description: str,
        min_score: int,
    ) -> list[Lead]:
        """Fetch, score, and return leads from this source.

        ``config`` is the source-specific config dict (e.g. for Reddit it
        contains ``subreddits``, ``reply_tone``, etc.). ``product`` and
        ``product_description`` drive LLM scoring. ``min_score`` filters
        out low-intent posts.
        """

    async def draft_reply(self, lead: Lead, *, tone: str) -> str:
        """Generate a reply draft. Default: raises ``NotImplementedError``."""
        raise NotImplementedError(
            f"{self.source_id}: draft_reply not implemented (capability not declared)"
        )

    async def refine_reply(self, lead: Lead, draft: str) -> str:
        """Refine an existing draft. Default: raises ``NotImplementedError``."""
        raise NotImplementedError(f"{self.source_id}: refine_reply not implemented")

    async def post_reply(self, lead: Lead, text: str) -> None:
        """Post a reply to the external platform. Default: raises ``NotImplementedError``."""
        raise NotImplementedError(f"{self.source_id}: post_reply not implemented")
