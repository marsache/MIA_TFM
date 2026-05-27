# Ollama + MCP (FastMCP) – Song Search Agent

Interactive agent that uses a **local Ollama model** to answer questions about
Ibero-American popular songs by calling tools exposed through an
**MCP server** built with [FastMCP](https://github.com/jlowin/fastmcp).

## Architecture

```
┌──────────┐   prompt    ┌───────────────┐   tool call   ┌─────────────┐
│  User    │ ──────────► │  Ollama LLM   │ ────────────► │  MCP Client │
│  (REPL)  │ ◄────────── │  (llama3.2)   │ ◄──────────── │  (FastMCP)  │
└──────────┘   answer    └───────────────┘   result      └──────┬──────┘
                                                                │
                                                         ┌──────▼──────┐
                                                         │  MCP Server │
                                                         │  (FastMCP)  │
                                                         │             │
                                                         │  Tools:     │
                                                         │  • search   │
                                                         │  • analyse  │
                                                         │  • genres   │
                                                         │  • country  │
                                                         └─────────────┘
```

### Components

| File | Description |
|---|---|
| `mcp_server.py` | FastMCP server that registers the song-search and analysis tools. |
| `mcp_client.py` | Thin wrapper around `fastmcp.Client` with helpers to list and call tools. |
| `ollama_client.py` | Bridges Ollama's tool-calling API with the MCP client, implementing the agentic loop. |
| `app.py` | Entry-point REPL that ties everything together. |
| `config.py` | Central configuration (model name, host, server name). |

### Available MCP Tools

| Tool | Description |
|---|---|
| `search_songs(query)` | Search songs by title or artist (substring match). |
| `get_song_by_id(song_id)` | Get full details of a song by its ID. |
| `list_genres()` | List all distinct genres in the catalogue. |
| `search_by_country(country)` | Filter songs by country of origin. |
| `analyze_song(song_id)` | Return a musical-analysis summary (key, tempo, genre). |

## Prerequisites

* **Python 3.10+**
* **Ollama** running locally (`ollama serve`) with a model that supports tool
  calling (e.g. `llama3.2`).

## Setup

```bash
cd ollama_mcp

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Pull the Ollama model (if not already available)
ollama pull llama3.2
```

## Usage

```bash
python app.py
```

You will see an interactive prompt.  Try questions like:

```
You: What Mexican songs do you have?
You: Analyse the song La Bamba
You: What genres are available?
You: Find songs from Cuba
```

Type `exit` or `quit` to leave.

## How It Works

1. **`app.py`** creates a `fastmcp.Client` pointing at the in-process
   `FastMCP` server and starts a REPL.
2. Each user message is passed to **`ollama_client.run_agent`**, which:
   - Discovers MCP tools via the client and converts their schemas to
     Ollama's tool-calling format.
   - Sends the conversation to Ollama's `chat` endpoint with the tool
     definitions attached.
   - When Ollama responds with tool calls, executes them through the MCP
     client and feeds the results back.
   - Repeats until Ollama produces a final text answer.
3. The **MCP server** handles each tool call against a simulated in-memory
   song catalogue.
