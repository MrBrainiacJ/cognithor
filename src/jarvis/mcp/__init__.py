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
    # Discovery (v15 new)
    "AgentCard",
    "DiscoveryManager",
    # Client (existing)
    "JarvisMCPClient",
    # Server (v15 new)
    "JarvisMCPServer",
    "JarvisPromptProvider",
    # Providers (v15 new)
    "JarvisResourceProvider",
    # Bridge (v15 new)
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
