# intelligence_processor/brain/vectorizer.py
import os
import logging
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

# --- Configuration ---
INDEX_NAME = "meeting-brain-index"
AI_SEARCH_ENDPOINT = os.getenv("AI_SEARCH_ENDPOINT")
AI_SEARCH_KEY = os.getenv("AI_SEARCH_KEY")

# Re-use the OpenAI client for creating embeddings
try:
    openai_client = AzureOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),  
        api_version="2023-07-01-preview",
        azure_endpoint=os.getenv("OPENAI_ENDPOINT")
    )
    # The name of your embedding model deployment
    EMBEDDING_MODEL_NAME = "text-embedding-ada-002"
except Exception as e:
    logging.error(f"Failed to initialize OpenAI client for embeddings: {e}")
    raise

def get_embedding(text: str) -> list[float]:
    """Generates a vector embedding for the given text."""
    response = openai_client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL_NAME
    )
    return response.data[0].embedding

def vectorize_and_save(transcript_text: str, classification_result: dict, meeting_id: str, meeting_date: str):
    """
    Creates vector embeddings and saves the data to Azure AI Search.
    """
    logging.info(f"-> Starting vectorization for meeting {meeting_id}...")

    try:
        # 1. Generate the vector embedding for the transcript
        embedding = get_embedding(transcript_text)
        
        # 2. Prepare the document to be uploaded
        document = {
            "id": meeting_id,
            "meeting_date": meeting_date,
            "transcript_content": transcript_text,
            "summary_content": "Summary will be added later.", # Placeholder for now
            "content_vector": embedding,
            "subsidiary": classification_result.get("subsidiary"),
            "department": classification_result.get("department"),
            "participants": ["Syed Owais", "Rain"], # Placeholder
            "tags": classification_result.get("tags", [])
        }
        
        # 3. Upload the document to Azure AI Search
        search_client = SearchClient(
            endpoint=AI_SEARCH_ENDPOINT,
            index_name=INDEX_NAME,
            credential=AzureKeyCredential(AI_SEARCH_KEY)
        )
        
        result = search_client.upload_documents(documents=[document])
        
        if result[0].succeeded:
            logging.info(f"-> Successfully vectorized and saved document id '{meeting_id}' to Azure AI Search.")
        else:
            logging.error(f"Failed to save document id '{meeting_id}': {result[0].error_message}")
            return False

    except Exception as e:
        logging.error(f"An error occurred during vectorization: {e}", exc_info=True)
        return False
        
    return True