
import os
import base64
import datetime
import io
import openai
from flask import Flask, request, jsonify
from PIL import Image
import pytesseract
import gspread
from oauth2client.service_account import ServiceAccountCredentials

openai.api_key = "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"
SPREADSHEET_NAME = "Turnos_Laboratorio"
GPT_MODEL = "gpt-3.5-turbo"
app = Flask(__name__)

def conectar_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    return client.open(SPREADSHEET_NAME).sheet1

def agendar_turno(nombre):
    ahora = datetime.datetime.now()
    if ahora.hour < 7 or ahora.hour > 11 or ahora.weekday() >= 6:
        return "El horario de atención es de lunes a sábado, de 7:00 a 11:00 hs."
    sheet = conectar_sheets()
    sheet.append_row([nombre, ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M")])
    return f"Turno registrado para {nombre} el {ahora.strftime('%d/%m/%Y a las %H:%M')}."

def procesar_imagen_base64(imagen_b64):
    try:
        image_data = base64.b64decode(imagen_b64)
        image = Image.open(io.BytesIO(image_data))
        texto = pytesseract.image_to_string(image)
        return texto if texto.strip() else "No se pudo leer el contenido de la orden médica."
    except Exception as e:
        return f"Error procesando la imagen: {e}"

def responder_chatgpt(mensaje):
    try:
        response = openai.ChatCompletion.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": "Sos un asistente digital para un laboratorio de análisis clínicos. Responde en español y de forma clara."},
                {"role": "user", "content": mensaje}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error al consultar con ChatGPT: {str(e)}"

@app.route("/", methods=["POST"])
def webhook():
    req = request.get_json()
    intent = req["queryResult"]["intent"]["displayName"]
    params = req["queryResult"].get("parameters", {})
    texto_usuario = req["queryResult"].get("queryText", "")

    if intent == "Saludo":
        return jsonify({"fulfillmentText": "Hola, ¿en qué puedo ayudarte hoy con tus análisis?"})
    elif intent == "PedirTurno":
        nombre = params.get("nombre", "Paciente")
        mensaje = agendar_turno(nombre)
        return jsonify({"fulfillmentText": mensaje})
    elif intent == "EnviarImagenOrden":
        imagen = params.get("imagen_b64", "")
        mensaje = procesar_imagen_base64(imagen) if imagen else "No se recibió imagen para procesar."
        return jsonify({"fulfillmentText": mensaje})
    elif intent == "ConsultarEstudios":
        return jsonify({"fulfillmentText": "Podés enviarme tu orden médica y te confirmo los estudios que incluye."})
    elif intent == "Ubicacion":
        return jsonify({"fulfillmentText": "El laboratorio se encuentra en Av. Siempreviva 742, Buenos Aires."})
    elif intent == "Agradecimiento":
        return jsonify({"fulfillmentText": "¡Gracias a vos! Estoy para ayudarte cuando lo necesites."})
    elif intent == "AyudaHumana":
        return jsonify({"fulfillmentText": "Enseguida te derivo con un operador humano."})
    else:
        respuesta = responder_chatgpt(texto_usuario)
        return jsonify({"fulfillmentText": respuesta})

@app.route("/test-gpt", methods=["GET"])
def test_gpt():
    try:
        response = openai.ChatCompletion.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": "¿Qué estudios requieren estar en ayunas?"}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error al conectarse con OpenAI: {str(e)}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
