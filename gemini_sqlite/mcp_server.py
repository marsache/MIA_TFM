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
- autor_genero: Género asociado al autor o autora de la obra (TEXT) (Categorías: 'masculino', 'femenino', 'desconocido').
- compas: Métrica de la pieza, ej. '4/4', '2/4', '6/8' (TEXT).
- tonalidad / modo / modo_completo: Datos armónicos de la pieza.
- bpm: Velocidad/Tempo (INTEGER).
- region: Zona geográfica de origen (TEXT).
- region_justificacion: Justificación de la región asignada (TEXT).
- midi_volume: Volumen detectado en la pieza (INTEGER).
- nota_mas_grave: Nota más grave en la pieza (TEXT).
- nota_mas_aguda: Nota más aguda en la pieza (TEXT).
- software_codificacion: Software utilizado para la codificación de la pieza (TEXT).
- convertido_via_verovio: Indica si la pieza ha sido convertida mediante Verovio (INTEGER: 0 o 1).
- fecha_codificacion: Fecha de codificación de la pieza (TEXT).
- formato_origen: Formato original de la pieza (TEXT).

TABLA 'analisis_musical' (Análisis rítmico, melódico y crítico):
- pieza_id: Relación con el ID de la tabla 'piezas' (FOREIGN KEY).
- temas: Palabras clave del contenido o género (TEXT). Ej: 'naturaleza, religión, infantil'. ¡Aquí se buscan las 'Nanas' o canciones de cuna!
- desajuste_duracion_meter: Indica si un compás (típicamente el primero) difiere de la métrica oficial (INTEGER: 0 o 1). ¡ESTO REPRESENTA LA PRESENCIA DE ANACRUSA!
- tiene_sincopas / conteo_sincopas: Presencia y cantidad de síncopas detectadas.
- compases_sincopas: En qué compases se encuentran las síncopas (TEXT).
- tiene_hemiolia_vertical / tiene_hemiolia_horizontal: Presencia de hemiolias (0 o 1).
- compases_hemiolia_vertical / compases_hemiolia_horizontal: En qué compases se encuentran las hemiolias, tanto verticales como horizontales (TEXT).
- conteo_hemiolia_vertical / conteo_hemiolia_horizontal: Cantidad de hemiolias detectadas en cada dirección (INTEGER).
- total_eventos_musicales: Cantidad total de notas y silencios (INTEGER).
- total_compases: Duración en compases de la pieza (INTEGER).
- densidad_notas_por_compas: Promedio de notas por compás (REAL).
- secuencia_notas_silencios: Cadena de texto con las notas musicales de la melodía (ej. 'G4 - B4 - D5').
- tendencia_melodica: Dirección de la línea melódica (TEXT).
- cambio_resolucion_ppq: Determina si el valor de resolución rítmica (ppq base o dur.ppq por figura) cambia a mitad de una sección (INTEGER: 0 o 1).
- compases_cambio_resolucion: Si hay cambio de resolución, en qué compases ocurre (TEXT).
- desajuste_duracion_meter: Localiza compases en archivos MEI donde la suma de las duraciones de las notas/acordes internos de una voz (layer) no coincide con la capacidad del meterSig activo en el staffDef (INTEGER: 0 o 1).
- compases_desajuste_duracion_meter: Si hay desajuste, en qué compases ocurre (TEXT).
- valores_irregulares_ocultos: Detecta valores irregulares (como tresillos) en archivos MusicXML que no han sido declarados explícitamente mediante la etiqueta <time-modification> (INTEGER: 0 o 1).
- compases_valores_irregulares_ocultos: Si hay valores irregulares ocultos, en qué compases ocurren (TEXT).
- conteo_valores_irregulares_ocultos: Cuántos valores irregulares ocultos se han detectado (INTEGER).
- tiene_polirritmia: Detecta el uso de polirritmias verticales en la partitura. Se considera polirritmia cuando en un mismo compás coexisten de forma simultánea subdivisiones rítmicas conflictivas (por ejemplo, tresillos frente a corcheas binarias, o combinaciones como 3 contra 4, 5 contra 4, etc.) entre diferentes partes o voces (INTEGER: 0 o 1).
- compases_polirritmia: Si hay polirritmia, en qué compases ocurre (TEXT).
- conteo_polirritmia: Cuántos compases contienen polirritmia (INTEGER).
- lirica_voz: Analiza semánticamente el texto de la letra para identificar la voz del narrador. Busca marcas de género gramatical (ej: 'estoy cansado' vs 'estoy cansada')(Categorías:'femenino', 'masculino', 'neutro', 'desconocido').
- texto_letras_extraido: Texto completo de la letra extraído de la partitura (TEXT).
- porcentaje_intervalos_ascendentes: Porcentaje de intervalos ascendentes en la melodía (REAL).
- porcentaje_intervalos_descendentes: Porcentaje de intervalos descendentes en la melodía (REAL)
- mapeo_silabas_duraciones: Mapea cada sílaba con sus duraciones musicales en la pieza. Se representa como una cadena de texto con formato JSON, donde cada entrada tiene la forma "sílabas": "duraciones". Por ejemplo: {"la": [0.5], "be": [1.0], "si": [1.0]} (TEXT).
- accidentales_compases_json: Lista de compases que contienen notas con alteraciones accidentales (sostenidos, bemoles, becuadros) representada como una cadena de texto con formato JSON. Cada entrada tiene la forma "nota": ["compás1", "compás2"]. Por ejemplo: {"F#4": ["2", "3"], "G#4": ["9"]} (TEXT).
- accidentales_resumen_texto: Resumen en texto plano de los tipos de alteraciones accidentales presentes en la pieza y su frecuencia. Por ejemplo: "Ab4 (cc. 10, 11, 13, 14, 15, 17), Db5 (cc. 10, 14)" (TEXT).
- conteo_accidentales_totales: Cantidad total de alteraciones accidentales detectadas en la pieza (INTEGER).
- qc_compases_vacios: Número de compases vacíos en la pieza (INTEGER).
- qc_notas_duracion_cero: Número de notas con duración cero en la pieza (INTEGER).
- qc_advertencias_criticas: Lista de advertencias críticas encontradas en la pieza (TEXT).
- qc_puntuacion_integridad: Indica si la puntuación está completa y sin errores (INTEGER: 0-100).
- tiene_leitmotivs: Indica si se han detectado patrones recurrentes de motivos musicales (leitmotivs) a lo largo de la pieza (INTEGER: 0 o 1).
- patrones_leitmotivs_json: Si hay leitmotivs, representa los patrones detectados como una cadena de texto con formato JSON. Cada entrada tiene la forma "motivo": veces que se repite. Por ejemplo: {"0 -> +5 -> -5": 2, "+5 -> -5 -> +2": 2, "-5 -> +2 -> -2": 2, "+2 -> -2 -> -3": 2, "-2 -> -3 -> -2": 2, "-3 -> -2 -> -2": 2, "0 -> +3 -> 0": 2, "+3 -> 0 -> 0": 2, "0 -> +5 -> -5 -> +2": 2, "+5 -> -5 -> +2 -> -2": 2, "-5 -> +2 -> -2 -> -3": 2, "+2 -> -2 -> -3 -> -2": 2, "-2 -> -3 -> -2 -> -2": 2, "0 -> +3 -> 0 -> 0": 2} (TEXT).
- tiene_plicas_anomalas: Indica si se han detectado plicas anómalas en la pieza (plicas cuya dirección no se corresponde con la posición de la nota en el pentagrama) (INTEGER: 0 o 1).
- conteo_plicas_anomalas: Número de plicas anómalas detectadas en la pieza (INTEGER).
- compases_plicas_anomalas: Lista de compases que contienen plicas anómalas (TEXT).
- lirica_sustantivos: Lista de sustantivos encontrados en el texto de la letra (TEXT).
- lirica_nombres_propios: Lista de nombres propios encontrados en el texto de la letra (TEXT).
- intervalo_frontera_mas_frecuente: Intervalo musical más frecuente que actúa como frontera entre frases musicales (ej. '-3', '+5', '0') (TEXT).
- frecuencia_intervalo_frontera: Frecuencia de aparición del intervalo frontera más frecuente (INTEGER).
- tiene_etiqueta_sb: Indica si la partitura contiene etiquetas de System Break (SB) que marcan divisiones estructurales importantes (INTEGER: 0 o 1).
- sb_coincide_con_frase_logica: Indica si las etiquetas de System Break coinciden con las divisiones de frases musicales lógicas detectadas (INTEGER: 0 o 1).
- sb_total_system_breaks: Número total de etiquetas de System Break presentes en la partitura (INTEGER).
- sb_saltos_en_fin_de_frase: Número de saltos de línea o System Breaks que ocurren al final de frases musicales (INTEGER).

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