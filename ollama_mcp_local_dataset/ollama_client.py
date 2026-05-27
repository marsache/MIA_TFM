"""
Ollama ↔ MCP bridge for the local dataset RAG agent.

This module connects to a local Ollama instance and uses its tool-calling
capabilities to invoke tools exposed by the MCP server through the FastMCP
client.

Flow
----
1. Discover available MCP tools and convert their JSON-Schema descriptions
   into the format that Ollama's ``chat`` API expects.
2. Send the user prompt to Ollama together with the tool definitions.
3. When Ollama responds with one or more tool calls, execute them via the
   MCP client and feed the results back to Ollama.
4. Repeat until Ollama produces a final text answer.

Known model quirk (llama3.2 and similar small models)
------------------------------------------------------
After receiving tool results some models "hallucinate" a function call as
plain text (e.g. ``{"name": "search_songs", "parameters": {...}}``) instead
of either making a real structured tool call or giving a prose answer.  When
this is detected the conversation receives an extra nudge message that asks
the model to synthesise a human-readable answer from the results it already
has, breaking the loop.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Optional

import ollama as ollama_lib
from fastmcp import Client

import mcp_client
from config import OLLAMA_HOST, OLLAMA_MODEL

# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

_SCALAR_TYPES = {"string", "integer", "number", "boolean"}


def _normalize_tool_args(arguments: dict) -> dict:
    """Unwrap schema-dict arguments returned by some Ollama model versions."""
    return {key: _unwrap_schema_value(val) for key, val in arguments.items()}


def _unwrap_schema_value(val: object) -> object:
    """Recursively unwrap a single schema-dict or JSON-encoded schema value."""
    if isinstance(val, str):
        stripped = val.strip()
        if stripped.startswith("{"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict) and "type" in parsed:
                    return _unwrap_schema_value(parsed)
            except (json.JSONDecodeError, ValueError):
                pass
        return val

    if not isinstance(val, dict):
        return val

    has_type = "type" in val
    is_scalar_type = val.get("type") in _SCALAR_TYPES

    if has_type and "value" in val:
        return val["value"]

    if is_scalar_type and "description" in val and len(val) <= 3:
        return val["description"]

    return val


def _mcp_tools_to_ollama(mcp_tools: list[dict]) -> list[dict]:
    """Convert MCP tool schemas to the Ollama tool-calling format."""
    ollama_tools: list[dict] = []
    for tool in mcp_tools:
        params = dict(tool.get("inputSchema", {}))
        params.setdefault("type", "object")
        params.setdefault("properties", {})
        ollama_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": params,
                },
            }
        )
    return ollama_tools


# ---------------------------------------------------------------------------
# Conversation loop
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a helpful music research assistant specialised in Spanish folk songs. "
    "You have access to a local dataset of folk songs that includes:\n"
    "  • The «Cancionero básico de Castilla y León» (a collection of traditional "
    "    songs from Castilla y León, Spain, organised by thematic categories such as "
    "    work songs, life-cycle songs, narrative songs, dance songs, etc.).\n"
    "  • The «Muiñeiras» collection (Galician bagpipe dance tunes from various "
    "    historical cancioneros).\n\n"
    "IMPORTANT – search strategy:\n"
    "1. For EVERY question about a song, artist, category, or musical attribute, "
    "   you MUST call at least one tool before answering.  Never answer from memory "
    "   alone.\n"
    "2. Start with search_songs to find relevant songs using keywords from the "
    "   user's question (title words, lyric fragments, category names, themes).\n"
    "3. If the user asks about the structure or contents of the dataset, call "
    "   list_categories or get_dataset_overview.\n"
    "4. If the user asks about musical attributes (key, time signature), call "
    "   search_by_musical_attributes.\n"
    "5. If the user asks for full details or lyrics of a specific song, call "
    "   get_song_details with the song's ID.\n\n"
    "Using tool results:\n"
    "- After receiving tool results, write a clear, informative prose answer "
    "  using only the information from those results.\n"
    "- Always answer in the same language the user used.\n"
    "- Do NOT claim information not present in the tool results.\n"
    "- If no results are found, say so clearly.\n\n"
    "IMPORTANT – tool calling rules:\n"
    "- Pass every tool argument as a plain scalar value "
    "  (string, number, boolean), NOT as a JSON schema object.\n"
    "- Correct:   search_songs(query=\"marzas\")\n"
    "- Incorrect: search_songs(query={\"type\":\"string\",\"value\":\"marzas\"})\n"
    "- After you receive tool results, write a normal prose response. "
    "  Do NOT output raw JSON, function call syntax, or any text like "
    "'Llamando a la función …' or '{\"name\": …}' in your answer."
)


async def run_agent(
    user_prompt: str,
    client: Client,
    *,
    model: str = OLLAMA_MODEL,
    host: str = OLLAMA_HOST,
    max_iterations: int = 10,
    on_event: Optional[Callable[[dict], Awaitable[None]]] = None,
) -> str:
    """Send *user_prompt* to Ollama, letting it call MCP tools as needed.

    Returns the final text answer produced by the model.

    *on_event* is an optional async callback that receives progress events so
    that callers (e.g. the web frontend) can stream tool call activity in real
    time.  Each event is a ``dict`` with at least a ``"type"`` key:

    * ``{"type": "tool_call",   "name": "…", "args": {…}}``
    * ``{"type": "tool_result", "name": "…", "content": "…"}``
    """
    tools_meta = await mcp_client.list_tools(client)
    ollama_tools = _mcp_tools_to_ollama(tools_meta)

    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    ollama_client = ollama_lib.Client(host=host)

    _json_call_re = re.compile(
        r'[{"\']?\s*(?:name|function)\s*["\']?\s*:',
        re.IGNORECASE,
    )

    for _ in range(max_iterations):
        response = ollama_client.chat(
            model=model,
            messages=messages,
            tools=ollama_tools,
        )

        assistant_message = response.message

        if not assistant_message.tool_calls:
            content = assistant_message.content or ""
            if _json_call_re.search(content):
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Based on the search results you already received, "
                            "please write a complete, human-readable answer to "
                            "the original question. Do not output any JSON or "
                            "function call syntax."
                        ),
                    }
                )
                continue
            return content

        tool_calls_serialised = []
        for tc in assistant_message.tool_calls:
            tool_calls_serialised.append(
                {
                    "function": {
                        "name": tc.function.name,
                        "arguments": dict(tc.function.arguments),
                    }
                }
            )
        assistant_dict: dict = {
            "role": "assistant",
            "content": assistant_message.content or "",
        }
        if tool_calls_serialised:
            assistant_dict["tool_calls"] = tool_calls_serialised
        messages.append(assistant_dict)

        for tool_call in assistant_message.tool_calls:
            fn = tool_call.function
            tool_name = fn.name
            tool_args = _normalize_tool_args(fn.arguments)

            print(f"  [tool call] {tool_name}({json.dumps(tool_args)})")
            if on_event:
                await on_event({"type": "tool_call", "name": tool_name, "args": tool_args})

            result = await mcp_client.call_tool(client, tool_name, tool_args)

            print(f"  [tool result] {result[:500]}{'...' if len(result) > 500 else ''}")
            if on_event:
                await on_event({"type": "tool_result", "name": tool_name, "content": result})

            messages.append(
                {
                    "role": "tool",
                    "name": tool_name,
                    "content": result,
                }
            )

    return assistant_message.content or "(max iterations reached)"
