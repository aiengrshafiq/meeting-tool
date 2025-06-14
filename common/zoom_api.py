# common/zoom_api.py
import os
import requests
import psycopg2
from datetime import datetime, timedelta
from common.zoom_auth import get_server_token
from datetime import timezone

# Load environment variables
# ✅ Define your managed Zoom users
HOST_EMAILS = [
    "meeting@6t3media.com",
    "meeting_host@6t3media.com",
    "meeting_host2@6t3media.com"
]

def is_host_available(host_email: str, start_time_iso: str, duration_minutes: int, postgres_url: str) -> bool:
    start_time = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
    end_time = start_time + timedelta(minutes=duration_minutes)

    try:
        conn = psycopg2.connect(postgres_url)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT start_time, duration FROM scheduled_meetings
            WHERE host_email = %s
            AND start_time >= %s - interval '15 minutes'
            AND start_time <= %s + interval '15 minutes'
        """, (host_email, start_time, end_time))
        rows = cursor.fetchall()
    except Exception as e:
        print(f"[❌ DB error in is_host_available]: {e}")
        raise
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

    for mt_start, mt_duration in rows:
        mt_start = mt_start.replace(tzinfo=timezone.utc)
        mt_end = mt_start + timedelta(minutes=mt_duration)
        if not (end_time <= mt_start or start_time >= mt_end):
            return False
    return True


def find_available_host(start_time_iso: str, duration_minutes: int, postgres_url: str):
    start_time = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
    end_time = start_time + timedelta(minutes=duration_minutes)

    try:
        conn = psycopg2.connect(postgres_url)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT host_email, start_time, duration FROM scheduled_meetings
            WHERE start_time >= %s - interval '15 minutes'
            AND start_time <= %s + interval '15 minutes'
        """, (start_time, end_time))
        rows = cursor.fetchall()
    except Exception as e:
        print(f"[❌ DB error in find_available_host]: {e}")
        raise
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

    busy_hosts = set()
    for host_email, mt_start, mt_duration in rows:
        if host_email not in HOST_EMAILS:
            continue
        mt_start = mt_start.replace(tzinfo=timezone.utc)
        mt_end = mt_start + timedelta(minutes=mt_duration)
        if not (end_time <= mt_start or start_time >= mt_end):
            busy_hosts.add(host_email)

    for host in HOST_EMAILS:
        if host not in busy_hosts:
            return host
    return None


def create_zoom_meeting(payload: dict, host_email: str) -> dict:
    if not host_email:
        raise ValueError("host_email is required for Zoom meeting creation.")

    token = get_server_token()
    if not token:
        raise ValueError("Failed to get Zoom API access token.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload.setdefault("settings", {
        "auto_recording": "cloud",
        "join_before_host": False,
        "waiting_room": True,
        "mute_upon_entry": True,
        "approval_type": 0,
        "registration_type": 1
    })

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

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

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
