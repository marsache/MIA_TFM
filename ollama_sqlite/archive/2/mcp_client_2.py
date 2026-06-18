import asyncio
import sys
import ollama

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODELO = "qwen3:8b"


# -----------------------------
# UTIL: limpiar texto MCP
# -----------------------------
def extraer_texto(resultado):
    texto = ""
    for bloque in resultado.content:
        if hasattr(bloque, "text"):
            texto += bloque.text
    return texto.strip()


# -----------------------------
# ESQUEMA
# -----------------------------
async def obtener_esquema(session):
    resultado = await session.call_tool("obtener_esquema", arguments={})
    return extraer_texto(resultado)


# -----------------------------
# SQL EXEC
# -----------------------------
async def ejecutar_sql(session, sql):
    resultado = await session.call_tool(
        "ejecutar_consulta_sql",
        arguments={"query_sql": sql}
    )
    return extraer_texto(resultado)


# -----------------------------
# MODELO → SQL
# -----------------------------
def generar_sql(pregunta_usuario, esquema):
    prompt = f"""
Eres un experto en SQLite.

Genera exclusivamente una consulta SQL válida.

REGLAS:
- Solo SQL
- Sin markdown
- Sin explicaciones
- Usa solo tablas y columnas del esquema
- Si no es posible responder:

SELECT 'NO_DISPONIBLE_EN_ESQUEMA' AS error;

ESQUEMA:
{esquema}

PREGUNTA:
{pregunta_usuario}
"""

    respuesta = ollama.chat(
        model=MODELO,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0}
    )

    return respuesta["message"]["content"].strip()


# -----------------------------
# MODELO → respuesta final
# -----------------------------
def redactar_respuesta(pregunta_usuario, resultado):
    prompt = f"""
Responde al usuario usando SOLO los datos proporcionados.

No inventes información.

Pregunta:
{pregunta_usuario}

Datos:
{resultado}
"""

    respuesta = ollama.chat(
        model=MODELO,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.2}
    )

    return respuesta["message"]["content"].strip()


# -----------------------------
# ROUTER DE INTENCIÓN (CLAVE)
# -----------------------------
def decidir_tool(pregunta: str):
    p = pregunta.lower()

    # Tools semánticas (MCP)
    if "hemiolia" in p:
        return "consultar_hemiolia"

    if "sincopa" in p:
        return "consultar_sincopas"

    if "voz" in p or "lirica" in p:
        return "consultar_lirica_voz"

    if "tendencia" in p:
        return "consultar_tendencia_melodica"

    # fallback SQL
    return "sql"


# -----------------------------
# MAIN LOOP
# -----------------------------
async def main():

    parametros = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server_2.py"]
    )

    async with stdio_client(parametros) as (read_stream, write_stream):

        async with ClientSession(read_stream, write_stream) as session:

            await session.initialize()

            print("Cargando esquema...")

            esquema = await obtener_esquema(session)

            print("Sistema listo.")

            while True:

                pregunta = input("\nUsuario: ")

                if pregunta.lower() in ["salir", "exit"]:
                    break

                print("\n[1] Decidiendo estrategia...")

                tool = decidir_tool(pregunta)

                # -------------------------
                # CASO 1: SQL genérico
                # -------------------------
                if tool == "sql":

                    print("[SQL] Generando consulta...")
                    sql = generar_sql(pregunta, esquema)
                    print(sql)

                    print("\n[SQL] Ejecutando...")
                    resultado = await ejecutar_sql(session, sql)

                # -------------------------
                # CASO 2: TOOL MCP
                # -------------------------
                else:

                    print(f"[MCP TOOL] Usando {tool}...")

                    # versión simple: pide id si hace falta
                    try:
                        pieza_id = int(input("ID de la pieza: "))
                    except:
                        print("ID inválido")
                        continue

                    resultado = await session.call_tool(
                        tool,
                        {"id_pieza_solicitada": pieza_id}
                    )

                    resultado = extraer_texto(resultado)

                # -------------------------
                # RESPUESTA FINAL
                # -------------------------
                print("\n[3] Generando respuesta...")

                respuesta = redactar_respuesta(pregunta, resultado)

                print("\nAsistente:")
                print(respuesta)


if __name__ == "__main__":
    asyncio.run(main())