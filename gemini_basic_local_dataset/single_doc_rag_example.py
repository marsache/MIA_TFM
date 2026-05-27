from google import genai
from google.genai import types
import time

client = genai.Client()

# Create the File Search store with an optional display name
file_search_store = client.file_search_stores.create(config={'display_name': 'your-fileSearchStore-name'})

# Upload and import a file into the File Search store, supply a file name which will be visible in citations
operation = client.file_search_stores.upload_to_file_search_store(
  #file='35_adios_rosina_adios_clavel.xml',
  #file='568.mscz',
  file='CO-1935-00-LL-03570_updated.mei',
  file_search_store_name=file_search_store.name,
  config={
        'display_name' : 'display-file-name',
        'mime_type': 'application/xml'
  }
)

# Wait until import is complete
while not operation.done:
    time.sleep(5)
    operation = client.operations.get(operation)

# Ask a question about the file
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="""Can you tell me about the song?""",
    config=types.GenerateContentConfig(
        tools=[
            types.Tool(
                file_search=types.FileSearch(
                    file_search_store_names=[file_search_store.name]
                )
            )
        ]
    )
)

print(response.text)