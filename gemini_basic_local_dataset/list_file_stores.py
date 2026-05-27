from google import genai

client = genai.Client()

# List all available stores
stores = client.file_search_stores.list()

for store in stores:
    print(f"\nSTORE: {store.display_name}")
    print(f"NAME:  {store.name}")

    docs = client.file_search_stores.documents.list(
        parent=store.name
    )

    # Convert it to a Python list to get its length
    docs_list = list(docs)
    
    # Print the count
    print(f"TOTAL DOCUMENTS: {len(docs_list)}")

    for doc in docs:
        print("  -", doc.name)