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

        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
            tmp.write(response.content)
            tmp.flush()
            
            print(f"[🎙️ Transcribing with Speaker Diarization] {tmp.name}")
            with open(tmp.name, "rb") as audio_file:
                # THE FIX: Change response format and enable speaker labels
                transcript_response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json", # Get detailed data
                    timestamp_granularities=["word"],
                    diarize=True # Enable speaker identification
                )

        # Process the structured response into a readable format
        full_transcript = ""
        if transcript_response.words:
            current_speaker = None
            for word in transcript_response.words:
                speaker_label = f"Speaker {word.speaker}"
                if current_speaker != speaker_label:
                    full_transcript += f"\n\n**{speaker_label}:**"
                    current_speaker = speaker_label
                full_transcript += f" {word.word}"
        else:
            # Fallback for older models or if diarization fails
            full_transcript = transcript_response.text

        print("[✅ Transcription complete]")
        return full_transcript.strip()

    except Exception as e:
        print(f"[❌ Error] Transcription failed: {str(e)}")
        # Print the full traceback for better debugging
        import traceback
        traceback.print_exc()
        return f"Transcription failed: {e}"
    finally:
        if 'tmp' in locals() and os.path.exists(tmp.name):
            os.remove(tmp.name)