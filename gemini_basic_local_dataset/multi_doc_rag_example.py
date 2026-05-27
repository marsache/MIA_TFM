from google import genai
from google.genai import types

from pathlib import Path
import unicodedata
import time

# -----------------------------
# CLIENT
# -----------------------------

MODEL_NAME = "gemini-2.5-flash"
client = genai.Client()

# -----------------------------
# GET FILE SEARCH STORE
# -----------------------------

STORE_DISPLAY_NAME = "music-dataset-store"
file_search_store = None

print("Checking for existing file search store...")

# Look for an existing store with your display name
existing_stores = client.file_search_stores.list()
for store in existing_stores:
    if store.display_name == STORE_DISPLAY_NAME:
        file_search_store = store
        print(f"Found existing store: {file_search_store.name}")
        break

# 2. Create it only if it doesn't exist
if file_search_store is None:
    print(f"Couldn't find store: {STORE_DISPLAY_NAME}")


# -----------------------------
# ASK QUESTIONS
# -----------------------------

while True:

    question = input("\nQuestion (or 'exit'): ")

    if question.lower() == "exit":
        break

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=question,
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[
                            file_search_store.name
                        ]
                    )
                )
            ]
        )
    )

    print("\nANSWER:\n")
    print(response.text)