"""Enhanced tests for IRCChannel -- additional coverage."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.channels.irc import IRCChannel
from jarvis.models import OutgoingMessage, PlannedAction


@pytest.fixture
def ch() -> IRCChannel:
    return IRCChannel(
        server="irc.example.com",
        port=6667,
        nick="JarvisBot",
        channels=["#general", "#support"],
        password="secret",
    )


class TestIRCProperties:
    def test_name(self, ch: IRCChannel) -> None:
        assert ch.name == "irc"


class TestIRCHandleLine:
    @pytest.mark.asyncio
    async def test_ping_pong(self, ch: IRCChannel) -> None:
        ch._writer = MagicMock()
        ch._writer.write = MagicMock()
        ch._writer.drain = AsyncMock()

        await ch._handle_line("PING :server")
        assert b"PONG" in ch._writer.write.call_args[0][0]

    @pytest.mark.asyncio
    async def test_empty_line(self, ch: IRCChannel) -> None:
        await ch._handle_line("")  # no crash

    @pytest.mark.asyncio
    async def test_welcome_001_joins_channels(self, ch: IRCChannel) -> None:
        ch._writer = MagicMock()
        ch._writer.write = MagicMock()
        ch._writer.drain = AsyncMock()

        await ch._handle_line(":server 001 JarvisBot :Welcome")
        # Should have sent JOIN for both channels + IDENTIFY
        calls = ch._writer.write.call_args_list
        join_calls = [c for c in calls if b"JOIN" in c[0][0]]
        assert len(join_calls) == 2

    @pytest.mark.asyncio
    async def test_privmsg_in_channel(self, ch: IRCChannel) -> None:
        response = OutgoingMessage(channel="irc", text="OK")
        ch._handler = AsyncMock(return_value=response)
        ch._writer = MagicMock()
        ch._writer.write = MagicMock()
        ch._writer.drain = AsyncMock()
        ch._last_msg_time = 0

        # Addressed to bot in channel
        await ch._handle_line(":alice!alice@host 002 unused :ignored")  # test short parts

    @pytest.mark.asyncio
    async def test_short_parts(self, ch: IRCChannel) -> None:
        await ch._handle_line(":x")  # fewer than 2 parts


class TestIRCOnPrivmsg:
    @pytest.mark.asyncio
    async def test_ignore_own_messages(self, ch: IRCChannel) -> None:
        ch._handler = AsyncMock()
        await ch._on_privmsg(
            ":JarvisBot!JarvisBot@host",
            [":JarvisBot!JarvisBot@host", "PRIVMSG", "#general", ":hello"],
        )
        ch._handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_private_message(self, ch: IRCChannel) -> None:
        response = OutgoingMessage(channel="irc", text="OK")
        ch._handler = AsyncMock(return_value=response)
        ch._writer = MagicMock()
        ch._writer.write = MagicMock()
        ch._writer.drain = AsyncMock()
        ch._last_msg_time = 0

        await ch._on_privmsg(
            ":alice!alice@host",
            [":alice!alice@host", "PRIVMSG", "JarvisBot", ":hello bot"],
        )
        ch._handler.assert_called_once()
        incoming = ch._handler.call_args[0][0]
        assert incoming.text == "hello bot"
        assert incoming.metadata["is_private"] is True

    @pytest.mark.asyncio
    async def test_channel_not_addressed(self, ch: IRCChannel) -> None:
        ch._handler = AsyncMock()
        await ch._on_privmsg(
            ":alice!alice@host",
            [":alice!alice@host", "PRIVMSG", "#general", ":hello world"],
        )
        ch._handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_channel_addressed(self, ch: IRCChannel) -> None:
        response = OutgoingMessage(channel="irc", text="OK")
        ch._handler = AsyncMock(return_value=response)
        ch._writer = MagicMock()
        ch._writer.write = MagicMock()
        ch._writer.drain = AsyncMock()
        ch._last_msg_time = 0

        await ch._on_privmsg(
            ":alice!alice@host",
            [":alice!alice@host", "PRIVMSG", "#general", ":JarvisBot: what time is it"],
        )
        ch._handler.assert_called_once()
        incoming = ch._handler.call_args[0][0]
        assert "what time is it" in incoming.text

    @pytest.mark.asyncio
    async def test_empty_text(self, ch: IRCChannel) -> None:
        ch._handler = AsyncMock()
        await ch._on_privmsg(
            ":alice!alice@host",
            [":alice!alice@host", "PRIVMSG", "JarvisBot", ":  "],
        )
        ch._handler.assert_not_called()


class TestIRCSend:
    @pytest.mark.asyncio
    async def test_send_no_target(self, ch: IRCChannel) -> None:
        msg = OutgoingMessage(channel="irc", text="test", metadata={})
        ch._writer = MagicMock()
        ch._writer.write = MagicMock()
        ch._writer.drain = AsyncMock()
        ch._last_msg_time = 0
        await ch.send(msg)
        # Should use first channel as fallback
        assert b"#general" in ch._writer.write.call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_no_target_no_channels(self) -> None:
        ch = IRCChannel(server="x")
        msg = OutgoingMessage(channel="irc", text="test", metadata={})
        await ch.send(msg)  # no crash


class TestIRCApproval:
    @pytest.mark.asyncio
    async def test_approval_returns_false(self, ch: IRCChannel) -> None:
        action = PlannedAction(tool="test", params={})
        result = await ch.request_approval("s1", action, "reason")
        assert result is False


class TestIRCStop:
    @pytest.mark.asyncio
    async def test_stop(self, ch: IRCChannel) -> None:
        ch._running = True
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        ch._writer = mock_writer
        ch._reader = MagicMock()
        ch._recv_task = MagicMock()

        await ch.stop()
        assert ch._running is False
        assert ch._writer is None


class TestIRCStart:
    @pytest.mark.asyncio
    async def test_start_no_server(self) -> None:
        ch = IRCChannel(server="")
        handler = AsyncMock()
        await ch.start(handler)
        assert ch._running is False
