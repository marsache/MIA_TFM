# Ollama + MCP – Local Song Dataset RAG Agent

Interactive RAG (Retrieval-Augmented Generation) agent that uses a **local
Ollama model** to answer questions about Spanish folk songs by searching a
local dataset through an **MCP server** built with
[FastMCP](https://github.com/jlowin/fastmcp).

All searches are performed **exclusively on the local dataset** – no external
network requests are made.

## Dataset

The `datasets/` directory contains two collections:

| Collection | Format | Contents |
|---|---|---|
| `para nlp/cancionero básico de Castilla y León` | MusicXML (`.xml`) | 316 traditional songs from Castilla y León, organised by thematic category (work songs, life-cycle songs, narrative songs, dance songs, etc.) |
| `Muiñeiras/Muiñeiras` | MuseScore (`.mscz`) | 76 Galician muiñeira tunes from historical cancioneros (Archivo Irlanda, Cancionero de Torner, Cancionero Sampedro Casto) |

Metadata extracted per song: **title**, **collection**, **category**,
**subcollection**, **key**, **time signature**, **tempo** (where available),
and **lyrics** (for MusicXML files).

## Architecture

```
┌──────────┐   prompt    ┌───────────────┐   tool call   ┌─────────────┐
│  User    │ ──────────► │  Ollama LLM   │ ────────────► │  MCP Client │
│  (REPL/  │ ◄────────── │  (llama3.2)   │ ◄──────────── │  (FastMCP)  │
│  Web UI) │   answer    └───────────────┘   result      └──────┬──────┘
└──────────┘                                                    │
                                                         ┌──────▼──────┐
                                                         │  MCP Server │
                                                         │  (FastMCP)  │
                                                         │             │
                                                         │  RAG Tools: │
                                                         │  • search   │
                                                         │  • details  │
                                                         │  • filters  │
                                                         │  • overview │
                                                         └──────┬──────┘
                                                                │
                                                         ┌──────▼──────┐
                                                         │  RAG Engine │
                                                         │  (TF-IDF)   │
                                                         └──────┬──────┘
                                                                │
                                                         ┌──────▼──────┐
                                                         │  Dataset    │
                                                         │  Parser     │
                                                         │  (.xml/.mscz│
                                                         └─────────────┘
```

### Components

| File | Description |
|---|---|
| `config.py` | Central configuration (model name, host, dataset paths). |
| `dataset_parser.py` | Parses MusicXML and MuseScore files; extracts title, key, time, lyrics, etc. |
| `rag_engine.py` | TF-IDF–based in-memory search engine over the parsed dataset. |
| `mcp_server.py` | FastMCP server that exposes RAG tools. |
| `mcp_client.py` | Thin wrapper around `fastmcp.Client`. |
| `ollama_client.py` | Bridges Ollama's tool-calling API with the MCP client. |
| `app.py` | CLI REPL entry-point. |
| `web_app.py` | FastAPI + WebSocket web frontend. |
| `static/index.html` | Chat web UI. |

### Available MCP Tools

| Tool | Description |
|---|---|
| `search_songs(query, max_results)` | Full-text search over title, lyrics, category, key, time signature. |
| `get_song_details(song_id)` | Full metadata + lyrics for one song. |
| `list_categories()` | All collections, categories, subcollections with counts. |
| `search_by_musical_attributes(key, time_signature, collection, category)` | Filter by musical or structural attributes. |
| `get_dataset_overview()` | Aggregate statistics (totals, key distribution, time-signature distribution). |

## Prerequisites

* **Python 3.10+**
* **Ollama** running locally (`ollama serve`) with a model that supports tool
  calling (e.g. `llama3.2`).

## Setup

```bash
cd ollama_mcp_local_dataset

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Pull the Ollama model (if not already available)
ollama pull llama3.2
```

## Usage

### CLI (REPL)

```bash
python app.py
```

Example questions:

```
You: ¿Qué canciones hay sobre bodas?
You: Muéstrame canciones en compás de 6/8
You: ¿Cuántas canciones tiene el dataset?
You: Busca muiñeiras del Cancionero de Torner
You: Dame la letra completa de la canción número 42
You: ¿Qué categorías existen en el Cancionero de Castilla y León?
You: Busca canciones en tonalidad de Sol mayor
```

### Web UI

```bash
uvicorn web_app:app --reload
```

Then open **http://localhost:8000** in your browser.

## How It Works

1. At startup, `dataset_parser.py` scans both dataset directories, parses
   every MusicXML and MuseScore file, and extracts structured metadata.
2. `rag_engine.py` builds an in-memory TF-IDF index over all songs, enabling
   fast full-text retrieval without any external database.
3. When the user asks a question, the Ollama model calls the appropriate MCP
   tool(s), retrieves relevant songs from the local dataset, and uses those
   results to compose a factual answer.
4. No external network requests are ever made – all information comes from
   the local `datasets/` directory.
