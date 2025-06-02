import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
FROM_NAME = os.getenv("FROM_NAME", "Universal Meeting Assistant")
FROM_EMAIL = os.getenv("FROM_EMAIL", "no-reply@yourdomain.com")




def send_meeting_invite(to_email, to_name, meeting):
    subject = f"📅 Zoom Meeting Scheduled: {meeting['meeting_id']} on {meeting['start_time_gst']}"

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; color: #333;">
        <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.05);">
          <p>Hello {to_name},</p>
          <h3>✅ Zoom Meeting Scheduled</h3>

          <div style="background:#f0f0f0; padding:10px 15px; border-left:4px solid #007bff; margin-bottom:20px;">
            <p><strong>Meeting ID:</strong> {meeting['meeting_id']}</p>
            <p><strong>Start Time:</strong> {meeting['start_time_gst']}</p>
            <p><strong>Duration:</strong> {meeting['duration']} minutes</p>
          </div>

          <a href="{meeting['start_url']}" style="display:inline-block; padding:10px 20px; background-color:#007bff; color:#fff; border-radius:5px; text-decoration:none;">🚀 Start Meeting</a><br><br>
          <a href="{meeting['join_url']}" style="display:inline-block; padding:10px 20px; background-color:#007bff; color:#fff; border-radius:5px; text-decoration:none;">👥 Join Meeting</a>

          <p>If the buttons above don’t work, you can use these links:</p>
          <p><strong>Start:</strong> <a href="{meeting['start_url']}">{meeting['start_url']}</a></p>
          <p><strong>Join:</strong> <a href="{meeting['join_url']}">{meeting['join_url']}</a></p>

          <p>Thanks,<br>The Universal Meeting Assistant Team</p>
        </div>
      </body>
    </html>
    """

    data = {
        "sender": {
            "name": FROM_NAME,
            "email": FROM_EMAIL
        },
        "to": [{"email": to_email, "name": to_name or "Participant"}],
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

    if response.status_code != 201:
        print(f"[❌ Email Failed] {response.status_code} - {response.text}")
    else:
        print(f"[✅ Email Sent] To: {to_email}")
        print("📨 Brevo Response:", response.text)



def send_summary_email(to_email, to_name, subject, summary_text, transcript_text=None, join_url=None):
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; color: #333;">
        <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.05);">
          <p>Hello {to_name},</p>
          <h3>📝 Meeting Summary</h3>

          <p><strong>Summary:</strong></p>
          <pre style="background:#f5f5f5; padding:10px; white-space:pre-wrap;">{summary_text}</pre>
    """

    if transcript_text:
        html_content += f"""
          <p><strong>Transcript:</strong></p>
          <pre style="background:#f5f5f5; padding:10px; white-space:pre-wrap;">{transcript_text}</pre>
        """

    if join_url:
        html_content += f"""
          <a href="{join_url}" style="display:inline-block; padding:10px 20px; background-color:#007bff; color:#fff; border-radius:5px; text-decoration:none;">👥 Join Meeting</a>
          <p>If the button above doesn’t work, use this link:</p>
          <p><a href="{join_url}">{join_url}</a></p>
        """

    html_content += """
          <p>Thanks,<br>The Universal Meeting Assistant Team</p>
        </div>
      </body>
    </html>
    """

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
