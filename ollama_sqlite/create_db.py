import sqlite3

def crear_base_de_datos(db_path='corpus_musical.db'):
    conexion = sqlite3.connect(db_path)
    cursor = conexion.cursor()

    # Habilitar soporte para claves foráneas en SQLite
    cursor.execute("PRAGMA foreign_keys = ON;")

    # METADATOS GENERALES DE LA PIEZA
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS piezas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            titulo TEXT,
            autor TEXT,
            compas TEXT,
            tonalidad TEXT,
            modo TEXT,
            modo_completo TEXT,
            bpm INTEGER,
            midi_volume INTEGER,
            nota_mas_grave TEXT,
            nota_mas_aguda TEXT,
            region TEXT,
            region_justificacion TEXT,
            autor_genero TEXT,
            software_codificacion TEXT,
            convertido_via_verovio INTEGER,
            fecha_codificacion TEXT,
            formato_origen TEXT
        )
    ''')

    # ANÁLISIS MUSICAL DETALLADO Y COMPLEJO
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analisis_musical (
            pieza_id INTEGER PRIMARY KEY,
            tiene_hemiolia_vertical INTEGER,
            compases_hemiolia_vertical TEXT,
            conteo_hemiolia_vertical INTEGER,
            tiene_hemiolia_horizontal INTEGER,
            compases_hemiolia_horizontal TEXT,
            conteo_hemiolia_horizontal INTEGER,
            tiene_sincopas INTEGER,
            compases_sincopas TEXT,
            conteo_sincopas INTEGER,
            temas TEXT,
            cambio_resolucion_ppq INTEGER,
            compases_cambio_resolucion TEXT,
            desajuste_duracion_meter INTEGER,
            compases_desajuste_duracion_meter TEXT,
            valores_irregulares_ocultos INTEGER,
            compases_valores_irregulares_ocultos TEXT,
            conteo_valores_irregulares_ocultos INTEGER,
            total_eventos_musicales INTEGER,
            total_compases INTEGER,
            densidad_notas_por_compas REAL,
            tiene_polirritmia INTEGER,
            compases_polirritmia TEXT,
            conteo_polirritmia INTEGER,
            lirica_voz TEXT,
            texto_letras_extraido TEXT,
            secuencia_notas_silencios TEXT,
            tendencia_melodica TEXT,
            porcentaje_intervalos_ascendentes REAL,
            porcentaje_intervalos_descendentes REAL,
            mapeo_silabas_duraciones TEXT,
            accidentales_compases_json TEXT,
            accidentales_resumen_texto TEXT,
            conteo_accidentales_totales INTEGER,
            qc_compases_vacios INTEGER,
            qc_notas_duracion_cero INTEGER,
            qc_advertencias_criticas TEXT,
            qc_puntuacion_integridad REAL,
            tiene_leitmotivs INTEGER,
            patrones_leitmotivs_json TEXT,
            tiene_plicas_anomalas INTEGER,
            conteo_plicas_anomalas INTEGER,
            compases_plicas_anomalas TEXT,
            lirica_sustantivos TEXT,
            lirica_nombres_propios TEXT,
            intervalo_frontera_mas_frecuente TEXT,
            frecuencia_intervalo_frontera INTEGER,
            tiene_etiqueta_sb INTEGER,
            sb_coincide_con_frase_logica INTEGER,
            sb_total_system_breaks INTEGER,
            sb_saltos_en_fin_de_frase INTEGER,
            FOREIGN KEY(pieza_id) REFERENCES piezas(id) ON DELETE CASCADE
        )
    ''')

    conexion.commit()
    conexion.close()
    print("¡Base de datos y tablas creadas con éxito con todos los nuevos campos!")

if __name__ == '__main__':
    crear_base_de_datos()