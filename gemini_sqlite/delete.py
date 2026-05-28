from db_tools import analizar_pieza
from pathlib import Path

_BASE_DIR = Path(__file__).parent
DATASET_DIR = _BASE_DIR.parent / "datasets"
#print(analizar_pieza(DATASET_DIR / "corpus/MEI-20260315T140319Z-1-001/MEI/Miscellanous/MI-1921-00-AL-03553_updated.mei"))
print(analizar_pieza(DATASET_DIR / "corpus/MEI-20260315T140319Z-1-001/MEI/Colombia/CO-1935-00-LL-03561_updated.mei"))
#print(analizar_pieza("ejemplos/hemiolia_h_ejemplo.xml"))