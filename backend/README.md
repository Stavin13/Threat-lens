# ThreatLens Backend

This is the backend API server for ThreatLens, built with FastAPI and Python.

## Features

- **Log Ingestion**: Upload and process security logs
- **Real-time Analysis**: AI-powered threat detection
- **WebSocket API**: Real-time updates and notifications
- **Console Integration**: macOS Console log support
- **Database**: SQLite with SQLAlchemy ORM
- **Authentication**: JWT-based auth system
- **Monitoring**: Health checks and metrics

## Quick Start

### Prerequisites

- Python 3.8+
- Virtual environment (recommended)

### Installation

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment**:
   ```bash
   python setup_env.py
   ```

4. **Initialize database**:
   ```bash
   python -c "from app.database import init_db; init_db()"
   ```

### Running the Server

```bash
# Development server
python main.py

# Production server (with Gunicorn)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Project Structure

```
backend/
├── app/                    # Main application code
│   ├── realtime/          # Real-time processing
│   ├── migrations/        # Database migrations
│   ├── models.py          # Database models
│   ├── schemas.py         # Pydantic schemas
│   ├── parser.py          # Log parsing engine
│   ├── analyzer.py        # Threat analysis
│   └── ...
├── tests/                 # Test suite
├── data/                  # Sample data and logs
├── scripts/               # Utility scripts
├── examples/              # Usage examples
├── logs/                  # Application logs
├── main.py               # Application entry point
└── requirements.txt      # Python dependencies
```

## API Endpoints

### Core Endpoints
- `POST /api/ingest/file` - Upload log file
- `POST /api/ingest/text` - Submit log text
- `POST /api/parse/{raw_log_id}` - Parse raw logs
- `POST /api/analyze/{raw_log_id}` - Analyze events
- `GET /api/events/{raw_log_id}` - Get analysis results

### Real-time Endpoints
- `WebSocket /ws` - Real-time updates
- `GET /api/realtime/status` - System status
- `POST /api/realtime/start` - Start monitoring
- `POST /api/realtime/stop` - Stop monitoring

### Console Integration
- Use `scripts/console_integration.py` for macOS Console logs
- Use `scripts/console_log_exporter.py` for log export

## Configuration

Environment variables (`.env`):
```bash
DATABASE_URL=sqlite:///./threatlens.db
SECRET_KEY=your-secret-key
DEBUG=true
LOG_LEVEL=INFO
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_parser.py
```

## Console Integration

The backend supports macOS Console logs with enhanced parsing:

```bash
# Quick integration
python scripts/console_integration.py

# Security monitoring
python scripts/console_integration.py --mode security --hours 24

# Process monitoring
python scripts/console_integration.py --mode process --process sshd
```

## Development

### Adding New Features

1. **Models**: Add to `app/models.py`
2. **Schemas**: Add to `app/schemas.py`
3. **API Routes**: Add to appropriate module in `app/`
4. **Tests**: Add to `tests/`

### Database Migrations

```bash
# Create migration
python -c "from app.migrations.runner import create_migration; create_migration('description')"

# Run migrations
python -c "from app.migrations.runner import run_migrations; run_migrations()"
```

## Deployment

See `../DEPLOYMENT.md` for production deployment instructions.

## Monitoring

- **Health Endpoint**: `/health`
- **Metrics**: `/metrics` (if enabled)
- **Logs**: Check `logs/` directory
- **Real-time Status**: WebSocket connection at `/ws`