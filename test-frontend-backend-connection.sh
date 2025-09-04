#!/bin/bash

echo "🔍 Testing Frontend-Backend Connection"
echo "======================================"

echo "1. Testing backend directly..."
echo "Backend health check:"
curl -s http://localhost:8000/health-simple | jq . 2>/dev/null || curl -s http://localhost:8000/health-simple

echo -e "\n2. Testing frontend..."
echo "Frontend response:"
curl -s -I http://localhost:3000 | head -5

echo -e "\n3. Testing if frontend can reach backend API..."
echo "Testing frontend API proxy (if configured):"
curl -s http://localhost:3000/api/health-simple | jq . 2>/dev/null || curl -s http://localhost:3000/api/health-simple

echo -e "\n4. Checking frontend API configuration..."
echo "Checking what API base URL the frontend is using..."