"""Tests for jarvis.mcp.desktop_tools."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def desktop_tools(workspace: Path):
    from jarvis.mcp.desktop_tools import DesktopTools

    return DesktopTools(workspace)


@pytest.fixture
def mock_mcp_client() -> MagicMock:
    client = MagicMock()
    client.register_builtin_handler = MagicMock()
    return client


@pytest.fixture
def mock_config(workspace: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.workspace_dir = workspace
    return cfg


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_desktop_tools(self, mock_mcp_client, mock_config):
        from jarvis.mcp.desktop_tools import register_desktop_tools

        tools = register_desktop_tools(mock_mcp_client, mock_config)
        assert tools is not None

        # Should register 4 handlers
        assert mock_mcp_client.register_builtin_handler.call_count == 4

        registered_names = [
            call.args[0] for call in mock_mcp_client.register_builtin_handler.call_args_list
        ]
        assert "get_clipboard" in registered_names
        assert "set_clipboard" in registered_names
        assert "screenshot_desktop" in registered_names
        assert "screenshot_region" in registered_names

    def test_screenshots_dir_created(self, workspace: Path, desktop_tools):
        assert (workspace / "screenshots").is_dir()


# ---------------------------------------------------------------------------
# Path generation
# ---------------------------------------------------------------------------


class TestPathGeneration:
    def test_timestamp_format(self, desktop_tools):
        ts = desktop_tools._timestamp()
        # Should be YYYYMMDD_HHMMSS
        assert len(ts) == 15
        assert ts[8] == "_"


# ---------------------------------------------------------------------------
# Clipboard - get_clipboard
# ---------------------------------------------------------------------------


class TestGetClipboard:
    @pytest.mark.asyncio
    async def test_get_clipboard_text(self, desktop_tools):
        with patch(
            "jarvis.mcp.desktop_tools._ps_get_clipboard_text",
            return_value="Hello World",
        ):
            result = await desktop_tools.get_clipboard()
            assert result["type"] == "text"
            assert result["content"] == "Hello World"
            assert result["length"] == 11

    @pytest.mark.asyncio
    async def test_get_clipboard_empty(self, desktop_tools):
        with (
            patch(
                "jarvis.mcp.desktop_tools._ps_get_clipboard_text",
                return_value="",
            ),
            patch(
                "jarvis.mcp.desktop_tools._ps_get_clipboard_image",
                return_value=False,
            ),
        ):
            result = await desktop_tools.get_clipboard()
            assert result["type"] == "empty"

    @pytest.mark.asyncio
    async def test_get_clipboard_image(self, desktop_tools):
        def mock_get_image(save_path: str) -> bool:
            # Create a fake PNG file
            Path(save_path).write_bytes(b"\x89PNG fake")
            return True

        with (
            patch(
                "jarvis.mcp.desktop_tools._ps_get_clipboard_text",
                side_effect=RuntimeError("no text"),
            ),
            patch(
                "jarvis.mcp.desktop_tools._ps_get_clipboard_image",
                side_effect=mock_get_image,
            ),
        ):
            result = await desktop_tools.get_clipboard()
            assert result["type"] == "image"
            assert "path" in result

    @pytest.mark.asyncio
    async def test_get_clipboard_with_vision(self, desktop_tools):
        """When vision analyzer is set, description should be included."""
        mock_vision = MagicMock()
        mock_vision.analyze = AsyncMock(return_value="A screenshot of a desktop")
        desktop_tools._set_vision(mock_vision)

        def mock_get_image(save_path: str) -> bool:
            Path(save_path).write_bytes(b"\x89PNG fake")
            return True

        with (
            patch(
                "jarvis.mcp.desktop_tools._ps_get_clipboard_text",
                side_effect=RuntimeError("no text"),
            ),
            patch(
                "jarvis.mcp.desktop_tools._ps_get_clipboard_image",
                side_effect=mock_get_image,
            ),
        ):
            result = await desktop_tools.get_clipboard()
            assert result["type"] == "image"
            assert result.get("description") == "A screenshot of a desktop"


# ---------------------------------------------------------------------------
# Clipboard - set_clipboard
# ---------------------------------------------------------------------------


class TestSetClipboard:
    @pytest.mark.asyncio
    async def test_set_clipboard(self, desktop_tools):
        with patch("jarvis.mcp.desktop_tools._ps_set_clipboard") as mock_set:
            result = await desktop_tools.set_clipboard("Test text")
            assert result["status"] == "ok"
            assert result["chars"] == 9
            mock_set.assert_called_once_with("Test text")


# ---------------------------------------------------------------------------
# Screenshot - desktop
# ---------------------------------------------------------------------------


class TestScreenshotDesktop:
    @pytest.mark.asyncio
    async def test_screenshot_via_mss(self, desktop_tools):
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        with patch(
            "jarvis.mcp.desktop_tools._try_mss_screenshot",
            return_value=(fake_png, 1920, 1080),
        ):
            result = await desktop_tools.screenshot_desktop()
            assert "path" in result
            assert result["width"] == 1920
            assert result["height"] == 1080
            assert result["backend"] == "mss"
            assert Path(result["path"]).exists()

    @pytest.mark.asyncio
    async def test_screenshot_fallback_pil(self, desktop_tools):
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        with (
            patch("jarvis.mcp.desktop_tools._try_mss_screenshot", return_value=None),
            patch(
                "jarvis.mcp.desktop_tools._try_pil_screenshot",
                return_value=(fake_png, 1920, 1080),
            ),
        ):
            result = await desktop_tools.screenshot_desktop()
            assert result["backend"] == "PIL"

    @pytest.mark.asyncio
    async def test_screenshot_fallback_powershell(self, desktop_tools):
        with (
            patch("jarvis.mcp.desktop_tools._try_mss_screenshot", return_value=None),
            patch("jarvis.mcp.desktop_tools._try_pil_screenshot", return_value=None),
            patch("jarvis.mcp.desktop_tools.sys") as mock_sys,
            patch(
                "jarvis.mcp.desktop_tools._try_ps_screenshot",
                return_value=(1920, 1080),
            ),
        ):
            mock_sys.platform = "win32"
            result = await desktop_tools.screenshot_desktop()
            assert result["backend"] == "PowerShell"

    @pytest.mark.asyncio
    async def test_screenshot_no_backend(self, desktop_tools):
        with (
            patch("jarvis.mcp.desktop_tools._try_mss_screenshot", return_value=None),
            patch("jarvis.mcp.desktop_tools._try_pil_screenshot", return_value=None),
            patch("jarvis.mcp.desktop_tools.sys") as mock_sys,
        ):
            mock_sys.platform = "linux"
            result = await desktop_tools.screenshot_desktop()
            assert "error" in result

    @pytest.mark.asyncio
    async def test_screenshot_custom_path(self, desktop_tools, tmp_path: Path):
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        custom = tmp_path / "custom" / "shot.png"

        with patch(
            "jarvis.mcp.desktop_tools._try_mss_screenshot",
            return_value=(fake_png, 1920, 1080),
        ):
            result = await desktop_tools.screenshot_desktop(save_path=str(custom))
            assert result["path"] == str(custom)
            assert custom.exists()


# ---------------------------------------------------------------------------
# Screenshot - region
# ---------------------------------------------------------------------------


class TestScreenshotRegion:
    @pytest.mark.asyncio
    async def test_region_via_mss(self, desktop_tools):
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        with patch(
            "jarvis.mcp.desktop_tools._try_mss_screenshot",
            return_value=(fake_png, 400, 300),
        ):
            result = await desktop_tools.screenshot_region(x=100, y=200, width=400, height=300)
            assert result["width"] == 400
            assert result["height"] == 300
            assert "region_100_200_400_300_" in result["path"]

    @pytest.mark.asyncio
    async def test_region_fallback_pil(self, desktop_tools):
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        with (
            patch("jarvis.mcp.desktop_tools._try_mss_screenshot", return_value=None),
            patch(
                "jarvis.mcp.desktop_tools._try_pil_screenshot",
                return_value=(fake_png, 400, 300),
            ),
        ):
            result = await desktop_tools.screenshot_region(x=0, y=0, width=400, height=300)
            assert result["backend"] == "PIL"

    @pytest.mark.asyncio
    async def test_region_no_backend(self, desktop_tools):
        with (
            patch("jarvis.mcp.desktop_tools._try_mss_screenshot", return_value=None),
            patch("jarvis.mcp.desktop_tools._try_pil_screenshot", return_value=None),
        ):
            result = await desktop_tools.screenshot_region(x=0, y=0, width=100, height=100)
            assert "error" in result


# ---------------------------------------------------------------------------
# Downscaling
# ---------------------------------------------------------------------------


class TestDownscale:
    def test_no_downscale_needed(self):
        from jarvis.mcp.desktop_tools import _downscale_if_needed

        data = b"fake"
        out, w, h = _downscale_if_needed(data, 1920, 1080)
        assert out is data
        assert w == 1920
        assert h == 1080

    def test_downscale_needed_without_pillow(self):
        from jarvis.mcp.desktop_tools import _downscale_if_needed

        data = b"fake"
        # 5K resolution -> should attempt downscale, but without valid PNG + PIL it falls back
        out, w, h = _downscale_if_needed(data, 5120, 2880)
        # Falls back to original since data is not valid PNG
        assert out is data


# ---------------------------------------------------------------------------
# Vision integration
# ---------------------------------------------------------------------------


class TestVisionIntegration:
    def test_set_vision(self, desktop_tools):
        mock_vision = MagicMock()
        desktop_tools._set_vision(mock_vision)
        assert desktop_tools._vision_analyzer is mock_vision

    @pytest.mark.asyncio
    async def test_screenshot_with_vision(self, desktop_tools):
        mock_vision = MagicMock()
        mock_vision.analyze = AsyncMock(return_value="Desktop with icons")
        desktop_tools._set_vision(mock_vision)

        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        with patch(
            "jarvis.mcp.desktop_tools._try_mss_screenshot",
            return_value=(fake_png, 1920, 1080),
        ):
            result = await desktop_tools.screenshot_desktop()
            assert result.get("description") == "Desktop with icons"
