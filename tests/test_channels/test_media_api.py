from __future__ import annotations

from pathlib import Path  # noqa: TC003
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cognithor.channels.media_api import build_media_app
from cognithor.channels.media_server import MediaUploadServer
from cognithor.config import CognithorConfig, VLLMConfig


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    cfg = CognithorConfig(
        cognithor_home=tmp_path,
        vllm=VLLMConfig(enabled=True, video_max_upload_mb=10, video_quota_gb=1),
    )
    media_server = MediaUploadServer(cfg)
    media_server._port = 4711  # not running, but public_url needs a port
    app = build_media_app(config=cfg, media_server=media_server)
    return TestClient(app)


class TestUploadEndpoint:
    def test_upload_valid_video_returns_metadata(self, client: TestClient):
        from cognithor.core.video_sampling import VideoSampling

        with (
            patch(
                "cognithor.channels.media_api.resolve_sampling",
                return_value=VideoSampling(fps=1.0, duration_sec=93.5),
            ),
            patch(
                "cognithor.channels.media_api._extract_thumbnail",
                return_value=True,
            ),
        ):
            r = client.post(
                "/api/media/upload",
                files={"file": ("drone.mp4", b"\x00" * 2048, "video/mp4")},
            )
        assert r.status_code == 200
        data = r.json()
        assert "uuid" in data
        assert data["url"].startswith("http://host.docker.internal:4711/media/")
        assert data["duration_sec"] == 93.5
        assert data["sampling"] == {"fps": 1.0}
        assert data["thumb_url"].startswith("/api/media/thumb/")

    def test_upload_too_large_returns_413(self, client: TestClient):
        too_big = b"\x00" * (11 * 1024 * 1024)
        r = client.post(
            "/api/media/upload",
            files={"file": ("big.mp4", too_big, "video/mp4")},
        )
        assert r.status_code == 413
        assert "recovery_hint" in r.json().get("detail", {})

    def test_upload_unsupported_extension_returns_400(self, client: TestClient):
        r = client.post(
            "/api/media/upload",
            files={"file": ("trojan.exe", b"\x00" * 1024, "application/octet-stream")},
        )
        assert r.status_code == 400


class TestThumbEndpoint:
    def test_thumb_returns_jpeg(self, client: TestClient, tmp_path: Path):
        uuid = "test-uuid-1234"
        media_dir = tmp_path / "media" / "vllm-uploads"
        media_dir.mkdir(parents=True, exist_ok=True)
        thumb = media_dir / f"{uuid}.jpg"
        thumb.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
        r = client.get(f"/api/media/thumb/{uuid}.jpg")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/")

    def test_thumb_returns_404_for_missing(self, client: TestClient):
        r = client.get("/api/media/thumb/not-a-real-uuid.jpg")
        assert r.status_code == 404


class TestUploadDoesNotBlockEventLoop:
    @pytest.mark.asyncio
    async def test_concurrent_requests_not_serialized_by_subprocess(self, tmp_path: Path):
        """When ffprobe/ffmpeg are slow, concurrent upload requests must
        not serialize on the event loop.

        We drive this by patching resolve_sampling to sleep (simulating
        ffprobe hanging on a slow HTTP URL) and firing two uploads
        concurrently. If the handler runs subprocess.run directly on the
        loop, total wall time ~ 2*sleep. With asyncio.to_thread it's ~
        1*sleep."""
        import asyncio as _asyncio
        import time

        from cognithor.channels.media_server import MediaUploadServer
        from cognithor.config import CognithorConfig, VLLMConfig
        from cognithor.core.video_sampling import VideoSampling

        cfg = CognithorConfig(
            cognithor_home=tmp_path,
            vllm=VLLMConfig(enabled=True, video_max_upload_mb=10, video_quota_gb=1),
        )
        ms = MediaUploadServer(cfg)
        ms._port = 4711
        from cognithor.channels.media_api import build_media_app

        app = build_media_app(config=cfg, media_server=ms)

        sleep_seconds = 0.5

        def _slow_sampling(*args, **kwargs) -> VideoSampling:
            time.sleep(sleep_seconds)  # blocking sync sleep - a proxy for ffprobe
            return VideoSampling(fps=1.0, duration_sec=10.0)

        with (
            patch(
                "cognithor.channels.media_api.resolve_sampling",
                side_effect=_slow_sampling,
            ),
            patch(
                "cognithor.channels.media_api._extract_thumbnail",
                return_value=True,
            ),
        ):
            # TestClient runs in a separate thread so we can't use it for
            # concurrent-async testing. Instead use httpx.AsyncClient against
            # an ASGITransport.
            from httpx import ASGITransport, AsyncClient

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                start = time.perf_counter()
                responses = await _asyncio.gather(
                    client.post(
                        "/api/media/upload",
                        files={"file": ("a.mp4", b"\x00" * 2048, "video/mp4")},
                    ),
                    client.post(
                        "/api/media/upload",
                        files={"file": ("b.mp4", b"\x00" * 2048, "video/mp4")},
                    ),
                )
                elapsed = time.perf_counter() - start

        for r in responses:
            assert r.status_code == 200, r.text

        # With asyncio.to_thread: ~sleep_seconds (parallel) + overhead
        # Without: ~2*sleep_seconds (serialized)
        # Tolerance: pass if < 1.6*sleep_seconds (i.e. strictly less than
        # serial execution, accounting for thread-pool startup).
        assert elapsed < 1.6 * sleep_seconds, (
            f"Upload handler appears to serialize: {elapsed:.2f}s for two 0.5s uploads "
            f"(expected ~0.5s parallel, got {elapsed:.2f}s)"
        )
