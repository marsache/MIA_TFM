import pandas as pd
from langchain_core.documents.base import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables.passthrough import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser


def build_rag_pipeline(csv_file_path='CoplasData.csv'):
    df = pd.read_csv(csv_file_path)

    # Convert to documents
    documents = []
    for _, row in df.iterrows():
        doc = Document(
            page_content=row["Letra"],
            metadata={"nombre": row["Nombre"]}
        )
        documents.append(doc)

    # Embeddings
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    )

    # Vector store
    vector_store = FAISS.from_documents(documents, embedding_model)

    # LLM
    llm = ChatOllama(
        model="qwen3:8b",
        temperature=0
    )

    # Retriever
    retriever = vector_store.as_retriever(search_kwargs={"k": 15})

    # Prompt
    prompt = PromptTemplate.from_template("""
Eres un musicólogo especialista en música folclórica iberoamericana con un amplio conocimiento en géneros, tradiciones regionales, instrumentos, temáticas culturales y evolución histórica.

Tu tarea es analizar información proveniente de una base de datos (CSV) que contiene canciones y responder preguntas del usuario utilizando únicamente la información proporcionada en el contexto.
                                          
Responde en HTML usando:
- <h3> para títulos
- <ul><li> para listas
- <strong> para nombres
- <p> para texto

No uses markdown.

INSTRUCCIONES IMPORTANTES:

- Usa exclusivamente la información incluida en el CONTEXTO.
- No inventes información ni completes con conocimiento externo.
- Si la información no está disponible, responde exactamente:
  "No tengo esa información en los datos proporcionados."
- Puedes identificar canciones no sólo por coincidencia exacta de palabras clave, sino también por similitud semántica (por ejemplo, relaciones temáticas, culturales, regionales o estilísticas).
- Si la pregunta implica recomendaciones, explica brevemente por qué las canciones encontradas son relevantes según el contexto.
- Mantén un tono profesional y especializado en folklore iberoamericano.
- Sé claro, estructurado y conciso.

CONTEXTO:
{context}

PREGUNTA DEL USUARIO:
{question}

RESPUESTA:
""")

    # Pipeline
    rag_pipeline = (
        {
            "context": retriever,
            "question": RunnablePassthrough()
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_pipeline