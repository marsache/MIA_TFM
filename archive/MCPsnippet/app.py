from mcp.server.fastmcp import FastMCP
from ollama_manager import OllamaManager
from tools.wikidata import wikidata_mcp_tool_json
import json

mcp = FastMCP("Guía Folk Iberoamericano")
manager = OllamaManager(model="qwen3:8b")

# ──────────────────────────────────────────────
# Definición de tools disponibles para el LLM
# ──────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "wikidata_search",
            "description": (
                "Busca información en Wikidata sobre un artista, canción, "
                "instrumento, región o cualquier entidad relacionada con la "
                "música folk iberoamericana. Devuelve propiedades y enlaces "
                "de Wikipedia."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Nombre en inglés de la entidad a buscar (ej: 'Atahualpa Yupanqui')"
                    }
                },
                "required": ["label"]
            }
        }
    }
]

# ──────────────────────────────────────────────
# Dispatcher: ejecuta la tool que pidió el LLM
# ──────────────────────────────────────────────

def execute_tool(tool_name: str, tool_args: dict) -> str:
    if tool_name == "wikidata_search":
        return wikidata_mcp_tool_json(tool_args["label"])
    return json.dumps({"error": f"Tool desconocida: {tool_name}"})

# ──────────────────────────────────────────────
# Lógica del agente (el "loop" de razonamiento)
# ──────────────────────────────────────────────

def run_agent(historial: list) -> str:
    """
    Ejecuta el ciclo agente:
    1. LLM decide si responde o llama a una tool
    2. Si llama a una tool → ejecutarla → devolver resultado al LLM
    3. Repetir hasta que el LLM dé respuesta final (máx. 5 iteraciones)
    """
    MAX_ITERATIONS = 5

    for _ in range(MAX_ITERATIONS):
        response = manager.chat(historial, tools=TOOLS)

        # Sin tool_calls → respuesta final de texto
        if not response.get("tool_calls"):
            return response.get("content", "")

        # Añadir el mensaje del asistente con las tool_calls al historial
        historial.append({
            "role": "assistant",
            "content": response.get("content", ""),
            "tool_calls": response["tool_calls"]
        })

        # Ejecutar cada tool y añadir resultados al historial
        for tool_call in response["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]

            # Ollama puede devolver args como string JSON o como dict
            if isinstance(tool_args, str):
                tool_args = json.loads(tool_args)

            tool_result = execute_tool(tool_name, tool_args)

            historial.append({
                "role": "tool",
                "content": tool_result,
                "name": tool_name  # Ollama usa "name" para identificar la tool
            })

    return "No se pudo generar una respuesta tras varios intentos."

# ──────────────────────────────────────────────
# Tool MCP expuesta al cliente (Claude, Cursor…)
# ──────────────────────────────────────────────

@mcp.tool()
def chat_folk(mensaje: str, historial_previo: str = "[]") -> str:
    """
    Chatea con un guía experto en música folk iberoamericana.
    El asistente puede buscar información en Wikidata automáticamente.

    Args:
        mensaje: Mensaje del usuario.
        historial_previo: JSON con el historial anterior de la conversación.
    """
    historial = json.loads(historial_previo)

    # Añadir system prompt si es el primer mensaje
    if not historial:
        historial.append({
            "role": "system",
            "content": (
                "Eres un guía experto en canciones de la cultura folk iberoamericana. "
                "Cuando necesites datos concretos sobre artistas, canciones o instrumentos, "
                "usa la herramienta wikidata_search para obtener información actualizada."
            )
        })

    historial.append({"role": "user", "content": mensaje})

    respuesta = run_agent(historial)

    historial.append({"role": "assistant", "content": respuesta})

    # Devuelve respuesta + historial actualizado para la siguiente llamada
    return json.dumps({
        "reply": respuesta,
        "historial": historial
    }, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()