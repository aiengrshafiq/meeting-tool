# frontend/auth.py
from flask import Blueprint, request, redirect, render_template, session, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import os
import requests
from sqlalchemy import desc, or_

from models import User, MeetingLog, ScheduledMeeting
from .db import SessionLocal

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        db = SessionLocal()
        email = request.form["email"]
        password = request.form["password"]
        
        existing_user = db.query(User).filter_by(email=email).first()
        if existing_user:
            flash("User already exists", "warning")
            db.close()
            return redirect(url_for("auth.register"))
            
        hashed_password = generate_password_hash(password)
        db.add(User(email=email, password=hashed_password, role='user'))
        db.commit()
        db.close()
        
        flash("Registered! Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = SessionLocal()
        email = request.form["email"]
        password = request.form["password"]
        
        user = db.query(User).filter_by(email=email).first()
        db.close()
        
        if not user or not check_password_hash(user.password, password):
            flash("Invalid credentials", "danger")
            return redirect(url_for("auth.login"))
            
        session["user_id"] = user.id
        session["user_email"] = user.email
        session["user_role"] = user.role
        flash("Logged in successfully", "success")
        # THE FIX: Redirect to the new main dashboard
        return redirect(url_for("home"))
    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("auth.login"))

@auth_bp.route("/dashboard")
def dashboard():
    if session.get("user_role") != "admin":
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for("home"))

    db = SessionLocal()
    try:
        meetings = db.query(MeetingLog).order_by(desc(MeetingLog.meeting_time)).limit(200).all()
        return render_template("dashboard.html", meetings=meetings)
    except Exception as e:
        print(f"[❌ Error loading dashboard] {e}")
        flash("Failed to load dashboard.", "danger")
        return redirect(url_for("home"))
    finally:
        db.close()

@auth_bp.route("/meetings")
def meetings():
    db = SessionLocal()
    try:
        query = db.query(ScheduledMeeting)
        
        # Role-based access control
        if session.get("user_role") != "admin":
            user_email = session.get("user_email")
            query = query.filter(
                or_(
                    ScheduledMeeting.created_by_email == user_email,
                    ScheduledMeeting.participants.contains(f'"{user_email}"')
                )
            )

        scheduled = query.order_by(desc(ScheduledMeeting.created_at)).limit(200).all()
        return render_template("meetings.html", meetings=scheduled)
    except Exception as e:
        print(f"[❌ Error loading meetings] {e}")
        flash("Failed to load meetings.", "danger")
        return redirect(url_for("home"))
    finally:
        db.close()

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
        api_base_url = os.getenv('API_BASE_URL')
        res = requests.delete(f"{api_base_url}/api/cancel-meeting/{meeting_id}")
        res.raise_for_status()
        flash("Meeting cancelled successfully.", "success")
    except requests.exceptions.RequestException as e:
        flash(f"Failed to cancel meeting: {str(e)}", "danger")

    return redirect(url_for("auth.meetings"))