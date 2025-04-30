from fastapi import FastAPI, HTTPException, Form
from backend.webhook import router as webhook_router
from common.zoom_api import create_zoom_meeting
from dotenv import load_dotenv
import os
import json
from pathlib import Path

load_dotenv()

app = FastAPI()
app.include_router(webhook_router)


from fastapi.responses import RedirectResponse
from starlette.requests import Request
from starlette.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="frontend/templates")

def save_participants(meeting_id: str, participants: list[str]):
    os.makedirs("data", exist_ok=True)
    path = Path(f"data/participants_{meeting_id}.json")
    with open(path, "w") as f:
        json.dump(participants, f)

@app.post("/api/create-meeting")
def create_meeting(
    topic: str = Form(...),
    start_time: str = Form(...),
    duration: int = Form(...),
    agenda: str = Form(""),
    participants: str = Form(...)
):
    participants_list = [p.strip() for p in participants.split(",") if p.strip()]

    payload = {
        "topic": topic,
        "type": 2,
        "start_time": start_time,
        "duration": duration,
        "agenda": agenda,
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
        save_participants(result["id"], participants_list)

        return {
            "meeting_id": result["id"],
            "join_url": result["join_url"],
            "start_url": result["start_url"],
            "start_time": result["start_time"],
            "duration": result["duration"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
