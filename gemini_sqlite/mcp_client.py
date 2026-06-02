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
                    "Eres un asistente experto en musicología computacional con acceso a 'corpus_musical.db'. "
                    "SIEMPRE que el usuario te pida conceptos musicales (como anacrusas, síncopas, o géneros como Nanas), "
                    "ejecuta PRIMERO la herramienta 'obtener_esquema'. "
                    "Lee atentamente el Diccionario de Datos que te devolverá la herramienta para mapear los términos "
                    "del usuario a las columnas correctas (por ejemplo: anacrusa se mapea como 'desajuste_duracion_meter' "
                    "y las Nanas se buscan en 'temas' o 'titulo' usando LIKE). Genera consultas SQL limpias de tipo SELECT."
                )
            }]
            
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
                
                # Bucle de Tool Calling: Mientras Ollama decida que necesita ejecutar SQL...
                while respuesta.get('message', {}).get('tool_calls'):
                    historial_mensajes.append(respuesta['message'])
                    
                    for llamada in respuesta['message']['tool_calls']:
                        nombre_tool = llamada['function']['name']
                        argumentos_tool = llamada['function']['arguments']
                        
                        print(f"   [Herramienta detectada] El modelo ejecuta '{nombre_tool}' con: {argumentos_tool}")
                        
                        # Ejecutamos la herramienta de manera real en el Servidor MCP
                        resultado_mcp = await session.call_tool(nombre_tool, arguments=argumentos_tool)
                        
                        # Extraemos el texto plano devuelto por el servidor
                        texto_respuesta_tool = ""
                        for bloque in resultado_mcp.content:
                            if hasattr(bloque, 'text'):
                                texto_respuesta_tool += bloque.text
                        
                        # Añadimos el resultado de la base de datos al historial de la conversación
                        historial_mensajes.append({
                            "role": "tool",
                            "content": texto_respuesta_tool,
                            "name": nombre_tool
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