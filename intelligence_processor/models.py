# models.py
import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False) # In your schema, but named password_hash in auth.py. Renamed for consistency.
    role = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # --- NEW FIELD FOR VOICE PROFILE ---
    voice_profile_id = Column(String, nullable=True, unique=True)

    # Relationship for Phase 2
    training_moments = relationship("TrainingQueue", back_populates="user")

class ScheduledMeeting(Base):
    __tablename__ = 'scheduled_meetings'
    
    meeting_id = Column(String, primary_key=True)
    topic = Column(Text)
    start_time = Column(DateTime)
    duration = Column(Integer)
    agenda = Column(Text)
    participants = Column(Text) # Storing as JSON string
    host_email = Column(String)
    created_by_email = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class MeetingLog(Base):
    __tablename__ = 'meeting_logs'
    
    meeting_id = Column(String, primary_key=True)
    host_email = Column(String)
    summary = Column(Text)
    transcript = Column(Text)
    recipients = Column(Text) 
    meeting_time = Column(DateTime)
    created_by_email = Column(String)
    recording_full_url = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    # --- NEW FIELDS FOR PHASE 2 ---
    subsidiary = Column(String)
    department = Column(String)
    meeting_type = Column(String)
    meeting_subtype = Column(String)
    tags = Column(JSONB) # Using JSONB for better tag querying
    key_decisions = Column(JSONB)
    enriched_output_path = Column(Text) # Path to the final JSON in blob storage

    # Relationship for Phase 2
    training_moments = relationship("TrainingQueue", back_populates="meeting")

    __table_args__ = (
        Index('idx_meeting_created_at', created_at.desc()),
    )


class MeetingProcessingLog(Base):
    __tablename__ = 'meeting_processing_log'
    
    meeting_id = Column(String, primary_key=True)
    processed_at = Column(DateTime, default=datetime.datetime.utcnow)

# --- NEW TABLE FOR PHASE 2 ---
class TrainingQueue(Base):
    __tablename__ = 'training_queue'
    
    id = Column(Integer, primary_key=True)
    meeting_id = Column(String, ForeignKey('meeting_logs.meeting_id'), nullable=False)
    participant_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    coaching_category = Column(String(255), nullable=False)
    status = Column(String(50), default='Pending Review')
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships to easily access related objects
    meeting = relationship("MeetingLog", back_populates="training_moments")
    user = relationship("User", back_populates="training_moments")