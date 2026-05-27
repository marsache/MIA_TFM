"""
Main application – Interactive Ollama + MCP agent.

Run this script to start a REPL where you can ask questions about
Ibero-American popular songs.  Ollama will use MCP tools served by
``mcp_server.py`` to find and analyse songs before answering.

Usage::

    python app.py

Type ``exit`` or ``quit`` to leave the REPL.
"""

from __future__ import annotations

import asyncio

from fastmcp import Client

from mcp_server import mcp  # import the FastMCP server instance
from ollama_client import run_agent
from config import OLLAMA_MODEL


async def main() -> None:
    """Run the interactive agent loop."""
    # The Client can take a FastMCP server directly (in-process transport),
    # so there is no need to start a separate process or open a network port.
    client = Client(mcp)

    print("=" * 60)
    print("  Ollama + MCP Song Search Agent")
    print(f"  Model : {OLLAMA_MODEL}")
    print("  Type 'exit' or 'quit' to leave.")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        print()
        answer = await run_agent(user_input, client)
        print(f"\nAssistant: {answer}\n")


if __name__ == "__main__":
    asyncio.run(main())
