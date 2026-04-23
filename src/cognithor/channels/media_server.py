"""MediaUploadServer — local HTTP file-server for vLLM to fetch user uploads.

vLLM inside the Cognithor-managed Docker container reaches this server via
``http://host.docker.internal:<port>/media/<uuid>.<ext>``. The server binds
only on ``127.0.0.1``, so only processes on the host machine can reach it.

This file contains the storage + quota logic. The FastAPI app + port binding
live in companion methods `start()` / `stop()` added in Task 7.
"""

from __future__ import annotations

import contextlib
import uuid as _uuid
from typing import TYPE_CHECKING

from cognithor.core.llm_backend import (
    MediaUploadQuotaExceededError,
    MediaUploadTooLargeError,
    MediaUploadUnsupportedFormatError,
)
from cognithor.utils.logging import get_logger

if TYPE_CHECKING:
    from cognithor.config import CognithorConfig

log = get_logger(__name__)

_ALLOWED_EXTS = frozenset({"mp4", "webm", "mov", "mkv", "avi"})


class MediaUploadServer:
    """Local-loopback static file server for vLLM media fetches.

    Lifecycle: instantiate with the live CognithorConfig, call ``await start()``
    to bind the ephemeral port (returns the port number), ``await stop()`` at
    shutdown. In between, call ``save_upload(data, ext) -> uuid`` to store
    bytes and ``public_url(uuid, ext) -> str`` to get the URL vLLM should fetch.
    """

    def __init__(self, config: CognithorConfig) -> None:
        self._config = config
        self._media_dir = config.cognithor_home / "media" / "vllm-uploads"
        self._media_dir.mkdir(parents=True, exist_ok=True)
        self._max_per_file_bytes = config.vllm.video_max_upload_mb * 1024 * 1024
        self._quota_bytes = config.vllm.video_quota_gb * 1024 * 1024 * 1024
        self._port: int | None = None
        self._server = None  # filled by start() in Task 7

    def save_upload(self, data: bytes, ext: str) -> str:
        """Store ``data`` under ``<uuid>.<ext>`` in the media dir, return uuid.

        Raises MediaUploadTooLargeError / MediaUploadUnsupportedFormatError /
        MediaUploadQuotaExceededError on the respective failure modes. LRU-
        evicts older files if the new upload would push total size over quota.
        """
        ext_lower = ext.lower().lstrip(".")
        if ext_lower not in _ALLOWED_EXTS:
            raise MediaUploadUnsupportedFormatError(
                f"Unsupported extension: {ext!r}. Allowed: {sorted(_ALLOWED_EXTS)}",
                status_code=400,
            )
        if len(data) > self._max_per_file_bytes:
            mb = len(data) / 1024 / 1024
            cap = self._max_per_file_bytes / 1024 / 1024
            raise MediaUploadTooLargeError(
                f"Upload is {mb:.1f} MB, max per file is {cap:.0f} MB",
                status_code=413,
                recovery_hint="Shorten or downscale the clip before uploading.",
            )
        if len(data) > self._quota_bytes:
            raise MediaUploadQuotaExceededError(
                f"Upload alone ({len(data) / 1024 / 1024:.1f} MB) exceeds the full quota"
                f" ({self._quota_bytes / 1024 / 1024 / 1024:.1f} GB)",
                status_code=413,
                recovery_hint="Raise config.vllm.video_quota_gb or shrink the file.",
            )

        # LRU eviction until the new file fits
        self._evict_until_fits(len(data))

        uuid_str = _uuid.uuid4().hex
        path = self._media_dir / f"{uuid_str}.{ext_lower}"
        path.write_bytes(data)
        log.info(
            "video_upload_saved",
            uuid=uuid_str,
            ext=ext_lower,
            bytes=len(data),
        )
        return uuid_str

    def _evict_until_fits(self, incoming_bytes: int) -> None:
        """Delete oldest files (by mtime) until adding ``incoming_bytes`` fits under quota."""
        files = [f for f in self._media_dir.iterdir() if f.is_file()]
        current = sum(f.stat().st_size for f in files)
        if current + incoming_bytes <= self._quota_bytes:
            return
        files.sort(key=lambda f: f.stat().st_mtime)  # oldest first
        for f in files:
            if current + incoming_bytes <= self._quota_bytes:
                break
            size = f.stat().st_size
            try:
                f.unlink()
            except OSError as exc:
                log.warning("video_evict_failed", file=str(f), error=str(exc))
                continue
            # Also drop sidecar thumbnail if present
            thumb = f.with_suffix(".jpg")
            if thumb.exists():
                with contextlib.suppress(OSError):
                    thumb.unlink()
            current -= size
            log.info("video_evicted_lru", file=f.name, freed_bytes=size)

    def delete(self, uuid: str, ext: str) -> None:
        """Remove a specific upload (and its thumbnail). Noop if missing."""
        ext_lower = ext.lower().lstrip(".")
        path = self._media_dir / f"{uuid}.{ext_lower}"
        if path.exists():
            try:
                path.unlink()
            except OSError as exc:
                log.warning("video_delete_failed", uuid=uuid, error=str(exc))
        thumb = self._media_dir / f"{uuid}.jpg"
        if thumb.exists():
            with contextlib.suppress(OSError):
                thumb.unlink()

    def public_url(self, uuid: str, ext: str) -> str:
        """Return the URL vLLM should fetch: ``http://host.docker.internal:<port>/media/<uuid>.<ext>``.

        Requires ``start()`` to have been called (or ``_port`` manually set in tests).
        """
        if self._port is None:
            raise RuntimeError("MediaUploadServer not started; call await start() first")
        ext_lower = ext.lower().lstrip(".")
        return f"http://host.docker.internal:{self._port}/media/{uuid}.{ext_lower}"

    # start() / stop() added in Task 7
