import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def summarize_transcript(transcript_text: str) -> str:
    """
    Analyzes a transcript and returns a structured summary, key decisions, and tags as a JSON string.
    This also generates a human-readable summary for the email.
    """
    try:
        # This prompt is designed to force the model to return a JSON object
        prompt = f"""
You are an expert meeting analyst AI. Your task is to analyze the following meeting transcript and extract structured data.
The participants' roles and subsidiaries may be mentioned in the text. Infer the correct values.

**Transcript:**
\"\"\"
{transcript_text}
\"\"\"

**Instructions:**
Return a single, valid JSON object with the following keys. Do not include any text or formatting outside of this JSON object.
- "subsidiary": (string) The subsidiary mentioned (e.g., "Metamorphic", "6T3 Media", "Legal").
- "department": (string) The department involved (e.g., "Ops", "Legal", "Sales", "Creative").
- "meeting_type": (string) The main type of meeting (e.g., "Internal", "Client", "Coaching", "Compliance").
- "meeting_subtype": (string) The specific subtype (e.g., "Strategy", "Daily Standup", "Intake", "Performance Handling").
- "key_decisions": (array of strings) A list of specific decisions that were made.
- "tags": (array of strings) A list of relevant keywords or hashtags (e.g., "#Training", "#ClientEscalation").
- "human_summary": (string) A concise, human-readable summary in bullet points and action items, suitable for an email.
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an AI assistant that only responds with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000,
            # THE FIX: Force the model to output a JSON object
            response_format={"type": "json_object"}
        )

        structured_result_str = response.choices[0].message.content
        
        # We now have a JSON string. We can parse it to get the human-readable part.
        try:
            structured_data = json.loads(structured_result_str)
            human_summary = structured_data.get("human_summary", "Summary could not be generated.")
            print("[✅ Structured summary and classification generated]")
            # For the email, we only need the human-readable part.
            # The full JSON will be used by the Phase 2 function later.
            return human_summary
        except json.JSONDecodeError:
            logging.error("Failed to decode JSON from OpenAI response.")
            # Fallback to returning the raw string if it's not valid JSON
            return structured_result_str

    except Exception as e:
        print(f"[❌ Error] Summary generation failed: {str(e)}")
        return "Summary generation failed."

