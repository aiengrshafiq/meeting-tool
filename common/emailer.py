import os
import json
import requests
from dotenv import load_dotenv
load_dotenv()
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
FROM_NAME = os.getenv("FROM_NAME", "Universal Meeting Assistant")
FROM_EMAIL = os.getenv("FROM_EMAIL", "no-reply@yourdomain.com")


def send_meeting_invite(to_email, to_name, meeting):
    html_content = f"""
    <h3>✅ Zoom Meeting Scheduled</h3>
    <p><strong>Meeting ID:</strong> {meeting['meeting_id']}</p>
    <p><strong>Start Time:</strong> {meeting['start_time_gst']}</p>
    <p><strong>Duration:</strong> {meeting['duration']} minutes</p>
    <p><a href="{meeting['join_url']}">🔗 Join Meeting</a></p>
    <p><a href="{meeting['start_url']}">🔗 Start Meeting</a></p>
    """

    data = {
        "sender": {
            "name": FROM_NAME,
            "email": FROM_EMAIL
        },
        "to": [{"email": to_email, "name": to_name or "Participant"}],
        "subject": "📅 Zoom Meeting Scheduled - 6T3Media.com",
        "htmlContent": html_content
    }

    headers = {
        "Accept": "application/json",
        "Api-Key": BREVO_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers=headers,
        data=json.dumps(data)
    )

    if response.status_code != 201:
        print(f"[❌ Email Failed] {response.status_code} - {response.text}")
    else:
        print(f"[✅ Email Sent] To: {to_email}")


def send_summary_email(to_email, to_name, subject, summary_text, transcript_text=None, join_url=None):
    html_content = f"""
    <h2>Meeting Summary</h2>
    <p><strong>Summary:</strong></p>
    <pre style="background:#f5f5f5;padding:10px;">{summary_text}</pre>
    """

    if transcript_text:
        html_content += f"""
        <p><strong>Transcript:</strong></p>
        <pre style="background:#f5f5f5;padding:10px;white-space:pre-wrap;">{transcript_text}</pre>
        """

    if join_url:
        html_content += f'<p><a href="{join_url}">🔗 Join Meeting</a></p>'

    data = {
        "sender": {
            "name": FROM_NAME,
            "email": FROM_EMAIL
        },
        "to": [{
            "name": to_name,
            "email": to_email
        }],
        "subject": subject,
        "htmlContent": html_content
    }

    headers = {
        "Accept": "application/json",
        "Api-Key": BREVO_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers=headers,
        data=json.dumps(data)
    )

    if response.status_code == 201:
        print(f"[✅ Email sent] To: {to_email}")
    else:
        print(f"[❌ Email error] {response.status_code}: {response.text}")
