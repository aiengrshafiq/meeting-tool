import os
import requests
from dotenv import load_dotenv
load_dotenv()

def get_server_token():
    client_id = os.getenv("ZOOM_CLIENT_ID")
    client_secret = os.getenv("ZOOM_CLIENT_SECRET")
    account_id = os.getenv("ZOOM_ACCOUNT_ID")

    if not client_id:
        raise ValueError("client_id is not set in environment variables.")
    if not client_secret:
        raise ValueError("client_secret is not set in environment variables.")
    if not account_id:
        raise ValueError("account_id is not set in environment variables.")

    url = "https://zoom.us/oauth/token"
    payload = {
        "grant_type": "account_credentials",
        "account_id": account_id
    }

    response = requests.post(
        url,
        auth=(client_id, client_secret),
        data=payload
    )

    if response.status_code != 200:
        raise Exception(f"[❌ Zoom Token Error] {response.status_code}: {response.text}")

    access_token = response.json()["access_token"]
    return access_token
