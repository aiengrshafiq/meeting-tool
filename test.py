
import requests

payload = {
    "topic": "Test Zoom",
    "start_time": "2025-05-30T10:00:00Z",
    "duration": 30,
    "agenda": "Dev debug",
    "participants": ["test@example.com"]
}
print(f"payload is: {payload}")
res = requests.post("http://127.0.0.1:8000/api/create-meeting", json=payload)
print(res.status_code)
print(res.json())
print(f"result is: {res}")

