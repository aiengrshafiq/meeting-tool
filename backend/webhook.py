# backend/webhook.py
from fastapi import APIRouter, Request, Depends, Response
from sqlalchemy.orm import Session
import os, json, hmac, hashlib, tempfile, httpx, traceback
from pathlib import Path
from datetime import datetime

# NEW IMPORT FOR PHASE 2 TRIGGER
from azure.storage.blob import BlobServiceClient
# NEW IMPORT TO HANDLE A COMMON WEBHOOK ISSUE
from starlette.requests import ClientDisconnect

# REFACTOR: Import models and db session
from models import MeetingProcessingLog, MeetingLog
from frontend.db import get_db

from common.blob_storage import upload_file_to_blob
from common.transcriber import transcribe_from_blob_url
from common.summarizer import summarize_transcript
from common.emailer import send_summary_email

router = APIRouter()

ZOOM_WEBHOOK_SECRET = os.getenv("ZOOM_WEBHOOK_SECRET")
P2_STORAGE_CONN_STR = os.getenv("P2_STORAGE_CONNECTION_STRING")

def load_participants(meeting_id):
    path = Path(f"data/participants_{meeting_id}.json")
    if path.exists():
        with open(path, "r") as f:
            data = json.load(f)
        return (
            data.get("emails", []),
            data.get("created_by_email", "unknown"),
            data.get("form_host_email", None)
        )
    return [], "unknown", None

@router.post("/api/zoom/webhook")
async def zoom_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.body()
        payload = json.loads(body)
        event = payload.get("event")

        if event == "endpoint.url_validation":
            plain_token = payload["payload"]["plainToken"]
            encrypted_token = hmac.new(ZOOM_WEBHOOK_SECRET.encode(), plain_token.encode(), hashlib.sha256).hexdigest()
            return {"plainToken": plain_token, "encryptedToken": encrypted_token}

        if event != "recording.completed":
            return Response(status_code=204)

        recording = payload.get("payload", {}).get("object", {})
        meeting_id = str(recording.get("id"))

        processed_log = db.query(MeetingProcessingLog).filter_by(meeting_id=meeting_id).first()
        if processed_log:
            print(f"[🛑 Already processed] Skipping meeting {meeting_id}")
            return {"status": "duplicate skipped"}
        
        audio_file = next((f for f in recording.get("recording_files", []) if f["file_type"] == "M4A"), None)
        if not audio_file:
            print(f"[⚠️ No M4A audio file found] Skipping meeting {meeting_id}")
            return {"status": "no audio file"}
            
        download_url = audio_file["download_url"]
        filename = f"audio_{audio_file['id']}.m4a"
        download_token = payload.get("download_token")
        full_url = f"{download_url}?access_token={download_token}"

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".m4a")
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=90.0) as client:
                async with client.stream("GET", full_url) as r:
                    r.raise_for_status()
                    async for chunk in r.aiter_bytes():
                        tmp.write(chunk)
            
            blob_url = upload_file_to_blob(meeting_id, tmp.name, filename) 
            
            transcript = transcribe_from_blob_url(blob_url)
            summary = summarize_transcript(transcript)
            recipients, created_by_email, form_host_email = load_participants(meeting_id)
            
            effective_host_email = form_host_email or recording.get("host_email")
            if not recipients:
                recipients = [effective_host_email] if effective_host_email else []
            if effective_host_email and effective_host_email not in recipients:
                recipients.append(effective_host_email)

            for email in recipients:
                send_summary_email(
                    to_email=email,
                    to_name="Participant",
                    subject=f"📝 Summary for Zoom Meeting {meeting_id}",
                    summary_text=summary,
                    transcript_text=transcript
                )

            new_log = MeetingLog(
                meeting_id=meeting_id, host_email=effective_host_email, summary=summary,
                transcript=transcript, recipients=json.dumps(recipients), 
                meeting_time=datetime.fromisoformat(recording["start_time"].replace("Z", "+00:00")),
                created_by_email=created_by_email, recording_full_url=blob_url
            )
            db.add(new_log)
            
            new_proc_log = MeetingProcessingLog(meeting_id=meeting_id)
            db.add(new_proc_log)
            
            db.commit()
            print(f"[✅ Phase 1] DB records for {meeting_id} committed.")

            if P2_STORAGE_CONN_STR:
                try:
                    blob_service_client = BlobServiceClient.from_connection_string(P2_STORAGE_CONN_STR)
                    blob_path = f"{meeting_id}/transcript.txt"
                    blob_client = blob_service_client.get_blob_client(container="raw-transcripts-phase2", blob=blob_path)
                    blob_client.upload_blob(transcript.encode('utf-8'), overwrite=True)
                    print(f"[✅ Phase 2 Trigger] Uploaded transcript to '{blob_path}' to start intelligence processing.")
                except Exception as e:
                    print(f"[❌ Phase 2 Trigger] Blob Upload Error: {e}")
            else:
                print("[⚠️ Phase 2 Trigger] P2_STORAGE_CONNECTION_STRING not set. Skipping trigger.")
        finally:
            tmp.close()
            os.remove(tmp.name)

        return {"status": "processed", "meeting_id": meeting_id}

    # THE FIX: Specifically catch the ClientDisconnect error and log it as a non-critical warning.
    except ClientDisconnect:
        print("[⚠️ Warning] Client disconnected before the full response could be sent. This is usually not a critical error.")
        return {"status": "processed_but_client_disconnected"}
    except Exception as e:
        print(f"[❌ Top-level Error in Webhook] {e}")
        traceback.print_exc()
        # Return a proper JSON response for errors
        return JSONResponse(status_code=500, content={"error": str(e)})