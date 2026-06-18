import asyncio
import sys
import json
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from google import genai
from google.genai import types

import time
from google.genai.errors import ServerError

BASE_DIR = Path(__file__).resolve().parents[2]

sys.path.append(str(BASE_DIR))

from ollama_sqlite.info_columnas import RELACIONES

# GEMINI CLIENT
client_gemini = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)


def extraer_tool_calls(response):
    """Extrae function_calls desde respuesta Gemini"""
    llamadas = []

    if not response.candidates:
        return llamadas

    for part in response.candidates[0].content.parts:
        fc = getattr(part, "function_call", None)

        if fc:
            llamadas.append({
                "name": fc.name,
                "args": dict(fc.args)
            })

    return llamadas


# async def preguntar_gemini(prompt, herramientas):
#     return client_gemini.models.generate_content(
#         model="gemini-2.5-flash",
#         contents=prompt,
#         config={
#             "tools": herramientas
#         }
#     )

async def preguntar_gemini(prompt, herramientas, retries=5):
    for i in range(retries):
        try:
            return client_gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"tools": herramientas}
            )
        except ServerError as e:
            if i == retries - 1:
                raise
            wait = 2 ** i
            print(f"[Gemini ocupado] retry en {wait}s...")
            time.sleep(wait)


def convertir_a_gemini_contents(historial):
    contents = []

    for msg in historial:
        role = msg["role"]
        text = msg.get("content", "")

        if text is None:
            continue

        if role == "system":
            role = "user"
            text = "INSTRUCCIONES DEL SISTEMA:\n\n" + text

        contents.append(
            types.Content(
                role=role,
                parts=[types.Part(text=str(text))]
            )
        )

    return contents


# HELPERS MCP
def construir_mini_esquema(columnas_json: str) -> str:
    columnas = json.loads(columnas_json)
    tablas = {}

    for col in columnas:
        tabla = col["tabla"]
        tablas.setdefault(tabla, []).append(
            f"- {col['columna']} ({col.get('tipo', 'TEXT')})"
        )

    partes = ["ESQUEMA RELEVANTE\n"]

    for tabla, cols in tablas.items():
        partes.append(f"Tabla: {tabla}")
        partes.extend(cols)
        partes.append("")

    tablas_presentes = set(tablas.keys())
    joins = []

    for rel in RELACIONES:
        if rel["tabla_a"] in tablas_presentes and rel["tabla_b"] in tablas_presentes:
            joins.append(rel["join"])

    if joins:
        partes.append("RELACIONES:")
        partes.extend([f"- {j}" for j in joins])

    return "\n".join(partes)


async def recuperar_columnas_relevantes(session, pregunta):
    resultado = await session.call_tool(
        "buscar_columnas_relevantes",
        {
            "pregunta": pregunta,
            "top_k": 5
        }
    )

    texto = ""
    for bloque in resultado.content:
        if hasattr(bloque, "text"):
            texto += bloque.text

    return texto


# MAIN CHAT
async def iniciar_chat_mcp():

    parametros_servidor = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"],
        env=None
    )

    print("Conectando al servidor MCP y cargando Gemini...")

    async with stdio_client(parametros_servidor) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:

            await session.initialize()

            # TOOLS MCP -> GEMINI
            mcp_tools = await session.list_tools()
            herramientas_mcp = [
                t for t in mcp_tools.tools
                if t.name != "buscar_columnas_relevantes"
            ]

            function_declarations = [
                types.FunctionDeclaration(
                    name=t.name,
                    description=t.description,
                    parameters=t.inputSchema
                )
                for t in herramientas_mcp
            ]

            herramientas_gemini = [
                types.Tool(
                    function_declarations=function_declarations
                )
            ]

            print("\nSistema listo (Gemini + MCP)")
            print("Tools:", [t.name for t in herramientas_mcp])

            # SYSTEM PROMPT
            system_prompt = """
            Eres un asistente experto en musicología computacional.

            IMPORTANTE:

            Cuando necesites información de la base de datos:

            1. Genera SQL.
            2. Ejecuta ejecutar_consulta_sql.
            3. Lee el resultado.
            4. Responde al usuario usando lenguaje natural.

            NO muestres SQL al usuario.

            NO expliques cómo harías la consulta.

            NO propongas consultas alternativas.

            Antes de ejecutar cualquier consulta SQL debes llamar SIEMPRE a obtener_esquema y usarlo como fuente de verdad del esquema.

            La respuesta final debe ser siempre una respuesta normal para un usuario final.

            Si la consulta devuelve registros:
            - Resume la información encontrada.
            - Muestra listas o tablas si es útil.

            Si la herramienta devuelve filas de una consulta:
            - Resume los resultados.
            - No expliques la estructura de los datos.
            - No actúes como analizador de JSON.
            - Contesta como un asistente musical para un usuario final.

            Si la consulta no devuelve registros:
            - Indica claramente que no se encontraron resultados.

            REGLAS IMPORTANTES:
            - Cuando tengas resultados de la base de datos, responde SIEMPRE en lenguaje natural para el usuario.
            - Nunca expliques el formato de los datos.
            - Nunca describas columnas o estructuras técnicas.
            - Devuelve solo una respuesta final útil (lista o resumen).

            IMPORTANTE:
            Los resultados devueltos por las herramientas son datos internos.
            Nunca describas el JSON, la estructura de los registros ni expliques el formato de los datos salvo que el usuario lo solicite explícitamente.

            Después de recibir el resultado de una herramienta:

            1. Interpreta los datos.
            2. Responde a la pregunta original del usuario.
            3. Extrae únicamente la información relevante.
            4. Utiliza lenguaje natural.
            5. No muestres código, SQL ni explicaciones sobre JSON.

            Ejemplo:

            Usuario: "dame obras que tengan anacrusa"

            Incorrecto:
            "Este JSON contiene varias piezas musicales..."

            Correcto:
            "Se encontraron las siguientes obras con anacrusa: ..."
            """

            mensajes = [
                {
                    "role": "user",
                    "content": "INSTRUCCIONES DEL SISTEMA:\n\n" + system_prompt
                }
            ]

            # CHAT LOOP
            while True:

                usuario_input = input("\nUsuario (salir para terminar): ")
                if usuario_input.lower() in ["salir", "exit", "quit"]:
                    break

                columnas = await recuperar_columnas_relevantes(
                    session,
                    usuario_input
                )

                mini_esquema = construir_mini_esquema(columnas)

                prompt_usuario = f"""
                Pregunta del usuario:
                {usuario_input}

                {mini_esquema}

                INSTRUCCIONES:

                - Usa únicamente las tablas y columnas anteriores.
                - Si necesitas unir tablas, utiliza exclusivamente
                las relaciones indicadas.
                - No inventes tablas.
                - No inventes columnas.
                - Genera SQL válido para SQLite.
"""

                mensajes.append({
                    "role": "user",
                    "content": prompt_usuario
                })

                print("Consultando Gemini...")

                contents = convertir_a_gemini_contents(mensajes)

                print("\n--- DEBUG CONTENTS ---")
                for c in contents:
                    print(c)
                respuesta = await preguntar_gemini(
                    prompt=contents,
                    herramientas=herramientas_gemini
                )

                tool_calls = extraer_tool_calls(respuesta)

                # TOOL LOOP
                while tool_calls:

                    mensajes.append({
                        "role": "model",
                        "content": respuesta.text
                    })

                    for call in tool_calls:

                        nombre = call["name"]
                        args = call["args"]

                        # limpieza SQL tool
                        if (
                            isinstance(args, dict)
                            and "query_sql" in args
                            and isinstance(args["query_sql"], dict)
                            and "value" in args["query_sql"]
                        ):
                            args["query_sql"] = args["query_sql"]["value"]

                        print(f"\nTool: {nombre}")
                        print("Args:", args)

                        resultado = await session.call_tool(
                            nombre,
                            arguments=args
                        )

                        texto = "".join(
                            b.text for b in resultado.content if hasattr(b, "text")
                        )

                        tool_response = {
                            "role": "user",
                            "content": f"RESULTADO TOOL {nombre}:\n{texto}"
                        }

                        mensajes.append(tool_response)

                    contents = convertir_a_gemini_contents(mensajes)

                    print("\n--- DEBUG CONTENTS ---")
                    for c in contents:
                        print(c)
                    respuesta = await preguntar_gemini(
                        prompt=contents,
                        herramientas=herramientas_gemini
                    )

                    tool_calls = extraer_tool_calls(respuesta)

                # FINAL RESPONSE
                print("\nRespuesta:")
                print(respuesta.text)

                mensajes.append({
                    "role": "model",
                    "content": respuesta.text
                })


# ENTRYPOINT
if __name__ == "__main__":
    asyncio.run(iniciar_chat_mcp())