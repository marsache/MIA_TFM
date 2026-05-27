"""
Ollama ↔ MCP bridge.

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
    """Unwrap schema-dict arguments returned by some Ollama model versions.

    llama3.2 (and similar models) occasionally hallucinate the JSON-Schema
    property object as the argument value instead of a plain scalar.  Three
    degenerate forms are handled:

    1. **Dict with ``value`` key** – model followed the schema template and
       put the real value in a ``value`` field::

           {"query": {"type": "string", "description": "...", "value": "hello"}}
           → {"query": "hello"}

    2. **Dict without ``value`` key** – model put the intended value in the
       ``description`` field (skipped the ``value`` slot entirely)::

           {"query": {"type": "string", "description": "Amalio Ramiro"}}
           → {"query": "Amalio Ramiro"}

    3. **JSON-encoded string** – model serialised the whole schema object into
       a string before placing it in the argument slot::

           {"query": "{\"type\":\"string\",\"value\":\"El 11 de febrero\"}"}
           → {"query": "El 11 de febrero"}

    In all other cases the value is returned unchanged.
    """
    normalized: dict = {}
    for key, val in arguments.items():
        normalized[key] = _unwrap_schema_value(val)
    return normalized


def _unwrap_schema_value(val: object) -> object:
    """Recursively unwrap a single schema-dict or JSON-encoded schema value."""
    # Case 3: JSON-encoded string that wraps a schema object
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

    # Case 1: explicit ``value`` key alongside a type hint
    if has_type and "value" in val:
        return val["value"]

    # Case 2: no ``value`` key, but the model put the real value in
    # ``description`` (only credible when ``type`` hints at a scalar)
    if is_scalar_type and "description" in val and len(val) <= 3:
        # len ≤ 3 guards against real nested-object schemas that happen to
        # have a description; genuine property schemas usually have just
        # {type, description} or {type, description, value}
        return val["description"]

    return val


def _mcp_tools_to_ollama(mcp_tools: list[dict]) -> list[dict]:
    """Convert MCP tool schemas to the Ollama tool-calling format.

    Ollama expects each tool as::

        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": { <JSON Schema> }
            }
        }
    """
    ollama_tools: list[dict] = []
    for tool in mcp_tools:
        # Build a clean parameters schema from the MCP inputSchema
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
    # 1. Discover tools
    tools_meta = await mcp_client.list_tools(client)
    ollama_tools = _mcp_tools_to_ollama(tools_meta)

    # 2. Initialise conversation
    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are a helpful music research assistant. "
                "You have access to tools for searching and analysing "
                "Ibero-American popular songs. Use the tools when the "
                "user asks about songs, artists, genres, or countries. "
                "Always provide clear, informative answers in the same "
                "language the user used.\n\n"
                "Search strategy – ALWAYS follow these steps for every "
                "song-related query:\n"
                "1. Call search_songs to check the local catalogue. "
                "You MUST call this tool even if you expect no local results. "
                "Always pass the song title (or artist/keyword) from the "
                "user's question as the query – NEVER pass an empty string.\n"
                "2. Call search_bdpi to search the BDPI (Biblioteca Digital "
                "del Patrimonio Iberoamericano) database. "
                "You MUST call this tool for every song query.\n"
                "3. If the user asks about a medieval Iberian song, also "
                "call search_cantigas.\n"
                "4. Do NOT claim to have used both methods unless you "
                "actually called both tools.\n\n"
                "Using tool results:\n"
                "- After receiving tool results, write your final answer "
                "using the information from those results.\n"
                "- If search_bdpi returns a 'direct_search_url', always "
                "tell the user they can search the BDPI directly at that "
                "URL to find more information.\n"
                "- If search_bdpi returns pseudo-results with "
                "source 'BDPI (link fallback)', list them for the user as "
                "possible matches found on the BDPI website.\n"
                "- If search_bdpi returns a 'page_text_snippet', look "
                "there for relevant information about the song.\n"
                "- Only report that a song cannot be found after you have "
                "tried BOTH search_songs AND search_bdpi.\n\n"
                "IMPORTANT – after you receive tool results:\n"
                "- Write a normal prose response. Do NOT output raw JSON, "
                "function call syntax, or any text like "
                "'Llamando a la función …' or '{\"name\": …}' in your answer.\n\n"
                "IMPORTANT – tool calling rules:\n"
                "- Pass every tool argument as a plain scalar value "
                "(string, number, boolean), NOT as a JSON schema object.\n"
                "- Correct:   search_songs(query=\"La Bamba\")\n"
                "- Incorrect: search_songs(query={\"type\":\"string\","
                "\"value\":\"La Bamba\"})\n"
                "- Never wrap argument values in objects with keys like "
                "'type', 'description', or 'value'."
            ),
        },
        {"role": "user", "content": user_prompt},
    ]

    ollama_client = ollama_lib.Client(host=host)

    # Regex to detect when the model outputs a JSON-ish function-call description
    # as plain text rather than making a real structured tool call.
    _json_call_re = re.compile(
        r'[{"\']?\s*(?:name|function)\s*["\']?\s*:',
        re.IGNORECASE,
    )

    for _ in range(max_iterations):
        # 3. Call Ollama
        response = ollama_client.chat(
            model=model,
            messages=messages,
            tools=ollama_tools,
        )

        assistant_message = response.message

        # If no tool calls, check whether the model hallucinated a JSON call
        # as plain text.  If so, nudge it to give a real prose answer instead.
        if not assistant_message.tool_calls:
            content = assistant_message.content or ""
            if _json_call_re.search(content):
                # The model is "describing" a tool call in text.  Append its
                # confused response to the history and add an explicit nudge.
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
                continue  # retry with the nudge in the history
            return content

        # 4. Append the assistant turn.  Build the dict manually so that we
        #    never pass None-valued fields (some Ollama versions reject them).
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
        assistant_dict: dict = {"role": "assistant", "content": assistant_message.content or ""}
        if tool_calls_serialised:
            assistant_dict["tool_calls"] = tool_calls_serialised
        messages.append(assistant_dict)

        # 5. Execute each tool call and append the result.
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
