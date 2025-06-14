# backend/api.py
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from backend.webhook import router as webhook_router
from common.zoom_api import create_zoom_meeting, find_available_host, is_host_available
from fastapi.responses import JSONResponse
from pathlib import Path
from dotenv import load_dotenv

import os, json, traceback
import psycopg2
from datetime import datetime

app = FastAPI()
app.include_router(webhook_router)

load_dotenv()
POSTGRES_URL = os.getenv("POSTGRES_URL")

class MeetingRequest(BaseModel):
    topic: str
    start_time: str
    duration: int
    agenda: str
    participants: list[str]
    host_email: str
    created_by_email: str

@app.get("/api/test")
async def test():
    return JSONResponse({"status": "✅ FastAPI is working with GET"})

@app.get("/api/test_post")
async def test_post():
    return JSONResponse({"status": "✅ FastAPI is working with POST"})

@app.post("/api/create-meeting")
def create_meeting(meeting: MeetingRequest):
    try:
        payload = {
            "topic": meeting.topic,
            "type": 2,
            "start_time": meeting.start_time,
            "duration": meeting.duration,
            "agenda": meeting.agenda,
            "settings": {
                "auto_recording": "cloud",
                "join_before_host": False,
                "waiting_room": True,
                "mute_upon_entry": True,
                "approval_type": 0,
                "registration_type": 1
            }
        }

        # 🔒 Validate host selection
        host_email = meeting.host_email.strip()
        if not host_email:
            raise HTTPException(status_code=400, detail="Please select a valid host email.")

        if not is_host_available(host_email, meeting.start_time, meeting.duration, POSTGRES_URL):
            raise HTTPException(
                status_code=400,
                detail=f"Requested host '{host_email}' is busy during that time. Please select another host or time."
            )

        # 🎯 Create Zoom meeting
        result = create_zoom_meeting(payload, host_email)

        if not result or "id" not in result:
            raise HTTPException(status_code=500, detail="Failed to create Zoom meeting.")

        # 🗂️ Save scheduled meeting to DB
        save_scheduled_meeting(result["id"], meeting)

        # 💾 Save participants
        os.makedirs("data", exist_ok=True)
        participants_path = Path(f"data/participants_{result['id']}.json")
        with open(participants_path, "w") as f:
            json.dump({
                "emails": meeting.participants,
                "created_by_email": meeting.created_by_email,
                "form_host_email": host_email
            }, f)

        return {
            "id": result["id"],
            "join_url": result["join_url"],
            "start_url": result["start_url"],
            "start_time": result["start_time"],
            "duration": result["duration"],
            "created_by_email": meeting.created_by_email,
            "form_host_email": host_email
        }

    except HTTPException as e:
        raise e  # Pass FastAPI validation/logic errors as-is

    except Exception as e:
        print(f"[❌ Exception creating meeting]: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")

def save_scheduled_meeting(meeting_id: str, meeting: MeetingRequest):
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_meetings (
                meeting_id VARCHAR PRIMARY KEY,
                topic TEXT,
                start_time TIMESTAMP,
                duration INTEGER,
                agenda TEXT,
                participants TEXT,
                host_email VARCHAR,
                created_by_email VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT INTO scheduled_meetings (
                meeting_id, topic, start_time, duration, agenda,
                participants, host_email, created_by_email
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (meeting_id) DO NOTHING
        """, (
            meeting_id,
            meeting.topic,
            meeting.start_time,
            meeting.duration,
            meeting.agenda,
            json.dumps(meeting.participants),
            meeting.host_email,
            meeting.created_by_email
        ))
        conn.commit()
    except Exception as e:
        print(f"[❌ Error saving meeting to DB]: {e}")
        raise
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
