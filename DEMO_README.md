# ThreatLens Demo Setup

This guide helps you quickly set up and run the ThreatLens demo to see AI-powered security log analysis in action.

## Quick Start

### 1. Automated Setup (Recommended)

```bash
# Clone and navigate to the project
git clone <repository-url>
cd threatlens

# Run automated demo setup
python setup_demo.py --auto

# Start the backend server
python main.py

# In another terminal, start the frontend
cd frontend
npm install
npm start
```

### 2. Manual Setup

```bash
# Set up Python environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your Groq API key

# Initialize database
python app/init_db.py

# Load demo data
python demo_data_loader.py

# Start servers (in separate terminals)
python main.py
cd frontend && npm install && npm start
```

## Demo Access Points

- **Backend API**: http://localhost:8000
- **Frontend Dashboard**: http://localhost:3000  
- **API Documentation**: http://localhost:8000/docs
- **Demo Status**: http://localhost:8000/demo/status

## Demo Features

### 1. Sample Log Processing
- **macOS System Logs**: Kernel messages, security violations, sandbox denials
- **macOS Auth Logs**: SSH attempts, sudo usage, authentication failures
- **Realistic Events**: Brute force attacks, malware detection, privilege escalation

### 2. AI-Powered Analysis
- **Severity Scoring**: 1-10 scale based on threat level
- **Contextual Explanations**: Human-readable security analysis
- **Actionable Recommendations**: Specific remediation steps

### 3. Interactive Dashboard
- **Event Table**: Sortable, filterable security events
- **Severity Charts**: Visual threat distribution
- **Event Details**: Comprehensive AI analysis modal
- **Real-time Updates**: Live event streaming

### 4. Automated Reporting
- **PDF Generation**: Daily security reports
- **Executive Summaries**: High-level security posture
- **Trend Analysis**: Severity distribution over time

## Demo Scenarios

### High-Severity Events (8-10/10)
- SSH brute force attacks from external IPs
- Code signing violations and malware detection
- Privilege escalation attempts
- Unauthorized system access

### Medium-Severity Events (5-7/10)
- Failed authentication attempts
- Sandbox violations
- Suspicious network connections
- Policy violations

### Low-Severity Events (1-4/10)
- Normal system operations
- Routine authentication events
- Standard application behavior
- Informational messages

## API Demo Endpoints

### Demo Status
```bash
curl http://localhost:8000/demo/status
```

### Sample Logs
```bash
curl http://localhost:8000/demo/sample-logs
```

### Raw vs. Analyzed Comparison
```bash
# Get event list first
curl "http://localhost:8000/events?per_page=5"

# Compare specific event
curl "http://localhost:8000/demo/comparison/{event_id}"
```

### Load Fresh Demo Data
```bash
curl -X POST "http://localhost:8000/demo/load-sample-data?clear_existing=true"
```

## Demo Walkthrough Script

### 1. Show Raw Logs (2 minutes)
"Here are typical macOS security logs - dense, unstructured text that's difficult to analyze manually."

```bash
head -10 data/sample_logs/macos_system.log
```

### 2. Process with ThreatLens (3 minutes)
"Watch as ThreatLens transforms these logs into structured events with AI analysis."

```bash
curl -X POST "http://localhost:8000/demo/load-sample-data"
```

### 3. View Analyzed Events (5 minutes)
"Now we have structured events with severity scores and explanations."

```bash
curl "http://localhost:8000/events?sort_by=severity&sort_order=desc&per_page=5"
```

### 4. Compare Raw vs. Analyzed (5 minutes)
"See the transformation from raw log to actionable intelligence."

```bash
curl "http://localhost:8000/demo/comparison/{event_id}"
```

### 5. Dashboard Demo (5 minutes)
Open http://localhost:3000 and show:
- Event filtering and sorting
- Severity distribution chart
- Detailed event analysis modal

### 6. Generate Report (2 minutes)
"Automated PDF reports provide executive summaries and trend analysis."

```bash
curl "http://localhost:8000/report/daily" -o demo_report.pdf
```

## Troubleshooting

### Common Issues

#### Demo Data Not Loading
```bash
# Check sample log files
ls -la data/sample_logs/

# Verify database
python -c "from app.database import check_database_health; print(check_database_health())"

# Check API key
python -c "import os; print('GROQ_API_KEY' in os.environ)"
```

#### API Connection Errors
```bash
# Check server status
curl http://localhost:8000/health

# View server logs
tail -f logs/threatlens.log
```

#### Frontend Issues
```bash
# Check React server
cd frontend && npm start

# Verify API connection
curl http://localhost:8000/demo/status
```

### Reset Demo Environment
```bash
# Clear all data and reload
python demo_data_loader.py --clear

# Or via API
curl -X POST "http://localhost:8000/demo/load-sample-data?clear_existing=true"
```

## Demo Data Statistics

The demo includes approximately:
- **60+ log entries** across system and auth logs
- **40+ parsed events** with structured data
- **35+ AI analyses** with severity scores
- **8 event categories**: Authentication, System, Network, Security, etc.
- **Severity range**: 1-10 with realistic distribution

## Key Demo Messages

### Value Proposition
- **Time Savings**: Hours of manual analysis → Seconds of automated intelligence
- **Expertise Amplification**: AI provides expert-level security analysis
- **Scalability**: Handles thousands of events automatically
- **Consistency**: Reliable, repeatable threat assessment

### Technical Benefits
- **Structured Data**: Raw logs → Organized events
- **Contextual Analysis**: Technical details → Business impact
- **Actionable Intelligence**: Observations → Specific recommendations
- **Automated Reporting**: Manual compilation → Automated insights

## Next Steps After Demo

1. **Upload Real Logs**: Process your actual security logs
2. **Customize Analysis**: Adjust AI prompts for your environment
3. **Configure Alerts**: Set up real-time notifications
4. **Schedule Reports**: Automate daily/weekly reporting
5. **Integrate Systems**: Connect to SIEM or other security tools

## Support

For demo support or questions:
- Check the full walkthrough: `DEMO_WALKTHROUGH.md`
- Review API documentation: http://localhost:8000/docs
- Examine sample data: `data/sample_logs/`

---

*This demo uses realistic but simulated security events for demonstration purposes. Production deployment should use actual log sources and customized analysis parameters.*