# ThreatLens Development Guide

This guide covers development workflows for the ThreatLens project with the new frontend/backend structure.

## 📁 Project Structure

```
threatlens/
├── frontend/                  # React TypeScript frontend
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── hooks/            # Custom React hooks
│   │   ├── services/         # API services
│   │   └── types/            # TypeScript definitions
│   ├── public/               # Static assets
│   ├── package.json          # Frontend dependencies
│   └── README.md             # Frontend documentation
│
├── backend/                   # FastAPI Python backend
│   ├── app/                  # Main application code
│   │   ├── realtime/         # Real-time processing
│   │   ├── migrations/       # Database migrations
│   │   ├── models.py         # Database models
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── parser.py         # Log parsing engine
│   │   └── ...               # Other modules
│   ├── tests/                # Backend tests
│   ├── data/                 # Sample data and logs
│   ├── scripts/              # Utility scripts
│   ├── examples/             # Usage examples
│   ├── logs/                 # Application logs
│   ├── main.py               # API server entry point
│   ├── requirements.txt      # Python dependencies
│   └── README.md             # Backend documentation
│
├── docs/                     # Project documentation
├── docker-compose.yml        # Development Docker setup
├── docker-compose.prod.yml   # Production Docker setup
├── Dockerfile.backend        # Backend Docker image
├── Dockerfile.frontend       # Frontend Docker image
├── Makefile                  # Development commands
├── start.sh                  # Quick start script
└── README.md                 # Main project documentation
```

## 🚀 Quick Start

### Option 1: Quick Start Script
```bash
./start.sh
```

### Option 2: Manual Setup

#### Backend Setup
```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
python setup_env.py

# Start development server
python main.py
```

#### Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev  # or npm start
```

### Option 3: Docker Setup
```bash
# Build and start all services
docker-compose up --build

# Or use Makefile
make build
make start
```

## 🛠️ Development Workflows

### Backend Development

#### Running the Backend
```bash
cd backend

# Activate virtual environment
source venv/bin/activate

# Development server with auto-reload
python main.py

# Or with uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Testing
```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_parser.py

# Run tests with verbose output
pytest -v
```

#### Database Operations
```bash
cd backend

# Initialize database
python setup_env.py

# Reset database
rm -f data/threatlens.db*
python setup_env.py

# Run migrations
python -c "from app.migrations.runner import run_migrations; run_migrations()"
```

#### Console Integration Testing
```bash
cd backend

# Test Console log parsing
python demo_console_integration.py

# Live Console integration
python scripts/console_integration.py

# Export Console logs
python scripts/console_log_exporter.py --mode security --hours 24
```

### Frontend Development

#### Running the Frontend
```bash
cd frontend

# Development server
npm start
# or
npm run dev

# Build for production
npm run build

# Run tests
npm test

# Run tests with coverage
npm test -- --coverage
```

#### Adding New Components
```bash
cd frontend/src/components

# Create new component
mkdir NewComponent
touch NewComponent/NewComponent.tsx
touch NewComponent/NewComponent.test.tsx
touch NewComponent/index.ts
```

#### TypeScript Development
```bash
cd frontend

# Type checking
npx tsc --noEmit

# Linting
npm run lint

# Formatting
npm run format
```

## 🧪 Testing

### Backend Testing
```bash
cd backend

# Unit tests
pytest tests/test_parser.py
pytest tests/test_analyzer.py

# Integration tests
pytest tests/test_api.py
pytest tests/test_realtime_integration.py

# Performance tests
python tests/stress_test_realtime_system.py

# Security tests
pytest tests/test_security_auth.py
```

### Frontend Testing
```bash
cd frontend

# Unit tests
npm test

# Component tests
npm test -- --testPathPattern=components

# Integration tests
npm test -- --testPathPattern=integration

# E2E tests (if configured)
npm run test:e2e
```

## 🔧 Configuration

### Backend Configuration
Edit `backend/.env`:
```bash
# Database
DATABASE_URL=sqlite:///./threatlens.db

# Security
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret

# API Settings
DEBUG=true
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000

# Real-time
REALTIME_ENABLED=true
WEBSOCKET_ENABLED=true
```

### Frontend Configuration
The frontend automatically connects to `http://localhost:8000`. For custom API URLs, edit `frontend/src/services/api.ts`.

## 📦 Building and Deployment

### Development Build
```bash
# Backend (no build needed for development)
cd backend && python main.py

# Frontend
cd frontend && npm start
```

### Production Build
```bash
# Backend with Gunicorn
cd backend
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000

# Frontend
cd frontend
npm run build
# Serve build/ directory with nginx or similar
```

### Docker Build
```bash
# Development
docker-compose up --build

# Production
docker-compose -f docker-compose.prod.yml up --build
```

## 🔍 Debugging

### Backend Debugging
```bash
cd backend

# Enable debug logging
export LOG_LEVEL=DEBUG
python main.py

# Use Python debugger
python -m pdb main.py

# Check logs
tail -f logs/threatlens.log
```

### Frontend Debugging
```bash
cd frontend

# Development server with source maps
npm start

# Check browser console for errors
# Use React Developer Tools browser extension
```

### API Testing
```bash
# Test API endpoints
curl -X GET http://localhost:8000/health
curl -X GET http://localhost:8000/docs

# Test log ingestion
curl -X POST -H "Content-Type: application/json" \
  -d '{"content":"test log","source":"test"}' \
  http://localhost:8000/api/ingest/text
```

## 🚀 Adding New Features

### Backend Feature Development
1. **Models**: Add to `backend/app/models.py`
2. **Schemas**: Add to `backend/app/schemas.py`
3. **API Routes**: Create new module in `backend/app/`
4. **Tests**: Add to `backend/tests/`
5. **Documentation**: Update API docs

### Frontend Feature Development
1. **Components**: Add to `frontend/src/components/`
2. **Services**: Add API calls to `frontend/src/services/`
3. **Types**: Add TypeScript types to `frontend/src/types/`
4. **Tests**: Add component tests
5. **Routes**: Update `frontend/src/App.tsx`

## 📊 Monitoring and Logging

### Backend Monitoring
- **Health Check**: `GET /health`
- **Metrics**: `GET /metrics` (if enabled)
- **Logs**: `backend/logs/threatlens.log`
- **Real-time Status**: WebSocket at `/ws`

### Frontend Monitoring
- **Console Logs**: Browser developer tools
- **Network Requests**: Browser network tab
- **Performance**: React DevTools Profiler

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Develop** following the patterns above
4. **Test** your changes: `make test`
5. **Commit** your changes: `git commit -m 'Add amazing feature'`
6. **Push** to the branch: `git push origin feature/amazing-feature`
7. **Open** a Pull Request

## 📚 Useful Commands

### Makefile Commands
```bash
make help           # Show all available commands
make install        # Install all dependencies
make dev-backend    # Start backend development server
make dev-frontend   # Start frontend development server
make test           # Run all tests
make build          # Build Docker images
make start          # Start with Docker
make clean          # Clean up Docker resources
```

### Direct Commands
```bash
# Backend
cd backend && python main.py
cd backend && pytest
cd backend && python scripts/console_integration.py

# Frontend
cd frontend && npm start
cd frontend && npm test
cd frontend && npm run build

# Docker
docker-compose up -d
docker-compose logs -f
docker-compose down
```

This structure provides clear separation between frontend and backend while maintaining easy development workflows.