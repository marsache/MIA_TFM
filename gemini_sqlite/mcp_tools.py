import sqlite3
import json
from typing import Any

def mcp_tool_consultar_hemiolia(id_pieza_solicitada):
    conexion = sqlite3.connect('corpus_musical.db')
    cursor = conexion.cursor()
    
    cursor.execute('''
        SELECT p.titulo, a.tiene_hemiolia_vertical, a.compases_hemiolia_vertical
        FROM piezas p
        JOIN analisis_ritmico a ON p.id = a.pieza_id
        WHERE p.id = ?
    ''', (id_pieza_solicitada,))
    
    resultado = cursor.fetchone()
    conexion.close()
    
    if resultado:
        titulo, tiene_hemiolia, compases = resultado
        
        if tiene_hemiolia == 1:
            return f"La pieza '{titulo}' contiene hemiolias verticales en los siguientes compases: {compases}."
        else:
            return f"La pieza '{titulo}' no contiene hemiolias verticales analizadas."
    else:
        return "No se encontró la pieza solicitada en el sistema."

# Lo que la herramienta le devuelve al LLM instantáneamente:
# "La pieza 'Muiñeira de Vigo' contiene hemiolias verticales en los siguientes compases: 4, 8, 12."

def analizar_constancia_silaba(registros: list[dict[str, Any]], silaba_objetivo: str) -> dict[str, Any]:
    """
    Tool Comparador Global: Cruza los datos de todo el dataset analizado
    para validar si una sílaba mantiene siempre la misma duración musical.
    """
    silaba_buscar = silaba_objetivo.strip().lower()
    piezas_donde_aparece = {}
    todas_las_duraciones_detectadas = set()
    
    for r in registros:
        # Recuperamos y decodificamos el JSON guardado de esa pieza
        mapeo_json = r.get("mapeo_silabas_duraciones", "{}")
        mapeo = json.loads(mapeo_json)
        
        if silaba_buscar in mapeo:
            duraciones_en_esta_pieza = mapeo[silaba_buscar]
            piezas_donde_aparece[r["titulo"] or r["file_path"]] = duraciones_en_esta_pieza
            todas_las_duraciones_detectadas.update(duraciones_en_esta_pieza)
            
    if not piezas_donde_aparece:
        return {
            "silaba_buscada": silaba_objetivo,
            "encontrada": False,
            "mensaje": f"La sílaba '{silaba_objetivo}' no existe en el dataset."
        }
        
    # CONDICIÓN CLAVE: Es constante si y solo si el set global contiene exactamente 1 duración
    es_constante_globalmente = len(todas_las_duraciones_detectadas) == 1
    
    return {
        "silaba_buscada": silaba_objetivo,
        "encontrada": True,
        "se_asigna_siempre_a_la_misma_duracion": es_constante_globalmente,
        "duraciones_totales_en_dataset": sorted(list(todas_las_duraciones_detectadas)),
        "apariciones_por_pieza": piezas_donde_aparece
    }