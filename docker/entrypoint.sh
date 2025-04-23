#!/bin/bash

# Load env vars if needed
export PYTHONPATH=/app

# Start backend API (FastAPI) and frontend (Flask) in background
echo "[🚀] Starting FastAPI on :9000"
uvicorn backend.api:app --host 0.0.0.0 --port 9000 &

echo "[🚀] Starting Flask on :5000"
cd frontend
flask run --host=0.0.0.0 --port=5000
