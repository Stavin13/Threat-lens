#!/bin/bash

echo "🚀 Starting ThreatLens Backend..."

cd backend

# Activate virtual environment
source venv/bin/activate

# Check if uvicorn is available
if command -v uvicorn >/dev/null 2>&1; then
    echo "Starting with uvicorn..."
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
else
    echo "Starting with python..."
    python main.py
fi