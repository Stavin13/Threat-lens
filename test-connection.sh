#!/bin/bash

echo "Testing ThreatLens Frontend-Backend Connection..."

# Stop existing containers
echo "Stopping existing containers..."
docker-compose down

# Rebuild containers
echo "Rebuilding containers..."
docker-compose build --no-cache

# Start containers
echo "Starting containers..."
docker-compose up -d

# Wait for services to start
echo "Waiting for services to start..."
sleep 30

# Test backend health
echo "Testing backend health..."
curl -f http://localhost:8000/health-simple || echo "Backend health check failed"

# Test frontend
echo "Testing frontend..."
curl -f http://localhost:3000/ || echo "Frontend check failed"

# Test API proxy through frontend
echo "Testing API proxy through frontend..."
curl -f http://localhost:3000/api/health-simple || echo "API proxy check failed"

echo "Connection test complete!"
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8000"
echo "Backend Docs: http://localhost:8000/docs"