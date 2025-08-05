# frontend/app.py

from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests
import os
from dotenv import load_dotenv
from frontend.auth import auth_bp

from models import MeetingLog, ScheduledMeeting
from sqlalchemy import desc, or_
import json
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError
from frontend.db import SessionLocal

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

# THE FIX: Make the current year available to all templates
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.utcnow().year}

@app.before_request
def require_login():
    if request.endpoint and 'static' not in request.endpoint and not session.get("user_id"):
        if request.endpoint not in ("auth.login", "auth.register"):
            return redirect(url_for("auth.login"))

@app.route('/')
def home():
    # The main dashboard is now the home page
    return render_template('main_dashboard.html')

@app.route('/create-meeting')
def create_meeting_form():
    # The form is now on its own dedicated page
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
        "topic": topic, "start_time": start_time, "duration": duration,
        "agenda": agenda, "participants": participants, "host_email": host_email,
        "created_by_email": created_by_email
    }

    try:
        res = requests.post(f"{API_BASE_URL}/api/create-meeting", json=payload)
        res.raise_for_status()
        data = res.json()
        
        start_utc = datetime.strptime(data['start_time'], "%Y-%m-%dT%H:%M:%SZ")
        start_gst = start_utc + timedelta(hours=4)
        data['start_time_gst'] = start_gst.strftime("%Y-%m-%d %H:%M") + " (GST)"
        data['meeting_id'] = data['id']

        # Combine all recipients for the email loop
        all_recipients = participants + [host_email]
        for email in all_recipients:
            send_meeting_invite(email, "", data)
        
        return render_template("success.html", meeting=data)

    except requests.exceptions.HTTPError as err:
        try:
            message = res.json().get("detail", "An unknown error occurred.")
        except Exception:
            message = "An unexpected error occurred while scheduling the meeting."
        flash(message, "danger")
        return redirect(url_for('create_meeting_form'))
    except Exception as e:
        flash("An internal error occurred. Please try again.", "danger")
        traceback.print_exc()
        return redirect(url_for('create_meeting_form'))

@app.route("/brain")
def brain_dashboard():
    db = SessionLocal()
    try:
        query = db.query(MeetingLog).filter(MeetingLog.enriched_output_path != None)
        
        # Role-based access control
        if session.get("user_role") != "admin":
            user_email = session.get("user_email")
            # Filter for meetings created by the user OR where they were a recipient
            query = query.filter(
                or_(
                    MeetingLog.created_by_email == user_email,
                    MeetingLog.recipients.contains(f'"{user_email}"')
                )
            )
            
        meetings = query.order_by(desc(MeetingLog.meeting_time)).all()
        return render_template("brain_dashboard.html", meetings=meetings)
    finally:
        db.close()

@app.route("/brain/meeting/<meeting_id>")
def brain_meeting_detail(meeting_id):
    db = SessionLocal()
    try:
        meeting = db.query(MeetingLog).filter(MeetingLog.meeting_id == meeting_id).first()
        if not meeting or not meeting.enriched_output_path:
            flash("Meeting details not found in the database.", "danger")
            return redirect(url_for("brain_dashboard"))

        p2_storage_conn_str = os.getenv("P2_STORAGE_CONNECTION_STRING")
        if not p2_storage_conn_str:
            flash("CRITICAL ERROR: P2_STORAGE_CONNECTION_STRING is not configured.", "danger")
            return redirect(url_for("brain_dashboard"))
            
        blob_service_client = BlobServiceClient.from_connection_string(p2_storage_conn_str)
        blob_client = blob_service_client.get_blob_client(
            container="enriched-output-phase2", 
            blob=meeting.enriched_output_path
        )
        
        try:
            blob_content = blob_client.download_blob().readall()
            if not blob_content:
                raise ValueError("Blob is empty.")
            meeting_details = json.loads(blob_content)
        except ResourceNotFoundError:
            flash(f"Error: The enriched output file was not found in storage.", "danger")
            return redirect(url_for("brain_dashboard"))
        except (json.JSONDecodeError, ValueError) as e:
            flash(f"Error parsing the meeting data file. It may be corrupted.", "danger")
            return redirect(url_for("brain_dashboard"))
            
        return render_template("meeting_detail.html", details=meeting_details, meeting_log=meeting)
    except Exception as e:
        flash(f"An unexpected server error occurred: {e}", "danger")
        traceback.print_exc()
        return redirect(url_for("brain_dashboard"))
    finally:
        db.close()

if __name__ == "__main__":
    app.run(debug=True, port=5000)