# Sistema híbrido de análisis musical y modelos de lenguaje para la recuperación de información de canciones populares iberoamericanas

## Estructura del proyecto
```text
.
├── datasets/
├── gemini_basic_local_dataset/
│   ├── multi_doc_rag_example_w_upload.py
│   ├── multi_doc_rag_example.py
│   └── pyproject.toml
├── ollama_sqlite/
│   ├── add_songs_to_db.py
│   ├── corpus_musical.db
│   ├── create_db.py
│   ├── db_tools.py
│   ├── info_columnas.py
│   ├── mcp_client.py
│   ├── mcp_server.py
│   ├── web_frontend.py
│   └── pyproject.toml
├── pruebas/
│   ├── rag_local/
│   │   ├── consultar_rag.py
│   │   └── indexar_partituras.py
│   ├── sqlite_gemini/
│   │   ├── mcp_client.py
│   │   └── mcp_server.py
│   └── pyproject.toml
└── README.md
```

## Requisitos
El archivo ```pyproject.toml``` de cada directorio contiene los requisitos específicos de cada implementación.  
Para ejecutar los proyectos en los que se usa la API de Gemini, debe añadirse previamente una API Key de Gemini:  
```$env:GEMINI_API_KEY="your_api_key"```  
Para ejecutar los proyectos que utilizan Ollama localmente, deben instalarse los modelos locales correspondientes:  
```"sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"``` y ```"llama3.1:8b"``` 

## Implementaciones disponibles
| Implementación | Directorio | Ejecución |
|---|---|---|
| Implementación de RAG con Gemini File Search | gemini_basic_local_dataset | python gemini_basic_local_dataset/multi_doc_rag_example_w_upload.py # Por primera vez, para proporcionar el corpus <br> python gemini_basic_local_dataset/multi_doc_rag_example.py # Siempre que se quiera utilizar el chat |
| Implementación de arquitectura híbrida basada en MCP y SQLite local | ollama_sqlite | python ollama_sqlite/create_db.py # Por primera vez, para crear la base de datos <br> python ollama_sqlite/add_songs_to_db.py # Para completar la base de datos ¡PRECAUCIÓN: TARDA DEMASIADO, SE RECOMIENDA UTILIZAR LA BASE DE DATOS YA GENERADA! <br> python ollama_sqlite/mcp_client.py # Siempre que se quiera utilizar el chat |
| Implementación de un sistema RAG básico con modelo local | pruebas/rag_local | python pruebas/rag_local/indexar_partituras.py # Por primera vez <br> python pruebas/rag_local/consultar_rag.py # Siempre que se quiera utilizar el chat |
| Implementación de arquitectura híbrida basada en MCP y SQLite con Gemini | pruebas/sqlite_gemini | python pruebas/sqlite_gemini/mcp_client.py |