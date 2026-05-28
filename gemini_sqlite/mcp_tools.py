import sqlite3

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