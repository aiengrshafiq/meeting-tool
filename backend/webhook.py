from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import os, json, hmac, hashlib, tempfile
import httpx, psycopg2
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

from common.blob_storage import upload_file_to_blob
from common.transcriber import transcribe_from_blob_url
from common.summarizer import summarize_transcript
from common.emailer import send_summary_email
import traceback

load_dotenv()
router = APIRouter()

ZOOM_WEBHOOK_SECRET = os.getenv("ZOOM_WEBHOOK_SECRET")
POSTGRES_URL = os.getenv("POSTGRES_URL")

if not ZOOM_WEBHOOK_SECRET or not POSTGRES_URL:
    raise ValueError("Missing required environment variables")

# --- PostgreSQL helpers for deduplication ---
def is_meeting_processed(meeting_id: str):
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meeting_processing_log (
                meeting_id VARCHAR PRIMARY KEY,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("SELECT meeting_id FROM meeting_processing_log WHERE meeting_id = %s", (meeting_id,))
        exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        return exists
    except Exception as e:
        print(f"[❌ DB Check Error] {e}")
        return False

def mark_meeting_as_processed(meeting_id: str):
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO meeting_processing_log (meeting_id, processed_at)
            VALUES (%s, %s)
            ON CONFLICT (meeting_id) DO NOTHING
        """, (meeting_id, datetime.utcnow()))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[📌 Marked as processed] Meeting {meeting_id}")
    except Exception as e:
        print(f"[❌ DB Write Error] {e}")

def load_participants(meeting_id):
    path = Path(f"data/participants_{meeting_id}.json")
    if path.exists():
        with open(path, "r") as f:
            data = json.load(f)
            return (
                data.get("emails", []),
                data.get("created_by_email", "unknown"),
                data.get("form_host_email", None)  # ✅ NEW
            )
    return [], "unknown", None

def save_meeting_to_postgres(meeting_id, host_email, summary, transcript, recipients, meeting_time, created_by_email,recording_full_url):
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meeting_logs (
                meeting_id VARCHAR PRIMARY KEY,
                host_email VARCHAR,
                summary TEXT,
                transcript TEXT,
                recipients TEXT,
                meeting_time TIMESTAMP,
                created_by_email VARCHAR,
                recording_full_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT INTO meeting_logs (eeting_id, host_email, summary, transcript,recipients, meeting_time, created_by_email,recording_full_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (meeting_id) DO NOTHING
        """, (
            meeting_id,
            host_email,
            summary,
            transcript,
            json.dumps(recipients),
            meeting_time,
            created_by_email,
            recording_full_url

        ))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[📝 Saved to DB] host_email={host_email}, created_by={created_by_email}")
        print(f"[✅ Saved to PostgreSQL] Meeting: {meeting_id}")
    except Exception as e:
        print(f"[❌ PostgreSQL Error] {e}")

@router.post("/api/zoom/webhook")
async def zoom_webhook(request: Request):
    try:
        body = await request.body()
        payload = json.loads(body)
        event = payload.get("event")
        print(f"[🧩 EVENT RECEIVED] {event}")
        print(f"[📦 PAYLOAD] {json.dumps(payload, indent=2)}")

        # 🔒 Zoom webhook URL validation
        if event == "endpoint.url_validation":
            plain_token = payload["payload"]["plainToken"]
            encrypted_token = hmac.new(
                ZOOM_WEBHOOK_SECRET.encode(),
                plain_token.encode(),
                hashlib.sha256
            ).hexdigest()
            return JSONResponse(content={
                "plainToken": plain_token,
                "encryptedToken": encrypted_token
            })

        # 🎯 Consolidate all relevant events
        if event not in ["recording.completed", "meeting.ended"]:
            print(f"[⚠️ Ignored event] {event}")
            return JSONResponse(content={"status": "ignored"}, status_code=200)

        recording = payload.get("payload", {}).get("object", {})
        meeting_id = str(recording.get("id"))
        meeting_time = recording.get("start_time")
        download_files = recording.get("recording_files", [])
        host_email = recording.get("host_email")

        # ✅ Deduplication check
        if is_meeting_processed(meeting_id):
            print(f"[🛑 Already processed] Skipping meeting {meeting_id}")
            return JSONResponse(content={"status": "duplicate skipped"}, status_code=200)

        uploaded_files = []

        for file in download_files:
            if file["file_type"] not in ["MP4", "M4A"]:
                continue

            download_url = file["download_url"]
            filename = f"{file['file_type'].lower()}_{file['id']}.{file['file_type'].lower()}"
            download_token = payload.get("download_token")
            if not download_token:
                raise ValueError("Zoom download_token is missing")
            full_url = f"{download_url}?access_token={download_token}"

            recording_full_url = full_url

            tmp = tempfile.NamedTemporaryFile(delete=False)
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
                    r = await client.get(full_url, headers={"User-Agent": "Zoom-Webhook-Bot"})
                    r.raise_for_status()
                    tmp.write(r.content)

                blob_url = upload_file_to_blob(meeting_id, tmp.name, filename)
                uploaded_files.append(blob_url)

                transcript = transcribe_from_blob_url(blob_url)
                summary = summarize_transcript(transcript)
                recipients, created_by_email, form_host_email = load_participants(meeting_id)
                if not recipients:
                    recipients = [host_email]

                if form_host_email and form_host_email not in recipients:
                    recipients.append(form_host_email)

                for email in recipients:
                    send_summary_email(
                        to_email=email,
                        to_name="Participant",
                        subject=f"📝 Summary for Zoom Meeting {meeting_id}",
                        summary_text=summary,
                        transcript_text=transcript
                    )

                

                effective_host_email = form_host_email or host_email
                save_meeting_to_postgres(meeting_id, effective_host_email, summary, transcript, recipients, meeting_time,created_by_email,recording_full_url)
                mark_meeting_as_processed(meeting_id)

            finally:
                tmp.close()
                os.remove(tmp.name)

        return JSONResponse({
            "status": "processed",
            "meeting_id": meeting_id,
            "files_uploaded": uploaded_files
        })

    except Exception as e:
        print(f"[❌ Top-level Error] {e}")
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
