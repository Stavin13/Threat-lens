#!/bin/bash

# ThreatLens Development Setup Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🛠️  Setting up ThreatLens development environment${NC}"

# Check prerequisites
echo -e "${GREEN}🔍 Checking prerequisites...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    exit 1
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Setup Python virtual environment
echo -e "${GREEN}🐍 Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Setup environment file
echo -e "${GREEN}⚙️  Setting up environment configuration...${NC}"
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Please edit .env file with your GROQ_API_KEY${NC}"
fi

# Create directories
echo -e "${GREEN}📁 Creating directories...${NC}"
mkdir -p data/reports logs data/sample_logs

# Initialize database
echo -e "${GREEN}🗄️  Initializing database...${NC}"
python setup_env.py

# Setup frontend
echo -e "${GREEN}⚛️  Setting up frontend...${NC}"
cd frontend
npm install
cd ..

# Load demo data
echo -e "${GREEN}📊 Loading demo data...${NC}"
python demo_data_loader.py

echo -e "${GREEN}🎉 Development environment setup complete!${NC}"
echo -e "${GREEN}💡 To start development:${NC}"
echo -e "${GREEN}   Backend: uvicorn main:app --reload${NC}"
echo -e "${GREEN}   Frontend: cd frontend && npm start${NC}"
echo -e "${GREEN}💡 Or use Docker: ./scripts/deploy.sh development${NC}"