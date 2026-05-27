import pandas as pd
from langchain_core.documents.base import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables.passthrough import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

def load_csv(csv_file_path = 'CoplasData.csv'):
    # Load CSV file
    data_frame = pd.read_csv(csv_file_path)

    print(f"Successfully loaded {len(data_frame)} rows from CSV")
    print(f"Columns available: {list(data_frame.columns)}")
    print(f"Data shape: {data_frame.shape}")

    # Look at the first few rows to understand the data structure
    print("First 5 rows of data:")
    print(data_frame.head())

    return data_frame

def create_readable_text_from_row(row):
    """
    Convert a single CSV row into a natural language description
    """
    # Customize this based on your CSV structure
    # This example assumes columns: Name, HEX, RGB
    description_parts = []
    for column_name, value in row.items():
        if pd.notna(value):  # Only include non-empty values
            description_parts.append(f"{column_name}: {value}")
    # Join everything into one readable sentence
    return ". ".join(description_parts) + "."


df = load_csv()

# Convert all rows to readable text documents
text_documents = []

for index, row in df.iterrows():
    # # Convert each row to readable text
    # readable_description = create_readable_text_from_row(row)
    # # Create a Document object (LangChain's format)
    # doc = Document(page_content=readable_description)
    # text_documents.append(doc)
    doc = Document(
        page_content=row["Letra"],
        metadata={"nombre": row["Nombre"]}
    )
    text_documents.append(doc)
  
print(f"Created {len(text_documents)} document objects")

# A few examples of what we created
print("\nExamples of converted documents:")
for i in range(min(3, len(text_documents))):
    print(f"Document {i+1}: {text_documents[i].page_content}")

# Embeddings
embedding_model = HuggingFaceEmbeddings(
    #model_name="sentence-transformers/all-MiniLM-L6-v2"
    model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
)
print("Embedding system initialized")
print("This will convert our text into numerical vectors that capture meaning")

# Create our vector store from the documents
print("Creating vector store from documents...")
vector_search_store = FAISS.from_documents(text_documents, embedding_model)
print(f"Vector store created with {len(text_documents)} documents")
print("Each document is now represented as a vector for fast similarity search")

# Test our search system
# test_query = "aves"
# similar_documents = vector_search_store.similarity_search(test_query, k=3)
# print(f"Testing search for: '{test_query}'")
# print(f"Found {len(similar_documents)} similar documents:")

# for i, doc in enumerate(similar_documents):
#     print(f"\nResult {i+1}: {doc.page_content}")

# Initialize our AI language model
ai_assistant = ChatOllama(
    model="qwen3:8b",
    temperature=0
)

print("AI assistant initialized")
print("Temperature set to 0 for consistent, factual responses")

# Create a retriever from our vector store
document_retriever = vector_search_store.as_retriever(
    search_kwargs={"k": 15}  # Retrieve top 3 most similar documents
)

print("Document retriever created")
print("It will find the k most relevant pieces of information for each question")

# Create a prompt template for our AI assistant
answer_prompt = PromptTemplate.from_template("""
Eres un especialista en música folclórica iberoamericana con un amplio conocimiento en géneros, tradiciones regionales, instrumentos, temáticas culturales y evolución histórica.

Tu tarea es analizar información proveniente de una base de datos (CSV) que contiene canciones y responder preguntas del usuario utilizando únicamente la información proporcionada en el contexto.

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

print("Prompt template created")

# Build the complete RAG chain using LCEL
rag_pipeline = (
    {
        "context": document_retriever,  # Find relevant documents
        "question": RunnablePassthrough()  # Pass the question through
    }
    | answer_prompt  # Format everything into our prompt
    | ai_assistant  # Generate the answer
    | StrOutputParser()  # Clean up the output
)
print("Complete RAG pipeline created!")

# Test multiple questions to see how our system handles different queries
test_questions = [
    "¿Qué canciones hablan sobre pájaros y aves?",
    "¿Qué canciones hablan sobre animales?",
    "¿Qué canciones hablan sobre alimentos?"
]

for question in test_questions:
    print(f"Pregunta: {question}")
    print("-" * 50)
    try:
        answer = rag_pipeline.invoke(question)
        print(f"Respuesta: {answer}")
    except Exception as e:
        print(f"Error: {str(e)}")
    print("="*60)