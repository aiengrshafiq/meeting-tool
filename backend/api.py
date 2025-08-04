# backend/api.py

# --- Standard Library Imports ---
import os
import json
import traceback
from pathlib import Path
from datetime import datetime
import io

# --- Third-party Imports ---
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from sqlalchemy.orm import Session
from pydub import AudioSegment
# THE FIX: Use the one, correct import for the speech SDK
import azure.cognitiveservices.speech as speechsdk

# --- Local Application Imports ---
from models import ScheduledMeeting, User
from frontend.db import get_db
from backend.webhook import router as webhook_router
from common.zoom_api import create_zoom_meeting, is_host_available, cancel_zoom_meeting

# --- FastAPI App Initialization ---
app = FastAPI()
app.include_router(webhook_router)

# --- Pydantic Models ---
class MeetingRequest(BaseModel):
    topic: str
    start_time: str
    duration: int
    agenda: str
    participants: list[str]
    host_email: str
    created_by_email: str

# --- Helper class for Azure Speech SDK ---
# This class is correct and does not need changes.
class WavStream(speechsdk.audio.PullAudioInputStreamCallback):
    def __init__(self, wav_bytes: bytes):
        super().__init__()
        self._buffer = io.BytesIO(wav_bytes)

    def read(self, buffer: memoryview) -> int:
        size = self._buffer.readinto(buffer)
        return size

    def close(self):
        self._buffer.close()

# --- API Routes ---

@app.get("/api/test")
async def test():
    return {"status": "✅ FastAPI is working with GET"}

@app.post("/api/create-meeting")
def create_meeting(meeting: MeetingRequest, db: Session = Depends(get_db)):
    # This is your existing, working code. It is preserved.
    try:
        payload = {
            "topic": meeting.topic, "type": 2, "start_time": meeting.start_time,
            "duration": meeting.duration, "agenda": meeting.agenda,
            "settings": {"auto_recording": "cloud", "join_before_host": False, "waiting_room": True, "mute_upon_entry": True, "approval_type": 0, "registration_type": 1}
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
    # This is your existing, working code. It is preserved.
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

@app.post("/api/enroll-voice")
async def enroll_voice(
    audio_file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    user_id_to_enroll = 1 
    user = db.query(User).filter(User.id == user_id_to_enroll).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    speech_key = os.getenv("SPEECH_KEY")
    speech_region = os.getenv("SPEECH_REGION")
    if not speech_key or not speech_region:
        raise HTTPException(status_code=500, detail="Speech service not configured.")

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    
    # THE FIX: All classes are accessed via the main 'speechsdk' module
    profile_client = speechsdk.VoiceProfileClient(speech_config)

    if not user.voice_profile_id:
        try:
            profile_type = speechsdk.VoiceProfileType.TextIndependentIdentification
            voice_profile = profile_client.create_profile(profile_type, "en-us")
            user.voice_profile_id = voice_profile.profile_id
            db.commit()
            print(f"Created new voice profile for user {user.email} with ID: {user.voice_profile_id}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create voice profile: {e}")
    
    try:
        audio_data = await audio_file.read()
        webm_audio = AudioSegment.from_file(io.BytesIO(audio_data), format="webm")
        wav_audio = webm_audio.set_frame_rate(16000).set_sample_width(2).set_channels(1)
        
        wav_bytes_io = io.BytesIO()
        wav_audio.export(wav_bytes_io, format="wav")
        wav_data = wav_bytes_io.getvalue()
        
        audio_stream_callback = WavStream(wav_data)
        pull_stream = speechsdk.audio.PullAudioInputStream(callback=audio_stream_callback)
        audio_config = speechsdk.audio.AudioConfig(stream=pull_stream)
        
        print(f"Enrolling audio for profile ID: {user.voice_profile_id}...")
        result = profile_client.enroll_profile_async(user.voice_profile_id, audio_config).get()

        if result.reason == speechsdk.ResultReason.EnrolledVoiceProfile:
            print(f"Successfully enrolled voice for user {user.email}. Remaining speech time: {result.remaining_enrollment_speech_time}")
            return {"status": "success", "profileId": user.voice_profile_id, "remainingTime": str(result.remaining_enrollment_speech_time)}
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = speechsdk.VoiceProfileEnrollmentCancellationDetails.from_result(result)
            raise HTTPException(status_code=400, detail=f"Enrollment canceled: {cancellation.reason} - {cancellation.error_details}")
        else:
            raise HTTPException(status_code=500, detail=f"Enrollment failed with reason: {result.reason}")

    except Exception as e:
        print(f"An error occurred during enrollment processing: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred during enrollment: {e}")