from fastapi import APIRouter, Header, Request, HTTPException
import os
import json
import tempfile
import httpx
from pathlib import Path
from dotenv import load_dotenv

from common.blob_storage import upload_file_to_blob
from common.transcriber import transcribe_from_blob_url
from common.summarizer import summarize_transcript
from common.emailer import send_summary_email

load_dotenv()
router = APIRouter()

ZOOM_WEBHOOK_SECRET = os.getenv("ZOOM_WEBHOOK_SECRET", "myzoomsecret")

def load_participants(meeting_id):
    path = Path(f"data/participants_{meeting_id}.json")
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return []

@router.post("/api/zoom/webhook")
async def zoom_webhook(request: Request, authorization: str = Header(None)):
    body = await request.body()
    payload = json.loads(body)

    event = payload.get("event")
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

        # Append access_token to download_url
        full_url = f"{download_url}?access_token={os.getenv('ZOOM_OAUTH_TOKEN')}"

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            async with httpx.AsyncClient() as client:
                r = await client.get(full_url)
                r.raise_for_status()
                tmp.write(r.content)

            blob_url = upload_file_to_blob(meeting_id, tmp.name, filename)
            uploaded_files.append(blob_url)

            # Transcribe with Whisper
            transcript = transcribe_from_blob_url(blob_url)
            if not transcript:
                continue

            # Summarize with GPT
            summary = summarize_transcript(transcript)

            # Email to participants (or fallback to host)
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

    return {
        "status": "recordings uploaded & summary sent",
        "meeting_id": meeting_id,
        "host": host_email,
        "recipients": recipients,
        "files": uploaded_files
    }
