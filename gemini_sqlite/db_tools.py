from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tempfile
import xml.etree.ElementTree as ET

import music21 as m21

import json
import requests


SUPPORTED_SONG_EXTENSIONS = {".xml", ".musicxml", ".mxl", ".mei"}
_EPSILON = 1e-3


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
        text = path_obj.read_text(encoding="utf-8")

        # music21 no soporta wordpos="s"
        text = text.replace('wordpos="s"', 'wordpos="i"')

        # Extraemos dinámicamente la extensión original (.xml, .musicxml, .mei...)
        orig_suffix = path_obj.suffix.lower()

        with tempfile.NamedTemporaryFile(
            suffix=orig_suffix,
            delete=False,
            mode="w",
            encoding="utf-8",
        ) as tmp:
            tmp.write(text)
            tmp_path = tmp.name

        return m21.converter.parse(tmp_path)

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


# def _has_6_8_feel(offsets: set[float]) -> bool:
#     return (
#         _contains_offset(offsets, 1.5)
#         and not _contains_offset(offsets, 1.0)
#         and not _contains_offset(offsets, 2.0)
#     )

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


# def _has_3_4_feel(offsets: set[float]) -> bool:
#     return (
#         (_contains_offset(offsets, 1.0) or _contains_offset(offsets, 2.0))
#         and not _contains_offset(offsets, 1.5)
#     )

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

                    print(num_compas, o1, o2)

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


# def detectar_sincopas(file_path: str | Path) -> tuple[int, str, int]:
#     score = _safe_parse_score(file_path)
#     if score is None:
#         return 0, "", 0

#     tiene_sincopas = 0
#     compases_sincopas: list[str] = []
#     conteo_sincopas = 0

#     for part in score.parts:
#         for measure in part.getElementsByClass(m21.stream.Measure):
#             num_compas = measure.measureNumber
#             if num_compas in (None, 0):
#                 continue

#             ts = _get_measure_time_signature(measure)
#             if not ts:
#                 continue

#             beat_ql = _to_float(ts.beatDuration.quarterLength)
#             bar_ql = _to_float(ts.barDuration.quarterLength)
#             if beat_ql <= 0 or bar_ql <= 0:
#                 continue

#             strong_beats: list[float] = []
#             beat_cursor = 0.0
#             while beat_cursor < bar_ql - _EPSILON:
#                 strong_beats.append(round(beat_cursor, 6))
#                 beat_cursor += beat_ql

#             # Aplanamos el compás para extraer notas de los <layer> / Voices
#             # y garantizar que sus offsets comiencen desde el inicio del compás.
#             flat_measure = measure.flatten()
            
#             syncopated_here = False
#             for note in flat_measure.notes:
#                 start = _to_float(note.offset)
#                 end = start + _to_float(note.duration.quarterLength)

#                 starts_on_strong = any(_is_close(start, sb) for sb in strong_beats)
#                 crosses_strong = any((start + _EPSILON) < sb < (end - _EPSILON) for sb in strong_beats)

#                 if (not starts_on_strong) and crosses_strong:
#                     compases_sincopas.append(str(num_compas))
#                     conteo_sincopas += 1
#                     syncopated_here = True
#                     break

#             if syncopated_here:
#                 tiene_sincopas = 1

#     # Eliminamos duplicados manteniendo el orden
#     compases_unicos = sorted(list(set(compases_sincopas)), key=int)
#     compases_texto = ", ".join(compases_unicos)

#     return tiene_sincopas, compases_texto, conteo_sincopas

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


def _extract_lyrics(score: m21.stream.Score) -> str:
    """Extrae y limpia todo el texto de la letra (versos) de la partitura."""
    palabras: list[str] = []
    
    # Recorremos todas las notas y acordes de la pieza
    for el in score.recurse().notes:
        # Caso 1: Tiene una sola letra directa (.lyric)
        if el.lyric:
            palabras.append(el.lyric)
        # Caso 2: Tiene múltiples estrofas (.lyrics es una lista de objetos Lyric)
        elif hasattr(el, 'lyrics') and el.lyrics:
            for lyr in el.lyrics:
                if lyr.text:
                    palabras.append(lyr.text)
                    
    # Unimos las sílabas/palabras. Como vienen separadas por notas, 
    # un simple espacio bastará para que el LLM entienda el contexto global.
    return " ".join(palabras).strip()


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

# def _extraer_region_de_ruta(file_path: str | Path) -> str | None:
#     """
#     Analiza la estructura de directorios buscando el nombre de la región.
#     Prioriza la carpeta madre directa o la subcarpeta posterior al último pivote organizacional.
#     """
#     parts = Path(file_path).parts
#     if len(parts) < 2:
#         return None
        
#     # Lista de términos genéricos del sistema que NO identifican regiones geográficas
#     carpetas_sistema = {
#         "mei", "xml", "musicxml", "mxl", "corpus", "dataset", "miscellanous", "líricas",
#         "datasets", "scores", "partituras", "songs", "updated", "vocal", "instrumental"
#     }
    
#     # Estrategia 1: Comprobación directa de la carpeta madre inmediata (parts[-2])
#     parent_name = parts[-2]
#     # Validamos que no sea genérica ni un nombre de extracción de un zip (ej: MEI-20260315...)
#     if parent_name.lower() not in carpetas_sistema and not parent_name.upper().startswith("MEI-"):
#         return parent_name
        
#     # Estrategia 2: Escaneo en reversa (de derecha a izquierda) buscando el pivote organizativo más cercano
#     for i in range(len(parts) - 2, -1, -1):
#         if parts[i].lower() in carpetas_sistema:
#             if i + 1 < len(parts) - 1:
#                 posible_region = parts[i + 1]
#                 if posible_region.lower() not in carpetas_sistema and not posible_region.upper().startswith("MEI-"):
#                     return posible_region
                    
#     return None

# def _inferir_region_con_ollama(titulo: str, letra: str, model_name: str = "llama3") -> dict[str, str]:
#     """
#     Conecta con Ollama para inferir la región geográfica o Comunidad Autónoma 
#     de procedencia basándose en el título, topónimos y el contexto lingüístico de la letra.
#     """
#     resultado_defecto = {"region": "Desconocida", "justificacion": "Datos insuficientes"}
#     if not titulo and not letra:
#         return resultado_defecto

#     prompt = f"""
#     Analiza rigurosamente el título y la letra de esta canción tradicional para deducir su región o Comunidad Autónoma española de origen.
    
#     Título: {titulo}
#     Letra: {letra}
#     """

#     system_prompt = (
#         "Eres un experto en musicología, dialectología y folklore español. Tu tarea es identificar la región de origen de las obras. "
#         "REGLAS ESTRICTAS DE SEGURIDAD:\n"
#         "1. Básate EXCLUSIVAMENTE en la letra proporcionada. NO inventes que la letra contiene palabras como 'jota', 'flamenco' o vocabulario regional si estas no aparecen textualmente.\n"
#         "2. Si el título contiene un topónimo (ej. 'Cabra') pero la letra no aporta ninguna pista lingüística, cultural o dialectal clara que lo secunde, NO des por segura la región; en su lugar, devuelve obligatoriamente 'Desconocida' en la región.\n"
#         "3. Debes responder EXCLUSIVAMENTE con un objeto JSON con las claves 'region' (la Comunidad Autónoma, región histórica o 'Desconocida') "
#         "y 'justificacion' (un motivo muy breve, veraz y de un solo renglón). No añadas nada de texto fuera del JSON.\n"
#         "Ejemplo si no estás seguro: {\"region\": \"Desconocida\", \"justificacion\": \"El título menciona un topónimo pero la letra es genérica y no contiene vocabulario regional que permita verificar el origen.\"}"
#     )

#     payload = {
#         "model": model_name,
#         "prompt": prompt,
#         "system": system_prompt,
#         "stream": False,
#         "format": "json",
#         "options": {
#             "temperature": 0.0  # Forzamos la máxima predictibilidad y reducimos la creatividad/alucinación
#         }
#     }

#     try:
#         response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=45)
#         if response.status_code == 200:
#             res_data = response.json()
#             response_text = res_data.get("response", "{}")
#             region_json = json.loads(response_text)
#             return {
#                 "region": region_json.get("region", "Desconocida"),
#                 "justificacion": region_json.get("justificacion", "Sin justificación")
#             }
#     except Exception as e:
#         print(f"Aviso: No se pudo inferir la región con Ollama para '{titulo}': {e}")
        
#     return resultado_defecto

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

    letra_cancion = _extract_lyrics(score)

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

    resultado = {
        "file_path": str(file_path),
        "titulo": titulo,
        "autor": autor,
        "compas": compas,
        "tonalidad": tonalidad,
        "modo": modo_musical,
        "modo_completo": modo_completo,
        "bpm": bpm,
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
        "compases_cambio_resolucion": compases_cambio_ppq
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