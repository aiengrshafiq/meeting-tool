# backend/api.py
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
import os, json, traceback
from pathlib import Path
from datetime import datetime

from models import ScheduledMeeting
from frontend.db import get_db
from backend.webhook import router as webhook_router
from common.zoom_api import create_zoom_meeting, is_host_available, cancel_zoom_meeting

app = FastAPI()
app.include_router(webhook_router)

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
    return {"status": "✅ FastAPI is working with GET"}

@app.post("/api/create-meeting")
def create_meeting(meeting: MeetingRequest, db: Session = Depends(get_db)):
    try:
        payload = {
            "topic": meeting.topic, "type": 2, "start_time": meeting.start_time,
            "duration": meeting.duration, "agenda": meeting.agenda,
            "settings": {"auto_recording": "cloud", "join_before_host": False, "waiting_room": True, "mute_upon_entry": True, "approval_type": 0, "registration_type": 1,"participant_video": True}
        }
        host_email = meeting.host_email.strip()
        if not host_email:
            raise HTTPException(status_code=400, detail="Please select a valid host email.")
        if not is_host_available(db, host_email, meeting.start_time, meeting.duration):
            raise HTTPException(
                status_code=409,
                detail=f"Requested host '{host_email}' is busy. Please select another host or time."
            )
        result = create_zoom_meeting(payload, host_email)
        if not result or "id" not in result:
            raise HTTPException(status_code=500, detail="Failed to create Zoom meeting.")
        
        new_meeting = ScheduledMeeting(
            meeting_id=result["id"],
            topic=meeting.topic,
            start_time=datetime.fromisoformat(meeting.start_time.replace("Z", "+00:00")),
            duration=meeting.duration,
            agenda=meeting.agenda,
            participants=json.dumps(meeting.participants),
            host_email=host_email,
            created_by_email=meeting.created_by_email
        )
        db.add(new_meeting)
        db.commit()
        
        os.makedirs("data", exist_ok=True)
        participants_path = Path(f"data/participants_{result['id']}.json")
        with open(participants_path, "w") as f:
            json.dump({
                "emails": meeting.participants,
                "created_by_email": meeting.created_by_email,
                "form_host_email": host_email
            }, f)
            
        return {
            "id": result["id"], "join_url": result["join_url"], "start_url": result["start_url"],
            "start_time": result["start_time"], "duration": result["duration"],
            "created_by_email": meeting.created_by_email, "form_host_email": host_email
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"[❌ Exception creating meeting]: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/cancel-meeting/{meeting_id}")
def cancel_meeting(meeting_id: str, db: Session = Depends(get_db)):
    try:
        cancel_zoom_meeting(meeting_id)
        meeting_to_delete = db.query(ScheduledMeeting).filter(ScheduledMeeting.meeting_id == meeting_id).first()
        if meeting_to_delete:
            db.delete(meeting_to_delete)
            db.commit()
        return {"status": "cancelled"}
    except Exception as e:
        print(f"[❌ Cancel error] {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))