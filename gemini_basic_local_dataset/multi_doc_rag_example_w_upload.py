from google import genai
from google.genai import types

from pathlib import Path
import unicodedata
import time

# -----------------------------
# CONFIG
# -----------------------------

_BASE_DIR = Path(__file__).parent
DATASET_DIR = _BASE_DIR.parent / "datasets"
MODEL_NAME = "gemini-2.5-flash"

# Allowed file extensions
# VALID_EXTENSIONS = {
#     ".txt",
#     ".xml",
#     ".md",
#     ".json",
#     ".csv",
#     ".mscz",
#     ".mei"
# }

# Mapping extensions to appropriate MIME types for the API
MIME_TYPES_MAP = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".csv": "text/csv",
    ".xml": "application/xml",
    # MEI is XML-based, so application/xml tells the backend it's readable text
    ".mei": "application/xml", 
    # MSCZ is a zipped binary format. application/octet-stream is a fallback
    ".mscz": "application/xml"
}

VALID_EXTENSIONS = set(MIME_TYPES_MAP.keys())

# -----------------------------
# CLIENT
# -----------------------------

client = genai.Client()

# -----------------------------
# CREATE FILE SEARCH STORE
# -----------------------------

# file_search_store = client.file_search_stores.create(
#     config={
#         "display_name": "music-dataset-store"
#     }
# )

# print(f"Created store: {file_search_store.name}")

# -----------------------------
# GET OR CREATE FILE SEARCH STORE 2
# -----------------------------

STORE_DISPLAY_NAME = "music-dataset-store"
file_search_store = None

print("Checking for existing file search store...")

# 1. Look for an existing store with your display name
existing_stores = client.file_search_stores.list()
for store in existing_stores:
    if store.display_name == STORE_DISPLAY_NAME:
        file_search_store = store
        print(f"Found existing store: {file_search_store.name}")
        break

# 2. Create it only if it doesn't exist
if file_search_store is None:
    file_search_store = client.file_search_stores.create(
        config={
            "display_name": STORE_DISPLAY_NAME
        }
    )
    print(f"Created new store: {file_search_store.name}")

# 3. Gather names of files already uploaded to prevent duplicates
existing_file_names = set()
try:
    # Fetch documents currently tracked in this store
    existing_docs = client.file_search_stores.documents.list(parent=file_search_store.name)
    for doc in existing_docs:
        # doc.display_name matches the safe_name we give it during upload
        if doc.display_name:
            existing_file_names.add(doc.display_name)
except Exception as e:
    print(f"Could not retrieve existing documents (skipping duplicate check): {e}")

# -----------------------------
# HELPER: SAFE ASCII FILENAMES
# -----------------------------

# def safe_display_name(path: Path) -> str:
#     """
#     Convert Unicode filenames into ASCII-safe display names.
#     """
#     return (
#         unicodedata
#         .normalize("NFKD", path.name)
#         .encode("ascii", "ignore")
#         .decode("ascii")
#     )

# -----------------------------
# HELPER: SAFE ASCII FILENAMES
# -----------------------------

import re

def safe_display_name(path: Path) -> str:

    normalized = unicodedata.normalize("NFKD", path.name)

    ascii_name = (
        normalized
        .encode("ascii", "ignore")
        .decode("ascii")
    )

    # remove dangerous leftovers
    ascii_name = re.sub(r"[^A-Za-z0-9._ -]", "", ascii_name)

    return ascii_name

# -----------------------------
# FIND FILES RECURSIVELY
# -----------------------------

# dataset_path = Path(DATASET_DIR)

# files_to_upload = []

# for file_path in dataset_path.rglob("*"):
#     if file_path.is_file():
#         if file_path.suffix.lower() in VALID_EXTENSIONS:
#             files_to_upload.append(file_path)

# print(f"Found {len(files_to_upload)} files")

# -----------------------------
# FIND FILES RECURSIVELY 2
# -----------------------------

dataset_path = Path(DATASET_DIR)
files_to_upload = []

for file_path in dataset_path.rglob("*"):
    if file_path.is_file():
        if file_path.suffix.lower() in VALID_EXTENSIONS:
            safe_name = safe_display_name(file_path)
            
            # If we are handling a MuseScore file, it gets renamed to .xml inside the batch uploader
            if file_path.suffix.lower() == ".mscz":
                safe_name = Path(safe_name).with_suffix('.xml').name

            # Skip file if it's already in the Gemini store
            if safe_name in existing_file_names:
                continue
                
            files_to_upload.append(file_path)

print(f"Found {len(files_to_upload)} new files to upload.")

# -----------------------------
# UPLOAD FILES
# -----------------------------

# operations = []

# for file_path in files_to_upload:

#     print(f"Uploading: {file_path}")

#     operation = client.file_search_stores.upload_to_file_search_store(
#         file=str(file_path),
#         file_search_store_name=file_search_store.name,
#         config={
#             "display_name": safe_display_name(file_path),
#         }
#     )

#     operations.append(operation)

# -----------------------------
# UPLOAD FILES 2
# -----------------------------

# import tempfile
# import shutil

# operations = []

# for file_path in files_to_upload:

#     safe_name = safe_display_name(file_path)

#     print(f"Uploading: {file_path}")

#     # Create temporary ASCII-safe file
#     with tempfile.TemporaryDirectory() as tmpdir:

#         temp_path = Path(tmpdir) / safe_name

#         shutil.copy2(file_path, temp_path)

#         operation = client.file_search_stores.upload_to_file_search_store(
#             file=str(temp_path),
#             file_search_store_name=file_search_store.name,
#             config={
#                 "display_name": safe_name,
#             }
#         )

#     operations.append(operation)

# # -----------------------------
# # WAIT FOR INDEXING
# # -----------------------------

# print("\nWaiting for indexing to finish...\n")

# all_done = False

# while not all_done:

#     all_done = True

#     for i, operation in enumerate(operations):

#         if not operation.done:

#             operations[i] = client.operations.get(operation)

#             if not operations[i].done:
#                 all_done = False

#     print("Still indexing...")
#     time.sleep(5)

# print("All files indexed!")

# -----------------------------
# BATCHED UPLOADS
# -----------------------------

import tempfile
import shutil
import math

BATCH_SIZE = 100
SLEEP_BETWEEN_BATCHES = 5

total_files = len(files_to_upload)
total_batches = math.ceil(total_files / BATCH_SIZE)

print(f"\nUploading in {total_batches} batches...\n")

# -----------------------------
# PROCESS BATCHES
# -----------------------------

for batch_index in range(total_batches):

    start = batch_index * BATCH_SIZE
    end = start + BATCH_SIZE

    batch_files = files_to_upload[start:end]

    print("=" * 60)
    print(f"BATCH {batch_index + 1}/{total_batches}")
    print(f"Files {start + 1} -> {min(end, total_files)}")
    print("=" * 60)

    operations = []

    # -----------------------------
    # UPLOAD BATCH
    # -----------------------------

    # for file_path in batch_files:

    #     try:

    #         safe_name = safe_display_name(file_path)

    #         print(f"Uploading: {safe_name}")

    #         # Create temporary ASCII-safe file
    #         with tempfile.TemporaryDirectory() as tmpdir:

    #             temp_path = Path(tmpdir) / safe_name

    #             shutil.copy2(file_path, temp_path)

    #             operation = client.file_search_stores.upload_to_file_search_store(
    #                 file=str(temp_path),
    #                 file_search_store_name=file_search_store.name,
    #                 config={
    #                     "display_name": safe_name,
    #                 }
    #             )

    #         operations.append(operation)

    #     except Exception as e:

    #         print(f"FAILED UPLOAD: {file_path}")
    #         print(e)

    # -----------------------------
    # UPLOAD BATCH 2
    # -----------------------------

    # for file_path in batch_files:

    #     try:
    #         safe_name = safe_display_name(file_path)
            
    #         # Determine the correct MIME type based on the extension
    #         file_extension = file_path.suffix.lower()
    #         mime_type = MIME_TYPES_MAP.get(file_extension, "application/octet-stream")

    #         print(f"Uploading: {safe_name} ({mime_type})")

    #         # Create temporary ASCII-safe file
    #         with tempfile.TemporaryDirectory() as tmpdir:

    #             temp_path = Path(tmpdir) / safe_name
    #             shutil.copy2(file_path, temp_path)

    #             operation = client.file_search_stores.upload_to_file_search_store(
    #                 file=str(temp_path),
    #                 file_search_store_name=file_search_store.name,
    #                 config={
    #                     "display_name": safe_name,
    #                     "mime_type": mime_type,  # <-- Added this line
    #                 }
    #             )

    #         operations.append(operation)

    #     except Exception as e:

    #         print(f"FAILED UPLOAD: {file_path}")
    #         print(e)

    # -----------------------------
    # UPLOAD BATCH
    # -----------------------------
    
    import zipfile  

    for file_path in batch_files:

        try:
            file_extension = file_path.suffix.lower()
            mime_type = MIME_TYPES_MAP.get(file_extension, "application/xml")
            
            # Generate the initial ASCII-safe name
            safe_name = safe_display_name(file_path)

            with tempfile.TemporaryDirectory() as tmpdir:
                temp_path = Path(tmpdir) / safe_name

                # SPECIAL CASE: Handle MuseScore Compressed files (.mscz)
                if file_extension == ".mscz":
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        # Find the main score file inside the zip
                        mscx_files = [f for f in zip_ref.namelist() if f.endswith('.mscx')]
                        
                        if not mscx_files:
                            raise ValueError(f"No .mscx file found inside archive: {file_path.name}")
                        
                        internal_file = mscx_files[0]
                        
                        # Update safe_name and temp_path for the extracted XML file
                        safe_name = Path(safe_name).with_suffix('.xml').name
                        temp_path = Path(tmpdir) / safe_name
                        
                        with zip_ref.open(internal_file) as source, open(temp_path, 'wb') as target:
                            shutil.copyfileobj(source, target)
                
                # STANDARD CASE: Normal XML, MEI, TXT files
                else:
                    shutil.copy2(file_path, temp_path)

                # UNIFIED PRINT: This will always show exactly what is hitting the API
                print(f"Uploading: {safe_name} ({mime_type})")

                # Send to Gemini File Search Store
                operation = client.file_search_stores.upload_to_file_search_store(
                    file=str(temp_path),
                    file_search_store_name=file_search_store.name,
                    config={
                        "display_name": safe_name,
                        "mime_type": mime_type,
                    }
                )

            operations.append(operation)

        except Exception as e:
            print(f"FAILED UPLOAD: {file_path}")
            print(e)

    # -----------------------------
    # WAIT FOR INDEXING
    # -----------------------------

    print("\nWaiting for indexing...\n")

    all_done = False

    while not all_done:

        all_done = True

        for i, operation in enumerate(operations):

            try:

                if not operation.done:

                    operations[i] = client.operations.get(operation)

                    if not operations[i].done:
                        all_done = False

            except Exception as e:

                print(f"Failed polling operation:")
                print(e)

        if not all_done:
            print("Still indexing...")
            time.sleep(5)

    print(f"\nBatch {batch_index + 1} indexed successfully!")

    # -----------------------------
    # RATE LIMIT PROTECTION
    # -----------------------------

    if batch_index < total_batches - 1:

        print(f"\nSleeping {SLEEP_BETWEEN_BATCHES}s before next batch...\n")
        time.sleep(SLEEP_BETWEEN_BATCHES)

print("\nALL FILES INDEXED!")

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