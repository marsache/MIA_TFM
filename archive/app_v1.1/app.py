from flask import Flask, request, jsonify, send_from_directory
from ollama_manager import OllamaManager

# Crea la aplicación Flask
app = Flask(__name__, static_folder=".", static_url_path="")
manager = OllamaManager(model="qwen3:8b")

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

    # TODO: LLM
    # Ahora mismo sólo copia el mensaje recibido por parte del usuario
    # bot_reply = f"You said: {user_message}"
    historial = [
        {"role": "system", "content": "Eres un guía experto en canciones de la cultura folk iberoamericana."},
        {"role": "user", "content": user_message}
    ]
    bot_reply = manager.chat(historial)

    # Devuelve la respuesta del modelo en formato JSON: { reply: bot_reply }
    json_answer = jsonify({"reply": bot_reply}) 
    return json_answer

if __name__ == "__main__":
    # TODO: una vez terminado, cambiar debug=True
    # debug=True: refresca la página cada vez que hay un cambio
    app.run(debug=True)