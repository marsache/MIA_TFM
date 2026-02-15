from flask import Flask, request, jsonify, send_from_directory

# Crea la aplicación Flask
app = Flask(__name__, static_folder=".", static_url_path="")

# Ruta para ejecutar el archivo index.html cuando se accede a localhost
@app.route("/")
def index(): # Ejecuta el archivo index.html
    return send_from_directory(".", "index.html")

# Recibe peticiones POST
@app.route("/chat", methods=["POST"])
def chat():
    # Se recibe lo que envió el navegador: { message: userText }
    # Vuelve a pasarse a formato JSON para procesarlo con más facilidad
    data = request.json # request: objeto que representa la petición http al servidor por parte del navegador
    user_message = data.get("message", "")

    # TODO: LLM
    # Ahora mismo sólo copia el mensaje recibido por parte del usuario
    bot_reply = f"You said: {user_message}"

    # Devuelve la respuesta del modelo en formato JSON: { reply: bot_reply }
    return jsonify({"reply": bot_reply})

if __name__ == "__main__":
    # TODO: una vez terminado, cambiar debug=True
    # debug=True: refresca la página cada vez que hay un cambio
    app.run(debug=True)


# LLM

# from openai import OpenAI
# client = OpenAI()

# response = client.chat.completions.create(
#     model="gpt-4o-mini",
#     messages=[{"role": "user", "content": user_message}]
# )

# bot_reply = response.choices[0].message.content
