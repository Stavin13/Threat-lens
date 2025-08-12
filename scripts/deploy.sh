#!/bin/bash

# ThreatLens Deployment Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-development}
COMPOSE_FILE="docker-compose.yml"

if [ "$ENVIRONMENT" = "production" ]; then
    COMPOSE_FILE="docker-compose.prod.yml"
fi

echo -e "${GREEN}🚀 Deploying ThreatLens in $ENVIRONMENT mode${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating from .env.example${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Please edit .env file with your configuration before continuing.${NC}"
    read -p "Press enter to continue after editing .env file..."
fi

# Create necessary directories
echo -e "${GREEN}📁 Creating directories...${NC}"
mkdir -p data/reports logs

# Build and start services
echo -e "${GREEN}🔨 Building and starting services...${NC}"
docker-compose -f $COMPOSE_FILE down --remove-orphans
docker-compose -f $COMPOSE_FILE build --no-cache
docker-compose -f $COMPOSE_FILE up -d

# Wait for services to be healthy
echo -e "${GREEN}⏳ Waiting for services to be healthy...${NC}"
sleep 10

# Check service health
echo -e "${GREEN}🏥 Checking service health...${NC}"
if docker-compose -f $COMPOSE_FILE ps | grep -q "unhealthy"; then
    echo -e "${RED}❌ Some services are unhealthy. Check logs:${NC}"
    docker-compose -f $COMPOSE_FILE logs --tail=50
    exit 1
fi

# Initialize database if needed
echo -e "${GREEN}🗄️  Initializing database...${NC}"
docker-compose -f $COMPOSE_FILE exec backend python setup_env.py

# Run health check
echo -e "${GREEN}🔍 Running health check...${NC}"
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is healthy${NC}"
else
    echo -e "${RED}❌ Backend health check failed${NC}"
    exit 1
fi

if curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend is healthy${NC}"
else
    echo -e "${RED}❌ Frontend health check failed${NC}"
    exit 1
fi

echo -e "${GREEN}🎉 ThreatLens deployed successfully!${NC}"
echo -e "${GREEN}📊 Dashboard: http://localhost:3000${NC}"
echo -e "${GREEN}🔧 API: http://localhost:8000${NC}"
echo -e "${GREEN}📖 API Docs: http://localhost:8000/docs${NC}"

if [ "$ENVIRONMENT" = "development" ]; then
    echo -e "${YELLOW}💡 Development mode: Code changes will require rebuild${NC}"
    echo -e "${YELLOW}💡 To view logs: docker-compose logs -f${NC}"
    echo -e "${YELLOW}💡 To stop: docker-compose down${NC}"
fi