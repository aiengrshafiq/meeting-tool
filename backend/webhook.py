from fastapi import APIRouter, Header, Request, HTTPException
import os
import json
import tempfile
import httpx
from pathlib import Path
from dotenv import load_dotenv
import psycopg2  # ✅ for PostgreSQL

from common.blob_storage import upload_file_to_blob
from common.transcriber import transcribe_from_blob_url
from common.summarizer import summarize_transcript
from common.emailer import send_summary_email

load_dotenv()
router = APIRouter()

ZOOM_WEBHOOK_SECRET = os.getenv("ZOOM_WEBHOOK_SECRET", "myzoomsecret")
POSTGRES_URL = os.getenv("POSTGRES_URL")

def load_participants(meeting_id):
    path = Path(f"data/participants_{meeting_id}.json")
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return []

def save_meeting_to_postgres(meeting_id, host_email, summary, transcript):
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meeting_logs (
                meeting_id VARCHAR PRIMARY KEY,
                host_email VARCHAR,
                summary TEXT,
                transcript TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO meeting_logs (meeting_id, host_email, summary, transcript)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (meeting_id) DO NOTHING
        """, (meeting_id, host_email, summary, transcript))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[✅ Saved to PostgreSQL] Meeting: {meeting_id}")
    except Exception as e:
        print(f"[❌ PostgreSQL Error] {e}")

@router.post("/api/zoom/webhook")
async def zoom_webhook(request: Request, x_zoom_signature: str = Header(None)):
    expected_token = os.getenv("ZOOM_WEBHOOK_SECRET", "your_webhook_verification_token")
    print(f"Parameters Received = {expected_token} and {x_zoom_signature}")
    if x_zoom_signature != expected_token:
        print(f"[❌ Invalid Signature] Received: {x_zoom_signature}")
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    print("[✅ Zoom Webhook Verified]", body)

    # Handle events here like recording.completed
    return {"status": "ok"}
