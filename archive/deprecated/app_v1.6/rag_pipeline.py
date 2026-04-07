import sys
import re
import pandas as pd
from typing import Optional
from langchain_core.documents.base import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables.passthrough import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from sparqltool import wikidata_mcp_tool_json
import os
import json
import xml.etree.ElementTree as ET
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever


def load_csv(path):
    df = pd.read_csv(path)
    docs = []

    for i, row in df.iterrows():
        # content = "\n".join([f"{col}: {row[col]}" for col in df.columns])

        content = f"""
            SONG TITLE: {row.get('title', '')}

            METADATA:
            - Genre: {row.get('genre', '')}
            - Region: {row.get('region', '')}

            LYRICS:
            {row.get('lyrics', '')}
            """

        docs.append(Document(
            page_content=content,
            metadata={
                "source": path,
                "row": i,
                "title": row.get("title", "")
            }
        ))

    return docs

def load_txt(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    return [
        Document(
            page_content=text,
            metadata={"source": path, "type": "txt"}
        )
    ]

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    def flatten_json(obj, prefix=""):
        lines = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                lines.extend(flatten_json(v, f"{prefix}{k}."))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                lines.extend(flatten_json(v, f"{prefix}{i}."))
        else:
            lines.append(f"{prefix[:-1]}: {obj}")
        return lines

    content = "\n".join(flatten_json(data))

    return [
        Document(
            page_content=content,
            metadata={"source": path, "type": "json"}
        )
    ]

def load_pdf(path):
    loader = PyPDFLoader(path)
    docs = loader.load()

    # Add metadata
    for d in docs:
        d.metadata["source"] = path
        d.metadata["type"] = "pdf"

    return docs

def load_xml(path):
    tree = ET.parse(path)
    root = tree.getroot()

    def extract_text(element):
        texts = []
        if element.text and element.text.strip():
            texts.append(element.text.strip())

        for child in element:
            texts.extend(extract_text(child))

        return texts

    content = "\n".join(extract_text(root))

    return [
        Document(
            page_content=content,
            metadata={"source": path, "type": "xml"}
        )
    ]

def load_mei(path):
    tree = ET.parse(path)
    root = tree.getroot()

    ns = {"mei": "http://www.music-encoding.org/ns/mei"}

    texts = []

    # Extract lyrics
    for syl in root.findall(".//mei:syl", ns):
        if syl.text:
            texts.append(f"lyric: {syl.text}")

    # Extract titles
    for title in root.findall(".//mei:title", ns):
        if title.text:
            texts.append(f"title: {title.text}")

    # Extract staff/instrument info
    for staff in root.findall(".//mei:staffDef", ns):
        label = staff.attrib.get("label")
        if label:
            texts.append(f"instrument: {label}")

    content = "\n".join(texts)

    return [
        Document(
            page_content=content,
            metadata={"source": path, "type": "mei"}
        )
    ]

def load_documents_from_directory(root_dir: str):
    documents = []

    for dirpath, _, filenames in os.walk(root_dir):
        for file in filenames:
            path = os.path.join(dirpath, file)

            try:
                if file.endswith(".csv"):
                    documents.extend(load_csv(path))

                elif file.endswith(".txt"):
                    documents.extend(load_txt(path))

                elif file.endswith(".json"):
                    documents.extend(load_json(path))

                elif file.endswith(".pdf"):
                    documents.extend(load_pdf(path))

                elif file.endswith(".xml"):
                    documents.extend(load_xml(path))

                elif file.endswith(".mei"):
                    documents.extend(load_mei(path))

            except Exception as e:
                print(f"Error loading {path}: {e}")

    return documents

def split_documents(documents):
    splitter = RecursiveCharacterTextSplitter(
        # chunk_size=800,
        # chunk_overlap=150
        chunk_size=1500,
        chunk_overlap=100
    )
    return splitter.split_documents(documents)

def build_rag_pipeline(root_dir='../corpus/'):
    if not os.path.exists(root_dir):
        raise ValueError(f"Directory does not exist: {root_dir}")

    if not os.path.isdir(root_dir):
        raise ValueError(f"Path is not a directory: {root_dir}")
    
    # Convert to documents
    documents = load_documents_from_directory(root_dir)
    # documents = split_documents(documents)

    # Only split long docs like PDFs, not CSV rows
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=100
    )

    new_docs = []

    for doc in documents:
        if doc.metadata.get("type") == "csv":
            new_docs.append(doc)
        else:
            new_docs.extend(splitter.split_documents([doc]))

    documents = new_docs

    print(f"Total documents: {len(documents)}")

    # TEMP
    # MAX_DOCS = 5000
    # if len(documents) > MAX_DOCS:
    #     print(f"Limiting documents to {MAX_DOCS}")
    #     documents = documents[:MAX_DOCS]
    
    # Embeddings
    # embedding_model = HuggingFaceEmbeddings(
    #     model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    # )
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        model_kwargs={"device": "cuda"},
        encode_kwargs={"batch_size": 32}
    )

    # Vector store
    # vector_store = FAISS.from_documents(documents, embedding_model)

    # Vector store persistence
    index_path = f"../faiss_index_{os.path.basename(root_dir)}"
    
    if os.path.exists(index_path):
        print("Loading existing FAISS index...")
        vector_store = FAISS.load_local(
            index_path,
            embedding_model,
            allow_dangerous_deserialization=True
        )
    else:
        # print("Creating new FAISS index...")
        # vector_store = FAISS.from_documents(documents, embedding_model)
        # vector_store.save_local(index_path)

        print("Creating new FAISS index...")

        print(f"Embedding {len(documents)} chunks...")

        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        embeddings = embedding_model.embed_documents(
            [text for text in tqdm(texts)]
        )

        vector_store = FAISS.from_embeddings(
            list(zip(texts, embeddings)),
            embedding_model,
            metadatas=metadatas
        )

        vector_store.save_local(index_path)

    # LLM
    llm = ChatOllama(
        model="qwen3:8b",
        temperature=0
    )

    # Retriever
    retriever = vector_store.as_retriever(search_kwargs={"k": 15})

    # retriever = vector_store.as_retriever(
    #     search_kwargs={"k": 15, "filter": {"source": "some_file"}}
    # )

    bm25 = BM25Retriever.from_documents(documents)
    bm25.k = 40

    faiss_retriever = vector_store.as_retriever(search_kwargs={"k": 20})

    retriever = EnsembleRetriever(
        retrievers=[bm25, faiss_retriever],
        weights=[0.5, 0.5]
)

    # Prompt
    prompt = PromptTemplate.from_template("""
Eres un musicólogo especialista en música folclórica iberoamericana con un amplio conocimiento en géneros, tradiciones regionales, instrumentos, temáticas culturales y evolución histórica.

Tu tarea es analizar información proveniente de una base de datos (CSV) que contiene canciones y responder preguntas del usuario utilizando:
                                        
1. El CONTEXTO proporcionado (base de datos CSV)
2. Herramientas externas SOLO si el contexto no es suficiente
                                          
Sé lo más objetivo posible.
                                          
Responde en HTML usando:
- <h3> para títulos
- <ul><li> para listas
- <strong> para nombres
- <p> para texto

No uses markdown.

USO DE HERRAMIENTAS:
                                          
Cuando necesites utilizar una herramienta, tu salida DEBE tener EXACTAMENTE el siguiente formato:
                                          
TOOL_CALL: function_name(arg1=value1, arg2=value2)

{tools_section}

Example:
User: Generate an elf name and a location
Assistant: TOOL_CALL: get_elf_name(count=1)
[System provides result]
Assistant: TOOL_CALL: get_location_description(style='detailed')
[System provides result]
Assistant: Here's your character: [use the provided name] in [use the provided location]
                 
IMPORTANTE:

- Muestra el TOOL_CALL en su propia línea
- Después de mostrar un TOOL_CALL, DETENTE y espera el resultado
- Cuando recibas un TOOL_RESULT, úsalo de forma natural en tu respuesta
- NO inventes ni alucines resultados de herramientas; usa siempre el TOOL_RESULT proporcionado

Ejemplo:
Usuario: Proporciona toda la información que tengas sobre "La Pájara Pinta"
Asistente: TOOL_CALL: wikidata_mcp_tool_json(name="La Pájara Pinta")
[Sistema proporciona el resultado]

INSTRUCCIONES IMPORTANTES:

- Usa exclusivamente la información incluida en el CONTEXTO.
- No inventes información ni completes con conocimiento externo.
- Si la información no está disponible, responde exactamente:
  "No tengo esa información en los datos proporcionados."
- Cita y justifica de dónde has sacado la información de tu respuesta.
- Puedes identificar canciones no sólo por coincidencia exacta de palabras clave, sino también por similitud semántica (por ejemplo, relaciones temáticas, culturales, regionales o estilísticas).
- Si la pregunta implica recomendaciones, explica brevemente por qué las canciones encontradas son relevantes según el contexto.
- Mantén un tono profesional y especializado en folklore iberoamericano.
- Sé claro, estructurado y conciso.
                                          
REGLA CRÍTICA:

- Si la información necesaria NO está en el CONTEXTO, DEBES usar la herramienta disponible.
- Antes de concluir que la información no está, revisa cuidadosamente el CONTEXTO en busca de coincidencias parciales o aproximadas del nombre de la canción.
- No respondas sin usar la herramienta si falta información.

HISTORIAL DE CONVERSACIÓN:
{chat_history}
                                                                             
CONTEXTO:
{context}

PREGUNTA DEL USUARIO:
{question}

FORMATO DE SALIDA (OBLIGATORIO):

- TODA respuesta final DEBE estar en HTML válido
- PROHIBIDO usar markdown (**, -, #, etc.)
- Si usas markdown, la respuesta es incorrecta
- No incluyas texto fuera de etiquetas HTML
                                          
Ejemplo de respuesta correcta:

<h3>Información sobre La Pájara Pinta</h3>
<p>Esta canción pertenece al repertorio tradicional...</p>
<ul>
  <li><strong>Género:</strong> Música infantil tradicional</li>
  <li><strong>Región:</strong> Colombia</li>
</ul>

RESPUESTA:
""")

    # Pipeline
    rag_pipeline = (
    {
        "context": lambda x: retriever.get_relevant_documents(x["question"]),
        "question": lambda x: x["question"],
        "chat_history": lambda x: x.get("chat_history", ""),
        "tools_section": lambda _: (
            "Herramientas disponibles:\n"
            "- wikidata_mcp_tool_json(label: string)\n\n"
            "Formato de uso:\n"
            "TOOL_CALL: wikidata_mcp_tool_json(label=\"texto\")\n\n"
            "Ejemplo:\n"
            "TOOL_CALL: wikidata_mcp_tool_json(label=\"La Pájara Pinta\")"
        )
    }
    | prompt
    | llm
    | StrOutputParser()
)

    return rag_pipeline

def extract_tool_call(text: str) -> Optional[tuple[str, dict]]:
    """Extract tool call from LLM response"""
    # Look for: TOOL_CALL: function_name(arg1=value1, arg2=value2)
    pattern = r'TOOL_CALL:\s*(\w+)\((.*?)\)'
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    
    if not match:
        return None
    
    function_name = match.group(1)
    args_str = match.group(2).strip()
    
    arguments = {}
    if args_str:
        # Parse: arg=value, arg=value
        for arg_pair in args_str.split(','):
            if '=' in arg_pair:
                key, value = arg_pair.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Try to convert to int
                try:
                    value = int(value)
                except ValueError:
                    value = value.strip('"\'')
                arguments[key] = value
    
    print(f"[PARSE] Extracted: {function_name}({arguments})", file=sys.stderr)
    return function_name, arguments

def mcp_tool_executor(function_name: str, arguments: dict) -> str:
    if function_name == "wikidata_mcp_tool_json":
        result = wikidata_mcp_tool_json(**arguments)
        return result[:3000]
    else:
        raise ValueError(f"Unknown tool: {function_name}")
    
def format_history(history):
    return "\n".join(
        [f"{role.upper()}: {msg}" for role, msg in history]
    )
    
# def run_rag_with_tools(rag_pipeline, question: str, max_iterations: int = 5):
def run_rag_with_tools(rag_pipeline, question: str, history: list, max_iterations: int = 5):
    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1} ---", file=sys.stderr)

        # response = rag_pipeline.invoke(question)

        response = rag_pipeline.invoke({
            "question": question,
            "chat_history": format_history(history)
        })

        print(f"[LLM OUTPUT]:\n{response}\n", file=sys.stderr)

        tool_call = extract_tool_call(response)

        if tool_call:
            if "TOOL_RESULT" in question:
                print("[WARNING] Tool already used, forcing final answer", file=sys.stderr)
                return response

            function_name, arguments = tool_call
            print(f"[TOOL CALL DETECTED] {function_name} {arguments}", file=sys.stderr)

            try:
                tool_result = mcp_tool_executor(function_name, arguments)
                print("TOOL RESULT: " + tool_result)
            except Exception as e:
                question += f"\n\nTOOL_ERROR: {str(e)}"
                continue

            question += (
                "\n\n---\n"
                f"TOOL_RESULT:\n{tool_result}\n"
                "---\n"
                "Ahora responde usando esta información. No vuelvas a llamar a la herramienta."
            )

            continue

        else:
            history.append(("user", question))
            history.append(("assistant", response))
            return response

    return "Error: max iterations reached"