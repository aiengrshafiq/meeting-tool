from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import os, json, hmac, hashlib, base64, tempfile
import httpx
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

from common.blob_storage import upload_file_to_blob
from common.transcriber import transcribe_from_blob_url
from common.summarizer import summarize_transcript
from common.emailer import send_summary_email

load_dotenv()
router = APIRouter()

ZOOM_WEBHOOK_SECRET = os.getenv("ZOOM_WEBHOOK_SECRET")
if not ZOOM_WEBHOOK_SECRET:
    raise ValueError("ZOOM_WEBHOOK_SECRET is not set in environment")

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
    try:
        body = await request.body()
        payload = json.loads(body)

        event = payload.get("event")
        print(f"[🧩 EVENT RECEIVED] {event}")
        print(f"[📦 PAYLOAD] {json.dumps(payload, indent=2)}")

        
         # ✅ Handle Zoom URL Validation
        if event == "endpoint.url_validation":
            plain_token = payload["payload"]["plainToken"]
            encrypted_token = hmac.new(
                ZOOM_WEBHOOK_SECRET.encode(),
                plain_token.encode(),
                hashlib.sha256
            ).hexdigest()
            print("🔒 URL validation succeeded")
            return JSONResponse(content={
                "plainToken": plain_token,
                "encryptedToken": encrypted_token
            })

        # ✅ Ignore unsupported events
        if event not in ["recording.completed", "recording.completed_all", "recording.stopped"]:
            print(f"[⚠️ Ignored event] {event}")
            return JSONResponse(content={"status": "ignored"}, status_code=200)

        recording = payload.get("payload", {}).get("object", {})
        meeting_id = str(recording.get("id"))
        download_files = recording.get("recording_files", [])
        host_email = recording.get("host_email")
        uploaded_files = []

        print(f"[📼 Stopped Recording] Meeting ID: {meeting_id}, Host: {host_email}")
        print(f"[📁 Files to process] {len(download_files)}")

        for file in download_files:
            if file["file_type"] not in ["MP4", "M4A"]:
                file_type = file["file_type"]
                print(f"[⚠️ Ignored File Type] {file_type}")
                continue

            download_url = file["download_url"]
            filename = f"{file['file_type'].lower()}_{file['id']}.{file['file_type'].lower()}"

            download_token = payload.get("download_token")
            if not download_token:
                raise ValueError("Zoom download_token is missing from webhook payload")
            full_url = f"{download_url}?access_token={download_token}"

            tmp = tempfile.NamedTemporaryFile(delete=False)
            try:
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    try:
                        r = await client.get(full_url)
                        r.raise_for_status()
                    except httpx.HTTPStatusError as e:
                        print(f"[❌ Download Failed] Status: {e.response.status_code}, URL: {full_url}")
                        raise
                    tmp.write(r.content)

                print(f"[⬆️ Uploading to Blob] {filename}")
                blob_url = upload_file_to_blob(meeting_id, tmp.name, filename)
                uploaded_files.append(blob_url)

                transcript = transcribe_from_blob_url(blob_url)
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

            except Exception as e:
                print(f"[❌ Error Processing File] {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})
            finally:
                tmp.close()
                os.remove(tmp.name)

        return JSONResponse({
            "status": "processed via recording.stopped",
            "meeting_id": meeting_id,
            "files_uploaded": uploaded_files
        })

    except Exception as e:
        print(f"[❌ Top-level Error] {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
