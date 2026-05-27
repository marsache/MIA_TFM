from flask import Flask, request, jsonify, send_from_directory
from rag_pipeline import build_rag_pipeline, run_rag_with_tools

# Crea la aplicación Flask
app = Flask(__name__, static_folder=".", static_url_path="")
rag_pipeline = build_rag_pipeline()

# Ruta para ejecutar el archivo index.html cuando se accede a localhost
@app.route("/")
def index(): # Ejecuta el archivo index.html
    return send_from_directory(".", "index.html")

# Recibe peticiones POST
@app.route("/chat", methods=["POST"]) # endpoint
def chat():
    # Se recibe lo que envió el navegador: { message: userText }
    # Vuelve a pasarse a formato JSON para procesarlo con más facilidad
    data = request.json # request: objeto que representa la petición http al servidor por parte del navegador
    user_message = data.get("message", "")

    try:
        #bot_reply = rag_pipeline.invoke(user_message)
        bot_reply = run_rag_with_tools(rag_pipeline, user_message)
    except Exception as e:
        bot_reply = f"Error: {str(e)}"

    return jsonify({"reply": bot_reply})

if __name__ == "__main__":
    # TODO: una vez terminado, cambiar debug=True
    # debug=True: refresca la página cada vez que hay un cambio
    app.run(debug=True)