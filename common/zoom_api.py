import os
import requests
from common.zoom_auth import get_server_token


def create_zoom_meeting(payload):
    

    token = get_server_token()
    print("access_token is inside function :", access_token)
    user_id = os.getenv("ZOOM_USER_ID")

    if not user_id:
        raise ValueError("ZOOM_USER_ID is not set in environment variables.")
    if not token:
        raise ValueError("Failed to get Zoom API access token.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Set default Zoom meeting settings
    payload.setdefault("settings", {
        "auto_recording": "cloud",
        "join_before_host": True,
        "mute_upon_entry": True,
        "approval_type": 0
    })

    try:
        response = requests.post(
            f"https://api.zoom.us/v2/users/{user_id}/meetings",
            headers=headers,
            json=payload
        )
        print("🔁 Response Status Code:", response.status_code)
        print("🔁 Response Body:", response.text)

        response.raise_for_status()  # Will raise an HTTPError for non-2xx status

    except requests.exceptions.RequestException as e:
        # Log detailed error message from Zoom API
        error_message = f"Zoom API Error: {response.status_code} - {response.text}" if response else str(e)
        raise Exception(error_message)

    return response.json()
