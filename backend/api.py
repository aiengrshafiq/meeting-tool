from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from backend.webhook import router as webhook_router
from common.zoom_api import create_zoom_meeting

app = FastAPI()
app.include_router(webhook_router)

class MeetingRequest(BaseModel):
    topic: str
    start_time: str
    duration: int
    agenda: str
    participants: list[str]

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
        result = create_zoom_meeting(payload)

        # Save participants (optional)
        from pathlib import Path
        import os, json
        os.makedirs("data", exist_ok=True)
        with open(Path(f"data/participants_{result['id']}.json"), "w") as f:
            json.dump(meeting.participants, f)

        return {
            "id": result["id"],
            "join_url": result["join_url"],
            "start_url": result["start_url"],
            "start_time": result["start_time"],
            "duration": result["duration"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
