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
