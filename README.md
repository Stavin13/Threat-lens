# ThreatLens

An AI-powered security log analysis system that ingests security logs, parses events, performs AI-driven threat analysis, and generates comprehensive security reports.

## Features

- **Log Ingestion**: Automated ingestion of security logs from multiple sources
- **Event Parsing**: Intelligent parsing of raw logs into structured security events
- **AI Analysis**: Claude-powered threat analysis with severity scoring and recommendations
- **Report Generation**: Automated PDF report generation with security insights
- **REST API**: FastAPI-based REST API for all operations
- **Database**: SQLite database with optimized schema and indexing

## Quick Start

### Prerequisites

- Python 3.8+
- pip or uv package manager

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd threat-lens
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Initialize the database:
```bash
python app/init_db.py
```

4. Start the application:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000` with interactive documentation at `http://localhost:8000/docs`.

## Project Structure

```
threat-lens/
├── app/
│   ├── __init__.py
│   ├── models.py          # SQLAlchemy database models
│   ├── database.py        # Database connection utilities
│   └── init_db.py         # Database initialization script
├── data/                  # Database files (gitignored)
├── reports/              # Generated PDF reports (gitignored)
├── logs/                 # Application logs (gitignored)
├── .kiro/
│   └── specs/
│       └── threat-lens/   # Feature specification documents
├── requirements.txt       # Python dependencies
└── README.md
```

## Database Schema

The system uses four main tables:

- **raw_logs**: Stores ingested raw log data
- **events**: Parsed security events with structured data
- **ai_analysis**: AI-generated threat analysis and recommendations
- **reports**: Tracking information for generated reports

## Development

### Database Management

- Initialize database: `python app/init_db.py`
- Check database health: Use the health check utilities in `app/database.py`

### API Development

The system is built with FastAPI and follows REST API conventions. See the specification documents in `.kiro/specs/threat-lens/` for detailed requirements and design.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license here]