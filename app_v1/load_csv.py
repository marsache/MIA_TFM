import pandas as pd
from langchain.schema import Document

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
    # Convert each row to readable text
    readable_description = create_readable_text_from_row(row)
    # Create a Document object (LangChain's format)
    doc = Document(page_content=readable_description)
    text_documents.append(doc)
  
print(f"Created {len(text_documents)} document objects")

# A few examples of what we created
print("\nExamples of converted documents:")
for i in range(min(3, len(text_documents))):
    print(f"Document {i+1}: {text_documents[i].page_content}")