RELACIONES = [
    {
        "tabla_a": "piezas",
        "columna_a": "id",
        "tabla_b": "analisis_musical",
        "columna_b": "pieza_id",
        "join": "piezas.id = analisis_musical.pieza_id"
    }
]

COLUMNAS = [
    {
        "tabla": "analisis_musical",
        "columna": "pieza_id",
        "descripcion": "Identificador único de la pieza, clave foránea (FOREIGN KEY) hacia piezas.id",
        "keywords": ["join", "relación", "pieza", "id"],
        "tipo": "INTEGER"
    },
    {
        "tabla": "piezas",
        "columna": "titulo",
        "descripcion": "Título de la obra musical",
        "keywords": ["título", "nombre"],  
        "ejemplos": [
            "Scotch Air in Guy Mannering",
            "IE-2019-D-HLS-007",
            "Los caracoles o el burro",
            "Matarile-rile-ró"
        ],
        "tipo": "TEXT"
    },
    {
        "tabla": "piezas",
        "columna": "bpm",
        "descripcion": "Tempo o velocidad de la pieza",
        "keywords": ["bpm", "tempo", "velocidad"],
        "ejemplos": [78, 120, 140],
        "tipo": "INTEGER"
    },
    {
        "tabla": "analisis_musical",
        "columna": "desajuste_duracion_meter",
        "descripcion": "Presencia de anacrusa o compás incompleto inicial",
        "keywords": ["anacrusa", "compas incompleto", "entrada anticipada"],
        "ejemplos": [0, 1],
        "tipo": "INTEGER",
        "valores_validos": [0, 1]
    },
    {
        "tabla": "analisis_musical",
        "columna": "tiene_sincopas",
        "descripcion": "Indica si existen síncopas en la pieza",
        "keywords": ["síncopa", "ritmo"],
        "ejemplos": [0, 1],
        "tipo": "INTEGER",
        "valores_validos": [0, 1],
        "consulta_ejemplo": "SELECT piezas.titulo, analisis_musical.tiene_sincopas FROM piezas JOIN analisis_musical ON piezas.id = analisis_musical.pieza_id WHERE analisis_musical.tiene_sincopas = 1;"
    },
    {
        "tabla": "piezas",
        "columna": "id",
        "descripcion": "Identificador principal (PRIMARY KEY AUTOINCREMENT) de la pieza musical",
        "keywords": ["id", "identificador", "clave primaria"],
        "tipo": "INTEGER"
    },
    {
        "tabla": "piezas",
        "columna": "file_path",
        "descripcion": "Ruta única del archivo correspondiente a la pieza musical",
        "keywords": ["ruta", "archivo", "path", "ubicación"],
        "tipo": "TEXT"
    },
    {
        "tabla": "piezas",
        "columna": "autor",
        "descripcion": "Nombre del autor o compositor de la pieza",
        "keywords": ["autor", "compositor", "creador", "autora", "compositora", "creadora"],
        "ejemplos": ["José Miguel Hernández Jaramillo", "Frank Livingstone", "Anónimo"],
        "tipo": "TEXT"
    },
    {
        "tabla": "piezas",
        "columna": "compas",
        "descripcion": "Firma de compás de la obra (ej. 4/4, 3/4)",
        "keywords": ["compás", "métrica", "tiempo"],
        "ejemplos": ["4/4", "3/4", "6/8", "2/2"],
        "tipo": "TEXT"
    },
    {
        "tabla": "piezas",
        "columna": "tonalidad",
        "descripcion": "Tonalidad en la que está escrita la pieza",
        "keywords": ["tonalidad", "tono", "key"],
        "ejemplos": ["D major", "E minor", "F# minor"],
        "tipo": "TEXT"
    },
    {
        "tabla": "piezas",
        "columna": "modo",
        "descripcion": "Modo musical de la pieza (ej. mayor, menor)",
        "keywords": ["modo", "escala"],
        "ejemplos": ["jónico (mayor)", "mixolidio", "eólico (menor)", "locrio"],
        "tipo": "TEXT"
    },


    #(TODO: completar)
]