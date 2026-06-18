def detectar_sincopas(file_path: str | Path) -> tuple[int, str, int]:
    score = _safe_parse_score(file_path)
    if score is None:
        return 0, "", 0

    tiene_sincopas = 0
    compases_sincopas: list[str] = []
    conteo_sincopas = 0

    for part in score.parts:
        for measure in part.getElementsByClass(m21.stream.Measure):
            num_compas = measure.measureNumber
            if num_compas in (None, 0):
                continue

            ts = _get_measure_time_signature(measure)
            if not ts:
                continue

            beat_ql = _to_float(ts.beatDuration.quarterLength)
            bar_ql = _to_float(ts.barDuration.quarterLength)
            if beat_ql <= 0 or bar_ql <= 0:
                continue

            strong_beats: list[float] = []
            beat_cursor = 0.0
            while beat_cursor < bar_ql - _EPSILON:
                strong_beats.append(round(beat_cursor, 6))
                beat_cursor += beat_ql

            # Aplanamos el compás para extraer notas de los <layer> / Voices
            # y garantizar que sus offsets comiencen desde el inicio del compás.
            flat_measure = measure.flatten()
            
            syncopated_here = False
            for note in flat_measure.notes:
                start = _to_float(note.offset)
                end = start + _to_float(note.duration.quarterLength)

                starts_on_strong = any(_is_close(start, sb) for sb in strong_beats)
                crosses_strong = any((start + _EPSILON) < sb < (end - _EPSILON) for sb in strong_beats)

                if (not starts_on_strong) and crosses_strong:
                    compases_sincopas.append(str(num_compas))
                    conteo_sincopas += 1
                    syncopated_here = True
                    break

            if syncopated_here:
                tiene_sincopas = 1

    # Eliminamos duplicados manteniendo el orden
    compases_unicos = sorted(list(set(compases_sincopas)), key=int)
    compases_texto = ", ".join(compases_unicos)

    return tiene_sincopas, compases_texto, conteo_sincopas

def _extraer_region_de_ruta(file_path: str | Path) -> str | None:
    """
    Analiza la estructura de directorios buscando el nombre de la región.
    Prioriza la carpeta madre directa o la subcarpeta posterior al último pivote organizacional.
    """
    parts = Path(file_path).parts
    if len(parts) < 2:
        return None
        
    # Lista de términos genéricos del sistema que NO identifican regiones geográficas
    carpetas_sistema = {
        "mei", "xml", "musicxml", "mxl", "corpus", "dataset", "miscellanous", "líricas",
        "datasets", "scores", "partituras", "songs", "updated", "vocal", "instrumental"
    }
    
    # Estrategia 1: Comprobación directa de la carpeta madre inmediata (parts[-2])
    parent_name = parts[-2]
    # Validamos que no sea genérica ni un nombre de extracción de un zip (ej: MEI-20260315...)
    if parent_name.lower() not in carpetas_sistema and not parent_name.upper().startswith("MEI-"):
        return parent_name
        
    # Estrategia 2: Escaneo en reversa (de derecha a izquierda) buscando el pivote organizativo más cercano
    for i in range(len(parts) - 2, -1, -1):
        if parts[i].lower() in carpetas_sistema:
            if i + 1 < len(parts) - 1:
                posible_region = parts[i + 1]
                if posible_region.lower() not in carpetas_sistema and not posible_region.upper().startswith("MEI-"):
                    return posible_region
                    
    return None

def _inferir_region_con_ollama(titulo: str, letra: str, model_name: str = "llama3") -> dict[str, str]:
    """
    Conecta con Ollama para inferir la región geográfica o Comunidad Autónoma 
    de procedencia basándose en el título, topónimos y el contexto lingüístico de la letra.
    """
    resultado_defecto = {"region": "Desconocida", "justificacion": "Datos insuficientes"}
    if not titulo and not letra:
        return resultado_defecto

    prompt = f"""
    Analiza rigurosamente el título y la letra de esta canción tradicional para deducir su región o Comunidad Autónoma española de origen.
    
    Título: {titulo}
    Letra: {letra}
    """

    system_prompt = (
        "Eres un experto en musicología, dialectología y folklore español. Tu tarea es identificar la región de origen de las obras. "
        "REGLAS ESTRICTAS DE SEGURIDAD:\n"
        "1. Básate EXCLUSIVAMENTE en la letra proporcionada. NO inventes que la letra contiene palabras como 'jota', 'flamenco' o vocabulario regional si estas no aparecen textualmente.\n"
        "2. Si el título contiene un topónimo (ej. 'Cabra') pero la letra no aporta ninguna pista lingüística, cultural o dialectal clara que lo secunde, NO des por segura la región; en su lugar, devuelve obligatoriamente 'Desconocida' en la región.\n"
        "3. Debes responder EXCLUSIVAMENTE con un objeto JSON con las claves 'region' (la Comunidad Autónoma, región histórica o 'Desconocida') "
        "y 'justificacion' (un motivo muy breve, veraz y de un solo renglón). No añadas nada de texto fuera del JSON.\n"
        "Ejemplo si no estás seguro: {\"region\": \"Desconocida\", \"justificacion\": \"El título menciona un topónimo pero la letra es genérica y no contiene vocabulario regional que permita verificar el origen.\"}"
    )

    payload = {
        "model": model_name,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0  # Forzamos la máxima predictibilidad y reducimos la creatividad/alucinación
        }
    }

    try:
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=45)
        if response.status_code == 200:
            res_data = response.json()
            response_text = res_data.get("response", "{}")
            region_json = json.loads(response_text)
            return {
                "region": region_json.get("region", "Desconocida"),
                "justificacion": region_json.get("justificacion", "Sin justificación")
            }
    except Exception as e:
        print(f"Aviso: No se pudo inferir la región con Ollama para '{titulo}': {e}")
        
    return resultado_defecto

def _has_3_4_feel(offsets: set[float]) -> bool:
    return (
        (_contains_offset(offsets, 1.0) or _contains_offset(offsets, 2.0))
        and not _contains_offset(offsets, 1.5)
    )

def _has_6_8_feel(offsets: set[float]) -> bool:
    return (
        _contains_offset(offsets, 1.5)
        and not _contains_offset(offsets, 1.0)
        and not _contains_offset(offsets, 2.0)
    )