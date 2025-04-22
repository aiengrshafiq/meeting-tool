import openai
import os
from dotenv import load_dotenv
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def summarize_transcript(transcript_text: str, language: str = "english") -> str:
    try:
        prompt = f"""
You are an AI assistant. Summarize the following meeting transcript into concise bullet points and action items. 
Focus on decisions made, follow-up tasks, and key discussion points.
Write in formal tone in {language.title()}:

Transcript:
\"\"\"
{transcript_text}
\"\"\"
"""

        response = openai.ChatCompletion.create(
            model="gpt-4",  # Or "gpt-3.5-turbo" if cost/speed preferred
            messages=[
                {"role": "system", "content": "You are a helpful meeting assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=800
        )

        summary = response.choices[0].message.content.strip()
        print("[✅ Summary generated]")
        return summary

    except Exception as e:
        print(f"[❌ Error] Summary generation failed: {str(e)}")
        return "Summary generation failed."
