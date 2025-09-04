#!/bin/bash

echo "🚀 ThreatLens Quick Start Guide"
echo "==============================="
echo ""
echo "To start ThreatLens, you need to run both backend and frontend:"
echo ""
echo "1. Open a new terminal and run:"
echo "   ./start-backend.sh"
echo ""
echo "2. Open another terminal and run:"
echo "   ./start-frontend.sh"
echo ""
echo "3. Once both are running, visit:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "4. To add test data, run:"
echo "   ./test-data.sh"
echo ""
echo "Press any key to start the backend in this terminal..."
read -n 1 -s

echo ""
echo "Starting backend..."
./start-backend.sh