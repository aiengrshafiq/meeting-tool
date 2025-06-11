from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from backend.webhook import router as webhook_router
from common.zoom_api import create_zoom_meeting
from fastapi.responses import JSONResponse
import os, json
import httpx, psycopg2

from dotenv import load_dotenv

app = FastAPI()
app.include_router(webhook_router)

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
    return JSONResponse({"status": "✅ FastAPI is working with get"})

@app.get("/api/test_post")
async def test_post():
    return JSONResponse({"status": "✅ FastAPI is working with post"})

@app.post("/api/create-meeting")
def create_meeting(meeting: MeetingRequest):
    payload = {
        "topic": meeting.topic,
        "type": 2,
        "start_time": meeting.start_time,
        "duration": meeting.duration,
        "agenda": meeting.agenda,
        "settings": {
            "auto_recording": "cloud",
            "join_before_host": True,
            "mute_upon_entry": True,
            "approval_type": 0,
            "registration_type": 1,
        }
    }

    

    try:
        print(f"payload is: {payload}")
        result = create_zoom_meeting(payload, meeting.host_email)
        print(f"result is is: {result}")
        if not result or "id" not in result:
            raise HTTPException(status_code=500, detail="Failed to create Zoom meeting with shafiq")

        # Save the scheduled meeting to the database
        save_scheduled_meeting(result["id"], meeting)
        # Save participants (optional)
        from pathlib import Path
        import os, json
        os.makedirs("data", exist_ok=True)
        print(f"Saving participants to data/participants_{result['id']}.json")
        
        
        with open(Path(f"data/participants_{result['id']}.json"), "w") as f:
            json.dump({
                "emails": meeting.participants,
                "created_by_email": meeting.created_by_email,
                "form_host_email": meeting.host_email 
            }, f)

        return {
            "id": result["id"],
            "join_url": result["join_url"],
            "start_url": result["start_url"],
            "start_time": result["start_time"],
            "duration": result["duration"],
            "created_by_email": meeting.created_by_email,
            "form_host_email": meeting.host_email
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def save_scheduled_meeting(meeting_id, meeting: MeetingRequest):
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
        cursor.close()
        conn.close()
        print(f"[🗂️ Saved scheduled meeting {meeting_id}]")
    except Exception as e:
        print(f"[❌ Error saving scheduled meeting] {e}")

