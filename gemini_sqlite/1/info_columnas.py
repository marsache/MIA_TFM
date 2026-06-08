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
        "keywords": ["anacrusa", "compas incompleto", "entrada anticipada", "anacrusas"],
        "ejemplos": [0, 1],
        "tipo": "INTEGER",
        "valores_validos": [0, 1]
    },
    # {
    #     "tabla": "analisis_musical",
    #     "columna": "compases_desajuste_duracion_meter",
    #     "descripcion": "Listado de compases donde ocurre anacrusa inicial o compás incompleto",
    #     "keywords": ["anacrusa", "compas incompleto", "entrada anticipada", "anacrusas"],
    #     "tipo": "TEXT",
    #     "ejemplos": ["5, 7, 16", "2, 4, 6, 10, 14", "24"]
    # },
    {
        "tabla": "analisis_musical",
        "columna": "tiene_sincopas",
        "descripcion": "Indica si existen síncopas en la pieza",
        "keywords": ["síncopa", "ritmo", "síncopas", "tiene síncopa"],
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
        "columna": "fecha_codificacion",
        "descripcion": "Fecha en la que se codificó la pieza",
        "keywords": ["fecha", "codificación"],
        "ejemplos": ["2024-03-04", "2025-03-13", "2015-06-03"],
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
    # {
    #     "tabla": "piezas",
    #     "columna": "modo_completo",
    #     "descripcion": "Descripción completa del modo musical de la obra",
    #     "keywords": ["modo completo", "escala completa"],
    #     "ejemplos": ["G jónico (mayor)", "E dórico", "F-sharp eólico (menor)"],
    #     "tipo": "TEXT"
    # },
    {
        "tabla": "piezas",
        "columna": "midi_volume",
        "descripcion": "Volumen de reproducción MIDI de la pieza",
        "keywords": ["volumen", "midi", "dinámica"],
        "ejemplos": [78, 79, 100],
        "tipo": "INTEGER"
    },
    {
        "tabla": "piezas",
        "columna": "nota_mas_grave",
        "descripcion": "Nota con el registro más bajo encontrado en la obra",
        "keywords": ["nota grave", "rango", "registro inferior", "mínima"],
        "ejemplos": ["G4", "B3", "F#4"],
        "tipo": "TEXT"
    },
    {
        "tabla": "piezas",
        "columna": "nota_mas_aguda",
        "descripcion": "Nota con el registro más alto encontrado en la obra",
        "keywords": ["nota aguda", "rango", "registro superior", "máxima"],
        "ejemplos": ["G5", "B5", "F#5"],
        "tipo": "TEXT"
    },
    {
        "tabla": "piezas",
        "columna": "autor_genero",
        "descripcion": "Género o estilo atribuido al autor de la obra",
        "keywords": ["género", "estilo", "autor"],
        "ejemplos": ["desconocido", "femenino", "masculino"],
        "valores_validos": ["desconocido", "femenino", "masculino"],
        "tipo": "TEXT"
    },
    {
        "tabla": "piezas",
        "columna": "software_codificacion",
        "descripcion": "Herramienta o programa utilizado para la codificación de la pieza",
        "keywords": ["software", "codificación", "herramienta", "programa"],
        "ejemplos": ["Sibelius 7.1.3", "Desconocido", "MuseScore 4.5.2"],
        "tipo": "TEXT"
    },
    {
        "tabla": "piezas",
        "columna": "convertido_via_verovio",
        "descripcion": "Indicador lógico si el archivo fue convertido usando Verovio",
        "keywords": ["verovio", "conversión", "mei"],
        "ejemplos": [0, 1],
        "tipo": "INTEGER",
        "valores_validos": [0, 1]
    },
    {
        "tabla": "piezas",
        "columna": "formato_origen",
        "descripcion": "Formato original del archivo musical antes de procesamiento",
        "keywords": ["formato", "origen", "extensión"],
        "ejemplos": ["XML", "MEI", "MSCZ"],
        "valores_validos": ["XML", "MEI", "MSCZ"],
        "tipo": "TEXT"
    },
    {
        "tabla": "analisis_musical",
        "columna": "tiene_hemiolia_vertical",
        "descripcion": "Indica si la pieza contiene hemiolia vertical",
        "keywords": ["hemiolia", "vertical", "ritmo", "polirritmia"],
        "ejemplos": [0, 1],
        "tipo": "INTEGER",
        "valores_validos": [0, 1]
    },
    # {
    #     "tabla": "analisis_musical",
    #     "columna": "compases_hemiolia_vertical",
    #     "descripcion": "Listado de compases donde ocurre hemiolia vertical",
    #     "keywords": ["compases", "hemiolia vertical", "ubicación"],
    #     "tipo": "TEXT",
    #     "ejemplos": ["5, 7, 16", "2, 4, 6, 10, 14", "24"]
    # },
    {
        "tabla": "analisis_musical",
        "columna": "tiene_hemiolia_horizontal",
        "descripcion": "Indica si la pieza contiene hemiolia horizontal",
        "keywords": ["hemiolia", "horizontal", "ritmo", "hemiolia horizontal"],
        "ejemplos": [0, 1],
        "tipo": "INTEGER",
        "valores_validos": [0, 1]
    },
    # {
    #     "tabla": "analisis_musical",
    #     "columna": "compases_hemiolia_horizontal",
    #     "descripcion": "Listado de compases donde ocurre hemiolia horizontal",
    #     "keywords": ["compases", "hemiolia horizontal", "ubicación"],
    #     "tipo": "TEXT",
    #     "ejemplos": ["5, 7, 16", "2, 4, 6, 10, 14", "24"]
    # },
    # {
    #     "tabla": "analisis_musical",
    #     "columna": "compases_sincopas",
    #     "descripcion": "Listado de compases en los que se registran síncopas",
    #     "keywords": ["compases", "síncopas", "ubicación", "síncopa"],
    #     "tipo": "TEXT",
    #     "ejemplos": ["5, 7, 16", "2, 4, 6, 10, 14", "24"]
    # },
    {
        "tabla": "analisis_musical",
        "columna": "temas",
        "descripcion": "Temáticas musicales identificadas en la pieza",
        "keywords": ["temas", "motivos", "temática"],
        "ejemplos": ["amor, naturaleza", "nana", "naturaleza, musical", "picaresca, viaje"],
        "tipo": "TEXT"
    },
    {
        "tabla": "analisis_musical",
        "columna": "cambio_resolucion_ppq",
        "descripcion": "Determina si el valor de resolución rítmica (ppq base o dur.ppq por figura) cambia a mitad de una sección",
        "keywords": ["resolución", "ppq", "resolución rítmica"],
        "ejemplos": [0, 1],
        "tipo": "INTEGER",
        "valores_validos": [0, 1]
    },
    # {
    #     "tabla": "analisis_musical",
    #     "columna": "compases_cambio_resolucion",
    #     "descripcion": "Listado de compases en los que se registran cambios en los valores de resolución rítmica",
    #     "keywords": ["compases", "resolución rítmica", "ppq"],
    #     "tipo": "TEXT",
    #     "ejemplos": ["5, 7, 16", "2, 4, 6, 10, 14", "24"]
    # },
    {
        "tabla": "analisis_musical",
        "columna": "valores_irregulares_ocultos",
        "descripcion": "Detecta valores irregulares (como tresillos) en archivos MusicXML que no han sido declarados explícitamente mediante la etiqueta <time-modification>",
        "keywords": ["valores irregulares", "grupillos", "tresillos", "dosillos", "cuatrillos", "cinquillos", "seisillos", "septillos", "octillos"],
        "ejemplos": [0, 1],
        "tipo": "INTEGER",
        "valores_validos": [0, 1]
    },
    {
        "tabla": "analisis_musical",
        "columna": "total_eventos_musicales",
        "descripcion": "Suma total de eventos o notas a lo largo de la pieza",
        "keywords": ["total", "eventos", "notas", "conteo"],
        "tipo": "INTEGER",
        "ejemplos": [33, 118, 78, 8]
    },
    {
        "tabla": "analisis_musical",
        "columna": "total_compases",
        "descripcion": "Cantidad total de compases en la estructura de la pieza musical",
        "keywords": ["total", "compases", "longitud", "duración"],
        "tipo": "INTEGER",
        "ejemplos": [33, 9, 20, 8]
    },
    {
        "tabla": "analisis_musical",
        "columna": "densidad_notas_por_compas",
        "descripcion": "Promedio o densidad del número de notas por compás",
        "keywords": ["densidad", "promedio", "notas por compás", "actividad rítmica"],
        "tipo": "REAL",
        "ejemplos": [3.89, 5.78, 6.0, 5.4]
    },
    {
        "tabla": "analisis_musical",
        "columna": "tiene_polirritmia",
        "descripcion": "Indicador que muestra si existe polirritmia en la pieza musical",
        "keywords": ["polirritmia", "ritmos simultáneos"],
        "ejemplos": [0, 1],
        "tipo": "INTEGER",
        "valores_validos": [0, 1]
    },
    # {
    #     "tabla": "analisis_musical",
    #     "columna": "compases_polirritmia",
    #     "descripcion": "Listado de compases en los que se registran polirritmias",
    #     "keywords": ["compases", "polirritmia", "ritmos simultáneos"],
    #     "tipo": "TEXT",
    #     "ejemplos": ["5, 7, 16", "2, 4, 6, 10, 14", "24"]
    # },
    {
        "tabla": "analisis_musical",
        "columna": "lirica_voz",
        "descripcion": "Letras asociadas a la línea melódica principal o voz",
        "keywords": ["letra", "lírica", "voz", "texto", "género"],
        "tipo": "TEXT",
        "ejemplos": ["neutro", "desconocido", "masculino", "femenino"],
        "valores_validos": ["neutro", "desconocido", "masculino", "femenino"]
    },
    {
        "tabla": "analisis_musical",
        "columna": "texto_letras_extraido",
        "descripcion": "Letra extraída de la obra",
        "keywords": ["letra", "texto", "lírica"],
        "tipo": "TEXT",
        "ejemplos": [
            "Yo bajo del monte por ver a un zagal; traigo un pajarito que sabe cantar. Vetar. rás cómo canta, qué lindo que es, con trinos graciosos te va a compla cer. Sarandá, sarandá, sarandita; sarandita, sarandá; que yo quiero ver a ese Niño que ha nadico en un portal.", 
            "Tralara la la la, tralara la lara: tralara la la la tralara lara. A a e e e e", 
            "Sal a bailar, buena moza, sal a bailar, resala da, que tienes la sal del mundo y no te meneas nada El jeringoso del fraile consu jeringosa, que muy bien lo bailaesa moza, lo digo cantando, que muy bien le gusta bailarbo, déjala sola, solita, sola. Que la qulero ver bai lar, saltar y brincar y andar por el ai re que ésta es la canción del fraile, fraile cornudo, que la cale se salio desnudo, busque compa ña que a la calle se salió otra vez, queva mos a él."
        ]
    },
    {
        "tabla": "analisis_musical",
        "columna": "secuencia_notas_silencios",
        "descripcion": "Representación textual secuencial de las notas y silencios en la obra",
        "keywords": ["secuencia", "notas", "silencios", "melodía"],
        "tipo": "TEXT",
        "ejemplos": [
            "E4 - E4 - F4 - G4 - G4 - G4 - G4 - G4 - A4 - A4 - G4 - A4 - A4 - A4 - A4 - B4 - B4 - A4 - G4 - E4 - G4 - G4 - G4 - G4 - A4 - A4 - G4 - F4 - D4 - F4 - F4 - F4 - F4 - F4 - F4 - F4 - G4 - F4 - E4 - E4",
            "Silencio - Silencio - Silencio - Eb5 - Eb5 - Bb4 - G4 - G4 - A4 - A4 - Bb4 - F4 - F5 - A4 - F4 - Eb4 - A4 - Bb4 - E5 - F5 - D5 - D5 - Bb5 - Bb5 - G4 - Bb4 - Bb4 - F5 - G5 - F5 - E5 - F5 - F5 - D5 - D5 - G4 - G4 - A4 - A4 - G4 - G4 - Bb4 - G4 - Eb5 - Bb4 - Bb4 - F4 - A4 - F4 - F4 - F4 - Eb4 - F4 - A4 - F4 - A4 - G4 - Bb4 - F4 - G4 - A4 - Bb4 - Bb4 - A4 - E5 - F5 - D5 - D5 - D5 - C5 - Bb4 - Bb4 - D5 - D5 - G4 - Bb4 - A4 - Bb4 - F5 - G5 - E5 - G5 - F5 - E5 - D5 - D5 - C5 - C5 - C5 - F4 - A4 - Bb5 - Bb5 - Bb4 - Eb4 - F4 - Eb4 - Eb4 - A4 - G4 - G4 - G4 - F4 - Bb4 - A4 - G4 - Bb4 - E5 - F4 - A4 - E5 - F5 - F5 - Bb4 - Bb4 - D4 - D4 - A4 - G4 - C5 - F5 - G5 - F5 - E5 - F5 - F5 - Gb5 - F5 - D5 - D5 - G4 - Bb4 - A4 - F4 - A4 - Bb4 - Bb4 - G4 - G4 - Bb4 - G4 - F4 - F4 - F4 - F4 - A4 - Bb4 - F5 - G5 - F5 - E5 - F5 - F5 - F5 - F5 - E5 - D5 - D5 - C5 - G4 - A4 - Bb4 - A4 - F4 - G4 - A4 - G4 - D5 - C5 - Bb4 - A4 - G4 - G4 - G4 - A4 - Bb5 - Bb4 - F5 - G5 - E5 - F5 - F5 - F5 - D5 - D5 - C5 - G4 - A4 - Bb4 - F4 - G4 - A4 - Bb4 - G4 - C5 - G4 - E4 - F4 - F4 - Bb4 - Bb4 - A4 - Bb4 - F5 - G5 - E5 - F5 - G5 - D5 - D5 - C5 - G4 - F4 - A4 - F4 - G4 - A4 - Bb4 - Bb4 - E4 - D4 - C5 - Bb4 - A4 - Bb4 - C5 - A4 - A4 - F5 - F5 - E5 - F5 - F5 - E5 - D5 - C5 - D5 - C5 - G4 - A4 - B4 - F4 - G4 - A4 - Bb4 - G4 - C5 - Bb4 - G4 - F4 - Bb4 - Bb4 - G4 - A4 - A4 - F5 - E5 - F5 - G5 - E5 - F5 - F5 - D5 - C5 - D5 - C5 - G4 - G4 - G4 - A4 - A4 - F4 - G4 - A4 - Bb4 - D5 - C5 - Bb4 - A4 - G4 - C4 - G4 - G4 - G4 - A4 - C4 - F4 - E5 - E5 - G5 - E5 - E5 - F5 - C5 - D5 - C5 - A4 - A4 - G4 - F4 - G4 - A4 - Bb4 - G4 - C5 - Bb4 - G4 - Bb4 - F4 - F4 - F4 - F4 - F4 - G4 - F4 - E4 - F4 - G4 - A4 - F4 - Bb4 - A4 - G4 - F4 - G4 - A4 - Bb4 - A4 - C5 - F5 - E5 - F5 - D5 - C5 - Bb4 - A4 - Bb4 - D5 - C5 - A4 - G4 - G4 - A4 - Bb4 - C5 - F5 - G5 - F5 - E5 - F5 - E5 - D5 - C5 - D5 - C5 - G4 - A4 - B4 - A4 - F4 - G4 - A4 - Bb4 - G4 - C5 - C6 - G4 - F4 - F4 - F4 - Bb4 - B4 - A4 - G4 - F4 - Bb4 - G4 - Bb4 - F4 - Bb4 - A4 - Bb4 - F4 - G4 - A4 - F4 - Bb4 - A4 - Bb4 - C5 - F4 - E5 - F5 - D5 - C5 - Bb4 - A4 - Bb4 - D5 - C5 - A4 - G4", 
            "C5 - Silencio - [E4+C5] - [C3+E3+G3] - G4 - G4 - [C3+E3+G3] - [E4+G4] - [C3+E3+G3] - E4 - E4 - [C3+E3+G3] - [E4+C5] - [C3+E3+G3] - G4 - G4 - [C3+E3+G3] - [F4+G4] - [B2+D3+G3] - A4 - B4 - [B2+D3+G3] - [E4+C5] - [C3+E3+G3] - G4 - G4 - [C3+E3+G3] - [E4+G4] - [C3+E3+G3] - [D4+F4] - [C4+E4] - [C3+E3+G3] - [B3+D4] - [G2+D3+G3] - G4 - G4 - [G2+D3+G3] - [B3+G4] - [G2+D3+G3] - B4 - Silencio - [E4+C5] - [C3+E3+G3] - G4 - G4 - [C3+E3+G3] - [E4+G4] - [C3+E3+G3] - E4 - E4 - [C3+E3+G3] - [E4+C5] - [C3+E3+G3] - G4 - G4 - [C3+E3+G3] - [F4+B4] - [D3+F3+G3] - A4 - G4 - [D3+F3+G3] - [E4+G4] - [C3+E3+G3] - A4 - B4 - [C3+E3+G3] - [G4+C5] - [E3+G3+C4] - E5 - D5 - [E3+G3+C4] - [A4+C5] - [E3+A3+C4] - A4 - A4 - [E3+A3+C4] - A4 - [E3+A3+C4] - E5 - Silencio - F5 - G5 - C3 - F5 - [E3+G3+C4] - [E5+G5] - [E3+G3+C4] - E5 - C3 - F5 - [E3+G3+C4] - [E5+G5] - [E3+G3+C4] - F5 - B2 - E5 - [D3+G3+B3] - D5 - [D3+G3+B3] - C5 - C3 - D5 - [E3+G3+C4] - E5 - [E3+G3+C4] - A5 - F3 - G5 - [A3+C4] - A5 - [A3+C4] - E5 - E3 - A5 - [A3+C4] - A5 - [A3+C4] - E5 - D3 - D5 - [F3+G3+B3] - C5 - [F3+G3+B3] - D5 - B2 - E5 - [F3+G3] - F5 - [F3+G3] - G5 - C3 - F5 - [E3+G3+C4] - [E5+G5] - [E3+G3+C4] - E5 - C3 - D5 - [E3+G3+C4] - C5 - [E3+G3+C4] - E5 - F3 - D5 - [A3+D4] - E5 - [A3+D4] - D5 - F3 - C5 - [A3+D4] - A4 - [A3+D4] - [E4+G4] - G3 - A4 - [G3+C4] - B4 - [G3+C4] - [G4+C5] - E3 - E5 - [G3+C4] - D5 - [G3+C4] - [A4+C5] - A3 - A4 - [C4+E4] - A4 - [C4+E4] - A4 - [C4+E4]", 
            "B4 - D5 - C5 - A4 - G4 - G4 - A4 - G4 - C5 - A4 - B4 - A4 - G4 - B4 - D5 - C5 - A4 - G4 - G5 - F#5 - D5 - C5 - A4 - G4 - G4 - F#5 - A5 - F#5 - G5 - A5 - G5 - F#5 - A5 - G5 - F#5 - D5 - D5 - F#5 - A5 - G5 - A5 - G5 - F#5 - D5 - C5 - A4 - G4 - G4 - F#5 - A5 - F#5 - G5 - A5 - G5 - F#5 - A5 - G5 - F#5 - D5 - D5 - F#5 - G5 - A5 - B5 - A5 - G5 - F#5 - D5 - C5 - A4 - G4 - G4"
        ]
    },
    {
        "tabla": "analisis_musical",
        "columna": "tendencia_melodica",
        "descripcion": "Indica la tendencia general de la melodía en términos de intervalos ascendentes o descendentes",
        "keywords": ["tendencia melódica", "melodía", "ascendente", "descendente"],
        "tipo": "TEXT",
        "ejemplos": ["Estática (solo notas repetidas o pieza vacía)", "Predominantemente descendente", "Predominantemente ascendente", "Equilibrada"],
        "valores_validos": ["Estática (solo notas repetidas o pieza vacía)", "Predominantemente descendente", "Predominantemente ascendente", "Equilibrada"]
    },
    {
        "tabla": "analisis_musical",
        "columna": "porcentaje_intervalos_ascendentes",
        "descripcion": "Cálculo en porcentaje de los intervalos melódicos que ascienden",
        "keywords": ["porcentaje", "intervalos", "ascendente", "melodía"],
        "tipo": "REAL",
        "ejemplos": [45.33, 50.0, 39.9, 47.06]
    },
    {
        "tabla": "analisis_musical",
        "columna": "porcentaje_intervalos_descendentes",
        "descripcion": "Cálculo en porcentaje de los intervalos melódicos que descienden",
        "keywords": ["porcentaje", "intervalos", "descendente", "melodía"],
        "tipo": "REAL",
        "ejemplos": [45.33, 50.0, 39.9, 47.06]
    },
    {
        "tabla": "analisis_musical",
        "columna": "mapeo_silabas_duraciones",
        "descripcion": "Datos en formato JSON que representan la correspondencia entre sílabas de la letra y sus duraciones musicales",
        "keywords": ["mapeo", "sílabas", "duraciones", "melodía"],
        "tipo": "TEXT",
        "ejemplos": [
            "{\"yo\": [0.5], \"no\": [0.5, 1.0]}", 
            "{\"ra\": [0.25], \"ta\": [0.25, 0.5]}", 
            "{\"oh\": [0.5], \"pan\": [0.5], \"buen\": [0.5], \"de\": [0.5]}", 
            "{\"da\": [0.25, 0.5, 1.0], \"nues\": [1.0]}"
        ]
    },
    {
        "tabla": "analisis_musical",
        "columna": "accidentales_compases_json",
        "descripcion": "Datos en formato JSON que representan la ubicación de alteraciones accidentales dentro de los compases",
        "keywords": ["alteraciones", "alteraciones accidentales", "compases", "melodía"],
        "tipo": "TEXT",
        "ejemplos": [
            "{\"F#5\": [5]}", 
            "{\"F#4\": [1], \"F#5\": [3]}", 
            "{\"C#5\": [3]}", 
            "{\"C#5\": [1], \"F#4\": [1]}"
        ]
    },
    {
        "tabla": "analisis_musical",
        "columna": "qc_compases_vacios",
        "descripcion": "Indica el número de compases vacíos en la obra",
        "keywords": ["compases vacíos", "vacíos", "calidad de datos", "qc"],
        "ejemplos": [0, 1, 10, 13],
        "tipo": "INTEGER"
    },
    {
        "tabla": "analisis_musical",
        "columna": "qc_notas_duracion_cero",
        "descripcion": "Indica el número de notas con duración cero en la obra",
        "keywords": ["notas", "duración cero", "calidad de datos", "qc"],
        "ejemplos": [0, 1, 10, 13],
        "tipo": "INTEGER"
    },
    {
        "tabla": "analisis_musical",
        "columna": "qc_advertencias_criticas",
        "descripcion": "Registro de advertencias críticas relacionadas con desajustes o silencios faltantes que podrían afectar la calidad de los datos",
        "keywords": ["advertencias", "desajustes", "silencios faltantes", "calidad de datos", "qc"],
        "tipo": "TEXT",
        "ejemplos": [
            "Advertencia: Pequeños desajustes o silencios faltantes detectados", 
            "Ninguna"
        ]
    },
    {
        "tabla": "analisis_musical",
        "columna": "qc_puntuacion_integridad",
        "descripcion": "Puntuación de control de calidad sobre la integridad general de los datos de la pieza",
        "keywords": ["calidad", "qc", "integridad", "puntuación"],
        "tipo": "REAL",
        "ejemplos": [85.0, 50.0, 100.0, 90.0]
    },
    {
        "tabla": "analisis_musical",
        "columna": "tiene_leitmotivs",
        "descripcion": "Indica si se han detectado leitmotivs dentro de la obra",
        "keywords": ["leitmotiv", "motivo", "repetición"],
        "ejemplos": [0, 1],
        "tipo": "INTEGER",
        "valores_validos": [0, 1]
    },
    {
        "tabla": "analisis_musical",
        "columna": "patrones_leitmotivs_json",
        "descripcion": "Datos en formato JSON que almacenan los patrones de leitmotivs detectados",
        "keywords": ["patrones", "leitmotiv", "json", "estructura"],
        "tipo": "TEXT",
        "ejemplos": [
            "{\"+2 -> -2 -> 0\": 11, \"-2 -> 0 -> +5\": 2}", 
            "{\"0 -> +5 -> -1\": 2, \"+5 -> -1 -> -4\": 2}", 
            "{\"-1 -> -4 -> +7\": 4, \"-4 -> +7 -> -3\": 4}", 
            "{\"-2 -> +2 -> +5 -> 0\": 2, \"+2 -> +5 -> 0 -> 0\": 2}"
        ]
    },
    {
        "tabla": "analisis_musical",
        "columna": "tiene_plicas_anomalas",
        "descripcion": "Indica si se han detectado plicas anómalas dentro de la obra",
        "keywords": ["plicas", "plicas anómalas", "anomalías", "notas"],
        "ejemplos": [0, 1],
        "tipo": "INTEGER",
        "valores_validos": [0, 1]
    },
    {
        "tabla": "analisis_musical",
        "columna": "conteo_plicas_anomalas",
        "descripcion": "Suma total de plicas anómalas detectadas en la obra",
        "keywords": ["total", "plicas", "anómalas", "conteo"],
        "tipo": "INTEGER",
        "ejemplos": [0, 1, 2, 6]
    },
    # {
    #     "tabla": "analisis_musical",
    #     "columna": "compases_plicas_anomalas",
    #     "descripcion": "Listado de compases donde ocurren plicas anómalas",
    #     "keywords": ["compases", "plicas anómalas", "ubicación"],
    #     "tipo": "TEXT",
    #     "ejemplos": ["5, 7, 16", "2, 4, 6, 10, 14", "24"]
    # },
    {
        "tabla": "analisis_musical",
        "columna": "lirica_sustantivos",
        "descripcion": "Listado de sustantivos encontrados en la letra de la pieza",
        "keywords": ["lírica", "sustantivos", "letra"],
        "tipo": "TEXT",
        "ejemplos": [
            "agravio, amigo, ave, cantora, hora, libertad, libro, puerta, ro, sabio, seve, tona, tone", 
            "almohadita, capullo, carmesí, día, mejilla", 
            "caricia, causa, chiquitín, encaje, escuela, fin, madre, mujercita, pequeñito, placer, trabajo"
            ]
    },
    {
        "tabla": "analisis_musical",
        "columna": "lirica_nombres_propios",
        "descripcion": "Listado de nombres propios encontrados en la letra de la pieza",
        "keywords": ["lírica", "nombres propios", "letra"],
        "tipo": "TEXT",
        "ejemplos": [
            "Fray, Martín, dindon, dindon don dindon don, don", 
            "Rosa", 
            "Antio, Bogotá, Bogotá Yo Una tierra, Boyacá, Boyacá No de Antio, Cartagena, Colombia, Colombianos, Nación, Nación Oja, Neiva, Oja, Patria, Popayán, Yo, de Colombia"
            ]
    },
    {
        "tabla": "analisis_musical",
        "columna": "intervalo_frontera_mas_frecuente",
        "descripcion": "Intervalo de frontera más frecuente en la pieza",
        "keywords": ["intervalo", "intervalo frontera", "frecuente"],
        "tipo": "TEXT",
        "ejemplos": ["-3", "+5", "0", "+2"]
    },
    {
        "tabla": "analisis_musical",
        "columna": "tiene_etiqueta_sb",
        "descripcion": "Presencia de etiquetas relacionadas con System Breaks (sb) u otras marcas estructurales",
        "keywords": ["etiqueta", "sb", "system break", "formato"],
        "ejemplos": [0, 1],
        "tipo": "INTEGER",
        "valores_validos": [0, 1]
    },
    {
        "tabla": "analisis_musical",
        "columna": "sb_coincide_con_frase_logica",
        "descripcion": "Coincidencia entre la ubicación de etiquetas sb y las frases lógicas o unidades musicales en la pieza",
        "keywords": ["etiqueta", "sb", "system break", "formato", "frase lógica"],
        "ejemplos": [0, 1, 3, 6],
        "tipo": "INTEGER"
    },
    {
        "tabla": "analisis_musical",
        "columna": "sb_total_system_breaks",
        "descripcion": "Total de system breaks encontrados en la pieza",
        "keywords": ["etiqueta", "sb", "system break", "formato"],
        "ejemplos": [0, 1, 3, 6],
        "tipo": "INTEGER"
    }
]