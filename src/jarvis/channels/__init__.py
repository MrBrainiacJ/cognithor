"""Jarvis channels module.

Alle Kommunikationskanäle zwischen User und Gateway.
Bibel-Referenz: §9 (Gateway & Channels)
"""

from jarvis.channels.base import Channel, MessageHandler

# v22: Canvas
from jarvis.channels.canvas import CanvasManager
from jarvis.channels.commands import (
    CommandRegistry,
    InteractionStore,
)
from jarvis.channels.connectors import (
    ConnectorRegistry,
    JiraConnector,
    ServiceNowConnector,
    TeamsConnector,
)
from jarvis.channels.discord import DiscordChannel
from jarvis.channels.feishu import FeishuChannel

# v22: Neue Channels (lazy imports um optionale Dependencies zu vermeiden)
from jarvis.channels.google_chat import GoogleChatChannel
from jarvis.channels.interactive import (
    AdaptiveCard,
    DiscordMessageBuilder,
    FallbackRenderer,
    FormField,
    InteractionStateStore,
    ModalHandler,
    ProgressTracker,
    SignatureVerifier,
    SlackMessageBuilder,
    SlashCommandRegistry,
)
from jarvis.channels.irc import IRCChannel
from jarvis.channels.mattermost import MattermostChannel
from jarvis.channels.slack import SlackChannel
from jarvis.channels.twitch import TwitchChannel

__all__ = [
    "AdaptiveCard",
    "CanvasManager",
    "Channel",
    "CommandRegistry",
    "ConnectorRegistry",
    "DiscordChannel",
    "DiscordMessageBuilder",
    "FallbackRenderer",
    "FeishuChannel",
    "FormField",
    # v22: Neue Channels
    "GoogleChatChannel",
    "IRCChannel",
    "InteractionStateStore",
    "InteractionStore",
    "JiraConnector",
    "MattermostChannel",
    "MessageHandler",
    "ModalHandler",
    "ProgressTracker",
    "ServiceNowConnector",
    "SignatureVerifier",
    "SlackChannel",
    "SlackMessageBuilder",
    "SlashCommandRegistry",
    "TeamsConnector",
    "TwitchChannel",
]
