import openai
import os
import requests
import tempfile
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def transcribe_from_blob_url(blob_url):
    try:
        print(f"[⬇️ Downloading audio from Blob] {blob_url}")
        response = requests.get(blob_url)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(response.content)
            tmp.flush()

            print(f"[🎙️ Transcribing] {tmp.name}")
            with open(tmp.name, "rb") as audio_file:
                transcript_response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )

            print("[✅ Transcription complete]")
            return transcript_response

    except Exception as e:
        print(f"[❌ Error] Transcription failed: {str(e)}")
        return None
