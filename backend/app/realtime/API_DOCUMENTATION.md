# Real-time Monitoring API Documentation

This document describes the REST API endpoints for managing real-time log monitoring in ThreatLens.

## Base URL

All endpoints are prefixed with `/api/v1/monitoring`

## Authentication

Currently, the API does not require authentication. In production, implement proper authentication and authorization.

## Log Source Management

### Create Log Source

**POST** `/log-sources`

Create a new log source configuration.

**Request Body:**
```json
{
  "source_name": "string",
  "path": "string",
  "source_type": "file|directory",
  "enabled": true,
  "recursive": false,
  "file_pattern": "string (optional)",
  "polling_interval": 1.0,
  "batch_size": 100,
  "priority": 5,
  "description": "string (optional)",
  "tags": ["string"]
}
```

**Response:**
```json
{
  "source_name": "string",
  "path": "string",
  "source_type": "file|directory",
  "enabled": true,
  "recursive": false,
  "file_pattern": "string",
  "polling_interval": 1.0,
  "batch_size": 100,
  "priority": 5,
  "description": "string",
  "tags": ["string"],
  "status": "active|inactive|error|paused",
  "last_monitored": "2023-01-01T00:00:00Z",
  "file_size": 1024,
  "last_offset": 512,
  "error_message": "string"
}
```

### List Log Sources

**GET** `/log-sources`

List all log source configurations.

**Query Parameters:**
- `enabled_only` (boolean, optional): Return only enabled sources

**Response:**
```json
[
  {
    "source_name": "string",
    "path": "string",
    "source_type": "file|directory",
    "enabled": true,
    "status": "active|inactive|error|paused",
    ...
  }
]
```

### Get Log Source

**GET** `/log-sources/{source_name}`

Get a specific log source configuration.

**Response:**
```json
{
  "source_name": "string",
  "path": "string",
  "source_type": "file|directory",
  "enabled": true,
  "status": "active|inactive|error|paused",
  ...
}
```

### Update Log Source

**PUT** `/log-sources/{source_name}`

Update an existing log source configuration.

**Request Body:** Same as create log source

**Response:** Same as create log source

### Delete Log Source

**DELETE** `/log-sources/{source_name}`

Delete a log source configuration.

**Response:**
```json
{
  "message": "Log source 'source_name' deleted successfully"
}
```

### Test Log Source

**POST** `/log-sources/{source_name}/test`

Test a log source configuration to verify it's accessible and valid.

**Response:**
```json
{
  "source_name": "string",
  "path": "string",
  "tests": {
    "path_exists": {
      "status": "passed|failed|error",
      "message": "string"
    },
    "path_type": {
      "status": "passed|failed|error",
      "message": "string"
    },
    "read_permission": {
      "status": "passed|failed|error",
      "message": "string"
    }
  },
  "overall_status": "passed|failed",
  "timestamp": "2023-01-01T00:00:00Z"
}
```

### Get Log Source Status

**GET** `/log-sources/{source_name}/status`

Get the current status and health of a log source.

**Response:**
```json
{
  "source_name": "string",
  "status": "active|inactive|error|paused",
  "enabled": true,
  "last_monitored": "2023-01-01T00:00:00Z",
  "file_size": 1024,
  "last_offset": 512,
  "error_message": "string",
  "health_info": {},
  "timestamp": "2023-01-01T00:00:00Z"
}
```

## Notification Management

### Create Notification Rule

**POST** `/notification-rules`

Create a new notification rule.

**Request Body:**
```json
{
  "rule_name": "string",
  "enabled": true,
  "min_severity": 1,
  "max_severity": 10,
  "categories": ["string"],
  "sources": ["string"],
  "channels": ["email", "webhook", "slack"],
  "throttle_minutes": 60,
  "email_recipients": ["email@example.com"],
  "webhook_url": "https://example.com/webhook",
  "slack_channel": "#alerts"
}
```

**Response:**
```json
{
  "rule_name": "string",
  "enabled": true,
  "min_severity": 1,
  "max_severity": 10,
  "categories": ["string"],
  "sources": ["string"],
  "channels": ["email", "webhook", "slack"],
  "throttle_minutes": 60,
  "email_recipients": ["email@example.com"],
  "webhook_url": "https://example.com/webhook",
  "slack_channel": "#alerts"
}
```

### List Notification Rules

**GET** `/notification-rules`

List all notification rules.

**Query Parameters:**
- `enabled_only` (boolean, optional): Return only enabled rules

**Response:**
```json
[
  {
    "rule_name": "string",
    "enabled": true,
    "min_severity": 1,
    "max_severity": 10,
    ...
  }
]
```

### Get Notification Rule

**GET** `/notification-rules/{rule_name}`

Get a specific notification rule.

**Response:** Same as create notification rule

### Update Notification Rule

**PUT** `/notification-rules/{rule_name}`

Update an existing notification rule.

**Request Body:** Same as create notification rule

**Response:** Same as create notification rule

### Delete Notification Rule

**DELETE** `/notification-rules/{rule_name}`

Delete a notification rule.

**Response:**
```json
{
  "message": "Notification rule 'rule_name' deleted successfully"
}
```

### Test Notification Rule

**POST** `/notification-rules/{rule_name}/test`

Test a notification rule by sending a test notification.

**Response:**
```json
{
  "rule_name": "string",
  "channels_tested": [
    {
      "channel": "email",
      "status": "passed|failed|error",
      "message": "string"
    }
  ],
  "overall_status": "passed|failed",
  "timestamp": "2023-01-01T00:00:00Z"
}
```

### Get Notification History

**GET** `/notification-history`

Get notification delivery history.

**Query Parameters:**
- `limit` (integer, 1-1000): Maximum number of entries to return (default: 50)
- `rule_name` (string, optional): Filter by rule name
- `channel` (string, optional): Filter by notification channel
- `status` (string, optional): Filter by delivery status

**Response:**
```json
{
  "history": [
    {
      "id": 1,
      "event_id": "string",
      "notification_type": "string",
      "channel": "string",
      "status": "sent|failed|pending",
      "sent_at": "2023-01-01T00:00:00Z",
      "error_message": "string"
    }
  ],
  "total_returned": 10,
  "filters_applied": {
    "rule_name": "string",
    "channel": "string",
    "status": "string",
    "limit": 50
  },
  "timestamp": "2023-01-01T00:00:00Z"
}
```

## System Monitoring

### Get Monitoring Health

**GET** `/health`

Get overall health status of the real-time monitoring system.

**Response:**
```json
{
  "overall_status": "healthy|degraded|unhealthy|unknown",
  "components": {},
  "timestamp": "2023-01-01T00:00:00Z"
}
```

### Get Processing Metrics

**GET** `/metrics`

Get real-time processing metrics.

**Query Parameters:**
- `source_name` (string, optional): Filter by source name
- `hours` (integer, 1-168): Hours of metrics to retrieve (default: 24)

**Response:**
```json
{
  "metrics": [
    {
      "id": 1,
      "metric_type": "string",
      "metric_value": "string",
      "timestamp": "2023-01-01T00:00:00Z",
      "metadata": {}
    }
  ],
  "summary": {
    "total_metrics": 100,
    "time_range": {
      "start": "2023-01-01T00:00:00Z",
      "end": "2023-01-02T00:00:00Z",
      "hours": 24
    },
    "source_filter": "string"
  },
  "timestamp": "2023-01-01T00:00:00Z"
}
```

### Get System Diagnostics

**GET** `/diagnostics`

Get detailed system diagnostic information.

**Response:**
```json
{
  "timestamp": "2023-01-01T00:00:00Z",
  "system_info": {},
  "component_status": {},
  "performance_metrics": {}
}
```

### Get Monitoring Configuration

**GET** `/config`

Get the current monitoring configuration.

**Response:**
```json
{
  "enabled": true,
  "max_concurrent_sources": 50,
  "processing_batch_size": 100,
  "max_queue_size": 10000,
  "health_check_interval": 30,
  "max_error_count": 10,
  "retry_interval": 60,
  "file_read_chunk_size": 8192,
  "websocket_max_connections": 100,
  "log_sources": [],
  "notification_rules": [],
  "config_version": "1.0",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

### Get Monitoring Statistics

**GET** `/stats`

Get monitoring system statistics and summary information.

**Response:**
```json
{
  "configuration": {
    "total_sources": 5,
    "enabled_sources": 3,
    "disabled_sources": 2,
    "notification_rules": 2,
    "enabled_notification_rules": 1
  },
  "runtime": {
    "uptime_seconds": 3600,
    "active_connections": 5,
    "queue_size": 10,
    "processing_rate": 15.5
  },
  "timestamp": "2023-01-01T00:00:00Z"
}
```

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "detail": "Configuration error message"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found message"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["field_name"],
      "msg": "Validation error message",
      "type": "validation_error"
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error message"
}
```

## Rate Limiting

The API implements rate limiting to prevent abuse:
- 120 requests per minute per client
- Burst limit of 10 requests
- Block duration of 5 minutes for rate limit violations

## Examples

### Create a Log Source

```bash
curl -X POST "http://localhost:8000/api/v1/monitoring/log-sources" \
  -H "Content-Type: application/json" \
  -d '{
    "source_name": "auth_logs",
    "path": "/var/log/auth.log",
    "source_type": "file",
    "enabled": true,
    "polling_interval": 2.0,
    "batch_size": 50,
    "priority": 8,
    "description": "System authentication logs",
    "tags": ["security", "auth"]
  }'
```

### Create a Notification Rule

```bash
curl -X POST "http://localhost:8000/api/v1/monitoring/notification-rules" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "high_severity_alerts",
    "enabled": true,
    "min_severity": 7,
    "max_severity": 10,
    "categories": ["security"],
    "channels": ["email", "webhook"],
    "throttle_minutes": 30,
    "email_recipients": ["admin@company.com"],
    "webhook_url": "https://hooks.slack.com/services/..."
  }'
```

### Test a Log Source

```bash
curl -X POST "http://localhost:8000/api/v1/monitoring/log-sources/auth_logs/test"
```

### Get Processing Metrics

```bash
curl "http://localhost:8000/api/v1/monitoring/metrics?hours=6&source_name=auth_logs"
```