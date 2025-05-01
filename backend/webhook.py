from fastapi import APIRouter, Header, Request, HTTPException
import os
import json
import tempfile
import httpx
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from common.blob_storage import upload_file_to_blob
from common.transcriber import transcribe_from_blob_url
from common.summarizer import summarize_transcript
from common.emailer import send_summary_email
from hmac import HMAC
import hashlib

load_dotenv()
router = APIRouter()
ZOOM_WEBHOOK_SECRET = os.getenv("ZOOM_WEBHOOK_SECRET", "your_webhook_verification_token")
print("your webhook secret is",ZOOM_WEBHOOK_SECRET)
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
async def zoom_webhook(request: Request):
    body = await request.body()
    payload = json.loads(body)
    event = payload.get("event")

    if event == "endpoint.url_validation":
        plain_token = payload["payload"]["plainToken"]
        encrypted_token = HMAC(ZOOM_WEBHOOK_SECRET.encode(), plain_token.encode(), digestmod=hashlib.sha256).hexdigest()
        print("[🔒 URL validation succeeded]")
        return {
            "plainToken": plain_token,
            "encryptedToken": encrypted_token
        }

    if event != "recording.completed":
        raise HTTPException(status_code=400, detail="Unsupported event type")

    recording = payload["payload"]["object"]
    meeting_id = str(recording["id"])
    download_files = recording.get("recording_files", [])
    host_email = recording.get("host_email")
    uploaded_files = []

    for file in download_files:
        if file["file_type"] not in ["MP4", "M4A"]:
            continue

        download_url = file["download_url"]
        filename = f"{file['file_type'].lower()}_{file['id']}.{file['file_type'].lower()}"
        full_url = f"{download_url}?access_token={os.getenv('ZOOM_OAUTH_TOKEN')}"

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            async with httpx.AsyncClient() as client:
                r = await client.get(full_url)
                r.raise_for_status()
                tmp.write(r.content)

            blob_url = upload_file_to_blob(meeting_id, tmp.name, filename)
            uploaded_files.append(blob_url)

            transcript = transcribe_from_blob_url(blob_url)
            if not transcript:
                continue

            summary = summarize_transcript(transcript)
            recipients = load_participants(meeting_id)
            if not recipients:
                recipients = [host_email]

            for email in recipients:
                send_summary_email(
                    to_email=email,
                    to_name="Participant",
                    subject=f"📝 Summary for Zoom Meeting {meeting_id}",
                    summary_text=summary,
                    transcript_text=transcript
                )

            save_meeting_to_postgres(meeting_id, host_email, summary, transcript)

    return {
        "status": "recordings uploaded & summary sent",
        "meeting_id": meeting_id,
        "host": host_email,
        "recipients": recipients,
        "files": uploaded_files
    }
