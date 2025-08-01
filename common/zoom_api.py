# common/zoom_api.py
import os
import requests
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from models import ScheduledMeeting
from common.zoom_auth import get_server_token

# Load environment variables
HOST_EMAILS = [
    "meeting@6t3media.com",
    "meeting_host@6t3media.com",
    "meeting_host2@6t3media.com"
]

def is_host_available(db: Session, host_email: str, start_time_iso: str, duration_minutes: int) -> bool:
    start_time = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
    end_time = start_time + timedelta(minutes=duration_minutes)
    
    # REFACTOR: Replaced psycopg2 with SQLAlchemy session
    try:
        conflicting_meetings = db.query(ScheduledMeeting).filter(
            ScheduledMeeting.host_email == host_email
        ).all()
    except Exception as e:
        print(f"[❌ DB error in is_host_available]: {e}")
        raise

    for meeting in conflicting_meetings:
        mt_start = meeting.start_time.replace(tzinfo=timezone.utc)
        mt_end = mt_start + timedelta(minutes=meeting.duration)
        # Check for overlap
        if max(start_time, mt_start) < min(end_time, mt_end):
            return False # Found an overlap, host is not available
    
    return True # No overlaps found

# NOTE: The find_available_host function can be simplified now that is_host_available is robust.
# We can iterate through hosts and check availability one by one.
def find_available_host(db: Session, start_time_iso: str, duration_minutes: int):
    for host in HOST_EMAILS:
        if is_host_available(db, host, start_time_iso, duration_minutes):
            return host
    return None

def create_zoom_meeting(payload: dict, host_email: str) -> dict:
    if not host_email:
        raise ValueError("host_email is required for Zoom meeting creation.")

    token = get_server_token()
    if not token:
        raise ValueError("Failed to get Zoom API access token.")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        response = requests.post(
            f"https://api.zoom.us/v2/users/{host_email}/meetings",
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        msg = f"[❌ Zoom API error for host '{host_email}']: {str(e)}"
        try:
            msg += f" | Response: {response.text}"
        except:
            pass
        print(msg)
        raise Exception(msg)

    return response.json()

def cancel_zoom_meeting(meeting_id: str):
    token = get_server_token()
    if not token:
        raise ValueError("Zoom token missing")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        res = requests.delete(
            f"https://api.zoom.us/v2/meetings/{meeting_id}",
            headers=headers,
            timeout=10
        )
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[❌ Zoom cancel error]: {e}")
        raise Exception("Failed to cancel Zoom meeting")