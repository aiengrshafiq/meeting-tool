from flask import Blueprint, request, redirect, render_template, session, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from .db import Base, SessionLocal

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
