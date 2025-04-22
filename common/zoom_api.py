import os
import requests
from common.zoom_auth import get_server_token


def create_zoom_meeting(payload):
    token = get_server_token()
    user_id = os.getenv("ZOOM_USER_ID")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload["settings"] = {
        "auto_recording": "cloud",
        "join_before_host": True,
        "mute_upon_entry": True,
        "approval_type": 0
    }


    response = requests.post(
        f"https://api.zoom.us/v2/users/{user_id}/meetings",
        headers=headers,
        json=payload
    )

    if response.status_code != 201:
        raise Exception(f"Zoom API Error: {response.status_code} - {response.text}")

    return response.json()