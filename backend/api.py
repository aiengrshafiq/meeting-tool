from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from backend.webhook import router as webhook_router
from common.zoom_api import create_zoom_meeting
from dotenv import load_dotenv
import os
import json
from pathlib import Path

load_dotenv()

app = FastAPI()
app.include_router(webhook_router)

class MeetingRequest(BaseModel):
    topic: str
    start_time: str
    duration: int
    agenda: str = ""
    participants: list[str]

def save_participants(meeting_id: str, participants: list[str]):
    os.makedirs("data", exist_ok=True)
    path = Path(f"data/participants_{meeting_id}.json")
    with open(path, "w") as f:
        json.dump(participants, f)

@app.post("/api/create-meeting")
def create_meeting(request: MeetingRequest):
    payload = {
        "topic": request.topic,
        "type": 2,
        "start_time": request.start_time,
        "duration": request.duration,
        "agenda": request.agenda,
        "settings": {
            "auto_recording": "cloud",
            "join_before_host": True,
            "mute_upon_entry": True,
            "approval_type": 0,
            "registration_type": 1,
        }
    }

    try:
        result = create_zoom_meeting(payload)

        # Save participants
        save_participants(result["id"], request.participants)

        return {
            "meeting_id": result["id"],
            "join_url": result["join_url"],
            "start_url": result["start_url"],
            "start_time": result["start_time"],
            "duration": result["duration"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
