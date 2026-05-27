"""Configuration for the Ollama MCP Local Dataset project."""

from pathlib import Path

# Ollama settings
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2"

# MCP Server settings
MCP_SERVER_NAME = "Local Song Dataset RAG Server"

# Dataset paths
_BASE_DIR = Path(__file__).parent
DATASETS_DIR = _BASE_DIR.parent / "datasets"
CANCIONERO_DIR = DATASETS_DIR / "para nlp" / "cancionero básico de Castilla y León"
MUINEIRAS_DIR = DATASETS_DIR / "Muiñeiras" / "Muiñeiras"

# RAG settings
RAG_MAX_RESULTS = 10
RAG_FUZZY_THRESHOLD = 0.35
