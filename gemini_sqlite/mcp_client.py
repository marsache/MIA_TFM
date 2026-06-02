# mcp_client.py
import asyncio
import sys
import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configura aquí el modelo local de Ollama que desees usar (debe soportar Tools)
MODELO_LLM = "qwen3:8b"

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
                "content": (
                    "Eres un asistente experto en musicología computacional que interactúa con 'corpus_musical.db'. "
                    "Tu único objetivo es responder a la pregunta del usuario con datos reales de la base de datos.\n\n"
                    "REGLAS OBLIGATORIAS DE COMPORTAMIENTO:\n"
                    "1. NO pidas permiso al usuario para ejecutar consultas.\n"
                    "2. NO simules los resultados ni inventes respuestas hipotéticas.\n"
                    "3. NO te limites a escribir el código SQL en texto plano si puedes ejecutarlo.\n"
                    "4. ACTÚA DE FORMA SECUENCIAL: Si no conoces las columnas, llama a 'obtener_esquema'. "
                    "En cuanto recibas la respuesta, procesa mentalmente las columnas y llama INMEDIATAMENTE a 'ejecutar_consulta_sql'.\n"
                    "5. Solo responderás al usuario en texto plano cuando tengas los resultados finales extraídos de la base de datos."
                )
            }]

            # historial_mensajes = [{
            #     "role": "system",
            #     "content": (
            #         "Eres un asistente experto en musicología computacional con acceso a 'corpus_musical.db'."
            #         "SIEMPRE que el usuario te pida conceptos musicales (como anacrusas, síncopas, o géneros como Nanas), "
            #         "ejecuta PRIMERO la herramienta 'obtener_esquema'. "
            #         "Lee atentamente el Diccionario de Datos que te devolverá la herramienta para mapear los términos "
            #         "del usuario a las columnas correctas (por ejemplo: anacrusa se mapea como 'desajuste_duracion_meter' "
            #         "y las Nanas se buscan en 'temas' o 'titulo' usando LIKE). Genera consultas SQL limpias de tipo SELECT."
            #         "Tu único objetivo es responder a la pregunta del usuario con datos reales de la base de datos.\n\n"
            #     )
            # }]
            
            # Bucle interactivo de consola
            while True:
                usuario_input = input("\nUsuario (escribe 'salir' para terminar): ")
                if usuario_input.lower() in ["salir", "exit", "quit"]:
                    break
                
                historial_mensajes.append({"role": "user", "content": usuario_input})
                print("Pensando/Consultando base de datos...")
                
                # Llamada inicial a Ollama pasándole las herramientas disponibles
                respuesta = ollama.chat(
                    model=MODELO_LLM,
                    messages=historial_mensajes,
                    tools=herramientas_ollama
                )
                
                # Permite la ejecución secuencial de herramientas
                while respuesta['message'].get('tool_calls'):
                    # Añadimos la intención del modelo de usar herramientas al historial
                    historial_mensajes.append(respuesta['message'])
                    
                    for tool_call in respuesta['message']['tool_calls']:
                        nombre_tool = tool_call['function']['name']
                        argumentos_tool = tool_call['function']['arguments']
                        
                        print(f"   [Herramienta detectada] El modelo ejecuta '{nombre_tool}' con: {argumentos_tool}")
                        
                        # Ejecutar la herramienta en el servidor MCP
                        resultado_mcp = await session.call_tool(nombre_tool, arguments=argumentos_tool)
                        
                        # Extraer la respuesta de texto
                        texto_respuesta_tool = ""
                        for bloque in resultado_mcp.content:
                            if hasattr(bloque, 'text'):
                                texto_respuesta_tool += bloque.text
                        
                        # Guardar el resultado de la herramienta en el historial
                        historial_mensajes.append({
                            "role": "tool",
                            "content": texto_respuesta_tool,
                            "name": nombre_tool
                        })
                    
                    # Volvemos a consultar a Ollama enviándole el resultado de la herramienta anterior.
                    # Si el modelo necesita otra herramienta (ej. ejecutar_consulta_sql), el bucle continuará.
                    respuesta = ollama.chat(
                        model=MODELO_LLM,
                        messages=historial_mensajes,
                        tools=herramientas_ollama
                    )
                
                # Fuera del bucle: cuando el modelo ya no requiera herramientas, muestra la respuesta final
                print("\nRespuesta del Asistente:")

                # --- SISTEMA DE AUTO-CORRECCIÓN DE AGENTE ---
                # Si el modelo esquivó las herramientas pero escribió código SQL en el texto,
                # lo interceptamos, le añadimos un mensaje de error y lo obligamos a ejecutarlo.
                for _ in range(2): # Máximo 2 intentos de corrección
                    contenido_asistente = respuesta['message'].get('content', '')
                    if ("```sql" in contenido_asistente or "SELECT" in contenido_asistente.upper()) and not respuesta['message'].get('tool_calls'):
                        print("   [Corrección de Cliente] ¡Detectado! El modelo redactó el SQL en vez de ejecutarlo. Forzando re-intento...")
                        
                        historial_mensajes.append(respuesta['message'])
                        historial_mensajes.append({
                            "role": "user",
                            "content": "ERROR: No has invocado la función. Ejecuta la consulta SQL que acabas de proponer utilizando OBLIGATORIAMENTE la herramienta 'ejecutar_consulta_sql'. No me des explicaciones de texto, ejecuta el código."
                        })
                        
                        respuesta = ollama.chat(
                            model=MODELO_LLM,
                            messages=historial_mensajes,
                            tools=herramientas_ollama
                        )
                        
                        # Si tras la corrección el modelo reacciona y genera un tool_call, lo procesamos
                        while respuesta['message'].get('tool_calls'):
                            historial_mensajes.append(respuesta['message'])
                            for tool_call in respuesta['message']['tool_calls']:
                                nombre_tool = tool_call['function']['name']
                                argumentos_tool = tool_call['function']['arguments']
                                print(f"   [Herramienta corregida] El modelo ejecuta '{nombre_tool}' con: {argumentos_tool}")
                                resultado_mcp = await session.call_tool(nombre_tool, arguments=argumentos_tool)
                                texto_respuesta_tool = "".join([b.text for b in resultado_mcp.content if hasattr(b, 'text')])
                                historial_mensajes.append({
                                    "role": "tool",
                                    "content": texto_respuesta_tool,
                                    "name": nombre_tool
                                })
                            respuesta = ollama.chat(model=MODELO_LLM, messages=historial_mensajes, tools=herramientas_ollama)
                    else:
                        break

                # Fuera del bucle y de las correcciones: muestra la respuesta final real
                print("\nRespuesta del Asistente:")
                print(respuesta['message']['content'])
                historial_mensajes.append(respuesta['message'])

if __name__ == "__main__":
    # Ejecutar el cliente asíncrono
    asyncio.run(iniciar_chat_mcp())