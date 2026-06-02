import sqlite3
import json
from pathlib import Path
from db_tools import descubrir_archivos_partitura, analizar_pieza


_BASE_DIR = Path(__file__).parent
DATASET_DIR = _BASE_DIR.parent / "datasets"

def sanitizar_y_aplanar_registro(resultado: dict) -> dict:
    """
    Toma el diccionario generado por analizar_pieza, aplana sub-diccionarios
    como detalles_sb y convierte listas o estructuras JSON en cadenas de texto.
    """
    # Aplanar el sub-diccionario 'detalles_sb'
    detalles_sb = resultado.get("detalles_sb", {}) if isinstance(resultado.get("detalles_sb"), dict) else {}
    resultado["sb_total_system_breaks"] = detalles_sb.get("total_system_breaks", 0)
    resultado["sb_saltos_en_fin_de_frase"] = detalles_sb.get("saltos_en_fin_de_frase", 0)
    
    # Asegurar que listas, sets o diccionarios se conviertan a texto plano o JSON String
    for clave, valor in resultado.items():
        if isinstance(valor, (list, set)):
            resultado[clave] = ", ".join(map(str, valor))
        elif isinstance(valor, dict) and clave != "detalles_sb":
            resultado[clave] = json.dumps(valor, ensure_ascii=False)
            
    return resultado

def insertar_analisis_en_db(resultado_analisis: dict, db_path='corpus_musical.db'):
    conexion = sqlite3.connect(db_path)
    cursor = conexion.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Sanitizamos los tipos de datos internos antes de la inserción
    datos = sanitizar_y_aplanar_registro(resultado_analisis)
    
    try:
        # Insertar en la tabla principal (Si el archivo ya existe, lo ignora o actualiza según prefieras)
        cursor.execute('''
            INSERT OR IGNORE INTO piezas (
                file_path, titulo, autor, compas, tonalidad, modo, modo_completo, bpm, 
                midi_volume, nota_mas_grave, nota_mas_aguda, region, region_justificacion, 
                autor_genero, software_codificacion, convertido_via_verovio, fecha_codificacion, formato_origen
            ) VALUES (
                :file_path, :titulo, :autor, :compas, :tonalidad, :modo, :modo_completo, :bpm, 
                :midi_volume, :nota_mas_grave, :nota_mas_aguda, :region, :region_justificacion, 
                :autor_genero, :software_codificacion, :convertido_via_verovio, :fecha_codificacion, :formato_origen
            )
        ''', datos)
        
        # Recuperamos el ID asignado a esta pieza basándonos en su ruta única
        cursor.execute('SELECT id FROM piezas WHERE file_path = ?', (datos['file_path'],))
        pieza_id = cursor.fetchone()[0]
        datos['pieza_id'] = pieza_id
        
        # Insertar o actualizar en la tabla de análisis musical vinculada al ID
        cursor.execute('''
            INSERT OR REPLACE INTO analisis_musical (
                pieza_id, tiene_hemiolia_vertical, compases_hemiolia_vertical, conteo_hemiolia_vertical,
                tiene_hemiolia_horizontal, compases_hemiolia_horizontal, conteo_hemiolia_horizontal,
                tiene_sincopas, compases_sincopas, conteo_sincopas, temas, cambio_resolucion_ppq,
                compases_cambio_resolucion, desajuste_duracion_meter, compases_desajuste_duracion_meter,
                valores_irregulares_ocultos, compases_valores_irregulares_ocultos, conteo_valores_irregulares_ocultos,
                total_eventos_musicales, total_compases, densidad_notas_por_compas, tiene_polirritmia,
                compases_polirritmia, conteo_polirritmia, lirica_voz, texto_letras_extraido,
                secuencia_notas_silencios, tendencia_melodica, porcentaje_intervalos_ascendentes,
                porcentaje_intervalos_descendentes, mapeo_silabas_duraciones, accidentales_compases_json,
                accidentales_resumen_texto, conteo_accidentales_totales, qc_compases_vacios,
                qc_notas_duracion_cero, qc_advertencias_criticas, qc_puntuacion_integridad,
                tiene_leitmotivs, patrones_leitmotivs_json, tiene_plicas_anomalas, conteo_plicas_anomalas,
                compases_plicas_anomalas, lirica_sustantivos, lirica_nombres_propios,
                intervalo_frontera_mas_frecuente, frecuencia_intervalo_frontera, tiene_etiqueta_sb,
                sb_coincide_con_frase_logica, sb_total_system_breaks, sb_saltos_en_fin_de_frase
            ) VALUES (
                :pieza_id, :tiene_hemiolia_vertical, :compases_hemiolia_vertical, :conteo_hemiolia_vertical,
                :tiene_hemiolia_horizontal, :compases_hemiolia_horizontal, :conteo_hemiolia_horizontal,
                :tiene_sincopas, :compases_sincopas, :conteo_sincopas, :temas, :cambio_resolucion_ppq,
                :compases_cambio_resolucion, :desajuste_duracion_meter, :compases_desajuste_duracion_meter,
                :valores_irregulares_ocultos, :compases_valores_irregulares_ocultos, :conteo_valores_irregulares_ocultos,
                :total_eventos_musicales, :total_compases, :densidad_notas_por_compas, :tiene_polirritmia,
                :compases_polirritmia, :conteo_polirritmia, :lirica_voz, :texto_letras_extraido,
                :secuencia_notas_silencios, :tendencia_melodica, :porcentaje_intervalos_ascendentes,
                :porcentaje_intervalos_descendentes, :mapeo_silabas_duraciones, :accidentales_compases_json,
                :accidentales_resumen_texto, :conteo_accidentales_totales, :qc_compases_vacios,
                :qc_notas_duracion_cero, :qc_advertencias_criticas, :qc_puntuacion_integridad,
                :tiene_leitmotivs, :patrones_leitmotivs_json, :tiene_plicas_anomalas, :conteo_plicas_anomalas,
                :compases_plicas_anomalas, :lirica_sustantivos, :lirica_nombres_propios,
                :intervalo_frontera_mas_frecuente, :frecuencia_intervalo_frontera, :tiene_etiqueta_sb,
                :sb_coincide_con_frase_logica, :sb_total_system_breaks, :sb_saltos_en_fin_de_frase
            )
        ''', datos)
        
        conexion.commit()
        print(f"-> [ÉXITO] Guardado análisis de: {datos['titulo']} ({datos['file_path']})")
    except Exception as e:
        print(f"!! [ERROR] Error procesando la inserción de {datos.get('file_path')}: {e}")
    finally:
        conexion.close()

def procesar_todo_el_corpus(directorio_corpus):
    """
    Función principal encargada de recorrer todo el árbol de directorios del corpus
    """
    path_corpus = Path(directorio_corpus)
    if not path_corpus.exists():
        print(f"La ruta del corpus '{directorio_corpus}' no existe.")
        return

    print(f"Buscando archivos musicales válidos en '{directorio_corpus}'...")
    archivos = descubrir_archivos_partitura(path_corpus)
    print(f"Se encontraron {len(archivos)} archivos. Iniciando análisis...")

    for i, file_path in enumerate(archivos, start=1):
        print(f"[{i}/{len(archivos)}] Analizando: {Path(file_path).name}")
        try:
            # Llamamos a tu motor analítico de music21/LLM
            analisis = analizar_pieza(file_path)
            # Insertamos en SQLite de manera robusta
            insertar_analisis_en_db(analisis)
        except Exception as err:
            nombre = getattr(file_path, "name", str(file_path))
            print(f"Error crítico analizando {nombre}: {err}")

if __name__ == '__main__':
    procesar_todo_el_corpus(DATASET_DIR)