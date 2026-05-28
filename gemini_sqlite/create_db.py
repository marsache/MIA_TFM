import sqlite3

# Nos conectamos (creará el archivo 'corpus_musical.db' en la misma carpeta)
conexion = sqlite3.connect('corpus_musical.db')
cursor = conexion.cursor()

# Creamos la tabla principal de piezas
cursor.execute('''
    CREATE TABLE IF NOT EXISTS piezas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT UNIQUE,
        titulo TEXT,
        compas TEXT,
        tonalidad TEXT,
        bpm INTEGER
    )
''')

# Creamos la tabla de características específicas (para las síncopas, hemiolias, etc.)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS analisis_ritmico (
        pieza_id INTEGER,
               
        -- CAMPOS PARA SINCOPAS --
        tiene_sincopas_sistematicas INTEGER, -- Usamos 1 para Sí, 0 para No
        conteo_sincopas INTEGER,
               
        -- CAMPOS PARA HEMIOLIAS --
        tiene_hemiolia_vertical INTEGER,      -- 1 si tiene, 0 si no
        compases_hemiolia_vertical TEXT,      -- Guardará texto como "4, 8, 12"
               
        FOREIGN KEY(pieza_id) REFERENCES piezas(id)
    )
''')

# Guardamos los cambios y cerramos
conexion.commit()
conexion.close()
print("¡Base de datos y tablas creadas con éxito!")