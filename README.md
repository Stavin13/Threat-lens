# ThreatLens - AI-Powered Security Log Analysis

ThreatLens is a comprehensive security log analysis platform that provides real-time threat detection, AI-powered analysis, and intuitive visualization of security events.

## 🚀 Features

- **Real-time Log Processing**: Monitor security logs in real-time
- **AI-Powered Analysis**: Advanced threat detection using machine learning
- **macOS Console Integration**: Native support for macOS Console logs
- **Web Dashboard**: Modern React-based user interface
- **WebSocket API**: Real-time updates and notifications
- **Multi-format Support**: Parse various log formats (syslog, Console, custom)
- **Threat Categorization**: Automatic event classification
- **Historical Analysis**: Search and analyze historical security events

## 📁 Project Structure

```
threatlens/
├── frontend/              # React TypeScript frontend
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── hooks/         # Custom React hooks
│   │   ├── services/      # API services
│   │   └── types/         # TypeScript definitions
│   ├── public/            # Static assets
│   └── package.json       # Frontend dependencies
│
├── backend/               # FastAPI Python backend
│   ├── app/               # Main application code
│   │   ├── realtime/      # Real-time processing
│   │   ├── migrations/    # Database migrations
│   │   └── ...            # Core modules
│   ├── tests/             # Backend tests
│   ├── data/              # Sample data
│   ├── scripts/           # Utility scripts
│   ├── main.py            # API server entry point
│   └── requirements.txt   # Python dependencies
│
├── docs/                  # Documentation
├── docker-compose.yml     # Docker configuration
└── README.md              # This file
```

## 🛠️ Quick Start

### Prerequisites

- **Node.js** 16+ and npm (for frontend)
- **Python** 3.8+ (for backend)
- **Docker** (optional, for containerized deployment)

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
python setup_env.py

# Start the backend server
python main.py
```

Backend will be available at: http://localhost:8000

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will be available at: http://localhost:3000

### 3. Docker Setup (Alternative)

```bash
# Start both frontend and backend
docker-compose up -d

# View logs
docker-compose logs -f
```

## 🔧 Configuration

### Backend Configuration

Copy `backend/.env.example` to `backend/.env` and configure:

```bash
# Database
DATABASE_URL=sqlite:///./threatlens.db

# Security
SECRET_KEY=your-secret-key

# API Settings
DEBUG=true
LOG_LEVEL=INFO
```

### Frontend Configuration

The frontend automatically connects to the backend API. For custom configurations, check `frontend/src/services/api.ts`.

## 📊 Usage

### 1. Log Ingestion

**Web Interface:**
1. Navigate to http://localhost:3000/ingest
2. Upload log files or paste log content
3. Click "Analyze" to process

**API:**
```bash
# Upload file
curl -X POST -F "file=@logfile.log" http://localhost:8000/api/ingest/file

# Submit text
curl -X POST -H "Content-Type: application/json" \
  -d '{"content":"log content","source":"test"}' \
  http://localhost:8000/api/ingest/text
```

### 2. macOS Console Integration

```bash
cd backend

# Analyze recent Console logs
python scripts/console_integration.py

# Security-focused monitoring
python scripts/console_integration.py --mode security --hours 24

# Monitor specific process
python scripts/console_integration.py --mode process --process sshd
```

### 3. Real-time Monitoring

The system supports real-time log monitoring through WebSocket connections. Connect to `ws://localhost:8000/ws` for live updates.

## 🧪 Testing

### Backend Tests

```bash
cd backend
pytest                    # Run all tests
pytest --cov=app         # Run with coverage
pytest tests/test_parser.py  # Run specific test
```

### Frontend Tests

```bash
cd frontend
npm test                  # Run tests
npm run test:coverage    # Run with coverage
```

## 🔍 API Documentation

Once the backend is running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## 🚀 Deployment

### Production Deployment

1. **Backend**: Use Gunicorn with Uvicorn workers
2. **Frontend**: Build and serve with nginx
3. **Database**: Consider PostgreSQL for production
4. **Monitoring**: Set up logging and health checks

See `DEPLOYMENT.md` for detailed deployment instructions.

### Docker Production

```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d
```

## 🛡️ Security Features

- **Authentication**: JWT-based user authentication
- **Input Validation**: Comprehensive input sanitization
- **Rate Limiting**: API rate limiting and abuse prevention
- **CORS**: Configurable cross-origin resource sharing
- **Audit Logging**: Complete audit trail of all actions

## 📈 Performance

- **Concurrent Processing**: Multi-threaded log processing
- **WebSocket Scaling**: Efficient real-time communication
- **Database Optimization**: Indexed queries and connection pooling
- **Caching**: In-memory caching for frequently accessed data

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the `docs/` directory
- **Issues**: Report bugs and request features via GitHub Issues
- **Discussions**: Join community discussions

## 🔄 Recent Updates

- ✅ **macOS Console Integration**: Full support for Console log format
- ✅ **Real-time Processing**: WebSocket-based live monitoring
- ✅ **Enhanced UI**: Modern React dashboard with real-time updates
- ✅ **Security Hardening**: Comprehensive security measures
- ✅ **Performance Optimization**: Improved processing speed and scalability

---

**ThreatLens** - Making security log analysis intelligent and accessible.