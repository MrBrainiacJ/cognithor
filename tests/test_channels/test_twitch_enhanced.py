"""Enhanced tests for TwitchChannel -- additional coverage."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.channels.twitch import TwitchChannel
from jarvis.models import OutgoingMessage, PlannedAction


@pytest.fixture
def ch() -> TwitchChannel:
    return TwitchChannel(
        token="oauth:test",
        channel="testchannel",
        nick="JarvisBot",
        allowed_users=["alice", "bob"],
        command_prefix="!jarvis",
    )


class TestTwitchProperties:
    def test_name(self, ch: TwitchChannel) -> None:
        assert ch.name == "twitch"

    def test_channel_lowercase(self, ch: TwitchChannel) -> None:
        assert ch._channel == "testchannel"

    def test_nick_lowercase(self, ch: TwitchChannel) -> None:
        assert ch._nick == "jarvisbot"


class TestTwitchHandleLine:
    @pytest.mark.asyncio
    async def test_ping_pong(self, ch: TwitchChannel) -> None:
        ch._writer = MagicMock()
        ch._writer.write = MagicMock()
        ch._writer.drain = AsyncMock()

        await ch._handle_line("PING :tmi.twitch.tv")
        ch._writer.write.assert_called_once()
        assert b"PONG" in ch._writer.write.call_args[0][0]

    @pytest.mark.asyncio
    async def test_empty_line(self, ch: TwitchChannel) -> None:
        await ch._handle_line("")  # no crash

    @pytest.mark.asyncio
    async def test_privmsg_line(self, ch: TwitchChannel) -> None:
        response = OutgoingMessage(channel="twitch", text="OK")
        ch._handler = AsyncMock(return_value=response)
        ch._writer = MagicMock()
        ch._writer.write = MagicMock()
        ch._writer.drain = AsyncMock()
        ch._last_msg_time = 0

        line = "@display-name=Alice;mod=0;subscriber=0 :alice!alice@alice.tmi.twitch.tv PRIVMSG #testchannel :!jarvis what is up"
        await ch._handle_line(line)
        ch._handler.assert_called_once()
        incoming = ch._handler.call_args[0][0]
        assert incoming.text == "what is up"

    @pytest.mark.asyncio
    async def test_privmsg_no_tags(self, ch: TwitchChannel) -> None:
        response = OutgoingMessage(channel="twitch", text="OK")
        ch._handler = AsyncMock(return_value=response)
        ch._writer = MagicMock()
        ch._writer.write = MagicMock()
        ch._writer.drain = AsyncMock()
        ch._last_msg_time = 0

        line = ":alice!alice@alice.tmi.twitch.tv PRIVMSG #testchannel :!jarvis hi"
        await ch._handle_line(line)
        ch._handler.assert_called_once()


class TestTwitchOnPrivmsg:
    @pytest.mark.asyncio
    async def test_ignore_own_messages(self, ch: TwitchChannel) -> None:
        ch._handler = AsyncMock()
        line = ":jarvisbot!jarvisbot@jarvisbot.tmi.twitch.tv PRIVMSG #testchannel :!jarvis test"
        await ch._on_privmsg(line, {})
        ch._handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitelist_blocks(self, ch: TwitchChannel) -> None:
        ch._handler = AsyncMock()
        line = ":charlie!charlie@charlie.tmi.twitch.tv PRIVMSG #testchannel :!jarvis test"
        await ch._on_privmsg(line, {})
        ch._handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_prefix_ignored(self, ch: TwitchChannel) -> None:
        ch._handler = AsyncMock()
        line = ":alice!alice@alice.tmi.twitch.tv PRIVMSG #testchannel :hello world"
        await ch._on_privmsg(line, {})
        ch._handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_prefix_only_ignored(self, ch: TwitchChannel) -> None:
        ch._handler = AsyncMock()
        line = ":alice!alice@alice.tmi.twitch.tv PRIVMSG #testchannel :!jarvis"
        await ch._on_privmsg(line, {})
        ch._handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_metadata_tags(self, ch: TwitchChannel) -> None:
        response = OutgoingMessage(channel="twitch", text="OK")
        ch._handler = AsyncMock(return_value=response)
        ch._writer = MagicMock()
        ch._writer.write = MagicMock()
        ch._writer.drain = AsyncMock()
        ch._last_msg_time = 0

        tags = {
            "display-name": "Alice",
            "mod": "1",
            "subscriber": "1",
            "badges": "broadcaster/1",
        }
        line = ":alice!alice@alice.tmi.twitch.tv PRIVMSG #testchannel :!jarvis check"
        await ch._on_privmsg(line, tags)
        incoming = ch._handler.call_args[0][0]
        assert incoming.metadata["is_mod"] is True
        assert incoming.metadata["is_sub"] is True
        assert incoming.metadata["is_broadcaster"] is True


class TestTwitchSend:
    @pytest.mark.asyncio
    async def test_send_no_writer(self, ch: TwitchChannel) -> None:
        ch._writer = None
        msg = OutgoingMessage(channel="twitch", text="test")
        await ch.send(msg)  # no crash


class TestTwitchApproval:
    @pytest.mark.asyncio
    async def test_approval_returns_false(self, ch: TwitchChannel) -> None:
        action = PlannedAction(tool="test", params={})
        result = await ch.request_approval("s1", action, "reason")
        assert result is False


class TestTwitchStop:
    @pytest.mark.asyncio
    async def test_stop(self, ch: TwitchChannel) -> None:
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
        assert ch._reader is None
        assert ch._recv_task is None


class TestTwitchSendRaw:
    @pytest.mark.asyncio
    async def test_send_raw_no_writer(self, ch: TwitchChannel) -> None:
        ch._writer = None
        await ch._send_raw("test")  # no crash

    @pytest.mark.asyncio
    async def test_send_raw_exception(self, ch: TwitchChannel) -> None:
        ch._writer = MagicMock()
        ch._writer.write = MagicMock(side_effect=RuntimeError("broken"))
        await ch._send_raw("test")  # no crash
