"""
Main application – Interactive Ollama + MCP RAG agent for local song dataset.

Run this script to start a REPL where you can ask questions about the local
song dataset (Cancionero básico de Castilla y León and Muiñeiras collection).
Ollama will use MCP tools to retrieve information from the local dataset
before answering.

Usage::

    python app.py

Type ``exit`` or ``quit`` to leave the REPL.
"""

from __future__ import annotations

import asyncio

from fastmcp import Client

from mcp_server import mcp
from ollama_client import run_agent
from config import OLLAMA_MODEL


async def main() -> None:
    """Run the interactive agent loop."""
    client = Client(mcp)

    print("=" * 60)
    print("  Ollama + MCP Local Song Dataset RAG Agent")
    print(f"  Model : {OLLAMA_MODEL}")
    print("  Dataset: Cancionero de Castilla y León + Muiñeiras")
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
