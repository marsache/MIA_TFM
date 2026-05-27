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
from langchain_community.document_loaders import UnstructuredXMLLoader, DirectoryLoader
import xml.etree.ElementTree as ET
from pathlib import Path

def extract_title_from_xml(xml_text: str) -> Optional[str]:
    try:
        root = ET.fromstring(xml_text)
        
        # Buscar <work-title>
        work_title = root.find(".//work-title")
        if work_title is not None and work_title.text:
            return work_title.text.strip()

        # Fallback opcional: <movement-title>
        movement_title = root.find(".//movement-title")
        if movement_title is not None and movement_title.text:
            return movement_title.text.strip()

    except Exception:
        pass

    return None


def clean_filename_title(filename: str) -> str:
    name = Path(filename).stem  # quita .xml

    # Quitar prefijo numérico tipo "289. "
    name = re.sub(r"^\d+\.\s*", "", name)

    return name.strip()


def extract_title_from_document(doc: Document) -> tuple[str, str]:
    """
    Devuelve: (titulo, fuente)
    fuente ∈ ["xml", "filename", "unknown"]
    """

    # 1. Intentar desde XML
    title_xml = extract_title_from_xml(doc.page_content)
    if title_xml:
        return title_xml, "xml"

    # 2. Fallback: filename
    source = doc.metadata.get("source", "")
    if source:
        filename_title = clean_filename_title(source)
        if filename_title:
            return filename_title, "filename"

    return "Sin título", "unknown"

def load_documents_from_directory(root_dir: str):
    documents = []

    for file_path in Path(root_dir).rglob("*.xml"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            doc = Document(
                page_content=content,
                metadata={"source": str(file_path)}
            )

            documents.append(doc)

        except Exception as e:
            print(f"Error loading {file_path}: {e}")

    return documents

def build_clean_content(doc: Document) -> str:
    titulo = doc.metadata.get("titulo", "Sin título")
    fuente = doc.metadata.get("titulo_fuente", "unknown")

    return f"""TÍTULO: {titulo}
FUENTE_TITULO: {fuente}

CONTENIDO_XML:
{doc.page_content}
"""

def build_rag_pipeline(root_dir='../corpus/datasets/para_nlp'):  
    if not os.path.exists(root_dir):
        raise ValueError(f"Directory does not exist: {root_dir}")

    if not os.path.isdir(root_dir):
        raise ValueError(f"Path is not a directory: {root_dir}")

    # Convert to documents
    documents = load_documents_from_directory(root_dir)
    normalized_documents = []

    for doc in documents:
        titulo, fuente = extract_title_from_document(doc)

        doc.metadata["titulo"] = titulo
        doc.metadata["titulo_fuente"] = fuente

        doc.metadata["filename"] = doc.metadata.get("source", "")

        normalized_documents.append(doc)

    documents = normalized_documents

    for doc in documents:
        doc.page_content = build_clean_content(doc)

    for doc in documents[:5]:
        print("TITULO:", doc.metadata["titulo"])
        print("FUENTE:", doc.metadata["titulo_fuente"])
        print("CONTENT PREVIEW:", doc.page_content[:200])
        print("------")

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
- No respondas sin usar la herramienta si falta información.
                                        
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
        "context": retriever,
        "question": RunnablePassthrough(),
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
    
def run_rag_with_tools(rag_pipeline, question: str, max_iterations: int = 5):
    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1} ---", file=sys.stderr)

        response = rag_pipeline.invoke(question)

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
            return response

    return "Error: max iterations reached"