import sqlite3
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Corpus Musical Smart Server")

DB_PATH = Path(__file__).parent.parent / "corpus_musical.db"


# AGRUPACIÓN SEMÁNTICA MUSICAL

SEMANTIC_GROUPS = {
    "ritmo": [
        "tiene_sincopas",
        "conteo_sincopas",
        "compases_sincopas",
        "tiene_hemiolia_vertical",
        "tiene_hemiolia_horizontal",
        "tiene_polirritmia"
    ],

    "melodia": [
        "tendencia_melodica",
        "porcentaje_intervalos_ascendentes",
        "porcentaje_intervalos_descendentes",
        "intervalo_frontera_mas_frecuente"
    ],

    "estructura": [
        "total_compases",
        "densidad_notas_por_compas"
    ],

    "lirica": [
        "lirica_voz",
        "lirica_sustantivos",
        "lirica_nombres_propios"
    ],

    "calidad": [
        "qc_puntuacion_integridad",
        "qc_compases_vacios",
        "qc_notas_duracion_cero"
    ]
}


# UTILIDADES INTERNAS

def get_connection():
    return sqlite3.connect(DB_PATH)


def get_all_columns():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(piezas)")
    piezas = [row[1] for row in cur.fetchall()]

    cur.execute("PRAGMA table_info(analisis_musical)")
    analisis = [row[1] for row in cur.fetchall()]

    conn.close()
    return set(piezas + analisis)


def validate_column(col: str) -> bool:
    return col in get_all_columns()


# TOOL 1: ESQUEMA REDUCIDO

@mcp.tool()
def obtener_esquema_sql() -> str:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT sql FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    conn.close()

    return "\n\n".join([t[0] for t in tables if t[0]])


# TOOL 2: CONSULTA POR CAMPO (GENÉRICA)

@mcp.tool()
def consultar_rasgo(pieza_id: int, campo: str) -> str:
    if not validate_column(campo):
        return f"Campo no válido: {campo}"

    conn = get_connection()
    cur = conn.cursor()

    try:
        query = f"""
        SELECT p.titulo, a.{campo}
        FROM piezas p
        JOIN analisis_musical a ON p.id = a.pieza_id
        WHERE p.id = ?
        """

        cur.execute(query, (pieza_id,))
        row = cur.fetchone()

        if not row:
            return "No se encontró la pieza."

        titulo, valor = row
        return f"🎵 {titulo}\n{campo}: {valor}"

    except Exception as e:
        return f"Error: {str(e)}"

    finally:
        conn.close()


# TOOL 3: CONSULTA POR GRUPO MUSICAL

@mcp.tool()
def consultar_grupo(grupo: str, pieza_id: int) -> str:
    if grupo not in SEMANTIC_GROUPS:
        return f"Grupo no válido: {grupo}"

    campos = SEMANTIC_GROUPS[grupo]

    conn = get_connection()
    cur = conn.cursor()

    try:
        select_fields = ", ".join(["p.titulo"] + [f"a.{c}" for c in campos])

        query = f"""
        SELECT {select_fields}
        FROM piezas p
        JOIN analisis_musical a ON p.id = a.pieza_id
        WHERE p.id = ?
        """

        cur.execute(query, (pieza_id,))
        row = cur.fetchone()

        if not row:
            return "No se encontró la pieza."

        titulo = row[0]
        valores = row[1:]

        output = f"{titulo}\n\n"

        for campo, valor in zip(campos, valores):
            output += f"- {campo}: {valor}\n"

        return output

    except Exception as e:
        return f"Error: {str(e)}"

    finally:
        conn.close()


# TOOL 4: ESTADÍSTICAS GENERALES

@mcp.tool()
def estadistica_campo(campo: str) -> str:
    if not validate_column(campo):
        return f"Campo no válido: {campo}"

    conn = get_connection()
    cur = conn.cursor()

    try:
        query = f"""
        SELECT {campo}, COUNT(*)
        FROM analisis_musical
        GROUP BY {campo}
        ORDER BY COUNT(*) DESC
        """

        cur.execute(query)
        rows = cur.fetchall()

        return "\n".join([f"{r[0]}: {r[1]}" for r in rows])

    except Exception as e:
        return f"Error: {str(e)}"

    finally:
        conn.close()


# TOOL 5: SQL LIBRE (FALLBACK CONTROLADO)

@mcp.tool()
def ejecutar_consulta_sql(query_sql: str) -> str:
    q = query_sql.strip().lower()

    if not q.startswith("select"):
        return "Solo se permiten consultas SELECT."

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(query_sql)

        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()

        conn.close()

        if not rows:
            return "Sin resultados."

        output = " | ".join(columns) + "\n"
        output += "-" * len(output) + "\n"

        for r in rows:
            output += " | ".join(map(str, r)) + "\n"

        return output

    except Exception as e:
        return f"Error SQL: {str(e)}"


# TOOL 6: VALIDACIÓN (DEBUG / SEGURIDAD)

@mcp.tool()
def validar_campo(campo: str) -> str:
    cols = get_all_columns()

    if campo in cols:
        return f"✔ Campo válido: {campo}"
    else:
        similares = [c for c in cols if campo in c]
        return f"Campo no existe. Posibles: {similares}"


# ARRANQUE

if __name__ == "__main__":
    mcp.run(transport="stdio")