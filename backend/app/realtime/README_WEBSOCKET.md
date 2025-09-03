# WebSocket API Documentation

## Overview

The ThreatLens WebSocket API provides real-time communication between the server and frontend clients. It enables live updates for security events, system status, processing updates, and health checks.

## Connection

### Endpoints

- `ws://localhost:8000/ws` - General WebSocket connection
- `ws://localhost:8000/ws/{client_id}` - Connection with specific client ID

### Connection Flow

1. Client connects to WebSocket endpoint
2. Server sends `connection_established` message with client ID
3. Client can subscribe to event types and set filters
4. Server broadcasts relevant events to subscribed clients

## Message Format

All WebSocket messages use JSON format:

```json
{
  "type": "message_type",
  "data": {
    // Message-specific data
  },
  "timestamp": "2024-01-01T12:00:00Z",
  "message_id": "optional_message_id"
}
```

## Client to Server Messages

### Subscribe to Events

```json
{
  "type": "subscribe",
  "data": {
    "event_types": ["security_event", "system_status"],
    "replace_existing": false
  }
}
```

### Unsubscribe from Events

```json
{
  "type": "unsubscribe",
  "data": {
    "event_types": ["security_event"]
  }
}
```

### Set Event Filter

```json
{
  "type": "set_filter",
  "data": {
    "event_types": ["security_event"],
    "categories": ["authentication", "authorization"],
    "min_priority": 5,
    "max_priority": 10,
    "sources": ["auth_service", "api_gateway"]
  }
}
```

### Clear Event Filter

```json
{
  "type": "clear_filter",
  "data": {}
}
```

### Ping

```json
{
  "type": "ping",
  "data": {}
}
```

### Get Status

```json
{
  "type": "get_status",
  "data": {}
}
```

## Server to Client Messages

### Connection Established

```json
{
  "type": "connection_established",
  "data": {
    "client_id": "uuid-string",
    "server_info": {
      "name": "ThreatLens WebSocket Server",
      "version": "1.0.0"
    }
  }
}
```

### Security Event

```json
{
  "type": "security_event",
  "data": {
    "event_id": "event_123",
    "severity": 8,
    "category": "authentication",
    "source": "auth_service",
    "message": "Failed login attempt detected",
    "timestamp": "2024-01-01T12:00:00Z",
    "analysis": {
      "threat_level": "high",
      "confidence": 0.85
    },
    "recommendations": [
      "Review user account",
      "Check for brute force patterns"
    ]
  },
  "priority": 8
}
```

### System Status

```json
{
  "type": "system_status",
  "data": {
    "component": "file_monitor",
    "status": "healthy",
    "uptime": 3600.5,
    "metrics": {
      "files_monitored": 5,
      "events_processed": 1250
    }
  },
  "priority": 3
}
```

### Processing Update

```json
{
  "type": "processing_update",
  "data": {
    "raw_log_id": "log_456",
    "stage": "analysis",
    "status": "completed",
    "progress": 1.0,
    "events_created": 3,
    "processing_time": 2.5
  },
  "priority": 5
}
```

### Health Check

```json
{
  "type": "health_check",
  "data": {
    "overall_status": "healthy",
    "components": {
      "websocket_manager": {
        "status": "healthy",
        "connections": 5
      },
      "event_broadcaster": {
        "status": "healthy",
        "queued_messages": 0
      }
    },
    "timestamp": "2024-01-01T12:00:00Z"
  },
  "priority": 2
}
```

### Error

```json
{
  "type": "error",
  "data": {
    "error": "Invalid subscription request: missing event_types",
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

## Event Types

- `security_event` - New security events detected
- `system_status` - System component status updates
- `processing_update` - Log processing progress updates
- `health_check` - System health information
- `user_action` - User-initiated actions

## Priority Levels

- `10` - Critical (system failures, high-severity security events)
- `8` - High (important security events, component errors)
- `5` - Medium (normal processing updates, moderate events)
- `3` - Low (routine status updates)
- `1` - Debug (detailed diagnostic information)

## Event Filtering

Clients can set filters to receive only relevant events:

- **Event Types**: Filter by specific event types
- **Categories**: Filter by event categories (authentication, network, etc.)
- **Priority Range**: Filter by minimum/maximum priority levels
- **Sources**: Filter by event sources (service names, log files, etc.)

## Connection Management

### Automatic Reconnection

Clients should implement automatic reconnection logic:

```javascript
class WebSocketClient {
  constructor(url) {
    this.url = url;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
  }
  
  connect() {
    this.ws = new WebSocket(this.url);
    
    this.ws.onopen = () => {
      console.log('Connected to WebSocket');
      this.reconnectAttempts = 0;
    };
    
    this.ws.onclose = () => {
      console.log('WebSocket connection closed');
      this.handleReconnect();
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };
  }
  
  handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => {
        console.log(`Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.connect();
      }, this.reconnectDelay * this.reconnectAttempts);
    }
  }
  
  subscribe(eventTypes) {
    this.send({
      type: 'subscribe',
      data: { event_types: eventTypes }
    });
  }
  
  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }
}
```

### Ping/Pong

The server automatically sends ping messages every 30 seconds to maintain connections. Clients should respond to pings or implement their own ping mechanism.

## Error Handling

Common error scenarios:

1. **Connection Limit Reached**: Server closes connection with code 1013
2. **Invalid Client ID**: Server closes connection with code 1003
3. **Service Unavailable**: Server closes connection with code 1011
4. **Invalid Message Format**: Server sends error message
5. **Unknown Message Type**: Server sends error message

## Rate Limiting

The WebSocket server implements rate limiting to prevent abuse:

- Maximum connections per server: Configurable (default: 100)
- Message queue size per client: Configurable (default: 1000)
- Automatic cleanup of old queued messages (1 hour)

## Security

- WebSocket connections should be authenticated
- Input validation on all incoming messages
- Rate limiting to prevent DoS attacks
- Audit logging of all configuration changes

## Monitoring

The WebSocket server provides monitoring endpoints:

- `GET /ws/info` - Connection statistics and server information
- `GET /realtime/status` - Real-time system status

## Example Usage

### Frontend Integration

```javascript
// Connect to WebSocket
const client = new WebSocketClient('ws://localhost:8000/ws');
client.connect();

// Subscribe to security events
client.subscribe(['security_event', 'system_status']);

// Set filter for high-priority events only
client.send({
  type: 'set_filter',
  data: {
    min_priority: 7
  }
});

// Handle incoming messages
client.handleMessage = (message) => {
  switch (message.type) {
    case 'security_event':
      updateSecurityDashboard(message.data);
      break;
    case 'system_status':
      updateSystemStatus(message.data);
      break;
    case 'error':
      console.error('WebSocket error:', message.data.error);
      break;
  }
};
```

This WebSocket API enables real-time, bidirectional communication between the ThreatLens server and frontend clients, providing immediate updates for security events and system status changes.