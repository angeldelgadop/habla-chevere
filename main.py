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
client = OpenAI(api_key=os.getenv("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"))

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()

def obtener_feedback_con_gpt(transcripcion, idioma="en"):
    if idioma == "es":
        prompt = f"""
Eres un profesor de español con acento latino (venezolano), que revisa grabaciones habladas de estudiantes extranjeros de nivel A2–B1.

Tu tarea es detectar errores reales de gramática, vocabulario o expresión, y explicarlos de forma clara y amigable. NO ignores errores comunes como:

- "yo sabo" → "yo sé"
- "has escribido" → "has escrito"
- "tú poniste" → "tú pusiste"
- "me recuerdo" → "me acuerdo"
- "haiga" → "haya"

⚠️ INSTRUCCIONES IMPORTANTES:

1. Si el texto es correcto, responde exactamente: ✅ El texto está correcto.  
   ❌ No expliques nada.  
   ❌ No des corrección.  
   ❌ No inventes errores.

2. Si hay errores, sigue este formato estructurado:

🔍 **Error 1**: texto con error  
💡 **Explicación**: por qué está mal  
✅ **Corrección**: forma correcta

(Repite para cada error si hay más de uno)

✍️ **Versión corregida sugerida**: el texto completo corregido

Texto del estudiante:
"{transcripcion}"
"""
    else:
        prompt = f"""
You are a friendly but precise Spanish teacher from Venezuela, reviewing spoken texts from A2–B1 students.

Your job is to detect real grammar, vocabulary, or expression mistakes. DO NOT ignore common learner errors like:

- "yo sabo" → "yo sé"
- "has escribido" → "has escrito"
- "tú poniste" → "tú pusiste"
- "me recuerdo" → "me acuerdo"

⚠️ INSTRUCTIONS:

1. If the sentence is correct, respond **exactly**: ✅ The text is correct.  
   ❌ Do NOT explain.  
   ❌ Do NOT suggest corrections.

2. If there are errors, follow this structure:

🔍 **Error 1**: incorrect phrase  
💡 **Explanation**: what’s wrong  
✅ **Correction**: the correct version

(Repeat for more errors if needed)

✍️ **Suggested corrected version**: full corrected sentence

Student's text:
"{transcripcion}"
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
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
