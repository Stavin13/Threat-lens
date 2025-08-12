# ThreatLens Real-Time API Documentation

## Overview

This document provides comprehensive API documentation for ThreatLens real-time monitoring features, including REST endpoints and WebSocket protocols.

## Table of Contents

1. [Authentication](#authentication)
2. [REST API Endpoints](#rest-api-endpoints)
3. [WebSocket API](#websocket-api)
4. [Data Models](#data-models)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)
7. [Examples](#examples)

## Authentication

### API Key Authentication

All API requests require authentication using an API key in the header:

```http
Authorization: Bearer YOUR_API_KEY
```

### WebSocket Authentication

WebSocket connections authenticate using query parameters:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws?token=YOUR_API_KEY');
```

## REST API Endpoints

### Log Source Management

#### List Log Sources

```http
GET /api/log-sources
```

**Response:**
```json
{
  "sources": [
    {
      "id": 1,
      "path": "/var/log/nginx/access.log",
      "source_name": "Nginx Access Logs",
      "enabled": true,
      "file_pattern": "*.log",
      "recursive": false,
      "polling_interval": 1.0,
      "last_monitored": "2024-01-15T10:30:00Z",
      "status": "active",
      "created_at": "2024-01-15T09:00:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

#### Create Log Source

```http
POST /api/log-sources
Content-Type: application/json

{
  "path": "/var/log/myapp/application.log",
  "source_name": "My Application Logs",
  "enabled": true,
  "file_pattern": "*.log",
  "recursive": false,
  "polling_interval": 1.0
}
```

**Response:**
```json
{
  "id": 2,
  "path": "/var/log/myapp/application.log",
  "source_name": "My Application Logs",
  "enabled": true,
  "file_pattern": "*.log",
  "recursive": false,
  "polling_interval": 1.0,
  "status": "pending",
  "created_at": "2024-01-15T11:00:00Z",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

#### Update Log Source

```http
PUT /api/log-sources/{id}
Content-Type: application/json

{
  "enabled": false,
  "polling_interval": 2.0
}
```

#### Delete Log Source

```http
DELETE /api/log-sources/{id}
```

**Response:**
```json
{
  "message": "Log source deleted successfully"
}
```

#### Get Log Source Status

```http
GET /api/log-sources/{id}/status
```

**Response:**
```json
{
  "id": 1,
  "status": "active",
  "last_monitored": "2024-01-15T10:30:00Z",
  "file_size": 1048576,
  "last_offset": 1024000,
  "events_processed": 150,
  "errors": 0,
  "health": "healthy"
}
```

#### Test Log Source

```http
POST /api/log-sources/{id}/test
```

**Response:**
```json
{
  "success": true,
  "message": "Log source is accessible and readable",
  "file_exists": true,
  "readable": true,
  "file_size": 1048576,
  "last_modified": "2024-01-15T10:29:45Z"
}
```

### System Health and Monitoring

#### Get System Health

```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "components": {
    "file_monitor": {
      "status": "healthy",
      "active_sources": 3,
      "last_check": "2024-01-15T10:29:55Z"
    },
    "processing_queue": {
      "status": "healthy",
      "queue_size": 25,
      "processing_rate": 150.5,
      "last_processed": "2024-01-15T10:29:58Z"
    },
    "websocket_server": {
      "status": "healthy",
      "connected_clients": 5,
      "last_broadcast": "2024-01-15T10:29:59Z"
    },
    "database": {
      "status": "healthy",
      "connection_pool": "8/10",
      "last_query": "2024-01-15T10:29:59Z"
    }
  },
  "metrics": {
    "uptime": 86400,
    "memory_usage": 512.5,
    "cpu_usage": 15.2,
    "disk_usage": 45.8
  }
}
```

#### Get Processing Metrics

```http
GET /api/metrics
```

**Query Parameters:**
- `start_time`: ISO 8601 timestamp (optional)
- `end_time`: ISO 8601 timestamp (optional)
- `metric_type`: Metric type filter (optional)

**Response:**
```json
{
  "metrics": [
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "metric_type": "processing_rate",
      "value": 150.5,
      "metadata": {
        "unit": "events_per_minute",
        "source": "realtime_processor"
      }
    },
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "metric_type": "queue_depth",
      "value": 25,
      "metadata": {
        "unit": "count",
        "source": "ingestion_queue"
      }
    }
  ],
  "summary": {
    "total_events_processed": 15000,
    "average_processing_time": 0.25,
    "error_rate": 0.02
  }
}
```

#### Get System Diagnostics

```http
GET /api/diagnostics
```

**Response:**
```json
{
  "system_info": {
    "platform": "linux",
    "python_version": "3.9.7",
    "threatlens_version": "1.0.0",
    "uptime": 86400
  },
  "configuration": {
    "log_sources_count": 3,
    "notification_channels": 2,
    "processing_batch_size": 100,
    "max_queue_size": 10000
  },
  "performance": {
    "memory_usage": {
      "current": 512.5,
      "peak": 768.2,
      "limit": 2048.0
    },
    "cpu_usage": {
      "current": 15.2,
      "average_1m": 18.5,
      "average_5m": 22.1
    },
    "disk_usage": {
      "logs": 45.8,
      "database": 12.3,
      "temp": 2.1
    }
  },
  "recent_errors": [
    {
      "timestamp": "2024-01-15T10:25:00Z",
      "component": "file_monitor",
      "level": "WARNING",
      "message": "Temporary file access denied: /var/log/secure.log"
    }
  ]
}
```

### Notification Management

#### List Notification Channels

```http
GET /api/notifications/channels
```

**Response:**
```json
{
  "channels": [
    {
      "id": 1,
      "name": "Email Alerts",
      "type": "email",
      "enabled": true,
      "configuration": {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "recipients": ["admin@company.com"]
      },
      "last_used": "2024-01-15T10:15:00Z",
      "status": "active"
    },
    {
      "id": 2,
      "name": "Slack Webhook",
      "type": "webhook",
      "enabled": true,
      "configuration": {
        "webhook_url": "https://hooks.slack.com/services/...",
        "method": "POST"
      },
      "last_used": "2024-01-15T10:20:00Z",
      "status": "active"
    }
  ]
}
```

#### Create Notification Channel

```http
POST /api/notifications/channels
Content-Type: application/json

{
  "name": "Security Team Email",
  "type": "email",
  "enabled": true,
  "configuration": {
    "smtp_server": "smtp.company.com",
    "smtp_port": 587,
    "username": "alerts@company.com",
    "password": "secure_password",
    "recipients": ["security@company.com", "admin@company.com"],
    "use_tls": true
  }
}
```

#### Test Notification Channel

```http
POST /api/notifications/channels/{id}/test
Content-Type: application/json

{
  "test_message": "This is a test notification from ThreatLens"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Test notification sent successfully",
  "delivery_time": 1.25,
  "response": "Message delivered to 2 recipients"
}
```

#### List Notification Rules

```http
GET /api/notifications/rules
```

**Response:**
```json
{
  "rules": [
    {
      "id": 1,
      "name": "Critical Security Alerts",
      "enabled": true,
      "conditions": {
        "min_severity": 8,
        "max_severity": 10,
        "categories": ["security", "authentication"],
        "sources": []
      },
      "channels": [1, 2],
      "created_at": "2024-01-15T09:00:00Z",
      "last_triggered": "2024-01-15T10:15:00Z"
    }
  ]
}
```

#### Get Notification History

```http
GET /api/notifications/history
```

**Query Parameters:**
- `start_time`: ISO 8601 timestamp (optional)
- `end_time`: ISO 8601 timestamp (optional)
- `channel_id`: Channel ID filter (optional)
- `status`: Status filter (sent, failed, pending) (optional)

**Response:**
```json
{
  "notifications": [
    {
      "id": 1,
      "event_id": "evt_123456",
      "channel_id": 1,
      "channel_name": "Email Alerts",
      "status": "sent",
      "sent_at": "2024-01-15T10:15:00Z",
      "delivery_time": 1.25,
      "error_message": null,
      "retry_count": 0
    },
    {
      "id": 2,
      "event_id": "evt_123457",
      "channel_id": 2,
      "channel_name": "Slack Webhook",
      "status": "failed",
      "sent_at": "2024-01-15T10:16:00Z",
      "delivery_time": null,
      "error_message": "Connection timeout",
      "retry_count": 2
    }
  ],
  "total": 2,
  "summary": {
    "sent": 1,
    "failed": 1,
    "pending": 0
  }
}
```

### Real-Time Events

#### Get Recent Events

```http
GET /api/events/recent
```

**Query Parameters:**
- `limit`: Number of events to return (default: 50, max: 1000)
- `severity_min`: Minimum severity level (optional)
- `category`: Event category filter (optional)
- `source`: Log source filter (optional)

**Response:**
```json
{
  "events": [
    {
      "id": "evt_123456",
      "timestamp": "2024-01-15T10:30:00Z",
      "severity": 8,
      "category": "authentication",
      "description": "Multiple failed login attempts detected",
      "source": "auth_logs",
      "raw_log": "Jan 15 10:30:00 server sshd[1234]: Failed password for user from 192.168.1.100",
      "ai_analysis": {
        "threat_type": "brute_force_attack",
        "confidence": 0.95,
        "indicators": ["multiple_failures", "short_time_window"]
      },
      "processing_time": 0.25,
      "realtime_processed": true,
      "notification_sent": true
    }
  ],
  "total": 1,
  "has_more": false
}
```

#### Get Event Stream

```http
GET /api/events/stream
```

**Server-Sent Events (SSE) endpoint for real-time event streaming**

**Response Headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

**Response Format:**
```
data: {"event_type": "new_event", "data": {...}}

data: {"event_type": "analysis_complete", "data": {...}}

data: {"event_type": "system_status", "data": {...}}
```

## WebSocket API

### Connection

Connect to the WebSocket endpoint:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws?token=YOUR_API_KEY');
```

### Message Format

All WebSocket messages use JSON format:

```json
{
  "type": "message_type",
  "data": {},
  "timestamp": "2024-01-15T10:30:00Z",
  "id": "msg_123456"
}
```

### Client to Server Messages

#### Subscribe to Events

```json
{
  "type": "subscribe",
  "data": {
    "event_types": ["new_event", "analysis_complete", "system_status"],
    "filters": {
      "severity_min": 5,
      "categories": ["security", "authentication"]
    }
  }
}
```

#### Unsubscribe from Events

```json
{
  "type": "unsubscribe",
  "data": {
    "event_types": ["system_status"]
  }
}
```

#### Ping

```json
{
  "type": "ping",
  "data": {}
}
```

### Server to Client Messages

#### New Event

```json
{
  "type": "new_event",
  "data": {
    "event": {
      "id": "evt_123456",
      "timestamp": "2024-01-15T10:30:00Z",
      "severity": 8,
      "category": "authentication",
      "description": "Multiple failed login attempts detected",
      "source": "auth_logs"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "id": "msg_123456"
}
```

#### Analysis Complete

```json
{
  "type": "analysis_complete",
  "data": {
    "event_id": "evt_123456",
    "analysis": {
      "threat_type": "brute_force_attack",
      "confidence": 0.95,
      "indicators": ["multiple_failures", "short_time_window"]
    },
    "processing_time": 0.25
  },
  "timestamp": "2024-01-15T10:30:01Z",
  "id": "msg_123457"
}
```

#### System Status Update

```json
{
  "type": "system_status",
  "data": {
    "component": "processing_queue",
    "status": "healthy",
    "metrics": {
      "queue_size": 25,
      "processing_rate": 150.5
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "id": "msg_123458"
}
```

#### Error Message

```json
{
  "type": "error",
  "data": {
    "code": "SUBSCRIPTION_ERROR",
    "message": "Invalid event type specified",
    "details": {
      "invalid_types": ["invalid_event_type"]
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "id": "msg_123459"
}
```

#### Pong

```json
{
  "type": "pong",
  "data": {},
  "timestamp": "2024-01-15T10:30:00Z",
  "id": "msg_123460"
}
```

## Data Models

### LogSourceConfig

```json
{
  "id": 1,
  "path": "/var/log/nginx/access.log",
  "source_name": "Nginx Access Logs",
  "enabled": true,
  "file_pattern": "*.log",
  "recursive": false,
  "polling_interval": 1.0,
  "last_monitored": "2024-01-15T10:30:00Z",
  "file_size": 1048576,
  "last_offset": 1024000,
  "status": "active",
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Event

```json
{
  "id": "evt_123456",
  "timestamp": "2024-01-15T10:30:00Z",
  "severity": 8,
  "category": "authentication",
  "description": "Multiple failed login attempts detected",
  "source": "auth_logs",
  "raw_log": "Jan 15 10:30:00 server sshd[1234]: Failed password for user from 192.168.1.100",
  "ai_analysis": {
    "threat_type": "brute_force_attack",
    "confidence": 0.95,
    "indicators": ["multiple_failures", "short_time_window"],
    "recommendations": ["block_ip", "increase_monitoring"]
  },
  "processing_time": 0.25,
  "realtime_processed": true,
  "notification_sent": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### NotificationChannel

```json
{
  "id": 1,
  "name": "Email Alerts",
  "type": "email",
  "enabled": true,
  "configuration": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "alerts@company.com",
    "recipients": ["admin@company.com", "security@company.com"],
    "use_tls": true
  },
  "last_used": "2024-01-15T10:15:00Z",
  "status": "active",
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-15T10:15:00Z"
}
```

### NotificationRule

```json
{
  "id": 1,
  "name": "Critical Security Alerts",
  "enabled": true,
  "conditions": {
    "min_severity": 8,
    "max_severity": 10,
    "categories": ["security", "authentication"],
    "sources": ["auth_logs", "security_logs"],
    "time_window": 300
  },
  "channels": [1, 2],
  "throttle": {
    "enabled": true,
    "max_notifications": 10,
    "time_window": 3600
  },
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z",
  "last_triggered": "2024-01-15T10:15:00Z"
}
```

### ProcessingMetric

```json
{
  "id": 1,
  "timestamp": "2024-01-15T10:30:00Z",
  "metric_type": "processing_rate",
  "value": 150.5,
  "metadata": {
    "unit": "events_per_minute",
    "source": "realtime_processor",
    "component": "enhanced_processor"
  }
}
```

## Error Handling

### HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict (e.g., duplicate name)
- `422 Unprocessable Entity`: Validation errors
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service temporarily unavailable

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid log source configuration",
    "details": {
      "field": "path",
      "reason": "File path does not exist or is not readable"
    },
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req_123456"
  }
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Request validation failed |
| `AUTHENTICATION_ERROR` | Authentication failed |
| `AUTHORIZATION_ERROR` | Insufficient permissions |
| `RESOURCE_NOT_FOUND` | Requested resource not found |
| `RESOURCE_CONFLICT` | Resource already exists |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `SERVICE_UNAVAILABLE` | Service temporarily unavailable |
| `CONFIGURATION_ERROR` | Invalid configuration |
| `FILE_ACCESS_ERROR` | File system access error |
| `NOTIFICATION_ERROR` | Notification delivery failed |

## Rate Limiting

### Limits

- **API Requests**: 1000 requests per hour per API key
- **WebSocket Connections**: 10 concurrent connections per API key
- **WebSocket Messages**: 100 messages per minute per connection

### Rate Limit Headers

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642248000
X-RateLimit-Window: 3600
```

### Rate Limit Exceeded Response

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again later.",
    "details": {
      "limit": 1000,
      "window": 3600,
      "reset_at": "2024-01-15T11:00:00Z"
    }
  }
}
```

## Examples

### JavaScript/Node.js

#### REST API Client

```javascript
class ThreatLensClient {
  constructor(baseUrl, apiKey) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  async request(method, endpoint, data = null) {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method,
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: data ? JSON.stringify(data) : null
    });

    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }

    return response.json();
  }

  async getLogSources() {
    return this.request('GET', '/api/log-sources');
  }

  async createLogSource(config) {
    return this.request('POST', '/api/log-sources', config);
  }

  async getSystemHealth() {
    return this.request('GET', '/api/health');
  }
}

// Usage
const client = new ThreatLensClient('http://localhost:8000', 'your-api-key');

// Get log sources
const sources = await client.getLogSources();
console.log('Log sources:', sources);

// Create new log source
const newSource = await client.createLogSource({
  path: '/var/log/myapp/app.log',
  source_name: 'My App Logs',
  enabled: true,
  polling_interval: 1.0
});
console.log('Created source:', newSource);
```

#### WebSocket Client

```javascript
class ThreatLensWebSocket {
  constructor(url, apiKey) {
    this.url = url;
    this.apiKey = apiKey;
    this.ws = null;
    this.eventHandlers = new Map();
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(`${this.url}?token=${this.apiKey}`);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        resolve();
      };

      this.ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        this.handleMessage(message);
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.reconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };
    });
  }

  subscribe(eventTypes, filters = {}) {
    this.send({
      type: 'subscribe',
      data: { event_types: eventTypes, filters }
    });
  }

  on(eventType, handler) {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, []);
    }
    this.eventHandlers.get(eventType).push(handler);
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  handleMessage(message) {
    const handlers = this.eventHandlers.get(message.type) || [];
    handlers.forEach(handler => handler(message.data));
  }

  reconnect() {
    setTimeout(() => {
      console.log('Attempting to reconnect...');
      this.connect();
    }, 5000);
  }
}

// Usage
const wsClient = new ThreatLensWebSocket('ws://localhost:8000/ws', 'your-api-key');

// Connect and subscribe to events
await wsClient.connect();
wsClient.subscribe(['new_event', 'analysis_complete']);

// Handle new events
wsClient.on('new_event', (data) => {
  console.log('New event:', data.event);
  updateDashboard(data.event);
});

// Handle analysis completion
wsClient.on('analysis_complete', (data) => {
  console.log('Analysis complete:', data);
  updateEventAnalysis(data.event_id, data.analysis);
});
```

### Python

#### REST API Client

```python
import requests
import json
from typing import Dict, List, Optional

class ThreatLensClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, json=data)
        response.raise_for_status()
        return response.json()

    def get_log_sources(self) -> Dict:
        return self._request('GET', '/api/log-sources')

    def create_log_source(self, config: Dict) -> Dict:
        return self._request('POST', '/api/log-sources', config)

    def get_system_health(self) -> Dict:
        return self._request('GET', '/api/health')

    def get_recent_events(self, limit: int = 50, severity_min: Optional[int] = None) -> Dict:
        params = {'limit': limit}
        if severity_min:
            params['severity_min'] = severity_min
        
        endpoint = '/api/events/recent'
        if params:
            endpoint += '?' + '&'.join(f"{k}={v}" for k, v in params.items())
        
        return self._request('GET', endpoint)

# Usage
client = ThreatLensClient('http://localhost:8000', 'your-api-key')

# Get system health
health = client.get_system_health()
print(f"System status: {health['status']}")

# Get recent high-severity events
events = client.get_recent_events(limit=10, severity_min=8)
print(f"Found {events['total']} high-severity events")
```

#### WebSocket Client

```python
import asyncio
import websockets
import json
from typing import Callable, Dict, List

class ThreatLensWebSocket:
    def __init__(self, url: str, api_key: str):
        self.url = f"{url}?token={api_key}"
        self.ws = None
        self.event_handlers = {}

    async def connect(self):
        self.ws = await websockets.connect(self.url)
        print("WebSocket connected")

    async def listen(self):
        async for message in self.ws:
            data = json.loads(message)
            await self.handle_message(data)

    async def subscribe(self, event_types: List[str], filters: Dict = None):
        message = {
            'type': 'subscribe',
            'data': {
                'event_types': event_types,
                'filters': filters or {}
            }
        }
        await self.send(message)

    async def send(self, message: Dict):
        if self.ws:
            await self.ws.send(json.dumps(message))

    def on(self, event_type: str, handler: Callable):
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    async def handle_message(self, message: Dict):
        event_type = message.get('type')
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                await handler(message.get('data', {}))

# Usage
async def main():
    ws_client = ThreatLensWebSocket('ws://localhost:8000/ws', 'your-api-key')
    
    # Event handlers
    async def handle_new_event(data):
        event = data.get('event', {})
        print(f"New event: {event.get('description')} (Severity: {event.get('severity')})")

    async def handle_analysis_complete(data):
        print(f"Analysis complete for event {data.get('event_id')}")

    # Register handlers
    ws_client.on('new_event', handle_new_event)
    ws_client.on('analysis_complete', handle_analysis_complete)

    # Connect and subscribe
    await ws_client.connect()
    await ws_client.subscribe(['new_event', 'analysis_complete'], {'severity_min': 5})

    # Listen for messages
    await ws_client.listen()

# Run the client
asyncio.run(main())
```

### cURL Examples

#### Get System Health

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8000/api/health
```

#### Create Log Source

```bash
curl -X POST \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "path": "/var/log/nginx/access.log",
       "source_name": "Nginx Access Logs",
       "enabled": true,
       "polling_interval": 1.0
     }' \
     http://localhost:8000/api/log-sources
```

#### Get Recent Events

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     "http://localhost:8000/api/events/recent?limit=10&severity_min=8"
```

#### Test Notification Channel

```bash
curl -X POST \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"test_message": "Test notification from ThreatLens"}' \
     http://localhost:8000/api/notifications/channels/1/test
```

This comprehensive API documentation provides all the necessary information for integrating with ThreatLens real-time monitoring features, including detailed examples in multiple programming languages.