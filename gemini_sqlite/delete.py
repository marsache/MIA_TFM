from db_tools import analizar_pieza
from pathlib import Path

_BASE_DIR = Path(__file__).parent
DATASET_DIR = _BASE_DIR.parent / "datasets"
#print(analizar_pieza(DATASET_DIR / "corpus/MEI-20260315T140319Z-1-001/MEI/Miscellanous/MI-1921-00-AL-03553_updated.mei"))
print(analizar_pieza(DATASET_DIR / "corpus/MEI-20260315T140319Z-1-001/MEI/Colombia/CO-1935-00-LL-03561_updated.mei"))
#print(analizar_pieza(DATASET_DIR / "Muiñeiras/Muiñeiras/Cancionero de Torner/568.mscz"))
#print(analizar_pieza(DATASET_DIR / "para nlp\\cancionero básico de Castilla y León\\RONDAS Y CANCIONES\\LÍRICAS\\35. Adios, rosina, adiós, clavel.xml"))
print(analizar_pieza("ejemplos/plicas_anomalas_ejemplo.musicxml"))

# archivos_encontrados = [
#     p for p in DATASET_DIR.rglob("*") 
#     if "35. Adios, rosina" in p.name
# ]

# if archivos_encontrados:
#     archivo_real = archivos_encontrados[0]
#     print(f"Archivo localizado con éxito en el sistema: {archivo_real}")
#     print(analizar_pieza(archivo_real))
# else:
#     print("No se encontró ningún archivo que coincida con ese nombre en el directorio.")
