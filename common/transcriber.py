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

        # Use a temporary file to save the audio content
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        
        print(f"[🎙️ Transcribing] {tmp_path}")
        with open(tmp_path, "rb") as audio_file:
            # THE FIX: Explicitly tell the model the language is English.
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text",
                language="en"  # <-- THIS IS THE CRITICAL FIX
            )

        print("[✅ Transcription complete]")
        return transcript_response

    except Exception as e:
        print(f"[❌ Error] Transcription failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Transcription failed: {e}"
    finally:
        # Ensure the temporary file is always cleaned up
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)
