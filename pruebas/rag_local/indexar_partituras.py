import os
import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from pathlib import Path

_BASE_DIR = Path(__file__).parent.parent
MUSIC_FOLDER = _BASE_DIR.parent / "datasets"

# Modelo de embeddings
embedding_model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# Base vectorial
client = chromadb.PersistentClient(path="./db_partituras")

collection = client.get_or_create_collection(
    name="partituras"
)

def leer_archivo(ruta):
    try:
        with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return None

# Obtener lista completa de archivos
archivos = []

for root, _, files in os.walk(MUSIC_FOLDER):
    for file in files:
        if file.endswith((".xml", ".musicxml", ".txt", ".mei", ".mscz")):
            archivos.append(os.path.join(root, file))

print(f"Se encontraron {len(archivos)} archivos")

contador = 0

with tqdm(
    total=len(archivos),
    desc="Indexando partituras",
    unit="archivo"
) as pbar:

    for ruta in archivos:

        contenido = leer_archivo(ruta)

        if contenido:

            embedding = embedding_model.encode(
                contenido[:10000]
            ).tolist()

            collection.add(
                ids=[str(contador)],
                embeddings=[embedding],
                documents=[contenido[:10000]],
                metadatas=[{"archivo": ruta}]
            )

            contador += 1

        pbar.set_postfix({
            "indexadas": contador
        })

        pbar.update(1)

print(f"\nIndexadas {contador} partituras")