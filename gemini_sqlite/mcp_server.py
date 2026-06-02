# mcp_server.py
import sqlite3
from mcp.server.fastmcp import FastMCP

# Inicializamos el servidor MCP para nuestro Corpus Musical
mcp = FastMCP("Corpus Musical Server")
DB_PATH = "corpus_musical.db"

@mcp.tool()
def obtener_esquema() -> str:
    """
    Devuelve el esquema de las tablas ('piezas' y 'analisis_musical') junto con el 
    diccionario de datos que explica el significado musicológico de cada columna.
    Usa esta herramienta al inicio para entender qué campos mapear según la petición del usuario.
    """
    diccionario_datos = """
=== DICCIONARIO DE DATOS DEL CORPUS MUSICAL ===

TABLA 'piezas' (Metadatos generales de la partitura):
- id: Identificador único (INTEGER).
- titulo: Título de la obra (TEXT). Puede contener nombres de géneros como 'Nana'.
- autor: Compositor o recopilador (TEXT).
- compas: Métrica de la pieza, ej. '4/4', '2/4', '6/8' (TEXT).
- tonalidad / modo / modo_completo: Datos armónicos de la pieza.
- bpm: Velocidad/Tempo (INTEGER).
- region: Zona geográfica de origen (TEXT).

TABLA 'analisis_musical' (Análisis rítmico, melódico y crítico):
- pieza_id: Relación con el ID de la tabla 'piezas' (FOREIGN KEY).
- temas: Palabras clave del contenido o género (TEXT). Ej: 'naturaleza, religión, infantil'. ¡Aquí se buscan las 'Nanas' o canciones de cuna!
- desajuste_duracion_meter: Indica si un compás (típicamente el primero) difiere de la métrica oficial (INTEGER: 0 o 1). ¡ESTO REPRESENTA LA PRESENCIA DE ANACRUSA!
- tiene_sincopas / conteo_sincopas: Presencia y cantidad de síncopas detectadas.
- tiene_hemiolia_vertical / tiene_hemiolia_horizontal: Presencia de hemiolias (0 o 1).
- total_eventos_musicales: Cantidad total de notas y silencios (INTEGER).
- total_compases: Duración en compases de la pieza (INTEGER).
- densidad_notas_por_compas: Promedio de notas por compás (REAL).
- secuencia_notas_silencios: Cadena de texto con las notas musicales de la melodía (ej. 'G4 - B4 - D5').
- tendencia_melodica: Dirección de la línea melódica (TEXT).

==============================================
"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
        tablas = cursor.fetchall()
        conn.close()
        
        esquema_sql = "\n=== ESTRUCTURA SQL REAL ===\n"
        for tabla in tablas:
            if tabla[0]:
                esquema_sql += f"{tabla[0]}\n\n"
                
        return diccionario_datos + esquema_sql
    except Exception as e:
        return f"Error al obtener el esquema y diccionario: {str(e)}"


@mcp.tool()
def ejecutar_consulta_sql(query_sql: str) -> str:
    """
    Ejecuta una consulta SQL de lectura (SELECT) en la base de datos corpus_musical.db 
    y devuelve los resultados estructurados. Usa esta herramienta para responder preguntas 
    numéricas, estadísticas, búsquedas de canciones o cruces de datos entre 'piezas' y 'analisis_musical'.
    """
    # Forzar seguridad básica de solo lectura
    query_limpia = query_sql.strip().lower()
    if not query_limpia.startswith("select"):
        return "Error de seguridad: Solo se permiten consultas de tipo SELECT (lectura)."

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(query_sql)
        
        # Obtener los nombres de las columnas resultantes
        columnas = [desc[0] for desc in cursor.description]
        filas = cursor.fetchall()
        conn.close()
        
        if not filas:
            return "La consulta se ejecutó con éxito pero no devolvió ningún registro."
        
        # Formatear el resultado como una tabla legible de texto plano
        lineas_resultado = [" | ".join(columnas)]
        lineas_resultado.append("-" * len(lineas_resultado[0]))
        
        for fila in filas:
            lineas_resultado.append(" | ".join(str(item) for item in fila))
            
        return "\n".join(lineas_resultado)
        
    except Exception as e:
        return f"Error al ejecutar SQL: {str(e)}"

if __name__ == "__main__":
    # Arrancamos el servidor usando el transporte estándar de entrada/salida (stdio)
    mcp.run(transport="stdio")