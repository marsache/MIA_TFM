import pandas as pd
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
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

# Convert entire CSV into structured text
full_context = ""

for _, row in df.iterrows():
    readable_description = create_readable_text_from_row(row)
    full_context += readable_description + "\n"

print("Full CSV converted to context text")

print("Full context length: " + str(len(full_context)))

# Initialize our AI language model
ai_assistant = ChatOllama(
    model="qwen3:8b",
    temperature=0
)

print("AI assistant initialized")
print("Temperature set to 0 for consistent, factual responses")

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
        "context": lambda x: full_context,  # Inject full CSV
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