import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def summarize_transcript(transcript_text: str) -> str:
    """
    Analyzes a transcript and returns a human-readable summary for email.
    It now handles cases where transcription might have failed.
    """
    if not transcript_text or "Transcription failed" in transcript_text:
        print("[⚠️ Warning] Transcription was empty or failed. Skipping summary.")
        return "Summary could not be generated because the transcription failed."

    try:
        # This prompt is designed for a clear, human-readable email summary.
        prompt = f"""
You are an AI assistant. Summarize the following meeting transcript into concise bullet points and action items.
Focus on decisions made, follow-up tasks, and key discussion points.

Transcript:
\"\"\"
{transcript_text}
\"\"\"

Summary:
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful meeting assistant that creates clear, concise summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=800
            # THE FIX: Removed the unsupported 'response_format' argument.
        )

        summary = response.choices[0].message.content.strip()
        print("[✅ Summary generated]")
        return summary

    except Exception as e:
        print(f"[❌ Error] Summary generation failed: {str(e)}")
        return "Summary generation failed."