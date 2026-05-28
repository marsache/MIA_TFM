import sqlite3
from db_tools import detectar_hemiolas_verticales

def guardar_analisis_en_db(file_path, titulo, compas, tonalidad, bpm, tiene_sincopa, num_sincopas):
    conexion = sqlite3.connect('corpus_musical.db')
    cursor = conexion.cursor()
    
    try:
        # Insertar en la tabla piezas
        cursor.execute('''
            INSERT INTO piezas (file_path, titulo, compas, tonalidad, bpm)
            VALUES (?, ?, ?, ?, ?)
        ''', (file_path, titulo, compas, tonalidad, bpm))
        
        # Recuperar el ID que se le acaba de asignar automáticamente a esta pieza
        id_pieza = cursor.lastrowid
        
        # Insertar sus analíticas rítmicas usando ese ID
        cursor.execute('''
            INSERT INTO analisis_ritmico (pieza_id, tiene_sincopas_sistematicas, conteo_sincopas)
            VALUES (?, ?, ?)
        ''', (id_pieza, 1 if tiene_sincopa else 0, num_sincopas))
        
        conexion.commit()
    except sqlite3.IntegrityError:
        print(f"El archivo {file_path} ya estaba registrado.")
    finally:
        conexion.close()

# Ejemplos: El script procesa dos canciones del corpus
# guardar_analisis_en_db("corpus/cancion_1.xml", "Charrada Salamantina", "2/4", "La menor", 85, tiene_sincopa=True, num_sincopas=12)
# guardar_analisis_en_db("corpus/cancion_2.mei", "Muiñeira de Poio", "6/8", "Sol mayor", 115, tiene_sincopa=False, num_sincopas=0)

def procesar_y_guardar_pieza(file_path, pieza_id):
    # Ejecutar el análisis musical con music21
    lista_compases = detectar_hemiolas_verticales(file_path)
    
    # Preparar los datos para SQLite
    tiene_hemiolia = 1 if len(lista_compases) > 0 else 0
    
    if tiene_hemiolia:
        # Convertimos la lista [4, 8, 12] en el texto "4, 8, 12"
        compases_texto = ", ".join(map(str, lista_compases))
    else:
        compases_texto = "Ninguno"

    # Insertar en la Base de Datos
    conexion = sqlite3.connect('corpus_musical.db')
    cursor = conexion.cursor()
    
    # Nota: Aquí hacemos un UPDATE suponiendo que la pieza ya existe en la DB,
    # o un INSERT si estás metiendo todos los datos rítmicos de golpe.
    cursor.execute('''
        INSERT INTO analisis_ritmico (pieza_id, tiene_hemiolia_vertical, compases_hemiolia_vertical)
        VALUES (?, ?, ?)
    ''', (pieza_id, tiene_hemiolia, compases_texto))
    
    conexion.commit()
    conexion.close()
    print(f"Procesado exitoso: ID {pieza_id} | Hemiolia: {tiene_hemiolia} | Compases: {compases_texto}")

# Ejemplo de ejecución simulada en tu bucle de 10.000 canciones:
# procesar_y_guardar_pieza("corpus/muineira_vigo.xml", pieza_id=42)