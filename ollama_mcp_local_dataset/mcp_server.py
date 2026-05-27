"""
MCP Server – Local Song Dataset RAG Tools.

This module creates a FastMCP server that exposes tools for searching and
querying the local song dataset using Retrieval-Augmented Generation (RAG).
All tools operate exclusively on the local dataset stored in the
``datasets/`` directory; no external network requests are made.

Available tools
---------------
* ``search_songs``              – full-text search over the entire dataset.
* ``get_song_details``          – retrieve complete information for one song.
* ``list_categories``           – list collections, categories, and counts.
* ``search_by_musical_attributes`` – filter by key, time signature, or
                                     collection.
* ``get_dataset_overview``      – statistics about the whole dataset.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP

from config import MCP_SERVER_NAME
from rag_engine import RAGEngine

# Initialise the RAG engine once at import time so the dataset is loaded and
# indexed only once even when multiple tool calls are made.
_engine = RAGEngine()

mcp = FastMCP(MCP_SERVER_NAME)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_song(song: dict, *, include_lyrics: bool = False) -> str:
    """Return a human-readable string summary of *song*."""
    lines: list[str] = [
        f"ID: {song['id']}",
        f"Title: {song['title']}",
        f"Collection: {song['collection']}",
    ]
    if song.get("category"):
        lines.append(f"Category: {song['category']}")
    if song.get("subcollection"):
        lines.append(f"Subcollection: {song['subcollection']}")
    if song.get("key"):
        lines.append(f"Key: {song['key']}")
    if song.get("time_signature"):
        lines.append(f"Time signature: {song['time_signature']}")
    if song.get("tempo_bpm") is not None:
        lines.append(f"Tempo: {song['tempo_bpm']} BPM")
    if include_lyrics and song.get("lyrics"):
        # Truncate very long lyrics for readability
        lyrics = song["lyrics"]
        if len(lyrics) > 800:
            lyrics = lyrics[:800] + "…"
        lines.append(f"Lyrics excerpt: {lyrics}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_songs(query: str, max_results: int = 10) -> str:
    """Search the local song dataset by title, lyrics, category, or any keyword.

    This is the primary retrieval tool.  Pass any relevant words from the
    user's question as *query* (song title, lyric fragments, category name,
    thematic keywords, etc.).  Returns the most relevant songs from the
    local dataset.

    Args:
        query: Search text – title, lyrics fragment, category, keyword.
        max_results: Maximum number of songs to return (default 10, max 20).

    Returns:
        A numbered list of matching songs with their key metadata.
    """
    max_results = min(max(1, max_results), 20)
    results = _engine.search(query, max_results=max_results)
    if not results:
        return f'No songs found matching "{query}" in the local dataset.'
    lines = [f"Found {len(results)} song(s) matching \"{query}\":\n"]
    for i, song in enumerate(results, 1):
        lines.append(f"{i}. {_fmt_song(song)}\n")
    return "\n".join(lines)


@mcp.tool()
def get_song_details(song_id: int) -> str:
    """Retrieve complete details for a song identified by its numeric ID.

    Use *search_songs* first to obtain the ID, then call this tool to get
    full metadata including lyrics and file path.

    Args:
        song_id: The integer ID of the song (as returned by search_songs).

    Returns:
        Full metadata and lyrics for the requested song.
    """
    song = _engine.get_by_id(song_id)
    if song is None:
        return f"No song found with ID {song_id}."
    return _fmt_song(song, include_lyrics=True)


@mcp.tool()
def list_categories() -> str:
    """List all collections, categories, and subcollections in the local dataset.

    Use this tool to understand the structure of the dataset, or when the
    user asks about the available types of songs, genres, or thematic groups.

    Returns:
        A structured summary of all categories with song counts.
    """
    cats = _engine.list_categories()
    lines: list[str] = ["Dataset structure:\n"]
    for coll_name, coll_info in cats.items():
        lines.append(f"Collection: {coll_name} ({coll_info['total']} songs)")
        for cat_name, cat_info in sorted(coll_info["categories"].items()):
            lines.append(f"  Category: {cat_name} ({cat_info['total']} songs)")
            for sub in cat_info["subcategories"]:
                lines.append(f"    Subcollection: {sub}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def search_by_musical_attributes(
    key: str = "",
    time_signature: str = "",
    collection: str = "",
    category: str = "",
    max_results: int = 10,
) -> str:
    """Filter the local dataset by musical attributes.

    Use this tool when the user asks about songs with a specific key,
    time signature, or belonging to a particular collection or category.
    All parameters are optional; supply only those relevant to the query.

    Args:
        key: Key name to filter by (e.g. «G major», «D minor»).
             A partial match is used, so «G» matches «G major».
        time_signature: Time signature to filter by (e.g. «3/4», «6/8»).
        collection: Collection name filter (e.g. «Muiñeiras»,
                    «Castilla y León»).
        category: Category or subcollection name filter (e.g.
                  «RUEDA DE AÑOS», «Cancionero de Torner»).
        max_results: Maximum number of results to return (default 10).

    Returns:
        A list of matching songs with their key metadata.
    """
    max_results = min(max(1, max_results), 20)
    results = _engine.search(
        "",
        max_results=max_results,
        collection=collection,
        category=category,
        key=key,
        time_signature=time_signature,
    )
    filters_desc = ", ".join(
        f"{k}={v!r}"
        for k, v in [
            ("key", key), ("time_signature", time_signature),
            ("collection", collection), ("category", category),
        ]
        if v
    )
    if not results:
        return f"No songs found matching filters: {filters_desc or '(none)'}."
    lines = [f"Found {len(results)} song(s) matching {filters_desc or '(no filters)'}:\n"]
    for i, song in enumerate(results, 1):
        lines.append(f"{i}. {_fmt_song(song)}\n")
    return "\n".join(lines)


@mcp.tool()
def get_dataset_overview() -> str:
    """Return statistics and a high-level overview of the local song dataset.

    Use this tool when the user asks general questions about the dataset,
    such as how many songs it contains, which keys are most common, or
    what time signatures appear.

    Returns:
        A text summary of dataset statistics.
    """
    stats = _engine.get_statistics()
    cats = _engine.list_categories()

    lines: list[str] = ["=== Local Song Dataset Overview ===\n"]
    lines.append(f"Total songs: {stats['total_songs']}")
    lines.append(f"Songs with lyrics: {stats['songs_with_lyrics']}\n")

    lines.append("Collections:")
    for coll_name, coll_info in cats.items():
        lines.append(f"  • {coll_name}: {coll_info['total']} songs")
    lines.append("")

    if stats["key_distribution"]:
        lines.append("Most common keys:")
        for key, count in list(stats["key_distribution"].items())[:8]:
            lines.append(f"  • {key}: {count} songs")
        lines.append("")

    if stats["time_signature_distribution"]:
        lines.append("Time signatures:")
        for ts, count in list(stats["time_signature_distribution"].items())[:8]:
            lines.append(f"  • {ts}: {count} songs")

    return "\n".join(lines)
