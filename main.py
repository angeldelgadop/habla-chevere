from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
import os
import shutil
import subprocess
import uuid
import speech_recognition as sr
from pydub import AudioSegment
from dotenv import load_dotenv
from openai import OpenAI
import traceback

# Cargar API KEY desde .env
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()

def obtener_feedback_con_gpt(transcripcion, idioma="en"):
    if idioma == "es":
        prompt = f"""
Eres un profesor venezolano de español que revisa textos hablados de estudiantes extranjeros (nivel A2–B1). 

Tu tarea es detectar y explicar errores reales de gramática, vocabulario o expresión oral. Sé claro, amable y directo, pero no ignores errores. 

Corrige incluso errores comunes como *"tú poniste"*, que deben decirse *"tú pusiste"*. No inventes errores si el texto está correcto.

⚠️ IMPORTANTE:
- Si el texto está correcto, responde solamente: ✅ El texto está correcto.
- NO incluyas versión corregida si no hay errores.
- Si hay errores, explícalos claramente y da una versión corregida al final.

Texto del estudiante:
"{transcripcion}"

Formato (solo si hay errores):
1. 🔍 Error: ...
   💡 Explicación: ...
   ✅ Corrección: ...
...
✍️ Versión corregida sugerida: ...
"""
    else:
        prompt = f"""
You are a Venezuelan Spanish teacher reviewing spoken texts from foreign students (level A2–B1). 

Your job is to detect and explain real grammar, vocabulary, or expression errors in Spanish. Be clear, kind, and direct — do not ignore common mistakes like *"tú poniste"*, which should be *"tú pusiste"*.

⚠️ IMPORTANT:
- If the text is correct, respond ONLY with: ✅ The text is correct.
- DO NOT give a corrected version if there are no errors.
- If there are errors, explain them clearly and give a corrected version at the end.

Student's text:
"{transcripcion}"

Format (ONLY if errors are found):
1. 🔍 Error: ...
   💡 Explanation: ...
   ✅ Correction: ...
...
✍️ Suggested corrected version: ...
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return response.choices[0].message.content.strip()

@app.post("/upload/")
async def upload_audio(file: UploadFile = File(...), language: str = Form("en")):
    try:
        os.makedirs("uploads", exist_ok=True)
        input_filename = f"uploads/{uuid.uuid4()}_{file.filename}"

        with open(input_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Convertir a WAV si es .webm (video)
        if input_filename.endswith(".webm"):
            audio_path = input_filename.replace(".webm", ".wav")
            command = [
                "ffmpeg", "-y", "-i", input_filename,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                audio_path
            ]
            subprocess.run(command, check=True)
        else:
            audio = AudioSegment.from_file(input_filename)
            audio_path = input_filename + ".wav"
            audio.export(audio_path, format="wav")

        # Transcripción con Google
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
        transcription = recognizer.recognize_google(audio_data, language="es-ES")

        # Feedback con OpenAI (idioma dinámico)
        feedback_text = obtener_feedback_con_gpt(transcription, idioma=language)

        return {
            "filename": file.filename,
            "transcription": transcription,
            "feedback": feedback_text
        }

    except subprocess.CalledProcessError:
        return {"error": "⚠️ Error converting video. Make sure ffmpeg is installed."}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
