import chromadb
import ollama
from sentence_transformers import SentenceTransformer

embedding_model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

client = chromadb.PersistentClient(path="./db_partituras")
collection = client.get_collection("partituras")
print("Collection Count: " + str(collection.count()))

print("Chat RAG iniciado.")
print("Escribe 'salir' para terminar.\n")

while True:

    pregunta = input("Pregunta: ").strip()

    if pregunta.lower() in ["salir", "exit", "quit"]:
        print("Finalizando...")
        break

    query_embedding = embedding_model.encode(
        pregunta
    ).tolist()

    resultados = collection.query(
        query_embeddings=[query_embedding],
        n_results=5
    )

    contexto = "\n\n".join(
        resultados["documents"][0]
    )

    print("\nRESULTADOS:")
    for i, meta in enumerate(resultados["metadatas"][0]):
        print(i + 1, meta["archivo"])

    prompt = f"""
Usa exclusivamente el contexto proporcionado.

CONTEXTO:
{contexto}

PREGUNTA:
{pregunta}
"""

    respuesta = ollama.chat(
        model="llama3.1:8b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    print("\nRespuesta:\n")
    print(respuesta["message"]["content"])
    print("\n" + "-" * 80 + "\n")