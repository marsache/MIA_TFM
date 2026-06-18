import asyncio
import sys
import ollama

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODELO = "qwen3:8b"


async def obtener_esquema(session):
    resultado = await session.call_tool("obtener_esquema", arguments={})

    texto = ""

    for bloque in resultado.content:
        if hasattr(bloque, "text"):
            texto += bloque.text

    return texto


async def ejecutar_sql(session, sql):

    resultado = await session.call_tool(
        "ejecutar_consulta_sql",
        arguments={"query_sql": sql}
    )

    texto = ""

    for bloque in resultado.content:
        if hasattr(bloque, "text"):
            texto += bloque.text

    return texto


def generar_sql(pregunta_usuario, esquema):

    prompt = f"""
Eres un experto en SQLite.

Debes generar EXCLUSIVAMENTE una consulta SQL.

REGLAS:

- Devuelve solo SQL.
- No uses markdown.
- No expliques nada.
- Usa únicamente tablas y columnas existentes.
- Si la pregunta no puede responderse con los datos disponibles, devuelve:

SELECT 'NO_DISPONIBLE_EN_ESQUEMA' AS error;

ESQUEMA:

{esquema}

PREGUNTA:

{pregunta_usuario}
"""

    respuesta = ollama.chat(
        model=MODELO,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        options={
            "temperature": 0
        }
    )

    return respuesta["message"]["content"].strip()


def redactar_respuesta(pregunta_usuario, resultado_sql):

    prompt = f"""
Responde al usuario utilizando únicamente
los resultados SQL proporcionados.

No inventes datos.

Si el resultado está vacío, dilo claramente.

Pregunta original:

{pregunta_usuario}

Resultado SQL:

{resultado_sql}
"""

    respuesta = ollama.chat(
        model=MODELO,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        options={
            "temperature": 0.2
        }
    )

    return respuesta["message"]["content"]


async def main():

    parametros = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"]
    )

    async with stdio_client(parametros) as (read_stream, write_stream):

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            await session.initialize()

            print("Cargando esquema...")

            esquema = await obtener_esquema(session)

            print("Sistema listo.")

            while True:

                pregunta = input("\nUsuario: ")

                if pregunta.lower() in ["salir", "exit"]:
                    break

                print("\n[1] Generando SQL...")

                sql = generar_sql(
                    pregunta,
                    esquema
                )

                print(sql)

                print("\n[2] Ejecutando SQL...")

                resultado = await ejecutar_sql(
                    session,
                    sql
                )

                print(resultado)

                print("\n[3] Generando respuesta...")

                respuesta_final = redactar_respuesta(
                    pregunta,
                    resultado
                )

                print("\nAsistente:")
                print(respuesta_final)


if __name__ == "__main__":
    asyncio.run(main())