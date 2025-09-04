#!/bin/bash

echo "🔄 Restarting ThreatLens Backend"
echo "================================"

# Kill any existing backend processes
echo "🛑 Stopping existing backend processes..."
pkill -f "uvicorn main:app" || true
pkill -f "python.*main.py" || true
pkill -f "python.*test-backend.py" || true

# Wait a moment for processes to stop
sleep 3

# Check if port is still in use
if lsof -i :8000 >/dev/null 2>&1; then
    echo "⚠️  Port 8000 still in use, force killing..."
    lsof -ti :8000 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

echo "✅ Old processes stopped"

# Start the backend
echo "🚀 Starting backend with updated rate limiting..."
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload