// El form del HTML que contiene la entrada de texto y el botón para enviar el mensaje
const form = document.getElementById("chatForm");
// El input del HTML que contiene la entrada de texto
const input = document.getElementById("input");
// El button del HTML que contiene el botón para enviar el mensaje
const messages = document.getElementById("messages");

// Agrega un evento para "escuchar" al botón de envío de mensaje
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!input.value.trim()) return; // Evita enviar mensajes vacíos

  // Procesa el mensaje del usuario, muestra el mensaje por pantalla y vacía la entrada de texto
  const userText = input.value;
  addMessage(userText, "user");
  input.value = "";

  // Envía la petición POST al backend de Flask
  const response = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: userText })
  });

  const data = await response.json(); // Convierte la respuesta a formato JSON
  addMessage(data.reply, "bot"); // Añade la respuesta al chat como un mensaje nuevo
});

/**
 * Crea un mensaje y lo muestra en la interfaz de chat
 * 
 * @param {string} text - El texto del mensaje
 * @param {string} role - El rol de la entidad que envía el mensaje. Posibles valores: "user", "bot"
 */
function addMessage(text, role) {
  const msg = document.createElement("div"); // Nuevo elemento div (HTMLDivElement)
  msg.className = `message ${role}`; // "message user", "message bot"
  msg.textContent = text;
  messages.appendChild(msg); // Añade un mensaje al div de mensajes
  messages.scrollTop = messages.scrollHeight; // El chat automáticamente hace scroll hasta el mensaje actual
}
