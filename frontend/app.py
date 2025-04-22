from flask import Flask, render_template, request, redirect, url_for, flash
import requests
import os
from dotenv import load_dotenv


load_dotenv()

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.emailer import send_meeting_invite

app = Flask(__name__)
app.secret_key = "supersecretkey"

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

from datetime import datetime, timedelta

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

    payload = {
        "topic": topic,
        "start_time": start_time,
        "duration": duration,
        "agenda": agenda,
        "participants": participants
    }

    try:
        res = requests.post(f"{API_BASE_URL}/api/create-meeting", json=payload)
        res.raise_for_status()
        data = res.json()
        # Convert ISO UTC start time to GST (UTC+4) for display
        start_utc = datetime.strptime(data['start_time'], "%Y-%m-%dT%H:%M:%SZ")
        start_gst = start_utc + timedelta(hours=4)
        data['start_time_gst'] = start_gst.strftime("%Y-%m-%d %H:%M") + " (GST)"

        # ✅ Send confirmation emails after meeting creation
        for email in participants:
            send_meeting_invite(email, "", data)

        return render_template("success.html", meeting=data)
    except Exception as e:
        flash(f"Error: {str(e)}")
        return redirect(url_for('home'))
