import sqlite3
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Corpus Musical Server")

_BASE_DIR = Path(__file__).parent
DB_PATH = _BASE_DIR.parent / "corpus_musical.db"


# =========================================================
# 2ESQUEMA LIGERO + DOMINIOS
# =========================================================

@mcp.tool()
def obtener_esquema() -> str:
    """
    Esquema compacto + dominios válidos.
    Diseñado para evitar alucinaciones SQL.
    """

    esquema = """
=== ESQUEMA CORPUS MUSICAL (SIMPLIFICADO) ===

TABLA: piezas
- id (INTEGER)
- titulo (TEXT)
- autor (TEXT)
- autor_genero (TEXT)
- compas (TEXT)
- tonalidad (TEXT)
- bpm (INTEGER)
- region (TEXT)

TABLA: analisis_musical
- pieza_id (INTEGER)
- tiene_sincopas (0/1)
- conteo_sincopas (INTEGER)
- compases_sincopas (TEXT)
- tiene_hemiolia_vertical (0/1)
- compases_hemiolia_vertical (TEXT)
- tendencia_melodica (TEXT)
- lirica_voz (TEXT)

=== DOMINIOS (VALORES VÁLIDOS) ===
autor_genero: masculino | femenino | desconocido
tiene_sincopas: 0 | 1
tiene_hemiolia_vertical: 0 | 1
compas: 2/4 | 3/4 | 4/4 | 6/8
"""

    return esquema


# =========================================================
# SQL EJECUTOR SEGURO
# =========================================================

@mcp.tool()
def ejecutar_consulta_sql(query_sql: str) -> str:

    sql = query_sql.strip().lower()

    if not sql.startswith("select"):
        return "Error: solo SELECT permitido"

    # protección anti-tablas inventadas
    forbidden = ["autores", "songs", "works", "music"]
    if any(f in sql for f in forbidden):
        return "Error: tabla no permitida"

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(query_sql)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]

        conn.close()

        if not rows:
            return "Sin resultados"

        output = [" | ".join(cols)]
        output.append("-" * len(output[0]))

        for r in rows:
            output.append(" | ".join(str(x) for x in r))

        return "\n".join(output)

    except Exception as e:
        return f"Error SQL: {str(e)}"


# =========================================================
# TOOLS SEMÁNTICAS (CLAVE PARA EVITAR SQL FRÁGIL)
# =========================================================

@mcp.tool()
def consultar_hemiolia(pieza_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.titulo,
               a.tiene_hemiolia_vertical,
               a.compases_hemiolia_vertical
        FROM piezas p
        JOIN analisis_musical a ON p.id = a.pieza_id
        WHERE p.id = ?
    """, (pieza_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return "Pieza no encontrada"

    titulo, tiene, compases = row

    if tiene == 1:
        return f"La pieza '{titulo}' tiene hemiolía en compases: {compases}"
    else:
        return f"La pieza '{titulo}' no presenta hemiolía vertical"


@mcp.tool()
def consultar_sincopas(pieza_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.titulo,
               a.tiene_sincopas,
               a.conteo_sincopas,
               a.compases_sincopas
        FROM piezas p
        JOIN analisis_musical a ON p.id = a.pieza_id
        WHERE p.id = ?
    """, (pieza_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return "Pieza no encontrada"

    titulo, tiene, conteo, compases = row

    if tiene == 1:
        return f"'{titulo}' tiene {conteo} síncopas en: {compases}"
    else:
        return f"'{titulo}' no presenta síncopas"


@mcp.tool()
def consultar_tendencia_melodica(pieza_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.titulo, a.tendencia_melodica
        FROM piezas p
        JOIN analisis_musical a ON p.id = a.pieza_id
        WHERE p.id = ?
    """, (pieza_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return "Pieza no encontrada"

    titulo, tendencia = row
    return f"La tendencia melódica de '{titulo}' es: {tendencia}"


@mcp.tool()
def consultar_lirica_voz(pieza_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.titulo, a.lirica_voz
        FROM piezas p
        JOIN analisis_musical a ON p.id = a.pieza_id
        WHERE p.id = ?
    """, (pieza_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return "Pieza no encontrada"

    titulo, voz = row
    return f"En '{titulo}', la voz lírica detectada es: {voz}"


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")