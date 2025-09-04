#!/bin/bash

# ThreatLens Quick Start Script

set -e

echo "🚀 ThreatLens Quick Start"
echo "========================="

# Check if we're in the right directory
if [ ! -d "frontend" ] || [ ! -d "backend" ]; then
    echo "❌ Error: Please run this script from the ThreatLens root directory"
    exit 1
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if port is in use
port_in_use() {
    lsof -i :$1 >/dev/null 2>&1
}

# Function to kill process on port
kill_port() {
    if port_in_use $1; then
        echo "Killing process on port $1..."
        # First try graceful shutdown
        lsof -ti :$1 | xargs kill -TERM 2>/dev/null || true
        sleep 3
        
        # If still running, force kill
        if port_in_use $1; then
            echo "Force killing process on port $1..."
            lsof -ti :$1 | xargs kill -9 2>/dev/null || true
            sleep 2
        fi
        
        # Verify port is free
        if port_in_use $1; then
            echo "⚠️  Warning: Could not free port $1"
        else
            echo "✅ Port $1 is now free"
        fi
    fi
}

# Check prerequisites
echo "🔍 Checking prerequisites..."

if ! command_exists python3; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

if ! command_exists node; then
    echo "❌ Node.js is required but not installed"
    exit 1
fi

if ! command_exists npm; then
    echo "❌ npm is required but not installed"
    exit 1
fi

echo "✅ Prerequisites check passed"

# Clean up any existing processes
echo ""
echo "🧹 Cleaning up existing processes..."
kill_port 8000
kill_port 3000

# Setup backend
echo ""
echo "🔧 Setting up backend..."
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Verify virtual environment is active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ Failed to activate virtual environment"
    exit 1
fi

echo "✅ Virtual environment activated: $VIRTUAL_ENV"

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Setup environment
echo "Setting up environment..."
if [ -f "setup_env.py" ]; then
    python setup_env.py
else
    echo "⚠️  setup_env.py not found, skipping environment setup"
fi

echo "✅ Backend setup complete"

# Setup frontend
echo ""
echo "🎨 Setting up frontend..."
cd ../frontend

# Install Node dependencies
echo "Installing Node.js dependencies..."
npm install

echo "✅ Frontend setup complete"

# Start services
echo ""
echo "🚀 Starting services..."

# Start backend in background
echo "Starting backend server on http://localhost:8000..."
cd ../backend

# Ensure virtual environment is activated and start uvicorn
if command_exists uvicorn; then
    echo "Starting with uvicorn..."
    source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
else
    echo "Starting with python main.py..."
    source venv/bin/activate && python main.py &
    BACKEND_PID=$!
fi

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 3

# Test backend health with better error reporting
echo "Testing backend health..."
for i in {1..15}; do
    if curl -f http://localhost:8000/health-simple >/dev/null 2>&1; then
        echo "✅ Backend is healthy"
        break
    fi
    
    # Check if backend process is still running
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "❌ Backend process died unexpectedly"
        echo "Check backend logs for errors"
        exit 1
    fi
    
    if [ $i -eq 15 ]; then
        echo "❌ Backend failed to start properly after 30 seconds"
        echo "Backend process is running but not responding on port 8000"
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
    
    echo "  Attempt $i/15: Backend not ready yet, waiting..."
    sleep 2
done

# Start frontend in background
echo "Starting frontend server on http://localhost:3000..."
cd ../frontend
npm run dev &
FRONTEND_PID=$!

# Wait for frontend to start
echo "Waiting for frontend to start..."
sleep 8

# Test frontend
for i in {1..10}; do
    if curl -f http://localhost:3000 >/dev/null 2>&1; then
        echo "✅ Frontend is running"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Frontend failed to start properly"
        kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
        exit 1
    fi
    sleep 2
done

# Setup console integration
echo ""
echo "🔧 Setting up console integration..."
cd ../backend
if [ -f "scripts/console_integration.py" ]; then
    echo "Running console integration setup..."
    python scripts/console_integration.py &
    CONSOLE_PID=$!
    echo "✅ Console integration started"
else
    echo "⚠️  Console integration script not found, skipping"
    CONSOLE_PID=""
fi

echo ""
echo "🎉 ThreatLens is running successfully!"
echo ""
echo "📊 Services:"
echo "  • Backend API: http://localhost:8000"
echo "  • Frontend UI: http://localhost:3000"
echo "  • API Documentation: http://localhost:8000/docs"
echo "  • Interactive API: http://localhost:8000/redoc"
echo ""
echo "🔧 Console Integration:"
if [ -n "$CONSOLE_PID" ]; then
    echo "  ✅ Console integration is running (PID: $CONSOLE_PID)"
else
    echo "  ⚠️  Console integration not available"
    echo "  📝 To run manually: cd backend && python scripts/console_integration.py"
fi
echo ""
echo "🧪 Quick Tests:"
echo "  • Backend health: curl http://localhost:8000/health-simple"
echo "  • API stats: curl http://localhost:8000/stats"
echo "  • Frontend: curl http://localhost:3000"
echo ""
echo "⏹️  To stop all services:"
if [ -n "$CONSOLE_PID" ]; then
    echo "  kill $BACKEND_PID $FRONTEND_PID $CONSOLE_PID"
else
    echo "  kill $BACKEND_PID $FRONTEND_PID"
fi
echo "  Or press Ctrl+C to stop this script"
echo ""
echo "📝 Check the logs above for any errors"
echo "🌐 Open http://localhost:3000 in your browser to get started!"

# Trap to clean up on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    if [ -n "$CONSOLE_PID" ]; then
        kill $CONSOLE_PID 2>/dev/null || true
    fi
    echo "✅ Services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Keep script running and show live status
echo ""
echo "📊 Live Status (press Ctrl+C to stop):"
while true; do
    sleep 30
    echo "$(date): Checking services..."
    
    # Check backend
    if curl -f http://localhost:8000/health-simple >/dev/null 2>&1; then
        echo "  ✅ Backend: healthy"
    else
        echo "  ❌ Backend: not responding"
    fi
    
    # Check frontend
    if curl -f http://localhost:3000 >/dev/null 2>&1; then
        echo "  ✅ Frontend: healthy"
    else
        echo "  ❌ Frontend: not responding"
    fi
done