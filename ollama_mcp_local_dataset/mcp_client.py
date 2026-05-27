"""
MCP Client – Connects to the MCP server and exposes helper methods.

This module wraps the FastMCP ``Client`` so the rest of the application can
discover and invoke tools without dealing with the low-level protocol.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError


async def create_client(server_ref: Any) -> Client:
    """Create and return a FastMCP ``Client`` pointing at *server_ref*.

    *server_ref* can be:
    - A ``FastMCP`` server instance (in-process, no network needed).
    - A string path to a server script (runs over stdio).
    - A URL for an HTTP / SSE transport.
    """
    return Client(server_ref)


async def list_tools(client: Client) -> list[dict]:
    """Return a list of available tools with their schemas.

    Each entry is a dictionary with ``name``, ``description``, and
    ``inputSchema`` keys so that the Ollama integration can build the
    tool-calling payload.
    """
    async with client:
        tools = await client.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema,
            }
            for tool in tools
        ]


async def call_tool(
    client: Client,
    tool_name: str,
    arguments: dict,
) -> str:
    """Call *tool_name* with *arguments* and return the result as a string.

    If the tool raises an exception FastMCP re-raises it as ``ToolError``
    (or a subclass thereof) on the client side.  We catch that here so that
    a single broken tool call never kills the entire agent loop.
    """
    try:
        async with client:
            result = await client.call_tool(tool_name, arguments)
    except ToolError as exc:
        return f'["{tool_name}" raised a tool error: {exc}]'
    except Exception as exc:  # noqa: BLE001
        return f'["{tool_name}" raised an unexpected error: {exc}]'

    # result is a CallToolResult; its .content is a list of content blocks
    parts: list[str] = []
    for block in result.content:
        if hasattr(block, "text"):
            parts.append(block.text)
        else:
            parts.append(json.dumps(block, default=str))
    text = "\n".join(parts)
    if not text.strip() or text.strip() == "[]":
        return f'["{tool_name}" returned no results]'
    return text
