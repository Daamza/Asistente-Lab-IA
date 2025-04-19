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

# Config
openai.api_key = os.getenv("OPENAI_API_KEY")
SPREADSHEET_NAME = "Turnos_ALIA"
GPT_MODEL = "gpt-4"
app = Flask(__name__)

# Google Sheets
def conectar_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    return client.open(SPREADSHEET_NAME).sheet1

# Guardar datos
def guardar_turno(nombre, tipo, direccion=None, entre_calles=None):
    ahora = datetime.datetime.now()
    sheet = conectar_sheets()
    sheet.append_row([
        nombre,
        tipo,
        direccion or "Sede",
        entre_calles or "-",
        ahora.strftime("%Y-%m-%d"),
        ahora.strftime("%H:%M")
    ])

# OCR
def procesar_imagen_base64(imagen_b64):
    try:
        image_data = base64.b64decode(imagen_b64)
        image = Image.open(io.BytesIO(image_data))
        texto = pytesseract.image_to_string(image)
        return texto if texto.strip() else "No se pudo leer el contenido de la orden médica."
    except Exception as e:
        return f"Error procesando la imagen: {e}"

# Detectar estudios
def dar_indicaciones(texto):
    indicaciones = []
    estudios = {
        "glucemia": "Ayuno de 8 a 12 hs.",
        "colesterol": "Ayuno de 12 hs.",
        "triglicéridos": "Ayuno de 12 hs.",
        "TSH": "No requiere ayuno.",
        "hemograma": "No requiere ayuno.",
        "orina": "Primera orina de la mañana, frasco estéril."
    }
    for clave, indicacion in estudios.items():
        if clave.lower() in texto.lower():
            indicaciones.append(f"{clave.capitalize()}: {indicacion}")
    return "\n".join(indicaciones) if indicaciones else "No se identificaron estudios específicos."

# GPT fallback
def responder_chatgpt(mensaje):
    try:
        response = openai.ChatCompletion.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": "Sos ALIA, un asistente virtual para laboratorio. Respondé en español y de forma clara."},
                {"role": "user", "content": mensaje}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "Hubo un error al consultar con el asistente."

# Webhook principal
@app.route("/", methods=["POST"])
def webhook():
    req = request.get_json()
    intent = req["queryResult"]["intent"]["displayName"]
    params = req["queryResult"].get("parameters", {})
    texto_usuario = req["queryResult"].get("queryText", "")

    if intent == "SaludoInicial":
        return jsonify({"fulfillmentText": "Hola, soy ALIA, tu asistente virtual. ¿Querés atención a domicilio o en nuestra sede?"})

    elif intent == "EleccionDomicilio":
        nombre = params.get("nombre", "Paciente")
        direccion = params.get("direccion", "")
        entre = params.get("entre_calles", "")
        if not direccion or not entre:
            return jsonify({"fulfillmentText": "Por favor indicame tu dirección completa y entre calles para agendar tu turno a domicilio."})
        guardar_turno(nombre, "Domicilio", direccion, entre)
        return jsonify({"fulfillmentText": f"Perfecto, {nombre}. Tu turno a domicilio fue registrado. ¿Tenés una orden médica para compartir como imagen o PDF?"})

    elif intent == "EleccionSede":
        nombre = params.get("nombre", "Paciente")
        guardar_turno(nombre, "Sede")
        return jsonify({"fulfillmentText": "Nuestro horario de atención en sede es de 7:30 a 11:00 hs para extracciones y de 7:30 a 17:00 hs para informes y consultas. ¿Tenés una orden médica para compartir?"})

    elif intent == "EnviarImagenOrden":
        imagen = params.get("imagen_b64", "")
        if not imagen:
            return jsonify({"fulfillmentText": "No se recibió imagen. Por favor, volvé a enviar la orden médica."})
        texto = procesar_imagen_base64(imagen)
        instrucciones = dar_indicaciones(texto)
        return jsonify({"fulfillmentText": f"Leí en tu orden:\n\n{texto}\n\nIndicaciones:\n{instrucciones}"})

    else:
        respuesta = responder_chatgpt(texto_usuario)
        return jsonify({"fulfillmentText": respuesta})

# Prueba directa
@app.route("/test-gpt", methods=["GET"])
def test_gpt():
    try:
        response = openai.ChatCompletion.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": "¿Qué análisis requieren ayuno?"}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error al conectarse con OpenAI: {str(e)}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
