from flask import Flask, render_template, request, redirect, url_for, flash,session

import requests
import os
from dotenv import load_dotenv
from frontend.auth import auth_bp

from models import MeetingLog
from sqlalchemy import desc
import json
from azure.storage.blob import BlobServiceClient
import os

load_dotenv()

import sys
import traceback
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.emailer import send_meeting_invite

app = Flask(__name__)
app.secret_key = "supersecretkey"

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

from datetime import datetime, timedelta



app.register_blueprint(auth_bp)

@app.before_request
def require_login():
    if request.endpoint not in ("auth.login", "auth.register", "static") and not session.get("user_id"):
        return redirect(url_for("auth.login"))


@app.route('/')
def home():
    return render_template('form.html')


@app.route('/schedule', methods=['POST'])
def schedule():
    topic = request.form['topic']
    start_time = request.form['start_time']
    duration = int(request.form['duration'])
    agenda = request.form['agenda']
    participants = [p.strip() for p in request.form['participants'].split(',')]
    host_email = request.form['host_email']
    created_by_email = session.get("user_email")
    payload = {
        "topic": topic,
        "start_time": start_time,
        "duration": duration,
        "agenda": agenda,
        "participants": participants,
        "host_email": host_email,
        "created_by_email": created_by_email
    }

    try:
        res = requests.post(f"{API_BASE_URL}/api/create-meeting", json=payload)
        res.raise_for_status()
        data = res.json()
        print("✅ Meeting created:", data)

        from datetime import datetime, timedelta
        start_utc = datetime.strptime(data['start_time'], "%Y-%m-%dT%H:%M:%SZ")
        start_gst = start_utc + timedelta(hours=4)
        data['start_time_gst'] = start_gst.strftime("%Y-%m-%d %H:%M") + " (GST)"
        data['meeting_id'] = data['id']

        # ✅ Send confirmation emails to participants
        for email in participants:
            print(f"📤 Sending invite to {email}...")
            send_meeting_invite(email, "", data)
        
        ## ✅ Send confirmation email to host
        print(f"📤 Sending invite to host {host_email}...")
        send_meeting_invite(host_email, "", data)
        

        return render_template("success.html", meeting=data)

    except requests.exceptions.HTTPError as err:
        try:
            error_json = res.json()
            message = error_json.get("detail", "An unknown error occurred.")
        except Exception:
            message = "An unexpected error occurred while scheduling the meeting."
        flash(message, "danger")
        return redirect(url_for('home'))

    except Exception as e:
        flash("An internal error occurred. Please try again.", "danger")
        print("❌ Exception occurred:", e)
        traceback.print_exc()
        return redirect(url_for('home'))


@app.route("/brain")
def brain_dashboard():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    db = SessionLocal()
    try:
        meetings = db.query(MeetingLog).filter(
            MeetingLog.enriched_output_path != None
        ).order_by(desc(MeetingLog.meeting_time)).all()
        
        return render_template("brain_dashboard.html", meetings=meetings)
    finally:
        db.close()

# --- NEW ROUTE FOR MEETING DETAILS ---
@app.route("/brain/meeting/<meeting_id>")
def brain_meeting_detail(meeting_id):
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    db = SessionLocal()
    try:
        # 1. Get the meeting record from the database
        meeting = db.query(MeetingLog).filter(MeetingLog.meeting_id == meeting_id).first()
        if not meeting or not meeting.enriched_output_path:
            flash("Meeting details not found.", "danger")
            return redirect(url_for("app.brain_dashboard"))

        # 2. Fetch the enriched JSON file from Blob Storage
        p2_storage_conn_str = os.getenv("P2_STORAGE_CONNECTION_STRING")
        if not p2_storage_conn_str:
            flash("Storage connection for Phase 2 is not configured.", "danger")
            return redirect(url_for("app.brain_dashboard"))
            
        blob_service_client = BlobServiceClient.from_connection_string(p2_storage_conn_str)
        blob_client = blob_service_client.get_blob_client(
            container="enriched-output-phase2", 
            blob=meeting.enriched_output_path
        )
        
        downloader = blob_client.download_blob()
        blob_content = downloader.readall()
        meeting_details = json.loads(blob_content)
        
        return render_template("meeting_detail.html", details=meeting_details)

    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for("app.brain_dashboard"))
    finally:
        db.close()

    
if __name__ == "__main__":
    app.run(debug=True, port=5000)
