from __future__ import annotations

import subprocess
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tempfile
import xml.etree.ElementTree as ET

import music21 as m21

import json
import requests

from fractions import Fraction
from collections import defaultdict
import zipfile
from typing import List, Dict, Any
import unicodedata
from collections import Counter


SUPPORTED_SONG_EXTENSIONS = {".xml", ".musicxml", ".mxl", ".mei", ".mscz"}
_EPSILON = 1e-3

m21.environment.set('musescoreDirectPNGPath', 'C:/Program Files/MuseScore 4/bin/MuseScore4.exe') # Windows

@dataclass
class RhythmPatternResult:
    tiene_patron: int
    compases: list[int]

    @property
    def compases_texto(self) -> str:
        return ", ".join(map(str, self.compases)) if self.compases else ""


def _to_float(value: Any) -> float:
    return float(value) if value is not None else 0.0


def _is_close(a: float, b: float, tol: float = _EPSILON) -> bool:
    return abs(a - b) <= tol


def _contains_offset(offsets: set[float], target: float) -> bool:
    return any(_is_close(value, target) for value in offsets)


def _safe_parse_score(file_path: str | Path) -> m21.stream.Score | None:
    try:
        path_obj = Path(file_path)
        orig_suffix = path_obj.suffix.lower()

        # Tratamiento especial para .mscz (No soportado nativamente por music21)
        if orig_suffix == ".mscz":
            musescore_exe = 'C:/Program Files/MuseScore 4/bin/MuseScore4.exe'
            
            # Creamos un archivo temporal con extensión .mxl (MusicXML Comprimido)
            with tempfile.NamedTemporaryFile(suffix=".mxl", delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                # Invocamos a MuseScore CLI para convertir el .mscz a .mxl
                # Comando equivalente: MuseScore4.exe -o destino.mxl origen.mscz
                cmd = [musescore_exe, "-o", tmp_path, str(path_obj)]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Ahora que es un .mxl estándar, music21 lo leerá sin problemas
                score = m21.converter.parse(tmp_path)
                return score
            finally:
                # Nos aseguramos de borrar el archivo temporal .mxl del disco duro
                try:
                    Path(tmp_path).unlink()
                except Exception:
                    pass

        # Los archivos .mxl sí son contenedores estándar que music21 lee de forma nativa
        if orig_suffix == ".mxl":
            return m21.converter.parse(str(path_obj))

        # Para archivos basados en texto plano estructurado (MEI y XML estándar)
        text = path_obj.read_text(encoding="utf-8")

        if orig_suffix == ".mei":
            # music21 no soporta wordpos="s"
            text = text.replace('wordpos="s"', 'wordpos="i"')

        with tempfile.NamedTemporaryFile(
            suffix=orig_suffix,
            delete=False,
            mode="w",
            encoding="utf-8",
        ) as tmp:
            tmp.write(text)
            tmp_path = tmp.name

        try:
            return m21.converter.parse(tmp_path)
        finally:
            try:
                Path(tmp_path).unlink()
            except Exception:
                pass

    except Exception as e:
        print(f"ERROR PARSEANDO {file_path}")
        print(type(e).__name__, e)
        raise

def _extract_mei_metadata_direct(file_path: str | Path) -> dict[str, Any]:
    """
    Scraper XML directo para archivos MEI. Extrae elementos que music21 suele omitir
    en su objeto metadata estándar.
    """
    meta = {"title": None, "author": None, "compas": None, "key_sig": None}
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        ns = {'mei': 'http://www.music-encoding.org/ns/mei'}
        
        # Extraer Título Principal
        title_el = root.find('.//mei:titleStmt/mei:title[@type="main"]', ns)
        if title_el is None:
            title_el = root.find('.//mei:titleStmt/mei:title', ns)
        if title_el is not None and title_el.text:
            meta["title"] = title_el.text.strip()
            
        # Extraer Autor desde workList
        author_el = root.find('.//mei:workList/mei:work/mei:author', ns)
        if author_el is None:
            author_el = root.find('.//mei:composer', ns)
        if author_el is not None and author_el.text:
            meta["author"] = author_el.text.strip()
            
        # Extraer Compás desde la definición del Staff
        meter_el = root.find('.//mei:meterSig', ns)
        if meter_el is not None:
            count = meter_el.get('count')
            unit = meter_el.get('unit')
            sym = meter_el.get('sym')
            if count and unit:
                meta["compas"] = f"{count}/{unit}"
            elif sym == "common":
                meta["compas"] = "4/4"
                
        # Extraer valor de la Armadura (ej: '1f' = 1 flat)
        key_el = root.find('.//mei:keySig', ns)
        if key_el is not None:
            meta["key_sig"] = key_el.get('sig')

        geog_el = root.find('.//mei:geogName', ns)
        if geog_el is None:
            geog_el = root.find('.//mei:region', ns)
        if geog_el is not None and geog_el.text:
            meta["region"] = geog_el.text.strip()
            
    except Exception as e:
        print(f"Aviso: No se pudo realizar el escaneo XML directo en {file_path}: {e}")
    return meta


def _infer_tonality_custom(score: m21.stream.Score, mei_sig: str | None) -> str | None:
    """
    Infiere la tonalidad cruzando el número de alteraciones de la armadura 
    con la última nota de la obra (Tónica por resolución de cadencia).
    """
    sharps = None
    for ks in score.recurse().getElementsByClass(m21.key.KeySignature):
        sharps = ks.sharps
        break
    
    if sharps is None and mei_sig:
        if mei_sig == "0":
            sharps = 0
        elif mei_sig.endswith("f"):
            sharps = -int(mei_sig[:-1])
        elif mei_sig.endswith("s"):
            sharps = int(mei_sig[:-1])
            
    if sharps is None:
        sharps = 0
        
    sharps_to_keys = {
         0: (("C", "major"), ("A", "minor")),
         1: (("G", "major"), ("E", "minor")),
         2: (("D", "major"), ("B", "minor")),
         3: (("A", "major"), ("F-sharp", "minor")),
         4: (("E", "major"), ("C-sharp", "minor")),
         5: (("B", "major"), ("G-sharp", "minor")),
         6: (("F-sharp", "major"), ("D-sharp", "minor")),
         7: (("C-sharp", "major"), ("A-sharp", "minor")),
        -1: (("F", "major"), ("D", "minor")),
        -2: (("B-flat", "major"), ("G", "minor")),
        -3: (("E-flat", "major"), ("C", "minor")),
        -4: (("A-flat", "major"), ("F", "minor")),
        -5: (("D-flat", "major"), ("B-flat", "minor")),
        -6: (("G-flat", "major"), ("E-flat", "minor")),
        -7: (("C-flat", "major"), ("A-flat", "minor")),
    }
    
    if sharps not in sharps_to_keys:
        return None
        
    major_opt, minor_opt = sharps_to_keys[sharps]
    
    all_notes = list(score.recurse().getElementsByClass(m21.note.Note))
    if not all_notes:
        return f"{major_opt[0]} {major_opt[1]}"
        
    last_note = all_notes[-1]
    last_pitch_name = last_note.pitch.name
    
    last_pitch_norm = last_pitch_name.replace('-', '-flat').replace('#', '-sharp')
    
    if last_pitch_norm == major_opt[0]:
        return f"{major_opt[0]} {major_opt[1]}"
    elif last_pitch_norm == minor_opt[0]:
        return f"{minor_opt[0]} {minor_opt[1]}"
        
    major_count = sum(1 for n in all_notes if n.pitch.name.replace('-', '-flat').replace('#', '-sharp') == major_opt[0])
    minor_count = sum(1 for n in all_notes if n.pitch.name.replace('-', '-flat').replace('#', '-sharp') == minor_opt[0])
    
    if minor_count > major_count:
        return f"{minor_opt[0]} {minor_opt[1]}"
    return f"{major_opt[0]} {major_opt[1]}"


def _get_measure_time_signature(
    measure: m21.stream.Measure,
) -> m21.meter.TimeSignature | None:
    return measure.timeSignature or measure.getContextByClass(m21.meter.TimeSignature)


def _extract_bpm(score: m21.stream.Score) -> int | None:
    for tempo_mark in score.recurse().getElementsByClass(m21.tempo.MetronomeMark):
        if tempo_mark.number is not None:
            return int(round(tempo_mark.number))
    return None


def _extract_compas(score: m21.stream.Score) -> str | None:
    for ts in score.recurse().getElementsByClass(m21.meter.TimeSignature):
        if ts.ratioString:
            return ts.ratioString
    return None


def _extract_tonality(score: m21.stream.Score) -> str | None:
    try:
        key = score.analyze("key")
    except Exception:
        return None

    if not key:
        return None

    tonic_name = key.tonic.name if key.tonic else ""
    mode_name = key.mode if key.mode else ""
    tonality = f"{tonic_name} {mode_name}".strip()
    return tonality or None


def _extract_title_and_author(
    score: m21.stream.Score,
    file_path: str | Path,
) -> tuple[str, str | None]:
    metadata = score.metadata

    title = None
    author = None
    if metadata:
        title = metadata.title or metadata.movementName
        author = metadata.composer or metadata.getContributorsByRole("composer")

    if title:
        title_lower = title.lower()
        es_temporal = title_lower.startswith("tmp")
        es_nombre_archivo = any(title_lower.endswith(ext) for ext in SUPPORTED_SONG_EXTENSIONS)
        
        if es_temporal or es_nombre_archivo:
            title = None

    if isinstance(author, list):
        author = ", ".join(str(person) for person in author if person)
    elif isinstance(author, tuple):
        author = ", ".join(str(person) for person in author if person)
    elif author is not None and not isinstance(author, str):
        author = str(author)

    if author:
        author_limpio = author.strip()
        if author_limpio in {"()", "[]", "{}"}:
            author = None
        else:
            author = author_limpio

    if not title:
        title = Path(file_path).stem

    return title, author


def _offsets_from_measure(measure: m21.stream.Measure) -> set[float]:
    """
    Extrae offsets reales del compás incluyendo voces internas.
    """
    offsets: set[float] = set()
    flat = measure.flatten()
    
    for n in flat.notesAndRests:
        if isinstance(n, (m21.note.Note, m21.chord.Chord)):
            offsets.add(round(_to_float(n.offset), 3))

    return offsets


def _has_binary_grouping(offsets: set[float]) -> bool:
    """
    Detecta agrupación binaria dentro de 3/4:
    ataques en 0 y 1.5
    """
    return (
        _contains_offset(offsets, 0.0)
        and _contains_offset(offsets, 1.5)
        and len(offsets) <= 2
    )


def _has_ternary_grouping(offsets: set[float]) -> bool:
    """
    Detecta agrupación ternaria:
    ataques regulares cada negra.
    """
    return (
        _contains_offset(offsets, 0.0)
        and _contains_offset(offsets, 1.0)
        and _contains_offset(offsets, 2.0)
    )


def _infer_mode_custom(score: m21.stream.Score) -> tuple[str | None, str | None]:
    """
    Infiere la tónica (finalis) y el modo eclesiástico (jónico, dórico, frigio...)
    basándose en la última nota de la obra y en la duración acumulada de sus alturas.
    """
    all_notes = list(score.recurse().getElementsByClass(m21.note.Note))
    if not all_notes:
        return None, None

    # Encontrar la tónica (la última nota es la reina del reposo en folklore)
    last_note = all_notes[-1]
    tonic_pc = last_note.pitch.pitchClass
    
    # Normalizamos el nombre al estilo de tu código actual
    tonic_name = last_note.pitch.name.replace('-', '-flat').replace('#', '-sharp')

    # Inicializar el contenedor de duraciones por cada intervalo (0 a 11 semitonos)
    interval_durations = {i: 0.0 for i in range(12)}
    
    for n in all_notes:
        dur = _to_float(n.quarterLength)
        if dur > 0:
            # Calculamos el intervalo en semitonos relativo a la tónica (módulo 12)
            interval = (n.pitch.pitchClass - tonic_pc) % 12
            interval_durations[interval] += dur

    # Definición de perfiles de los 7 modos naturales (grados que los componen)
    modos_perfiles = {
        "jónico (mayor)": {0, 2, 4, 5, 7, 9, 11},
        "dórico":         {0, 2, 3, 5, 7, 9, 10},
        "frigio":         {0, 1, 3, 5, 7, 8, 10},
        "lidio":          {0, 2, 4, 6, 7, 9, 11},
        "mixolidio":      {0, 2, 4, 5, 7, 9, 10},
        "eólico (menor)": {0, 2, 3, 5, 7, 8, 10},
        "locrio":         {0, 1, 3, 5, 6, 8, 10}
    }

    # Puntuar cada modo sumando la duración de las notas que encajan en él
    puntuaciones = {}
    for nombre_modo, grados in modos_perfiles.items():
        puntuaciones[nombre_modo] = sum(interval_durations[g] for g in grados)

    # El modo que sume más tiempo de ejecución es el ganador
    modo_ganador = max(puntuaciones, key=puntuaciones.get)
    
    return tonic_name, modo_ganador


def detectar_hemiolas_verticales(file_path: str | Path) -> list[int]:
    score = _safe_parse_score(file_path)

    if score is None:
        return []

    compases_con_hemiolia: set[int] = set()

    for part in score.parts:
        for measure in part.getElementsByClass(m21.stream.Measure):

            num_compas = measure.measureNumber

            if num_compas in (None, 0):
                continue

            ts = _get_measure_time_signature(measure)

            if not ts or ts.ratioString not in {"3/4", "6/8"}:
                continue

            voces = list(measure.voices)

            if len(voces) < 2:
                continue

            offsets_por_voz: list[set[float]] = []

            for voz in voces:
                offsets: set[float] = set()

                flat_voice = voz.flatten()

                for n in flat_voice.notesAndRests:
                    if isinstance(n, (m21.note.Note, m21.chord.Chord)):
                        offsets.add(round(_to_float(n.offset), 3))

                offsets_por_voz.append(offsets)

            # comparar todas las combinaciones de voces
            for i in range(len(offsets_por_voz)):

                for j in range(i + 1, len(offsets_por_voz)):

                    o1 = offsets_por_voz[i]
                    o2 = offsets_por_voz[j]

                    # print(num_compas, o1, o2)

                    if (
                        _has_binary_grouping(o1)
                        and _has_ternary_grouping(o2)
                    ) or (
                        _has_ternary_grouping(o1)
                        and _has_binary_grouping(o2)
                    ):

                        compases_con_hemiolia.add(num_compas)

    return sorted(compases_con_hemiolia)


def detectar_hemiolas_horizontales(file_path: str | Path) -> list[int]:
    """
    Detecta hemiolias horizontales (sucesivas) reales en la obra.
    Una hemiolia horizontal se da cuando, manteniendo el mismo compás escrito,
    el patrón de acentuación rítmica cambia drásticamente entre el pulso binario/ternario
    respecto al compás anterior o posterior (Ej: un compás de 6/8 articulado como 3/4).
    """
    score = _safe_parse_score(file_path)
    if score is None:
        return []

    compases_con_hemiolia: set[int] = set()
    
    for part in score.parts:
        # Guardaremos el "sentimiento métrico percibido" del compás anterior
        # Valores posibles: "BINARIO_TERNARIO" (6/8), "TERNARIO_BINARIO" (3/4), o None
        sentimiento_anterior = None
        compas_escrito_anterior = None
        
        for measure in part.getElementsByClass(m21.stream.Measure):
            num_compas = measure.measureNumber
            if num_compas in (None, 0):
                continue

            ts = _get_measure_time_signature(measure)
            if not ts or ts.ratioString not in {"6/8", "3/4"}:
                # Si cambia a 9/8 u otro compás, rompemos la cadena de regularidad métrica
                sentimiento_anterior = None
                compas_escrito_anterior = None
                continue

            offsets = _offsets_from_measure(measure)
            if not offsets:
                continue

            # Determinar el "sentimiento rítmico real" del compás por sus ataques dominantes
            sentimiento_actual = None
            
            # Un 3/4 real (Ternario puro) ataca los tiempos principales: 0.0, 1.0, 2.0
            es_percepcion_3_4 = _contains_offset(offsets, 0.0) and _contains_offset(offsets, 1.0) and _contains_offset(offsets, 2.0)
            # Un 6/8 real (Binario con subdivisión ternaria) prioriza los apoyos en 0.0 y 1.5
            es_percepcion_6_8 = _contains_offset(offsets, 0.0) and _contains_offset(offsets, 1.5)

            if es_percepcion_3_4 and not es_percepcion_6_8:
                sentimiento_actual = "3/4_FEEL"
            elif es_percepcion_6_8 and not es_percepcion_3_4:
                sentimiento_actual = "6/8_FEEL"
            elif es_percepcion_3_4 and es_percepcion_6_8:
                # Si tiene ambos ataques, nos guiamos estrictamente por el compás escrito (no hay cambio)
                sentimiento_actual = "6/8_FEEL" if ts.ratioString == "6/8" else "3/4_FEEL"

            # Comparar con el compás anterior para descubrir la alternancia (Hemiolia Horizontal)
            if sentimiento_anterior and compas_escrito_anterior == ts.ratioString:
                # Si el compás escrito NO ha cambiado, pero el sentimiento rítmico interno mutó:
                if ts.ratioString == "6/8" and sentimiento_actual == "3/4_FEEL" and sentimiento_anterior == "6/8_FEEL":
                    compases_con_hemiolia.add(num_compas)
                elif ts.ratioString == "3/4" and sentimiento_actual == "6/8_FEEL" and sentimiento_anterior == "3/4_FEEL":
                    compases_con_hemiolia.add(num_compas)

            # Actualizamos los rastreadores para el siguiente ciclo del bucle
            sentimiento_anterior = sentimiento_actual
            compas_escrito_anterior = ts.ratioString

    return sorted(list(compases_con_hemiolia))


def detectar_sincopas(file_path: str | Path) -> tuple[int, str, int]:
    """
    Detecta síncopas en la partitura.

    Definición usada:
    - Una nota empieza en parte débil del pulso
    - y se prolonga atravesando una parte fuerte.

    Retorna:
        (
            tiene_sincopas: int,
            compases_texto: str,
            conteo: int
        )
    """
    score = _safe_parse_score(file_path)
    if score is None:
        return (0, "", 0)

    compases_con_sincopa: set[int] = set()

    for part in score.parts:
        for measure in part.getElementsByClass(m21.stream.Measure):
            num_compas = measure.measureNumber

            if num_compas in (None, 0):
                continue

            ts = _get_measure_time_signature(measure)
            if ts is None:
                continue

            try:
                for note in measure.notesAndRests:
                    if not isinstance(note, (m21.note.Note, m21.chord.Chord)):
                        continue

                    offset = _to_float(note.offset)
                    dur = _to_float(note.quarterLength)

                    if dur <= 0:
                        continue

                    inicio = offset
                    final = offset + dur

                    # Fuerza métrica del inicio
                    inicio_strength = note.beatStrength or 0.0

                    # Revisamos si atraviesa un pulso más fuerte
                    sincopa_detectada = False

                    # Obtenemos posibles divisiones métricas
                    beat_points = []

                    bar_duration = ts.barDuration.quarterLength

                    current = 0.0
                    while current <= bar_duration + _EPSILON:
                        beat_points.append(round(current, 6))
                        current += 1.0

                    for beat_point in beat_points:
                        # Debe atravesar el pulso
                        if inicio < beat_point < final:
                            try:
                                beat_strength = ts.getAccentWeight(beat_point)
                            except Exception:
                                beat_strength = 1.0

                            # Si el punto atravesado es más fuerte
                            if beat_strength > inicio_strength:
                                sincopa_detectada = True
                                break

                    if sincopa_detectada:
                        compases_con_sincopa.add(num_compas)
                        break

            except Exception:
                continue

    compases_ordenados = sorted(compases_con_sincopa)

    return (
        1 if compases_ordenados else 0,
        ", ".join(map(str, compases_ordenados)),
        len(compases_ordenados),
    )


def _extract_lyrics_mei(file_path):
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        ns = {'mei': 'http://www.music-encoding.org/ns/mei'}

        # Diccionario para agrupar las sílabas por número de estrofa
        # { '1': [(texto, wordpos), ...], '2': [...] }
        versos = defaultdict(list)

        # Iteramos sobre cada elemento <verse> respetando el orden de la partitura
        for verse in root.findall('.//mei:verse', ns):
            # El atributo 'n' indica el número de estrofa/verso (por defecto '1')
            n_verse = verse.get('n', '1')
            
            # Buscamos la sílaba interna de este verso
            syl = verse.find('mei:syl', ns)
            if syl is not None:
                # Limpiamos el texto y quitamos los espacios duros (\xa0)
                texto = (syl.text or '').strip().replace('\xa0', ' ')
                wordpos = syl.get('wordpos', 's')
                
                versos[n_verse].append((texto, wordpos))

        # Reconstruimos el texto de cada estrofa por separado
        textos_finales = []
        
        # Función auxiliar para ordenar numéricamente las estrofas ('1', '2', '3'...)
        def ordenar_por_numero(v):
            try:
                return int(v)
            except ValueError:
                return 999

        for n_verse in sorted(versos.keys(), key=ordenar_por_numero):
            palabras = []
            palabra_actual = ""

            for texto, wordpos in versos[n_verse]:
                if wordpos == 's':  # Palabra de una sola sílaba
                    if palabra_actual:
                        palabras.append(palabra_actual)
                        palabra_actual = ""
                    palabras.append(texto)

                elif wordpos == 'i':  # Inicio de palabra
                    if palabra_actual:
                        palabras.append(palabra_actual)
                    palabra_actual = texto

                elif wordpos == 'm':  # Medio de palabra
                    palabra_actual += texto

                elif wordpos == 't':  # Final de palabra
                    palabra_actual += texto
                    palabras.append(palabra_actual)
                    palabra_actual = ""

            if palabra_actual:
                palabras.append(palabra_actual)

            # Unimos las palabras del verso actual y limpiamos dobles espacios
            verso_completo = " ".join(palabras)
            verso_completo = " ".join(verso_completo.split())
            
            if verso_completo:
                textos_finales.append(verso_completo)

        # Unimos todas las estrofas independientes con un espacio
        return " ".join(textos_finales)

    except Exception as e:
        print(f"Error extrayendo la letra MEI de {file_path}: {e}")
        return ""
    

def _extract_lyrics_musicxml(path):
    tree = ET.parse(path)
    root = tree.getroot()

    versos = defaultdict(list)

    for lyric in root.findall(".//lyric"):
        text_el = lyric.find("text")
        syll_el = lyric.find("syllabic")

        if text_el is None:
            continue

        # AÑADIDO: .replace("/", " ") para limpiar las sinalefas
        texto = (text_el.text or "").replace("/", " ")
        syllabic = syll_el.text if syll_el is not None else "single"
        numero = lyric.get("number", "1")
        versos[numero].append((texto, syllabic))

    letras = []

    for numero in sorted(versos):
        palabra = ""
        for texto, syllabic in versos[numero]:
            if syllabic == "single":
                if palabra:
                    letras.append(palabra)
                    palabra = ""

                letras.append(texto)

            elif syllabic == "begin":
                palabra = texto

            elif syllabic == "middle":
                palabra += texto

            elif syllabic == "end":
                palabra += texto
                letras.append(palabra)
                palabra = ""

        if palabra:
            letras.append(palabra)

    return " ".join(letras)


def _extract_lyrics_mscx(path: str | Path) -> str:
    """
    Extrae la letra de un archivo .mscx agrupando correctamente por número 
    de verso/estrofa para evitar la mezcla de sílabas.
    """
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        
        # Diccionario para agrupar las sílabas por número de verso
        versos = defaultdict(list)
        
        # Iterar sobre todos los elementos <Lyrics> en el XML
        for lyrics_node in root.iter('Lyrics'):
            # MuseScore usa <no> para el número de estrofa (0 por defecto)
            no_node = lyrics_node.find('no')
            verse_index = int(no_node.text) if no_node is not None else 0
            
            text_node = lyrics_node.find('text')
            syllabic_node = lyrics_node.find('syllabic')
            
            if text_node is not None and text_node.text:
                texto_silaba = text_node.text.strip()
                estado_silabico = syllabic_node.text if syllabic_node is not None else 'single'
                
                # Juntar sílabas según su posición en la palabra
                if estado_silabico in ['begin', 'middle']:
                    versos[verse_index].append(texto_silaba)
                else:
                    # Final de palabra o palabra suelta, añadimos espacio
                    versos[verse_index].append(texto_silaba + " ")

        # Construir el texto final ordenando por número de verso
        textos_finales = []
        for v_idx in sorted(versos.keys()):
            verso_completo = "".join(versos[v_idx]).strip()
            # Limpiar dobles espacios si los hubiera
            verso_completo = " ".join(verso_completo.split()) 
            if verso_completo:
                textos_finales.append(verso_completo)
        
        # Unimos las distintas estrofas con un espacio 
        # (puedes cambiar " " por " | " o "\n" si prefieres marcadores visuales en el CSV/JSON)
        letra_completa = " ".join(textos_finales)
        
        return letra_completa
        
    except Exception as e:
        print(f"Error extrayendo la letra de {path}: {e}")
        return ""
        
    
def _extract_lyrics_mscz(file_path):
    """
    Extrae el MSCX contenido dentro de un MSCZ y reutiliza
    el parser de letras de MuseScore XML.
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(file_path, "r") as z:
            mscx_files = [
                name
                for name in z.namelist()
                if name.lower().endswith(".mscx")
            ]

            if not mscx_files:
                return "Sin letra"

            mscx_name = mscx_files[0]
            extracted_path = Path(tmpdir) / Path(mscx_name).name

            with z.open(mscx_name) as src:
                extracted_path.write_bytes(src.read())

        return _extract_lyrics_mscx(extracted_path)


def _extract_lyrics(file_path):
    ext = Path(file_path).suffix.lower()

    if ext == ".mei":
        return _extract_lyrics_mei(file_path)

    elif ext in {".xml", ".musicxml", ".mxl"}:
        return _extract_lyrics_musicxml(file_path)

    elif ext == ".mscx":
        return _extract_lyrics_mscx(file_path)
    
    elif ext == ".mscz":
        return _extract_lyrics_mscz(file_path)

    return "Sin letra"


def _analizar_temas_con_ollama(titulo: str, letra: str, model_name: str = "llama3") -> list[str]:
    """
    Conecta con Ollama local para extraer una lista de temas/tópicos 
    basados en el título y la letra de la canción.
    """
    if not titulo and not letra:
        return []

    # Construimos el prompt con instrucciones muy claras y restrictivas
    prompt = f"""
    Analiza el título y la letra de esta canción tradicional para identificar sus temas o tópicos principales.
    
    Título: {titulo}
    Letra: {letra}
    
    Elige los temas más representativos (máximo 4). Ejemplos de temas: nana/cuna, naturaleza, muerte, religión, amor, trabajo, picaresca, fiesta, satírico, infantil, guerra, viaje.
    """

    system_prompt = (
        "Eres un experto en musicología y folklore. Tu tarea es analizar canciones y clasificar sus temas. "
        "Debes responder EXCLUSIVAMENTE con un objeto JSON que contenga una lista de strings bajo la clave 'temas'. "
        "No añadas introducciones, explicaciones ni notas. Ejemplo de formato: {\"temas\": [\"nana\", \"infantil\"]}"
    )

    payload = {
        "model": model_name,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,  # Desactivamos streaming para recibir la respuesta de golpe
        "format": "json"  # Forzamos a Ollama a garantizar un output JSON válido
    }

    try:
        # Ollama corre por defecto en el puerto 11434
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=45)
        
        if response.status_code == 200:
            res_data = response.json()
            response_text = res_data.get("response", "{}")
            
            # Parseamos el JSON devuelto por el LLM
            temas_json = json.loads(response_text)
            return temas_json.get("temas", [])
            
    except Exception as e:
        print(f"Aviso: No se pudo categorizar con Ollama para '{titulo}': {e}")
        
    return []


def _detectar_cambio_resolucion_ppq(file_path: str | Path) -> tuple[int, str]:
    """
    Analiza directamente el XML de un archivo MEI para encontrar si el valor 
    de resolución rítmica (ppq base o dur.ppq por figura) cambia a mitad de una sección.

    Retorna:
        (tiene_cambio: int, compases_texto: str)
    """
    # Esta métrica es exclusiva del formato MEI
    if Path(file_path).suffix.lower() != ".mei":
        return 0, ""

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        ns = {'mei': 'http://www.music-encoding.org/ns/mei'}
        
        compases_con_cambio: set[int] = set()
        
        # Iteramos sobre cada sección de la pieza de manera independiente
        for section in root.findall('.//mei:section', ns):
            # Diccionario para mapear: figura_nominal (int) -> ticks_ppq (int)
            # Se reinicia por sección porque el cambio debe ocurrir "a mitad de la sección"
            mapa_figura_a_pulso: dict[int, int] = {}
            ppq_def_activo: int | None = None
            
            # Procesamos secuencialmente los compases de esta sección
            for measure in section.findall('.//mei:measure', ns):
                num_compas = measure.get('n')
                try:
                    num_compas_int = int(num_compas) if num_compas else 0
                except ValueError:
                    num_compas_int = 0
                
                # Estrategia 1: Verificar si hay una redefinición explícita de cabecera en el compás
                cabeceras_locales = (
                    measure.findall('.//mei:scoreDef[@ppq]', ns) + 
                    measure.findall('.//mei:staffDef[@ppq]', ns)
                )
                for cabecera in cabeceras_locales:
                    val_ppq = int(cabecera.get('ppq'))
                    if ppq_def_activo is not None and val_ppq != ppq_def_activo:
                        if num_compas_int > 0:
                            compases_con_cambio.add(num_compas_int)
                    ppq_def_activo = val_ppq
                
                # Estrategia 2: Analizar los atributos individuales de las notas/silencios
                for elemento in measure.findall('.//*[@dur][@dur.ppq]'):
                    dur_nominal = elemento.get('dur')
                    dur_ppq_real = elemento.get('dur.ppq')
                    
                    if dur_nominal and dur_ppq_real:
                        try:
                            figura = int(dur_nominal)
                            pulsos = int(dur_ppq_real)
                            
                            if figura <= 0:
                                continue
                                
                            # Si ya habíamos registrado esta figura en esta sección,
                            # pero ahora sus pulsos asignados son diferentes -> ¡Cambio de resolución!
                            if figura in mapa_figura_a_pulso:
                                if mapa_figura_a_pulso[figura] != pulsos:
                                    if num_compas_int > 0:
                                        compases_con_cambio.add(num_compas_int)
                            
                            # Actualizamos el mapa con el valor activo
                            mapa_figura_a_pulso[figura] = pulsos
                        except ValueError:
                            continue
                            
        compases_ordenados = sorted(list(compases_con_cambio))
        return (1 if compases_ordenados else 0, ", ".join(map(str, compases_ordenados)))

    except Exception as e:
        print(f"Aviso: Error en el escaneo de resolución PPQ para {file_path}: {e}")
        return 0, ""

def _mei_dur_to_quarter_length(element: ET.Element) -> float:
    """
    Convierte los atributos 'dur' y 'dots' de un elemento MEI (<note>, <chord>, <rest>)
    a valores de duración basados en negras (Quarter Length).
    """
    dur_attr = element.get('dur')
    if not dur_attr:
        return 0.0
    
    try:
        dur_val = int(dur_attr)
        if dur_val <= 0:
            return 0.0
        # dur=1 (redonda) -> 4 negras, dur=2 (blanca) -> 2 negras, dur=4 (negra) -> 1 negra, etc.
        quarter_length = 4.0 / dur_val
    except ValueError:
        return 0.0
    
    # Aplicar puntos de prolongación (dots) si existen
    dots_attr = element.get('dots')
    if dots_attr:
        try:
            dots = int(dots_attr)
            factor = 1.0
            for i in range(1, dots + 1):
                factor += 1.0 / (2 ** i)
            quarter_length *= factor
        except ValueError:
            pass
            
    return quarter_length


def detectar_desajustes_meter_sig(file_path: str | Path) -> tuple[int, str]:
    """
    Localiza compases en archivos MEI donde la suma de las duraciones de las notas/acordes
    internos de una voz (layer) no coincide con la capacidad del meterSig activo en el staffDef.
    
    Retorna:
        (tiene_desajuste: int, compases_texto: str)
    """
    if Path(file_path).suffix.lower() != ".mei":
        return 0, ""

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        ns = {'mei': 'http://www.music-encoding.org/ns/mei'}
        
        compases_con_desajuste: set[int] = set()
        
        # Estado del indicador de compás (Meter) activo
        current_count = None
        current_unit = None
        
        # Buscar definición global inicial en scoreDef/staffDef de la cabecera
        initial_score_def = root.find('.//mei:scoreDef', ns)
        if initial_score_def is not None:
            if initial_score_def.get('meter.count'): current_count = int(initial_score_def.get('meter.count'))
            if initial_score_def.get('meter.unit'): current_unit = int(initial_score_def.get('meter.unit'))
            
        initial_staff_def = root.find('.//mei:staffDef', ns)
        if initial_staff_def is not None:
            if initial_staff_def.get('meter.count'): current_count = int(initial_staff_def.get('meter.count'))
            if initial_staff_def.get('meter.unit'): current_unit = int(initial_staff_def.get('meter.unit'))
            # También verificamos si está declarado como elemento hijo <meterSig>
            meter_sig_el = initial_staff_def.find('mei:meterSig', ns)
            if meter_sig_el is not None:
                if meter_sig_el.get('count'): current_count = int(meter_sig_el.get('count'))
                if meter_sig_el.get('unit'): current_unit = int(meter_sig_el.get('unit'))

        # Procesar secuencialmente cada compás de la obra
        for measure in root.findall('.//mei:measure', ns):
            num_compas = measure.get('n')
            try:
                num_compas_int = int(num_compas) if num_compas else 0
            except ValueError:
                num_compas_int = 0
            
            # Verificar si hay cambios de compás locales (locales al measure)
            local_staff_def = measure.find('.//mei:staffDef', ns)
            if local_staff_def is not None:
                if local_staff_def.get('meter.count'): current_count = int(local_staff_def.get('meter.count'))
                if local_staff_def.get('meter.unit'): current_unit = int(local_staff_def.get('meter.unit'))
                meter_sig_el = local_staff_def.find('mei:meterSig', ns)
                if meter_sig_el is not None:
                    if meter_sig_el.get('count'): current_count = int(meter_sig_el.get('count'))
                    if meter_sig_el.get('unit'): current_unit = int(meter_sig_el.get('unit'))
            
            # Si no hay meterSig definido aún en la obra, saltamos la validación en este compás
            if current_count is None or current_unit is None:
                continue
                
            # Duración teórica esperada del compás expresada en unidades de negra
            # Ej: 6/8 -> 6 * (4/8) = 3.0 negras.  3/4 -> 3 * (4/4) = 3.0 negras.
            expected_measure_duration = current_count * (4.0 / current_unit)
            
            # Analizar cada voz (<layer>) de manera independiente dentro del compás
            for layer in measure.findall('.//mei:layer', ns):
                layer_duration = 0.0
                
                # Iteramos secuencialmente sobre los hijos directos del layer para evitar
                # sobre-contar notas internas en los acordes (<chord>)
                for child in layer:
                    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    
                    if tag == 'note':
                        layer_duration += _mei_dur_to_quarter_length(child)
                    elif tag == 'chord':
                        # En MEI, la duración del acorde se define en la etiqueta contenedora <chord>
                        layer_duration += _mei_dur_to_quarter_length(child)
                    elif tag == 'rest':
                        # NOTA METODOLÓGICA: Se incluyen los silencios para evaluar la ocupación total.
                        # Si tu regla requiere evaluar ESTRICTAMENTE notas omitiendo silencios, comenta esta línea.
                        layer_duration += _mei_dur_to_quarter_length(child)
                
                # Comparamos la duración total acumulada con la teórica utilizando tu función de tolerancia _is_close
                if not _is_close(layer_duration, expected_measure_duration):
                    if num_compas_int > 0:
                        compases_con_desajuste.add(num_compas_int)
                        break  # Si una voz falla, el compás entero ya está marcado como erróneo

        compases_ordenados = sorted(list(compases_con_desajuste))
        return (1 if compases_ordenados else 0, ", ".join(map(str, compases_ordenados)))

    except Exception as e:
        print(f"Aviso: Error en el escaneo de coherencia de meterSig para {file_path}: {e}")
        return 0, ""


def detectar_valores_irregulares_ocultos(file_path: str | Path) -> tuple[int, str, int]:
    """
    Detecta valores irregulares (como tresillos) en archivos MusicXML que no
    han sido declarados explícitamente mediante la etiqueta <time-modification>.
    
    Retorna:
        (tiene_ocultos: int, compases_texto: str, conteo: int)
    """
    path_obj = Path(file_path)
    # Restringir el análisis exclusivamente a formatos MusicXML como pide el enunciado
    if path_obj.suffix.lower() not in {".xml", ".musicxml", ".mxl"}:
        return 0, "", 0

    score = _safe_parse_score(file_path)
    if score is None:
        return 0, "", 0

    compases_con_ocultos: set[int] = set()

    for part in score.parts:
        for measure in part.getElementsByClass(m21.stream.Measure):
            num_compas = measure.measureNumber
            if num_compas in (None, 0):
                continue

            for element in measure.notesAndRests:
                if not isinstance(element, (m21.note.Note, m21.chord.Chord)):
                    continue
                
                q_len = element.quarterLength
                if _to_float(q_len) <= 0:
                    continue
                
                # Convertimos a fracción limitando el denominador para corregir leves imprecisiones de floats
                frac = Fraction(str(q_len)).limit_denominator(1000)
                denom = frac.denominator
                
                # Comprobación matemática: ¿Es el denominador una potencia de 2?
                # (Las notas regulares y con puntillos siempre tienen denominadores potencia de 2: 1, 2, 4, 8...)
                es_potencia_de_2 = (denom > 0) and (denom & (denom - 1)) == 0
                
                if not es_potencia_de_2:
                    # El valor es matemáticamente irregular (p. ej. terceras partes de negra = tresillos)
                    # Si no contiene objetos Tuplet, significa que el MusicXML NO incluyó <time-modification>
                    if not element.duration.tuplets:
                        compases_con_ocultos.add(num_compas)
                        break  # Con uno detectado es suficiente para marcar el compás

    compases_ordenados = sorted(list(compases_con_ocultos))
    
    return (
        1 if compases_ordenados else 0,
        ", ".join(map(str, compases_ordenados)),
        len(compases_ordenados)
    )

def _calcular_densidad_eventos(score: m21.stream.Score) -> tuple[int, int, float]:
    """
    Analiza el objeto Score para contar el total de eventos musicales (notas y acordes),
    los compases reales únicos y calcular la densidad promedio de la pieza.
    """
    # Extraer y contar todas las notas y acordes (los silencios se ignoran)
    eventos = list(score.recurse().getElementsByClass((m21.note.Note, m21.chord.Chord)))
    total_eventos = len(eventos)
    
    # Obtener compases únicos (usamos un set con el número de compás para no 
    # duplicar cuentas si la obra tiene múltiples layers o tracks/instrumentos)
    compases_unicos = set()
    for measure in score.recurse().getElementsByClass(m21.stream.Measure):
        if measure.measureNumber is not None and measure.measureNumber > 0:
            compases_unicos.add(measure.measureNumber)
            
    total_compases = len(compases_unicos)
    
    # Calcular ratio de densidad con seguridad ante divisiones por cero
    densidad = round(total_eventos / total_compases, 2) if total_compases > 0 else 0.0
    
    return total_eventos, total_compases, densidad


def detectar_polirritmias(file_path: str | Path) -> list[int]:
    """
    Detecta el uso de polirritmias verticales en la partitura.
    Se considera polirritmia cuando en un mismo compás coexisten de forma simultánea
    subdivisiones rítmicas conflictivas (por ejemplo, tresillos frente a corcheas binarias,
    o combinaciones como 3 contra 4, 5 contra 4, etc.) entre diferentes partes o voces.
    
    Retorna:
        list[int]: Lista ordenada de números de compás donde se detectó polirritmia.
    """
    score = _safe_parse_score(file_path)
    if score is None:
        return []

    compases_con_polirritmia = set()
    
    # Agrupar las medidas de todas las partes del score por su número de compás
    medidas_por_numero = defaultdict(list)
    for part in score.parts:
        for measure in part.getElementsByClass(m21.stream.Measure):
            if measure.measureNumber is not None and measure.measureNumber > 0:
                medidas_por_numero[measure.measureNumber].append(measure)

    # Analizar cada compás de manera global e independiente
    for num_compas, lista_medidas in medidas_por_numero.items():
        subdivisiones_compas = set()
        tiene_subdivision_regular = False
        
        for measure in lista_medidas:
            # Aplanamos la medida para incluir todas las notas de las voces internas
            flat_measure = measure.flatten()
            for element in flat_measure.notesAndRests:
                if not isinstance(element, (m21.note.Note, m21.chord.Chord)):
                    continue
                
                q_len = _to_float(element.quarterLength)
                if q_len <= 0:
                    continue
                
                # Estrategia A: Identificación por tuplet explícito en metadatos
                if element.duration.tuplets:
                    for tuplet in element.duration.tuplets:
                        actual = tuplet.numberNotesActual
                        normal = tuplet.numberNotesNormal
                        if actual and normal and actual != normal:
                            subdivisiones_compas.add(actual)
                else:
                    # Estrategia B: Análisis matemático de la fracción por si es un valor irregular oculto
                    frac = Fraction(str(q_len)).limit_denominator(1000)
                    denom = frac.denominator
                    
                    # Descomponer el denominador eliminando los factores de base 2
                    temp_denom = denom
                    while temp_denom % 2 == 0 and temp_denom > 0:
                        temp_denom //= 2
                    
                    if temp_denom > 1:
                        # Conserva factores primos (3 para tresillo, 5 para quintillo, etc.)
                        subdivisiones_compas.add(temp_denom)
                    else:
                        # Ritmo puramente regular (potencias de 2)
                        tiene_subdivision_regular = True

        # Validar contexto según el indicador de compás (Time Signature)
        es_compas_compuesto = False
        if lista_medidas:
            ts = _get_measure_time_signature(lista_medidas[0])
            if ts and ts.ratioString in {"6/8", "9/8", "12/8"}:
                es_compas_compuesto = True

        # Limpiar las subdivisiones que representan conflicto real
        subdivisiones_conflictivas = set()
        for sub in subdivisiones_compas:
            if es_compas_compuesto and sub == 3:
                # En compases compuestos el 3 es el estándar de subdivisión regular
                continue
            subdivisiones_conflictivas.add(sub)

        # Evaluación del criterio de polirritmia vertical
        polirritmia_detectada = False
        if len(subdivisiones_conflictivas) >= 2:
            # Coexisten dos o más subdivisiones irregulares distintas (ej: 3 contra 5)
            polirritmia_detectada = True
        elif len(subdivisiones_conflictivas) == 1 and tiene_subdivision_regular:
            # Coexiste una subdivisión irregular contra ritmos binarios normales (ej: 3 contra 2)
            polirritmia_detectada = True

        if polirritmia_detectada:
            compases_con_polirritmia.add(num_compas)

    return sorted(list(compases_con_polirritmia))


def _calcular_tesitura(score: m21.stream.Score) -> tuple[str, str]:
    """
    Analiza las alturas de la obra para determinar la nota más grave y la más aguda.
    
    Retorna:
        tuple[str, str]: (nota_mas_grave, nota_mas_aguda) en formato científico (ej: 'C4', 'F#5').
                         Retorna ("N/A", "N/A") si no se encuentran notas con altura.
    """
    todos_los_pitches = []
    
    # Recorrer de forma recursiva todas las notas y acordes de la pieza
    for el in score.recurse().notes:
        if isinstance(el, m21.note.Note):
            todos_los_pitches.append(el.pitch)
        elif isinstance(el, m21.chord.Chord):
            # Un acorde contiene múltiples alturas simultáneas, las agregamos todas
            todos_los_pitches.extend(el.pitches)
            
    if not todos_los_pitches:
        return "N/A", "N/A"
        
    # Encontrar los extremos utilizando el valor numérico Pitch Space (.ps)
    pitch_mas_grave = min(todos_los_pitches, key=lambda p: p.ps)
    pitch_mas_aguda = max(todos_los_pitches, key=lambda p: p.ps)
    
    # Convertimos los objetos Pitch a strings legibles (ej: 'A4', 'E-5', 'C#3')
    # Nota: music21 usa el signo '-' para los bemoles en nameWithOctave (ej: 'E-4' es Mi bemol 4)
    return pitch_mas_grave.nameWithOctave, pitch_mas_aguda.nameWithOctave


def _clasificar_genero_autor(nombre_autor: str) -> str:
    """
    Clasifica heurísticamente o mediante NLP el género del autor.
    Categorías: 'femenino', 'masculino', 'desconocido'
    """
    if not nombre_autor or nombre_autor.lower() in ["anonymous", "anónimo", "traditional", "tradicional"]:
        return "desconocido"
        
    # Heurística rápida para nombres comunes en español (opcional como fallback rápido)
    nombre_limpio = nombre_autor.split()[0].lower()
    if nombre_limpio.endswith(('a', 'ines', 'isabel', 'menxu', 'carmen', 'luz')):
        # Excepciones rápidas de la heurística
        if nombre_limpio not in ["andrea", "borja"]:
            return "femenino"
    if nombre_limpio.endswith(('o', 'r', 'l', 's', 'e')):
        return "masculino"

    # Para generalización total, se puede extender con un diccionario o usar la misma API de Ollama
    return "desconocido"

def _analizar_perspectiva_lirica(texto_letras: str) -> str:
    """
    Analiza semánticamente el texto de la letra para identificar la voz del narrador.
    Busca marcas de género gramatical (ej: 'estoy cansado' vs 'estoy cansada').
    
    Categorías: 'femenino', 'masculino', 'neutro', 'desconocido'
    """
    if not texto_letras or len(texto_letras) < 10:
        return "desconocido"

    # Usamos Ollama (asumiendo que está corriendo localmente en el puerto 11434)
    # Si falla, el código tiene un bloque de seguridad (try/except) que devuelve 'desconocido'
    url = "http://localhost:11434/api/generate"
    prompt = f"""
    Analiza la siguiente letra de una canción en español y determina si el narrador o la voz lírica que canta es un hombre (masculino), una mujer (femenino), o si no tiene marcas de género claras (neutro).
    Fíjate en adjetivos (solo/sola, casado/casada) y el contexto lírico.

    Letra: "{texto_letras}"

    Responde ESTRICTAMENTE con un objeto JSON con la clave "voz_lirica" cuyo valor sea únicamente una de estas opciones: "masculino", "femenino", "neutro", "desconocido".
    Ejemplo de salida: {{"voz_lirica": "masculino"}}
    """
    
    payload = {
        "model": "llama3", # o el modelo que tengas configurado localmente
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            data = response.json()
            res_json = json.loads(data.get("response", "{}"))
            voz = res_json.get("voz_lirica", "desconocido").lower().strip()
            if voz in ["masculino", "femenino", "neutro", "desconocido"]:
                return voz
    except Exception:
        # Fallback analítico si el LLM local está apagado
        # Búsqueda de palabras clave morfológicas elementales en español
        texto_min = texto_letras.lower()
        v_masc = [" solo ", " cansado ", " loco ", " dueño ", " muerto ", " niño ", " hombre "]
        v_fem = [" sola ", " cansada ", " loca ", " dueña ", " muerta ", " niña ", " mujer "]
        
        c_masc = sum(texto_min.count(w) for w in v_masc)
        c_fem = sum(texto_min.count(w) for w in v_fem)
        
        if c_masc > c_fem: return "masculino"
        if c_fem > c_masc: return "femenino"
        return "neutro"

    return "desconocido"


def _extract_notes_and_rests(score: m21.stream.Score) -> str:
    """
    Recorre cronológicamente la partitura y extrae una cadena formateada
    con todas las notas (en notación científica) y silencios.
    Ejemplo: "F4 - G4 - Silencio - A4 - [C4+E4]"
    """
    secuencia = []
    
    # .notesAndRests obtiene Note, Chord y Rest ignorando claves, armaduras, etc.
    for el in score.flatten().notesAndRests:
        if isinstance(el, m21.note.Note):
            # nameWithOctave devuelve valores como 'C4', 'F#4', 'A-3' (el '-' indica bemol)
            # Reemplazamos el '-' por 'b' para que sea más legible/estándar (ej: 'Ab3')
            nombre_nota = el.pitch.nameWithOctave.replace('-', 'b')
            secuencia.append(nombre_nota)
            
        elif isinstance(el, m21.note.Rest):
            secuencia.append("Silencio")
            
        elif isinstance(el, m21.chord.Chord):
            # Si el archivo tiene polifonía (acordes), extraemos todas sus notas internas
            notas_acorde = [p.nameWithOctave.replace('-', 'b') for p in el.pitches]
            # Las envolvemos entre corchetes para indicar simultaneidad
            secuencia.append(f"[{'+'.join(notas_acorde)}]")
            
    return " - ".join(secuencia) if secuencia else "Vacío"



def _extract_melody_pitches(score: m21.stream.Score) -> List[m21.pitch.Pitch]:
    """
    Extrae cronológicamente las alturas (pitches) de la melodía.
    Si detecta polifonía (acordes), selecciona la nota más aguda (línea del soprano).
    """
    pitches = []
    # Usamos flatten() para garantizar un orden cronológico absoluto sin importar las voces
    for el in score.flatten().notes:
        if isinstance(el, m21.note.Note):
            pitches.append(el.pitch)
        elif isinstance(el, m21.chord.Chord):
            # Ordenamos las notas del acorde por su altura MIDI (.ps) de menor a mayor
            notas_ordenadas = sorted(el.pitches, key=lambda p: p.ps)
            # Extraemos la última (la más aguda) que suele llevar la melodía principal
            pitches.append(notas_ordenadas[-1])
    return pitches


def _analyze_interval_directions(pitches: List[m21.pitch.Pitch]) -> Dict[str, int]:
    """
    Compara cada nota con su sucesora inmediata utilizando su Pitch Space (.ps).
    Cuenta la cantidad de intervalos según su dirección.
    """
    conteo = {"ascendentes": 0, "descendentes": 0, "repetidos": 0}
    
    if len(pitches) < 2:
        return conteo  # Si la pieza tiene 1 o 0 notas, no hay intervalos que medir
        
    for i in range(len(pitches) - 1):
        nota_actual = pitches[i]
        nota_siguiente = pitches[i + 1]
        
        # .ps devuelve un número flotante/entero (ej: 60 para C4), ideal para comparar sin errores de texto
        if nota_siguiente.ps > nota_actual.ps:
            conteo["ascendentes"] += 1
        elif nota_siguiente.ps < nota_actual.ps:
            conteo["descendentes"] += 1
        else:
            conteo["repetidos"] += 1
            
    return conteo


def _determine_predominant_trend(conteo: Dict[str, int]) -> Dict[str, Any]:
    """
    Calcula los porcentajes reales de movimiento activo y 
    determina la tendencia predominante bajo un umbral de tolerancia.
    """
    movimientos_totales = conteo["ascendentes"] + conteo["descendentes"]
    
    if movimientos_totales == 0:
        return {
            "tendencia_melodica": "Estática (solo notas repetidas o pieza vacía)",
            "pct_ascendente": 0.0,
            "pct_descendente": 0.0
        }
        
    # Calculamos el porcentaje relativo al movimiento real de la melodía
    pct_asc = (conteo["ascendentes"] / movimientos_totales) * 100
    pct_desc = (conteo["descendentes"] / movimientos_totales) * 100
    
    # Ponemos un margen del 6% (por ejemplo, 53% vs 47% se considera una obra balanceada/equilibrada)
    if abs(pct_asc - pct_desc) <= 6.0:
        veredicto = "Equilibrada"
    elif pct_asc > pct_desc:
        veredicto = "Predominantemente ascendente"
    else:
        veredicto = "Predominantemente descendente"
        
    return {
        "tendencia_melodica": veredicto,
        "pct_ascendente": round(pct_asc, 2),
        "pct_descendente": round(pct_desc, 2)
    }


def _clean_syllable_text(text: str) -> str:
    """
    Limpia, normaliza y estandariza el texto de una sílaba para asegurar 
    que caracteres como la 'ñ' o las tildes se almacenen de forma nativa y limpia.
    """
    if not text:
        return ""
    
    # Normalización Unicode NFC: Junta caracteres divididos (ej: transforma 'n' + '~/tilde' en 'ñ')
    texto = unicodedata.normalize('NFC', text)
    
    # Limpieza de caracteres ocultos PUA (Private Use Area) comunes en MusicXML/MEI
    patron_pua = re.compile(r'[\ue000-\uf8ff]')
    texto = patron_pua.sub('', texto)
    
    # Eliminar guiones de separación silábica residuales
    texto = re.sub(r'[-_]+', '', texto)
    
    # Reemplazar espacios de no separación (\xa0), tabulaciones 
    # o múltiples espacios consecutivos por un único espacio estándar ' '
    texto = re.sub(r'\s+', ' ', texto)
    
    return texto.strip().lower()


def _extract_syllable_duration_mapping(score: m21.stream.Score) -> str:
    """
    Mapea cada sílaba con sus duraciones musicales en la pieza.
    Devuelve un string JSON en UTF-8 nativo (legible sin códigos \\u00f1).
    """
    mapeo = defaultdict(set)
    
    for el in score.flatten().notes:
        if not hasattr(el, 'lyrics') or not el.lyrics:
            continue
            
        duracion = float(el.duration.quarterLength)
        
        for lyr in el.lyrics:
            if not lyr.text:
                continue
                
            silaba_limpia = _clean_syllable_text(lyr.text)
            if silaba_limpia:
                mapeo[silaba_limpia].add(duracion)
                
    mapeo_serializable = {
        silaba: sorted(list(duraciones)) 
        for silaba, duraciones in mapeo.items()
    }
    
    # CLAVE: ensure_ascii=False le dice a Python que guarde la 'ñ' o 'á' tal cual, 
    # en lugar de convertirlas a \\u00f1 o \\u00e1
    return json.dumps(mapeo_serializable, ensure_ascii=False)


def _extract_accidental_events(score: m21.stream.Score) -> List[Dict[str, Any]]:
    """
    Tool 1: Recorre la partitura de forma estructurada (por compases) y extrae las 
    notas con alteraciones accidentales explícitas (sostenidos o bemoles), 
    filtrando y descartando de manera estricta aquellas que pertenecen a la armadura.
    """
    eventos = []
    
    # Recorremos la partitura por compases de manera jerárquica
    for measure in score.recurse().getElementsByClass('Measure'):
        num_compas = measure.number if measure.number is not None else 0
        
        # Localizamos la armadura de clave (KeySignature) activa para este compás específico
        key_sig = measure.getContextByClass(m21.key.KeySignature)
        
        # Analizamos las notas y acordes que contiene este compás
        for el in measure.notes:
            # Desglosamos tanto notas simples como acordes polifónicos
            pitches_a_revisar = el.pitches if isinstance(el, m21.chord.Chord) else [el.pitch] if hasattr(el, 'pitch') else []
            
            for p in pitches_a_revisar:
                if p.accidental is not None:
                    nombre_alteracion = p.accidental.name  # 'sharp', 'flat', etc.
                    
                    # Filtramos únicamente por sostenidos y bemoles (ignorando naturales según diseño)
                    if 'sharp' in nombre_alteracion or 'flat' in nombre_alteracion:
                        
                        # FILTRO CRUCIAL: Comprobar si la alteración viene dada por la armadura de clave
                        es_de_la_armadura = False
                        if key_sig is not None:
                            # Le preguntamos a la armadura qué alteración le corresponde a esta nota base (ej: 'F')
                            acc_armadura = key_sig.accidentalByStep(p.step)
                            
                            # Si la armadura ya contempla esta misma alteración, es parte de la armadura
                            if acc_armadura is not None and acc_armadura.name == nombre_alteracion:
                                es_de_la_armadura = True
                        
                        # Si NO pertenece a la armadura, es un accidental real de la pieza
                        if not es_de_la_armadura:
                            nombre_nota = p.nameWithOctave.replace('-', 'b')
                            eventos.append({
                                "nota": nombre_nota,
                                "compas": num_compas
                            })
    return eventos


def _format_accidentals_report(eventos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Procesa y agrupa la lista de eventos brutos.
    Devuelve un JSON indexado para queries y un texto legible para visualización inmediata.
    """
    mapeo_compases = defaultdict(set)
    
    for ev in eventos:
        mapeo_compases[ev["nota"]].add(ev["compas"])
        
    # Convertimos los conjuntos (sets) a listas ordenadas para poder serializar en JSON sin errores
    mapeo_serializable = {
        nota: sorted(list(compases))
        for nota, compases in sorted(mapeo_compases.items())
    }
    
    # Creamos un string amigable para humanos. Ej: "F#4 (cc. 5, 12), Bb4 (c. 8)"
    partes_texto = []
    for nota, compases in mapeo_serializable.items():
        if len(compases) == 1:
            compases_str = f"c. {compases[0]}"
        else:
            compases_str = f"cc. {', '.join(map(str, compases))}"
        partes_texto.append(f"{nota} ({compases_str})")
        
    texto_resumen = ", ".join(partes_texto) if partes_texto else "Ninguna"
    
    return {
        "lista_accidentales_json": json.dumps(mapeo_serializable, ensure_ascii=False),
        "resumen_accidentales": texto_resumen,
        "total_accidentales": len(eventos)
    }


def _extract_transcription_metadata(file_path: str | Path) -> Dict[str, Any]:
    """
    Examina el archivo de texto crudo (XML/MEI) para rastrear el historial
    de codificación, el software de conversión (como Verovio) y el origen del archivo.
    """
    path_obj = Path(file_path)
    ext = path_obj.suffix.lower()
    
    meta = {
        "software_codificacion": "Desconocido",
        "convertido_via_verovio": 0,
        "fecha_codificacion": "No disponible",
        "formato_origen": ext.replace('.', '').upper()
    }
    
    try:
        # Leemos el archivo como texto para parsear su XML crudo de forma rápida
        content = path_obj.read_text(encoding="utf-8", errors="ignore")
        
        # Eliminar namespaces temporales para facilitar búsquedas genéricas con ElementTree
        content_clean = re.sub(r'\sxmlns="[^"]+"', '', content, count=1)
        root = ET.fromstring(content_clean)
        
        # Rastrear en archivos MEI (<encodingDesc> -> <application>)
        if ext == '.mei':
            application = root.find('.//application')
            if application is not None:
                meta["software_codificacion"] = application.text if application.text else application.attrib.get('name', 'Desconocido')
            else:
                # Búsqueda por texto en comentarios o cabeceras si no está la etiqueta
                if "verovio" in content.lower():
                    meta["software_codificacion"] = "Verovio"

            # Buscar fecha de codificación MEI
            date_el = root.find('.//date')
            if date_el is not None and date_el.text:
                meta["fecha_codificacion"] = date_el.text
                
        # Rastrear en archivos MusicXML (<encoding> -> <software>)
        elif ext in ['.xml', '.musicxml']:
            software = root.find('.//software')
            if software is not None and software.text:
                meta["software_codificacion"] = software.text
                
            encoding_date = root.find('.//encoding-date')
            if encoding_date is not None and encoding_date.text:
                meta["fecha_codificacion"] = encoding_date.text

        # Comprobación específica de la condición del usuario (Verovio)
        if "verovio" in meta["software_codificacion"].lower() or "verovio" in content.lower():
            meta["convertido_via_verovio"] = 1
            if meta["software_codificacion"] == "Desconocido":
                meta["software_codificacion"] = "Verovio (Conversor)"

    except Exception:
        # Si el parseo manual falla, mantenemos los valores por defecto seguros
        pass
        
    return meta


def _extract_quality_control_metadata(score: m21.stream.Score) -> Dict[str, Any]:
    """
    Realiza una auditoría automatizada de Control de Calidad (QC) de la 
    estructura musical para identificar posibles errores de copia o digitalización.
    """
    qc = {
        "qc_compases_vacios": 0,
        "qc_notas_duracion_cero": 0,
        "qc_advertencias_criticas": "Ninguna",
        "qc_puntuacion_integridad": 100
    }
    
    compases_vacios = 0
    notas_cero = 0
    
    # Recorremos la estructura por compases
    for measure in score.recurse().getElementsByClass('Measure'):
        # print(
        #     measure.measureNumber,
        #     len(list(measure.notesAndRests)),
        #     measure.activeSite
        # )
        
        eventos = list(measure.recurse().notesAndRests)

        if len(eventos) > 0 and all(e.isRest for e in eventos):
            compases_vacios += 1

        for nota in measure.recurse().notes:
            if nota.duration.quarterLength <= 0:
                notas_cero += 1

    # Penalizaciones a la puntuación de integridad del control de calidad
    if compases_vacios > 0:
        qc["qc_compases_vacios"] = compases_vacios
        qc["qc_puntuacion_integridad"] -= min(compases_vacios * 15, 45) # Max 45 puntos de penalización
        
    if notas_cero > 0:
        qc["qc_notas_duracion_cero"] = notas_cero
        qc["qc_puntuacion_integridad"] -= min(notas_cero * 10, 35)
        
    # Clasificación final de estado del QC
    if qc["qc_puntuacion_integridad"] < 60:
        qc["qc_advertencias_criticas"] = "Revisión Manual Urgente: Estructura corrupta o incompleta"
    elif qc["qc_puntuacion_integridad"] < 90:
        qc["qc_advertencias_criticas"] = "Advertencia: Pequeños desajustes o silencios faltantes detectados"
        
    return qc


def _extract_melodic_intervals(score: m21.stream.Score) -> List[int]:
    """
    Recorre la partitura de forma lineal y extrae las distancias en 
    semitonos entre notas consecutivas, abstrayendo la melodía de su altura absoluta.
    """
    # flatten().notes obtiene Notas y Acordes omitiendo silencios
    elementos = score.flatten().notes
    alturas_midi = []
    
    for el in elementos:
        if el.isNote:
            alturas_midi.append(int(el.pitch.ps))
        elif el.isChord:
            # En acordes, extraemos la nota más aguda (típica de la melodía)
            alturas_midi.append(int(max(p.ps for p in el.pitches)))
            
    # Calcular los intervalos melódicos en semitonos (Nota B - Nota A)
    intervalos = [alturas_midi[i+1] - alturas_midi[i] for i in range(len(alturas_midi) - 1)]
    return intervalos


def _detect_leitmotivs_ngrams(score: m21.stream.Score, min_notas: int = 4, max_notas: int = 5, n_apariciones: int = 3) -> str:
    """
    Aplica ventanas deslizantes sobre los intervalos para descubrir 
    motivos redundantes (leitmotivs). Devuelve un JSON string con los patrones y sus frecuencias.
    """
    intervalos = _extract_melodic_intervals(score)
    motivos_finales = {}
    
    # El tamaño del n-gram en intervalos es (número de notas - 1)
    for tamano_notas in range(min_notas, max_notas + 1):
        n = tamano_notas - 1
        if len(intervalos) < n:
            continue
            
        # Generar todos los n-grams de intervalos posibles en la obra
        ngrams = [tuple(intervalos[i:i+n]) for i in range(len(intervalos) - n + 1)]
        conteo = Counter(ngrams)
        
        for patron, frecuencia in conteo.items():
            # Criterio: Debe repetirse al menos n_apariciones veces para considerarse leitmotiv
            if frecuencia >= n_apariciones:
                # Filtrar motivos triviales (ej: mantener la misma nota todo el tiempo [0, 0, 0])
                if all(intervalo == 0 for intervalo in patron):
                    continue
                
                # Convertir el patrón a un formato de texto legible (ej: "+4 -> -2 -> +1")
                patron_texto = " -> ".join(f"{'+' if i > 0 else ''}{i}" for i in patron)
                
                # Guardar el motivo y cuántas veces suena
                motivos_finales[patron_texto] = frecuencia

    # Devolvemos un JSON estandarizado para almacenar directamente en SQLite
    return json.dumps(motivos_finales, ensure_ascii=False)


def _get_middle_line_midi(clef_obj: m21.clef.Clef | None) -> float:
    """
    Devuelve el valor MIDI de la tercera línea (línea media del pentagrama)
    según la clave musical activa para realizar una comparación exacta de alturas.
    """
    if clef_obj is None:
        return 71.0  # Por defecto: B4 (Tercera línea en Clave de Sol)
    
    name = clef_obj.__class__.__name__
    
    if "Treble" in name or "GClef" in name:
        return 71.0  # Si4 / B4 (Clave de Sol en 2ª)
    elif "Bass" in name or "FClef" in name:
        return 50.0  # Re3 / D3 (Clave de Fa en 4ª)
    elif "Alto" in name:
        return 60.0  # Do4 / C4 (Clave de Do en 3ª)
    elif "Tenor" in name:
        return 57.0  # La3 / A3 (Clave de Do en 4ª)
        
    return 71.0  # Fallback seguro por si es una clave exótica
    

def _detect_stem_direction_anomalies(score: m21.stream.Score) -> dict[str, Any]:
    """
    Recorre todas las notas buscando excepciones de dirección de plica (stem):
    - Plica hacia ABAJO (down) estando estrictamente por DEBAJO de la tercera línea.
    - Plica hacia ARRIBA (up) estando estrictamente por ENCIMA de la tercera línea.
    """
    anomalies_count = 0
    compases_anomalos = set()
    
    # Recorremos todas las notas de la obra de forma estructurada
    for note_obj in score.recurse().getElementsByClass('Note'):
        # Extraemos la dirección de la plica guardada en el archivo original
        stem_dir = note_obj.stemDirection  # Puede ser 'up', 'down', 'none', o None
        
        # Si la plica es automática o no viene definida, nos la saltamos
        if stem_dir not in ['up', 'down']:
            continue
            
        # Obtenemos la clave activa en la sección exacta donde se encuentra esta nota
        active_clef = note_obj.getContextByClass(m21.clef.Clef)
        middle_line_midi = _get_middle_line_midi(active_clef)
        
        note_midi = note_obj.pitch.ps  # Altura de la nota en formato Pitch Space (MIDI)
        
        # Obtener el número de compás para indexar el error
        measure_num = note_obj.getContextByClass('Measure')
        measure_idx = measure_num.number if measure_num else 0
        
        # Condición 1: Plica "down" pero la nota está abajo de la 3ª línea
        if stem_dir == 'down' and note_midi < middle_line_midi:
            anomalies_count += 1
            compases_anomalos.add(measure_idx)
            
        # Condición 2: Plica "up" pero la nota está arriba de la 3ª línea
        elif stem_dir == 'up' and note_midi > middle_line_midi:
            anomalies_count += 1
            compases_anomalos.add(measure_idx)
            
    return {
        "tiene_plicas_anomalas": 1 if anomalies_count > 0 else 0,
        "conteo_plicas_anomalas": anomalies_count,
        "compases_plicas_anomalas": ", ".join(map(str, sorted(list(compases_anomalos)))) if compases_anomalos else ""
    }


def analizar_pieza(file_path: str | Path) -> dict[str, Any]:
    score = _safe_parse_score(file_path)
    if score is None:
        raise ValueError(f"No se pudo abrir la partitura: {file_path}")

    mei_meta = {}
    if Path(file_path).suffix.lower() == ".mei":
        mei_meta = _extract_mei_metadata_direct(file_path)

    titulo, autor = _extract_title_and_author(score, file_path)
    
    if not autor or autor.strip() == "":
        autor = mei_meta.get("author") or ""
        
    if titulo == Path(file_path).stem and mei_meta.get("title"):
        titulo = mei_meta.get("title")

    letra_cancion = _extract_lyrics(file_path)

    compas = _extract_compas(score)
    if not compas:
        compas = mei_meta.get("compas")

    tonalidad = _extract_tonality(score)
    if not tonalidad or tonalidad.strip() == "":
        tonalidad = _infer_tonality_custom(score, mei_meta.get("key_sig"))

    tonica_modo, modo_musical = _infer_mode_custom(score)
    modo_completo = f"{tonica_modo} {modo_musical}" if tonica_modo and modo_musical else None

    bpm = _extract_bpm(score)

    hemiolias_verticales = detectar_hemiolas_verticales(file_path)
    hemiolias_horizontales = detectar_hemiolas_horizontales(file_path)
    polirritmias = detectar_polirritmias(file_path)
    
    tiene_sinc, compases_sinc, conteo_sinc = detectar_sincopas(file_path)

    # Nota: Si el título quedó vacío, usamos el nombre del archivo
    titulo_analisis = titulo if titulo else Path(file_path).stem
    lista_temas = _analizar_temas_con_ollama(titulo_analisis, letra_cancion, model_name="llama3")
    temas_texto = ", ".join(lista_temas)

    # region_explicit = mei_meta.get("region")
    # if region_explicit:
    #     region_final = region_explicit
    #     justificacion_region = "Metadatos explícitos del archivo"
    # else:
    #     # Si no es explícito, delegamos la inferencia heurística a Ollama
    #     res_region = _inferir_region_con_ollama(titulo_analisis, letra_cancion, model_name="llama3")
    #     region_final = res_region["region"]
    #     justificacion_region = res_region["justificacion"]

    region_final = None
    justificacion_region = ""

    # Prioridad 1: Estructura de carpetas en la ruta (La fuente de verdad más fiable)
    # region_desde_ruta = _extraer_region_de_ruta(file_path)
    # if region_desde_ruta:
    #     region_final = region_desde_ruta
    #     justificacion_region = f"Deducido de la estructura de carpetas del corpus (Directorio: '{region_desde_ruta}')"

    # Prioridad 2: Metadatos internos explícitos del archivo MEI/XML
    if not region_final:
        region_explicit = mei_meta.get("region")
        if region_explicit:
            region_final = region_explicit
            justificacion_region = "Extraído de metadatos internos explícitos del archivo"

    # Prioridad 3: Inferencia heurística/LLM (Último recurso si el archivo está huérfano)
    # if not region_final:
    #     res_region = _inferir_region_con_ollama(titulo_analisis, letra_cancion, model_name="llama3")
    #     region_final = res_region["region"]
    #     justificacion_region = res_region["justificacion"]

    tiene_cambio_ppq, compases_cambio_ppq = _detectar_cambio_resolucion_ppq(file_path)

    tiene_desajuste_meter, compases_desajuste_meter = detectar_desajustes_meter_sig(file_path)

    tiene_irr_ocultos, compases_irr_ocultos, conteo_irr_ocultos = detectar_valores_irregulares_ocultos(file_path)

    total_eventos, total_compases, densidad_notas = _calcular_densidad_eventos(score)

    nota_mas_grave, nota_mas_aguda = _calcular_tesitura(score)

    autor_genero = _clasificar_genero_autor(autor)
    lirica_voz = _analizar_perspectiva_lirica(letra_cancion)

    notas_y_silencios_texto = _extract_notes_and_rests(score)

    lista_alturas = _extract_melody_pitches(score)
    conteo_direcciones = _analyze_interval_directions(lista_alturas)
    analisis_melodico = _determine_predominant_trend(conteo_direcciones)

    mapeo_silabas_json = _extract_syllable_duration_mapping(score)

    eventos_accidentales = _extract_accidental_events(score)
    reporte_accidentales = _format_accidentals_report(eventos_accidentales)

    metadatos_archivo = _extract_transcription_metadata(file_path)
    if score is None:
        raise ValueError(f"No se pudo parsear la partitura en {file_path}")
        
    control_calidad = _extract_quality_control_metadata(score)

    leitmotivs_json = _detect_leitmotivs_ngrams(score, min_notas=4, max_notas=5, n_apariciones=2)
    contiene_leitmotivs = 1 if leitmotivs_json != "{}" else 0

    resultado_plicas = _detect_stem_direction_anomalies(score)

    resultado = {
        "file_path": str(file_path),
        "titulo": titulo,
        "autor": autor,
        "compas": compas,
        "tonalidad": tonalidad,
        "modo": modo_musical,
        "modo_completo": modo_completo,
        "bpm": bpm,
        "nota_mas_grave": nota_mas_grave,
        "nota_mas_aguda": nota_mas_aguda,
        "tiene_hemiolia_vertical": 1 if hemiolias_verticales else 0,
        "compases_hemiolia_vertical": ", ".join(map(str, hemiolias_verticales)),
        "conteo_hemiolia_vertical": len(hemiolias_verticales),
        "tiene_hemiolia_horizontal": 1 if hemiolias_horizontales else 0,
        "compases_hemiolia_horizontal": ", ".join(map(str, hemiolias_horizontales)),
        "conteo_hemiolia_horizontal": len(hemiolias_horizontales),
        "tiene_sincopas": tiene_sinc,
        "compases_sincopas": compases_sinc,
        "conteo_sincopas": conteo_sinc,
        "temas": temas_texto,
        "region": region_final,
        "region_justificacion": justificacion_region,
        "cambio_resolucion_ppq": tiene_cambio_ppq,
        "compases_cambio_resolucion": compases_cambio_ppq,
        "desajuste_duracion_meter": tiene_desajuste_meter,
        "compases_desajuste_duracion_meter": compases_desajuste_meter,
        "valores_irregulares_ocultos": tiene_irr_ocultos,
        "compases_valores_irregulares_ocultos": compases_irr_ocultos,
        "conteo_valores_irregulares_ocultos": conteo_irr_ocultos,
        "total_eventos_musicales": total_eventos,
        "total_compases": total_compases,
        "densidad_notas_por_compas": densidad_notas,
        "tiene_polirritmia": 1 if polirritmias else 0,
        "compases_polirritmia": ", ".join(map(str, polirritmias)),
        "conteo_polirritmia": len(polirritmias),
        "autor_genero": autor_genero,
        "lirica_voz": lirica_voz,
        "texto_letras_extraido": letra_cancion[:500], # Guardamos una muestra del texto para auditoría
        "secuencia_notas_silencios": notas_y_silencios_texto,
        "tendencia_melodica": analisis_melodico["tendencia_melodica"],
        "porcentaje_intervalos_ascendentes": analisis_melodico["pct_ascendente"],
        "porcentaje_intervalos_descendentes": analisis_melodico["pct_descendente"],
        "mapeo_silabas_duraciones": mapeo_silabas_json,
        "accidentales_compases_json": reporte_accidentales["lista_accidentales_json"],
        "accidentales_resumen_texto": reporte_accidentales["resumen_accidentales"],
        "conteo_accidentales_totales": reporte_accidentales["total_accidentales"],
        "software_codificacion": metadatos_archivo["software_codificacion"],
        "convertido_via_verovio": metadatos_archivo["convertido_via_verovio"],
        "fecha_codificacion": metadatos_archivo["fecha_codificacion"],
        "formato_origen": metadatos_archivo["formato_origen"],
        "qc_compases_vacios": control_calidad["qc_compases_vacios"],
        "qc_notas_duracion_cero": control_calidad["qc_notas_duracion_cero"],
        "qc_advertencias_criticas": control_calidad["qc_advertencias_criticas"],
        "qc_puntuacion_integridad": control_calidad["qc_puntuacion_integridad"],
        "tiene_leitmotivs": contiene_leitmotivs,
        "patrones_leitmotivs_json": leitmotivs_json,
        "tiene_plicas_anomalas": resultado_plicas["tiene_plicas_anomalas"],
        "conteo_plicas_anomalas": resultado_plicas["conteo_plicas_anomalas"],
        "compases_plicas_anomalas": resultado_plicas["compases_plicas_anomalas"],
    }
    
    return resultado


def descubrir_archivos_partitura(corpus_dir: str | Path) -> list[str]:
    root = Path(corpus_dir)
    if not root.exists():
        return []

    files = [
        str(path)
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SONG_EXTENSIONS
    ]
    return sorted(files)


def preprocesar_corpus_para_sqlite(corpus_dir: str | Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    registros: list[dict[str, Any]] = []
    errores: list[dict[str, str]] = []

    for file_path in descubrir_archivos_partitura(corpus_dir):
        try:
            registros.append(analizar_pieza(file_path))
        except Exception as exc:
            errores.append({"file_path": file_path, "error": str(exc)})

    return registros, errores


def comparar_densidad_por_metro(registros: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Recibe la lista de canciones procesadas y calcula el promedio ponderado 
    de eventos musicales por compás agrupando por tipos de compás (4/4 vs 2/4).
    """
    # Filtrar las densidades registradas para cada tipo de compás
    densidades_44 = [r["densidad_notas_por_compas"] for r in registros if r["compas"] == "4/4"]
    densidades_24 = [r["densidad_notas_por_compas"] for r in registros if r["compas"] == "2/4"]
    
    promedio_44 = sum(densidades_44) / len(densidades_44) if densidades_44 else 0.0
    promedio_24 = sum(densidades_24) / len(densidades_24) if densidades_24 else 0.0
    
    ganador = "4/4" if promedio_44 > promedio_24 else ("2/4" if promedio_24 > promedio_44 else "Empate")
    
    return {
        "promedio_densidad_44": round(promedio_44, 2),
        "total_piezas_44": len(densidades_44),
        "promedio_densidad_24": round(promedio_24, 2),
        "total_piezas_24": len(densidades_24),
        "compas_mayor_densidad": ganador,
        "conclusion": f"El compás {ganador} tiene una mayor cantidad promedio de eventos musicales por compás en el dataset."
    }