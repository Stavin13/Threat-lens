#!/bin/bash

echo "🔍 Checking ThreatLens Services"
echo "==============================="

# Check backend
echo "Backend (port 8000):"
if curl -s http://localhost:8000/health-simple >/dev/null 2>&1; then
    echo "  ✅ Backend is running and healthy"
    curl -s http://localhost:8000/health-simple | jq .
else
    echo "  ❌ Backend is not responding"
fi

echo ""

# Check frontend
echo "Frontend (port 3000):"
if curl -s http://localhost:3000 >/dev/null 2>&1; then
    echo "  ✅ Frontend is running"
else
    echo "  ❌ Frontend is not responding"
fi

echo ""
echo "🌐 URLs:"
echo "  Frontend: http://localhost:3000"
echo "  Backend API: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"