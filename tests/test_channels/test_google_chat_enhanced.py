"""Enhanced tests for GoogleChatChannel -- additional coverage."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.channels.google_chat import GoogleChatChannel
from jarvis.models import OutgoingMessage, PlannedAction


@pytest.fixture
def ch() -> GoogleChatChannel:
    return GoogleChatChannel(credentials_path="creds.json", allowed_spaces=["spaces/abc"])


class TestGoogleChatProperties:
    def test_name(self, ch: GoogleChatChannel) -> None:
        assert ch.name == "google_chat"


class TestIsSpaceAllowed:
    def test_allowed(self, ch: GoogleChatChannel) -> None:
        assert ch._is_space_allowed("spaces/abc") is True

    def test_not_allowed(self, ch: GoogleChatChannel) -> None:
        assert ch._is_space_allowed("spaces/xyz") is False

    def test_no_whitelist(self) -> None:
        ch = GoogleChatChannel()
        assert ch._is_space_allowed("any_space") is True


class TestHandleWebhook:
    @pytest.mark.asyncio
    async def test_message_event(self, ch: GoogleChatChannel) -> None:
        response = OutgoingMessage(channel="google_chat", text="OK")
        ch._handler = AsyncMock(return_value=response)

        payload = {
            "type": "MESSAGE",
            "space": {"name": "spaces/abc"},
            "message": {
                "argumentText": "Hello",
                "text": "Hello",
                "sender": {"name": "users/123", "displayName": "Alice"},
                "name": "msg1",
                "thread": {"name": "thread1"},
            },
        }
        result = await ch.handle_webhook(payload)
        assert result == {"text": "OK"}
        ch._handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_not_allowed_space(self, ch: GoogleChatChannel) -> None:
        ch._handler = AsyncMock()
        payload = {
            "type": "MESSAGE",
            "space": {"name": "spaces/xyz"},
            "message": {"argumentText": "Hello", "sender": {}},
        }
        result = await ch.handle_webhook(payload)
        assert result is None
        ch._handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_card_clicked(self, ch: GoogleChatChannel) -> None:
        future = asyncio.get_event_loop().create_future()
        ch._approval_futures["appr_1"] = future

        payload = {
            "type": "CARD_CLICKED",
            "action": {
                "actionMethodName": "jarvis_approve",
                "parameters": [{"key": "approval_id", "value": "appr_1"}],
            },
        }
        await ch.handle_webhook(payload)
        assert future.result() is True

    @pytest.mark.asyncio
    async def test_card_clicked_reject(self, ch: GoogleChatChannel) -> None:
        future = asyncio.get_event_loop().create_future()
        ch._approval_futures["appr_2"] = future

        payload = {
            "type": "CARD_CLICKED",
            "action": {
                "actionMethodName": "jarvis_reject",
                "parameters": [{"key": "approval_id", "value": "appr_2"}],
            },
        }
        await ch.handle_webhook(payload)
        assert future.result() is False

    @pytest.mark.asyncio
    async def test_added_to_space(self, ch: GoogleChatChannel) -> None:
        payload = {"type": "ADDED_TO_SPACE", "space": {"name": "spaces/new"}}
        result = await ch.handle_webhook(payload)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_text_ignored(self, ch: GoogleChatChannel) -> None:
        ch._handler = AsyncMock()
        payload = {
            "type": "MESSAGE",
            "space": {"name": "spaces/abc"},
            "message": {"argumentText": "  ", "sender": {}},
        }
        result = await ch.handle_webhook(payload)
        assert result is None


class TestGoogleChatSend:
    @pytest.mark.asyncio
    async def test_send_no_client(self, ch: GoogleChatChannel) -> None:
        ch._http_client = None
        msg = OutgoingMessage(channel="google_chat", text="test", metadata={"space_name": "s"})
        await ch.send(msg)

    @pytest.mark.asyncio
    async def test_send_no_space(self, ch: GoogleChatChannel) -> None:
        ch._http_client = AsyncMock()
        ch._credentials = MagicMock()
        msg = OutgoingMessage(channel="google_chat", text="test", metadata={})
        await ch.send(msg)

    @pytest.mark.asyncio
    async def test_send_no_auth_headers(self, ch: GoogleChatChannel) -> None:
        ch._http_client = AsyncMock()
        ch._credentials = None
        msg = OutgoingMessage(
            channel="google_chat", text="test",
            metadata={"space_name": "spaces/abc"},
        )
        await ch.send(msg)  # no crash since _get_auth_headers returns {}


class TestGoogleChatApproval:
    @pytest.mark.asyncio
    async def test_approval_no_client(self, ch: GoogleChatChannel) -> None:
        ch._http_client = None
        action = PlannedAction(tool="test", params={})
        result = await ch.request_approval("s1", action, "reason")
        assert result is False


class TestGoogleChatStop:
    @pytest.mark.asyncio
    async def test_stop(self, ch: GoogleChatChannel) -> None:
        ch._running = True
        ch._http_client = AsyncMock()
        ch._http_client.aclose = AsyncMock()
        ch._credentials = MagicMock()

        await ch.stop()
        assert ch._running is False
        assert ch._http_client is None
        assert ch._credentials is None


class TestGoogleChatStart:
    @pytest.mark.asyncio
    async def test_start_no_credentials(self) -> None:
        ch = GoogleChatChannel()
        handler = AsyncMock()
        await ch.start(handler)
        assert ch._running is False
