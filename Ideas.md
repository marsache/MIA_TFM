# Añadir a la memoria
## Librerías de Python utilizadas
- [Flask](https://flask.palletsprojects.com/en/stable/): crea la aplicación web
## Secciones
- Methods and data (en qué máquina se corre el modelo, qué modelo se utiliza...)

## Referencias
- [Ollama API](https://docs.ollama.com/)

# Cambiar
- Nombre del script load_csv.py

# Ideas
- Reconocimiento de entidades nombradas

# Notas
- app_v1.1: embeddings and FAISS
    - Hipótesis de mal funcionamiento: k = 3 es un valor demasiado pequeño. Si una canción relevante no está en el top 3 por similitud vectorial, desaparece.
- app_v1.2: entire CSV in RAG
- app_v1.3: 