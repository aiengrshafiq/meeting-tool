# intelligence_processor/brain/classifier.py

import os
import json
import logging
from openai import AzureOpenAI

# --- Configuration ---
# This is the new, correct way to initialize the client for openai v1.0+
try:
    client = AzureOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),  
        api_version="2023-07-01-preview",
        azure_endpoint=os.getenv("OPENAI_ENDPOINT")
    )
    # This is the name of the model you deployed in the Azure OpenAI studio
    MODEL_DEPLOYMENT_NAME = "gpt4-classifier" 
except Exception as e:
    logging.error(f"Failed to initialize OpenAI client: {e}")
    raise

def classify_transcript(transcript_text: str, participants: list) -> dict:
    """
    Uses Azure OpenAI (GPT-4) to classify a meeting transcript.
    """
    logging.info("-> Starting REAL transcript classification with OpenAI...")
    
    system_prompt = """
    You are an AI assistant for Ecstasy Holdings. Your task is to analyze the following meeting transcript and classify it.
    Analyze the content, keywords, and participant roles to make your determination.
    Return ONLY a valid JSON object with the following schema and nothing else:
    {
      "subsidiary": "...",
      "department": "...",
      "meeting_type": "...",
      "meeting_subtype": "...",
      "key_decisions": ["...", "..."],
      "tags": ["...", "..."]
    }
    """
    
    user_prompt = f"""
    **Transcript:**
    "{transcript_text}"

    **Participants:**
    {', '.join(participants)}
    """
    
    try:
        # THE FIX: This is the new syntax for making the API call.
        response = client.chat.completions.create(
            model=MODEL_DEPLOYMENT_NAME, # The parameter is now 'model' instead of 'engine'
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0,
            max_tokens=500
        )
        
        result_text = response.choices[0].message.content
        classification_result = json.loads(result_text)
        
        logging.info(f"-> OpenAI classification successful: {classification_result}")
        return classification_result
        
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from OpenAI response: {e}")
        logging.error(f"Raw response text: {result_text}")
        return {"error": "Failed to parse OpenAI response"}
    except Exception as e:
        logging.error(f"An unexpected error occurred with OpenAI: {e}")
        return {"error": str(e)}