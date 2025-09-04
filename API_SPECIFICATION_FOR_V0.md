# ThreatLens API Specification for v0.dev

## Base URL
```
http://localhost:8000
```

## Authentication
- JWT-based authentication (optional for development)
- WebSocket connections support token-based auth via query parameter

## Core Endpoints

### 1. Health & Status

#### GET /health-simple
Simple health check for monitoring
```json
{
  "status": "healthy",
  "timestamp": "2025-01-09T10:30:00Z"
}
```

#### GET /health
Comprehensive health check
```json
{
  "status": "healthy",
  "database": {
    "status": "healthy",
    "connection_pool": "active",
    "response_time_ms": 5
  },
  "realtime": {
    "overall_status": "healthy",
    "components": {
      "file_monitor": "running",
      "websocket_manager": "running",
      "ingestion_queue": "running"
    }
  },
  "timestamp": "2025-01-09T10:30:00Z"
}
```

#### GET /stats
System statistics and metrics
```json
{
  "database": {
    "total_raw_logs": 1250,
    "total_events": 3420,
    "total_analyses": 3420,
    "disk_usage_mb": 45.2
  },
  "processing": {
    "total_processed": 1250,
    "success_rate": 98.5,
    "average_processing_time_ms": 150,
    "queue_size": 5
  },
  "api_version": "1.0.0",
  "timestamp": "2025-01-09T10:30:00Z"
}
```

### 2. Log Ingestion

#### POST /ingest-log
Ingest logs via file upload or text content
```bash
# File upload
curl -X POST -F "file=@logfile.log" -F "source=server1" http://localhost:8000/ingest-log

# Text content
curl -X POST -F "content=Jan 15 10:30:45 server sshd: Failed login" -F "source=server1" http://localhost:8000/ingest-log
```

Response:
```json
{
  "raw_log_id": "uuid-string",
  "message": "Log content ingested successfully",
  "events_parsed": 0,
  "ingested_at": "2025-01-09T10:30:00Z"
}
```

### 3. Events Management

#### GET /events
Retrieve paginated list of security events with filtering
```bash
GET /events?page=1&per_page=20&category=auth&min_severity=5&sort_by=timestamp&sort_order=desc
```

Query Parameters:
- `page` (int): Page number (default: 1)
- `per_page` (int): Events per page (default: 20, max: 100)
- `category` (string): Filter by category (auth, system, network, security, application, kernel, unknown)
- `min_severity` (int): Minimum severity score (1-10)
- `max_severity` (int): Maximum severity score (1-10)
- `start_date` (datetime): Start date filter
- `end_date` (datetime): End date filter
- `source` (string): Filter by source
- `sort_by` (string): Sort field (timestamp, severity, source, category)
- `sort_order` (string): Sort order (asc, desc)

Response:
```json
{
  "events": [
    {
      "id": "event-uuid",
      "raw_log_id": "raw-log-uuid",
      "timestamp": "2025-01-09T10:30:00Z",
      "source": "sshd[1234]",
      "message": "Failed password for invalid user admin from 192.168.1.100",
      "category": "auth",
      "parsed_at": "2025-01-09T10:30:05Z",
      "ai_analysis": {
        "id": "analysis-uuid",
        "event_id": "event-uuid",
        "severity_score": 8,
        "explanation": "Multiple failed SSH login attempts from external IP indicate potential brute force attack",
        "recommendations": [
          "Block IP address 192.168.1.100",
          "Enable fail2ban for SSH protection",
          "Review SSH configuration for security hardening"
        ],
        "analyzed_at": "2025-01-09T10:30:10Z"
      }
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 20,
  "total_pages": 8
}
```

#### GET /event/{event_id}
Get detailed information for a specific event
```json
{
  "id": "event-uuid",
  "raw_log_id": "raw-log-uuid",
  "timestamp": "2025-01-09T10:30:00Z",
  "source": "sshd[1234]",
  "message": "Failed password for invalid user admin from 192.168.1.100",
  "category": "auth",
  "parsed_at": "2025-01-09T10:30:05Z",
  "ai_analysis": {
    "id": "analysis-uuid",
    "event_id": "event-uuid",
    "severity_score": 8,
    "explanation": "Multiple failed SSH login attempts from external IP indicate potential brute force attack",
    "recommendations": [
      "Block IP address 192.168.1.100",
      "Enable fail2ban for SSH protection",
      "Review SSH configuration for security hardening"
    ],
    "analyzed_at": "2025-01-09T10:30:10Z"
  }
}
```

### 4. Real-time Monitoring

#### GET /realtime/status
Get real-time system status
```json
{
  "overall_status": "running",
  "components": {
    "file_monitor": {
      "status": "running",
      "monitored_paths": ["/var/log/system.log", "/var/log/auth.log"],
      "files_watched": 2,
      "events_processed": 1250
    },
    "ingestion_queue": {
      "status": "running",
      "queue_size": 5,
      "processed_count": 3420,
      "error_count": 12
    },
    "websocket_manager": {
      "status": "running",
      "active_connections": 3,
      "total_messages_sent": 15420
    }
  },
  "uptime_seconds": 86400,
  "last_activity": "2025-01-09T10:29:55Z"
}
```

#### GET /realtime/monitoring/config
Get monitoring configuration
```json
{
  "log_sources": [
    {
      "id": "source-uuid",
      "name": "System Logs",
      "type": "file",
      "path": "/var/log/system.log",
      "enabled": true,
      "format": "syslog",
      "created_at": "2025-01-09T09:00:00Z"
    }
  ],
  "notification_rules": [
    {
      "id": "rule-uuid",
      "name": "High Severity Alerts",
      "condition": "severity >= 8",
      "enabled": true,
      "channels": ["email", "webhook"],
      "created_at": "2025-01-09T09:00:00Z"
    }
  ]
}
```

#### POST /realtime/monitoring/log-sources
Add new log source for monitoring
```json
{
  "name": "Auth Logs",
  "type": "file",
  "path": "/var/log/auth.log",
  "format": "syslog",
  "enabled": true
}
```

#### GET /realtime/monitoring/metrics
Get processing metrics
```json
{
  "events_per_minute": 45.2,
  "average_processing_time_ms": 150,
  "queue_depth": 5,
  "error_rate_percent": 0.5,
  "memory_usage_mb": 256,
  "cpu_usage_percent": 15.3,
  "timestamp": "2025-01-09T10:30:00Z"
}
```

### 5. Reports & Analytics

#### GET /scheduler/status
Get scheduled report status
```json
{
  "scheduler_running": true,
  "next_report_time": "2025-01-10T00:00:00Z",
  "last_report_time": "2025-01-09T00:00:00Z",
  "total_reports_generated": 30,
  "failed_reports": 1
}
```

#### POST /scheduler/trigger-report
Manually trigger report generation
```json
{
  "success": true,
  "report_date": "2025-01-09",
  "report_file": "daily_report_20250109.json",
  "events_analyzed": 150,
  "threats_detected": 12,
  "generated_at": "2025-01-09T10:30:00Z"
}
```

#### GET /reports/files
Get available report files
```json
[
  {
    "filename": "daily_report_20250109.json",
    "date": "2025-01-09",
    "size_bytes": 15420,
    "events_count": 150,
    "threats_count": 12,
    "created_at": "2025-01-09T00:05:00Z"
  }
]
```

### 6. Processing Control

#### POST /trigger-processing/{raw_log_id}
Manually trigger processing for a specific raw log
```json
{
  "message": "Processing triggered for raw log abc-123",
  "raw_log_id": "abc-123",
  "triggered_at": "2025-01-09T10:30:00Z"
}
```

### 7. WebSocket Real-time Updates

#### WebSocket /ws
Real-time event streaming

Connection:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws?token=optional-jwt-token');
```

Message Types:
```json
// New event detected
{
  "type": "new_event",
  "data": {
    "id": "event-uuid",
    "timestamp": "2025-01-09T10:30:00Z",
    "source": "sshd[1234]",
    "message": "Failed login attempt",
    "category": "auth",
    "severity_score": 8
  }
}

// System status update
{
  "type": "status_update",
  "data": {
    "component": "file_monitor",
    "status": "running",
    "message": "Processing log file /var/log/auth.log"
  }
}

// Processing metrics
{
  "type": "metrics_update",
  "data": {
    "events_per_minute": 45.2,
    "queue_depth": 5,
    "active_connections": 3
  }
}
```

#### GET /ws/info
Get WebSocket server information
```json
{
  "active_connections": 3,
  "total_connections": 150,
  "messages_sent": 15420,
  "uptime_seconds": 86400,
  "server_status": "running"
}
```

## Data Models

### Event Categories
- `auth` - Authentication events
- `system` - System events
- `network` - Network events
- `security` - Security events
- `application` - Application events
- `kernel` - Kernel events
- `unknown` - Uncategorized events

### Severity Levels (1-10)
- 1-2: Very Low
- 3-4: Low
- 5-6: Medium
- 7-8: High
- 9-10: Critical

### Event Structure
```typescript
interface Event {
  id: string;
  raw_log_id: string;
  timestamp: string; // ISO 8601
  source: string;
  message: string;
  category: 'auth' | 'system' | 'network' | 'security' | 'application' | 'kernel' | 'unknown';
  parsed_at: string; // ISO 8601
  ai_analysis?: AIAnalysis;
}

interface AIAnalysis {
  id: string;
  event_id: string;
  severity_score: number; // 1-10
  explanation: string;
  recommendations: string[];
  analyzed_at: string; // ISO 8601
}
```

## Error Responses

All endpoints return consistent error responses:
```json
{
  "error": "ValidationError",
  "message": "Invalid input parameters",
  "timestamp": "2025-01-09T10:30:00Z",
  "details": {
    "field": "category",
    "issue": "Invalid category value"
  }
}
```

HTTP Status Codes:
- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 404: Not Found
- 422: Validation Error
- 500: Internal Server Error

## Rate Limiting
- 120 requests per minute per IP
- Burst limit: 10 requests
- Block duration: 5 minutes

## CORS
Configured for development with React frontend:
- Allowed origins: `http://localhost:3000`, `http://127.0.0.1:3000`
- Allowed methods: GET, POST, PUT, DELETE, OPTIONS
- Credentials: Supported

## Console Integration Endpoints

### POST /api/ingest/text
Specialized endpoint for Console log integration
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"content":"11:28:24.138308+0200 powerd DestinationCheck check on battery 8","source":"console"}' \
  http://localhost:8000/api/ingest/text
```

### Console Log Format Support
The API automatically detects and parses macOS Console logs with format:
```
11:28:24.138308+0200 process_name message content
11:28:24.138308+0200 process_name[pid] message content
```

Features:
- Microsecond precision timestamps
- Timezone-aware parsing
- Automatic UTC conversion
- Process identification
- PID extraction when available

## Frontend Integration Notes

### Key Features to Implement
1. **Dashboard**: Real-time metrics, recent events, system status
2. **Events List**: Paginated table with filtering and sorting
3. **Event Detail**: Detailed view with AI analysis
4. **Log Ingestion**: File upload and text input forms
5. **Real-time Updates**: WebSocket integration for live data
6. **System Monitoring**: Component status and health checks
7. **Reports**: View and download generated reports

### Recommended UI Components
- Data tables with pagination and filtering
- Real-time charts for metrics
- Alert/notification system for high-severity events
- File upload with drag-and-drop
- WebSocket connection status indicator
- Dark/light theme support
- Responsive design for mobile/tablet

### State Management
- Use React Query/SWR for API data fetching
- WebSocket state for real-time updates
- Local state for UI interactions
- Persistent state for user preferences

This specification provides all the endpoints and data structures needed to build a comprehensive security log analysis frontend with v0.dev.