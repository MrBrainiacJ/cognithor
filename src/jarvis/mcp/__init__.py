"""Jarvis MCP module -- Client, Server, Resources, Prompts, Discovery, Bridge."""

from jarvis.mcp.bridge import MCPBridge
from jarvis.mcp.client import JarvisMCPClient, ToolCallResult
from jarvis.mcp.discovery import AgentCard, DiscoveryManager
from jarvis.mcp.prompts import JarvisPromptProvider
from jarvis.mcp.resources import JarvisResourceProvider
from jarvis.mcp.server import (
    JarvisMCPServer,
    MCPPrompt,
    MCPPromptArgument,
    MCPResource,
    MCPResourceTemplate,
    MCPServerConfig,
    MCPServerMode,
    MCPToolDef,
)

__all__ = [
    # Discovery (v15 neu)
    "AgentCard",
    "DiscoveryManager",
    # Client (bestehend)
    "JarvisMCPClient",
    # Server (v15 neu)
    "JarvisMCPServer",
    "JarvisPromptProvider",
    # Providers (v15 neu)
    "JarvisResourceProvider",
    # Bridge (v15 neu)
    "MCPBridge",
    "MCPPrompt",
    "MCPPromptArgument",
    "MCPResource",
    "MCPResourceTemplate",
    "MCPServerConfig",
    "MCPServerMode",
    "MCPToolDef",
    "ToolCallResult",
]
