from fastapi import APIRouter, Header, Request, HTTPException
import os
import hashlib
import hmac
import json
import tempfile
import httpx
from common.blob_storage import upload_file_to_blob
from dotenv import load_dotenv
load_dotenv()

router = APIRouter()

ZOOM_WEBHOOK_SECRET = os.getenv("ZOOM_WEBHOOK_SECRET", "myzoomsecret")

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

        # Append JWT access_token to download_url if required
        full_url = f"{download_url}?access_token={os.getenv('ZOOM_OAUTH_TOKEN')}"

        # Download file to temp location
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            async with httpx.AsyncClient() as client:
                r = await client.get(full_url)
                r.raise_for_status()
                tmp.write(r.content)

            blob_url = upload_file_to_blob(meeting_id, tmp.name, filename)
            uploaded_files.append(blob_url)

    return {
        "status": "recordings uploaded",
        "meeting_id": meeting_id,
        "host": host_email,
        "files": uploaded_files
    }
