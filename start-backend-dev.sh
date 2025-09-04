#!/bin/bash

echo "🚀 Starting ThreatLens Backend (Development Mode)"
echo "================================================="

cd backend

# Activate virtual environment
source venv/bin/activate

# Clear any existing rate limiting
echo "🔧 Clearing rate limit cache..."
python ../clear-rate-limit.py

echo "🔄 Starting backend with relaxed rate limiting..."
echo "📖 API docs: http://localhost:8000/docs"
echo "🛑 Press Ctrl+C to stop"

# Start with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload