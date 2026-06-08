import asyncio
import sys
import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json
from info_columnas import RELACIONES

#MODELO_LLM = "qwen3:8b"
MODELO_LLM = "llama3.1:8b"

# SÓLO PARA FRONTEND
async def preguntar_mcp(usuario_input: str):

    parametros_servidor = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"],
        env=None
    )

    async with stdio_client(parametros_servidor) as (read_stream, write_stream):

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            await session.initialize()

            # Descubrir herramientas MCP
            mcp_tools_response = await session.list_tools()
            herramientas_mcp = mcp_tools_response.tools

            herramientas_mcp = [
                tool
                for tool in herramientas_mcp
                if tool.name != "buscar_columnas_relevantes"
            ]

            # Adaptar herramientas al formato de Ollama
            herramientas_ollama = []

            for tool in herramientas_mcp:
                herramientas_ollama.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })

            historial_mensajes = [{
                "role": "system",
                "content": """
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
            }]

            # Recuperación de columnas
            columnas_relevantes = await recuperar_columnas_relevantes(
                session,
                usuario_input
            )

            mini_esquema = construir_mini_esquema(
                columnas_relevantes
            )

            mensaje_enriquecido = f"""
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

            historial_mensajes.append({
                "role": "user",
                "content": mensaje_enriquecido
            })

            # Primera llamada a Ollama
            respuesta = ollama.chat(
                model=MODELO_LLM,
                messages=historial_mensajes,
                tools=herramientas_ollama
            )

            # Tool Calling Loop
            while respuesta.get("message", {}).get("tool_calls"):

                historial_mensajes.append(
                    respuesta["message"]
                )

                for llamada in respuesta["message"]["tool_calls"]:

                    nombre_tool = llamada["function"]["name"]
                    argumentos_tool = llamada["function"]["arguments"]

                    if (
                        isinstance(argumentos_tool, dict)
                        and "query_sql" in argumentos_tool
                        and isinstance(argumentos_tool["query_sql"], dict)
                    ):
                        q = argumentos_tool["query_sql"]

                        if "value" in q:
                            argumentos_tool["query_sql"] = q["value"]

                    resultado_mcp = await session.call_tool(
                        nombre_tool,
                        arguments=argumentos_tool
                    )

                    texto_respuesta_tool = ""

                    for bloque in resultado_mcp.content:
                        if hasattr(bloque, "text"):
                            texto_respuesta_tool += bloque.text

                    historial_mensajes.append({
                        "role": "tool",
                        "content": (
                            f"Resultado de {nombre_tool}:\n\n"
                            f"{texto_respuesta_tool}"
                        )
                    })

                respuesta = ollama.chat(
                    model=MODELO_LLM,
                    messages=historial_mensajes,
                    tools=herramientas_ollama
                )

            return respuesta["message"]["content"]


def construir_mini_esquema(columnas_json: str) -> str:
    columnas = json.loads(columnas_json)
    tablas = {}

    for col in columnas:
        tabla = col["tabla"]
        if tabla not in tablas:
            tablas[tabla] = []
        tablas[tabla].append(
            f"- {col['columna']} ({col.get('tipo', 'TEXT')})"
        )

    partes = ["ESQUEMA RELEVANTE\n"]

    for tabla, cols in tablas.items():
        partes.append(f"Tabla: {tabla}")
        for c in cols:
            partes.append(c)
        partes.append("")

    tablas_presentes = set(tablas.keys())
    joins = []

    for rel in RELACIONES:
        if (
            rel["tabla_a"] in tablas_presentes
            and rel["tabla_b"] in tablas_presentes
        ):
            joins.append(rel["join"])

    if joins:
        partes.append("RELACIONES:")

        for j in joins:
            partes.append(f"- {j}")

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

async def iniciar_chat_mcp():
    # Configurar los parámetros para lanzar el servidor MCP en segundo plano
    parametros_servidor = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"],
        env=None
    )

    print(f"Conectando al servidor MCP y cargando Ollama ({MODELO_LLM})...")

    # Establecer el canal de comunicación stdio con el servidor MCP
    async with stdio_client(parametros_servidor) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Inicializamos la sesión MCP
            await session.initialize()
            
            # Descubrimos las herramientas que el servidor ha expuesto dinámicamente
            mcp_tools_response = await session.list_tools()
            herramientas_mcp = mcp_tools_response.tools

            herramientas_para_llm = []
            for tool in herramientas_mcp:
                if tool.name == "buscar_columnas_relevantes":
                    continue
                herramientas_para_llm.append(tool)

            herramientas_mcp = herramientas_para_llm
            
            # Traducimos las herramientas del formato MCP al formato nativo de Ollama
            herramientas_ollama = []
            for tool in herramientas_mcp:
                herramientas_ollama.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })
            
            print("\n¡Sistema Listo! Servidor MCP conectado con Ollama con éxito.")
            print(f"Herramientas SQLite inyectadas al modelo: {[t.name for t in herramientas_mcp]}")
            
            # Prompt inicial del sistema para guiar al modelo local sobre la base de datos
            historial_mensajes = [{
                "role": "system",
                "content": """
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
            }]
            
            # Bucle interactivo de consola
            while True:
                usuario_input = input("\nUsuario (escribe 'salir' para terminar): ")
                if usuario_input.lower() in ["salir", "exit", "quit"]:
                    break

                columnas_relevantes = await recuperar_columnas_relevantes(
                    session,
                    usuario_input
                )

                print("\nColumnas relevantes encontradas:")
                print(columnas_relevantes)

                mini_esquema = construir_mini_esquema(
                    columnas_relevantes
                )

                print("\nMini esquema:")
                print(mini_esquema)

                # mensaje_enriquecido = f"""
                # Pregunta del usuario:

                # {usuario_input}

                # Columnas relevantes recuperadas:

                # {columnas_relevantes}

                # Genera la consulta SQL utilizando preferentemente
                # las columnas anteriores.
                # """

                mensaje_enriquecido = f"""
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
                
                historial_mensajes.append({"role": "user", "content": mensaje_enriquecido})
                print("Pensando/Consultando base de datos...")
                
                # Llamada inicial a Ollama pasándole las herramientas disponibles
                respuesta = ollama.chat(
                    model=MODELO_LLM,
                    messages=historial_mensajes,
                    tools=herramientas_ollama
                )
                
                # Bucle de Tool Calling: Mientras Ollama decida que necesita ejecutar SQL
                while respuesta.get('message', {}).get('tool_calls'):
                    historial_mensajes.append(respuesta['message'])
                    
                    for llamada in respuesta['message']['tool_calls']:
                        nombre_tool = llamada['function']['name']
                        argumentos_tool = llamada['function']['arguments']

                        if (
                            isinstance(argumentos_tool, dict)
                            and "query_sql" in argumentos_tool
                            and isinstance(argumentos_tool["query_sql"], dict)
                        ):
                            q = argumentos_tool["query_sql"]
                            if "value" in q:
                                argumentos_tool["query_sql"] = q["value"]
                        
                        print(f"   [Herramienta detectada] El modelo ejecuta '{nombre_tool}' con: {argumentos_tool}")
                        
                        # Ejecutamos la herramienta de manera real en el Servidor MCP
                        resultado_mcp = await session.call_tool(nombre_tool, arguments=argumentos_tool)
                        
                        # Extraemos el texto plano devuelto por el servidor
                        texto_respuesta_tool = ""
                        for bloque in resultado_mcp.content:
                            if hasattr(bloque, 'text'):
                                texto_respuesta_tool += bloque.text

                        print("\nResultado tool:")
                        print(texto_respuesta_tool)

                        # historial_mensajes.append({
                        #     "role": "tool",
                        #     "content": texto_respuesta_tool,
                        #     "name": nombre_tool
                        # })

                        historial_mensajes.append({
                            "role": "tool",
                            "content": f"Resultado de {nombre_tool}:\n\n{texto_respuesta_tool}"
                        })
                    
                    # Devolvemos el control a Ollama enviándole los datos que obtuvo de la DB
                    respuesta = ollama.chat(
                        model=MODELO_LLM,
                        messages=historial_mensajes,
                        tools=herramientas_ollama
                    )
                
                # Mostrar la respuesta final sintetizada por el modelo
                print("\nRespuesta del Asistente:")
                print(respuesta['message']['content'])
                historial_mensajes.append(respuesta['message'])

if __name__ == "__main__":
    # Ejecutar el cliente asíncrono
    asyncio.run(iniciar_chat_mcp())