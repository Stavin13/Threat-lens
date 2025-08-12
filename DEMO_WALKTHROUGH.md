# ThreatLens Demo Walkthrough

This document provides a comprehensive walkthrough of the ThreatLens demo, showcasing how the system transforms raw security logs into actionable intelligence using AI-powered analysis.

## Overview

ThreatLens demonstrates the power of AI-enhanced security log analysis by:
- Processing raw macOS system and authentication logs
- Parsing unstructured log data into structured security events
- Applying AI analysis to assess severity and provide explanations
- Generating actionable recommendations for security incidents
- Creating automated reports and real-time dashboards

## Demo Setup Instructions

### Prerequisites

1. **Python Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env file with your Groq API key
   ```

3. **Database Initialization**
   ```bash
   python app/init_db.py
   ```

### Loading Demo Data

#### Option 1: Using the Demo Data Loader Script

```bash
# Load demo data (keeps existing data)
python demo_data_loader.py

# Load demo data and clear existing data first
python demo_data_loader.py --clear

# Load demo data with minimal output
python demo_data_loader.py --quiet
```

#### Option 2: Using the API Endpoint

```bash
# Start the FastAPI server
python main.py

# Load demo data via API
curl -X POST "http://localhost:8000/demo/load-sample-data"

# Load demo data and clear existing data
curl -X POST "http://localhost:8000/demo/load-sample-data?clear_existing=true"
```

## Demo Walkthrough

### Step 1: Understanding Raw Log Data

The demo includes two types of macOS log files:

#### System Log (`macos_system.log`)
Contains kernel messages, application events, and security violations:
```
Dec  8 09:19:33 MacBook-Pro sshd[1567]: Failed password for invalid user admin from 192.168.1.100 port 22 ssh2
Dec  8 09:20:01 MacBook-Pro kernel[0]: CODE SIGNING: cs_invalid_page(0x1000): p=1789[GoogleChrome] final status 0x23000200, denying page sending SIGKILL
Dec  8 09:23:12 MacBook-Pro kernel[0]: AMFI: code signature validation failed for /usr/local/bin/suspicious_binary
```

#### Authentication Log (`macos_auth.log`)
Contains authentication attempts, authorization events, and user activities:
```
Dec  8 09:17:22 MacBook-Pro sshd[1567]: Invalid user admin from 192.168.1.100 port 22
Dec  8 09:20:15 MacBook-Pro authd[123]: Failed to authorize right 'system.privilege.admin' by client '/Applications/SuspiciousApp.app/Contents/MacOS/SuspiciousApp' [2001]
Dec  8 09:25:33 MacBook-Pro opendirectoryd[234]: Multiple authentication failures for user 'admin' from source 192.168.1.100
```

### Step 2: Viewing Parsed Events

After processing, raw logs become structured events:

```json
{
  "id": "event_12345",
  "timestamp": "2024-12-08T09:19:33Z",
  "source": "sshd[1567]",
  "message": "Failed password for invalid user admin from 192.168.1.100 port 22 ssh2",
  "category": "authentication",
  "parsed_at": "2024-12-08T10:15:00Z"
}
```

**Value Added:**
- **Structured Data**: Timestamp, source, and category extracted
- **Categorization**: Events classified by type (auth, system, network, etc.)
- **Normalization**: Consistent format across different log sources

### Step 3: AI-Enhanced Analysis

Each event receives AI-powered analysis:

```json
{
  "severity_score": 8,
  "explanation": "This event indicates a brute force attack attempt against an SSH service. An attacker is trying to authenticate using the common 'admin' username, which doesn't exist on this system. The attempt originated from IP 192.168.1.100, suggesting either an internal threat or a compromised internal system.",
  "recommendations": [
    "Block IP address 192.168.1.100 at the firewall level",
    "Review SSH configuration to disable password authentication",
    "Enable SSH key-based authentication only",
    "Implement fail2ban or similar intrusion prevention system",
    "Monitor for additional attempts from this IP range"
  ]
}
```

**Value Added:**
- **Severity Assessment**: 1-10 scale based on threat level
- **Contextual Explanation**: Human-readable analysis of the security event
- **Actionable Recommendations**: Specific steps to address the threat

### Step 4: Comparing Raw vs. Analyzed Data

Use the demo comparison endpoint to see the transformation:

```bash
# Get demo status and sample events
curl "http://localhost:8000/demo/status"

# Compare raw vs analyzed data for a specific event
curl "http://localhost:8000/demo/comparison/{event_id}"
```

The comparison shows:
- **Original log line** (unstructured text)
- **Parsed event data** (structured fields)
- **AI analysis** (severity, explanation, recommendations)
- **Value summary** (what ThreatLens added)

### Step 5: Dashboard Visualization

1. **Start the Frontend**
   ```bash
   cd frontend
   npm install
   npm start
   ```

2. **Access the Dashboard**
   - Open http://localhost:3000
   - View the event table with filtering and sorting
   - Click on events to see detailed AI analysis
   - Observe the severity distribution chart

3. **Key Dashboard Features**
   - **Event Table**: Sortable, filterable list of security events
   - **Severity Chart**: Visual distribution of threat levels
   - **Event Details**: Modal with comprehensive analysis
   - **Real-time Updates**: Live event streaming (if enabled)

### Step 6: Report Generation

Generate PDF reports to see aggregated insights:

```bash
# Generate today's report
curl "http://localhost:8000/report/daily" -o security_report.pdf

# Generate report for specific date
curl "http://localhost:8000/report/daily?report_date=2024-12-08" -o demo_report.pdf
```

Reports include:
- **Executive Summary**: High-level security posture
- **Event Statistics**: Counts by category and severity
- **Top Threats**: Most critical events with details
- **Recommendations**: Prioritized action items
- **Trend Analysis**: Severity distribution charts

## Demo Scenarios

### Scenario 1: SSH Brute Force Attack

**Raw Log:**
```
Dec  8 09:19:33 MacBook-Pro sshd[1567]: Failed password for invalid user admin from 192.168.1.100 port 22 ssh2
Dec  8 09:19:45 MacBook-Pro sshd[1568]: Failed password for invalid user root from 192.168.1.100 port 22 ssh2
```

**ThreatLens Analysis:**
- **Severity**: 8/10 (High)
- **Category**: Authentication
- **Explanation**: Coordinated brute force attack using common usernames
- **Recommendations**: IP blocking, SSH hardening, intrusion prevention

### Scenario 2: Code Signing Violation

**Raw Log:**
```
Dec  8 09:23:12 MacBook-Pro kernel[0]: AMFI: code signature validation failed for /usr/local/bin/suspicious_binary
```

**ThreatLens Analysis:**
- **Severity**: 9/10 (Critical)
- **Category**: Security
- **Explanation**: Unsigned binary execution attempt, potential malware
- **Recommendations**: Binary analysis, system scan, policy enforcement

### Scenario 3: Privilege Escalation Attempt

**Raw Log:**
```
Dec  8 09:37:11 MacBook-Pro sudo[2567]: user2 : command not allowed ; TTY=ttys002 ; PWD=/Users/user2 ; USER=root ; COMMAND=/bin/rm -rf /
```

**ThreatLens Analysis:**
- **Severity**: 10/10 (Critical)
- **Category**: System
- **Explanation**: Attempted system destruction via privilege escalation
- **Recommendations**: User investigation, access review, incident response

## API Endpoints for Demo

### Demo Status
```bash
GET /demo/status
```
Returns demo data availability and statistics.

### Sample Logs
```bash
GET /demo/sample-logs
```
Lists available sample log files with metadata.

### Raw vs. Analyzed Comparison
```bash
GET /demo/comparison/{event_id}
```
Shows transformation from raw log to AI analysis.

### Load Demo Data
```bash
POST /demo/load-sample-data?clear_existing=false
```
Loads sample data into the system.

## Key Demo Talking Points

### 1. **Time Savings**
- **Before**: Manual log review takes hours
- **After**: Automated analysis in seconds

### 2. **Expertise Amplification**
- **Before**: Requires deep security knowledge
- **After**: AI provides expert-level analysis

### 3. **Actionable Intelligence**
- **Before**: Raw logs provide limited context
- **After**: Specific recommendations for each threat

### 4. **Scalability**
- **Before**: Limited by human analyst capacity
- **After**: Processes thousands of events automatically

### 5. **Consistency**
- **Before**: Analysis quality varies by analyst
- **After**: Consistent AI-powered assessment

## Troubleshooting

### Demo Data Not Loading
```bash
# Check if sample log files exist
ls -la data/sample_logs/

# Verify database connection
python -c "from app.database import check_database_health; print(check_database_health())"

# Check API key configuration
python -c "import os; print('GROQ_API_KEY' in os.environ)"
```

### API Errors
```bash
# Check server logs
tail -f logs/threatlens.log

# Verify database schema
python app/init_db.py

# Test API connectivity
curl http://localhost:8000/health
```

### Frontend Issues
```bash
# Check React development server
cd frontend && npm start

# Verify API connection
curl http://localhost:8000/demo/status
```

## Next Steps

After the demo, users can:

1. **Upload Real Logs**: Use their own security logs
2. **Customize Analysis**: Adjust AI prompts and severity rules
3. **Configure Alerts**: Set up real-time notifications
4. **Schedule Reports**: Automate daily/weekly reporting
5. **Integrate Systems**: Connect to SIEM or other security tools

## Demo Script

### Opening (2 minutes)
"Today I'll show you ThreatLens, an AI-powered security log analyzer that transforms raw logs into actionable intelligence. We'll see how it processes real macOS security logs and provides expert-level analysis automatically."

### Raw Data Review (3 minutes)
"Let's start with raw security logs. Here we have typical macOS system and authentication logs - dense, unstructured text that's difficult to analyze manually. Notice the SSH brute force attempts, code signing violations, and privilege escalation attempts buried in the noise."

### Processing Demo (5 minutes)
"Watch as ThreatLens processes these logs. First, it parses the unstructured text into structured events. Then, AI analyzes each event for severity and provides detailed explanations. Finally, it generates specific recommendations for each threat."

### Dashboard Walkthrough (5 minutes)
"The dashboard provides immediate visibility into your security posture. Events are sorted by severity, with filtering and search capabilities. Click any event to see the AI analysis - notice how it explains the threat and provides actionable recommendations."

### Report Generation (3 minutes)
"ThreatLens automatically generates daily PDF reports with executive summaries, trend analysis, and prioritized recommendations. These reports are perfect for management briefings and compliance documentation."

### Value Proposition (2 minutes)
"ThreatLens transforms hours of manual log analysis into seconds of automated intelligence. It amplifies security expertise, provides consistent analysis, and scales to handle thousands of events. The result is faster threat detection and more effective incident response."

---

*This demo showcases ThreatLens capabilities using realistic but simulated security events. For production use, integrate with your actual log sources and customize analysis parameters for your environment.*