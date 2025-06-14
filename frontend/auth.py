from flask import Blueprint, request, redirect, render_template, session, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from .db import Base, SessionLocal
import os, json
import httpx, psycopg2
import requests


from dotenv import load_dotenv
auth_bp = Blueprint("auth", __name__)

# SQLAlchemy model
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default='user')
    created_at = Column(DateTime, default=datetime.utcnow)

# Initialize table
Base.metadata.create_all(bind=SessionLocal().bind)

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        db = SessionLocal()
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        if db.query(User).filter_by(email=email).first():
            flash("⚠️ User already exists", "danger")
            return redirect(url_for("auth.register"))
        db.add(User(email=email, password=password))
        db.commit()
        flash("✅ Registered! Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = SessionLocal()
        email = request.form["email"]
        password = request.form["password"]
        user = db.query(User).filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            flash("❌ Invalid credentials", "danger")
            return redirect(url_for("auth.login"))
        session["user_id"] = user.id
        session["user_email"] = user.email
        session["user_role"] = user.role
        flash("✅ Logged in successfully", "success")
        return redirect(url_for("home"))
    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("👋 Logged out", "info")
    return redirect(url_for("auth.login"))

@auth_bp.route("/dashboard")
def dashboard():
    if session.get("user_role") != "admin":
        flash("Access denied. Admins only.")
        return redirect(url_for("home"))

    try:
        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT meeting_id, host_email, created_by_email, meeting_time, summary,recipients, recording_full_url
            , transcript, created_at
            FROM meeting_logs
            ORDER BY meeting_time DESC
            LIMIT 200
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template("dashboard.html", meetings=rows)
    except Exception as e:
        print(f"[❌ Error loading dashboard] {e}")
        flash("Failed to load dashboard.")
        return redirect(url_for("home"))

@auth_bp.route("/meetings")
def meetings():
    if session.get("user_role") != "admin":
        flash("Access denied. Admins only.")
        return redirect(url_for("home"))

    try:
        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT meeting_id, topic, start_time, 
                participants, host_email, created_by_email, created_at
            FROM scheduled_meetings
            ORDER BY created_at DESC
            LIMIT 200
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template("meetings.html", meetings=rows)
    except Exception as e:
        print(f"[❌ Error loading meetings] {e}")
        flash("Failed to load meetings.")
        return redirect(url_for("home"))

@auth_bp.route("/cancel", methods=["POST"])
def cancel_meeting():
    if session.get("user_role") != "admin":
        flash("Unauthorized access", "danger")
        return redirect(url_for("auth.meetings"))

    meeting_id = request.form.get("meeting_id")
    if not meeting_id:
        flash("Missing meeting ID", "danger")
        return redirect(url_for("auth.meetings"))

    try:
        # Call FastAPI endpoint to cancel Zoom meeting
        res = requests.delete(f"{os.getenv('API_BASE_URL')}/api/cancel-meeting/{meeting_id}")
        res.raise_for_status()
        flash("✅ Meeting cancelled successfully.", "success")
    except requests.exceptions.RequestException as e:
        flash(f"❌ Failed to cancel meeting: {str(e)}", "danger")

    return redirect(url_for("auth.meetings"))