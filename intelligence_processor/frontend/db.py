# frontend/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# It's better to import Base from your models file to ensure everything is linked
from models import Base

DATABASE_URL = os.getenv("POSTGRES_URL")

if not DATABASE_URL:
    raise ValueError("POSTGRES_URL environment variable is not set.")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# This function will be used by FastAPI to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()