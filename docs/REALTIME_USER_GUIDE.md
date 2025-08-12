# ThreatLens Real-Time Monitoring User Guide

## Overview

ThreatLens real-time monitoring provides continuous log surveillance and immediate threat detection capabilities. This guide covers configuration, usage, and troubleshooting of the real-time monitoring system.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Configuring Log Sources](#configuring-log-sources)
3. [Setting Up Notifications](#setting-up-notifications)
4. [Using the Real-Time Dashboard](#using-the-real-time-dashboard)
5. [Monitoring System Health](#monitoring-system-health)
6. [Troubleshooting](#troubleshooting)

## Getting Started

### Prerequisites

- ThreatLens installed and running
- Python 3.8+ with required dependencies
- Web browser with WebSocket support
- Appropriate file system permissions for log monitoring

### Enabling Real-Time Monitoring

1. **Start the ThreatLens application**:
   ```bash
   python main.py
   ```

2. **Access the web interface**:
   Open your browser to `http://localhost:8000`

3. **Navigate to Configuration**:
   Click on "Configuration" in the sidebar to access real-time monitoring settings.

## Configuring Log Sources

### Adding a Log Source

1. **Navigate to Log Source Management**:
   - Go to Configuration → Log Sources
   - Click "Add New Source"

2. **Configure Source Settings**:
   ```
   Source Name: My Application Logs
   File Path: /var/log/myapp/application.log
   Monitoring Type: Real-time
   File Pattern: *.log (optional)
   Recursive: Yes/No
   Polling Interval: 1.0 seconds
   ```

3. **Validation**:
   - The system validates file paths and permissions
   - Test the configuration before saving
   - Enable the source to start monitoring

### Log Source Configuration Options

| Setting | Description | Default | Example |
|---------|-------------|---------|---------|
| Source Name | Friendly name for the log source | - | "Web Server Logs" |
| File Path | Absolute path to log file or directory | - | `/var/log/nginx/access.log` |
| File Pattern | Pattern to match files (for directories) | `*` | `*.log`, `access_*.log` |
| Recursive | Monitor subdirectories | `false` | `true` |
| Polling Interval | Check frequency in seconds | `1.0` | `0.5`, `2.0` |
| Enabled | Whether monitoring is active | `true` | `true`/`false` |

### Supported Log Formats

The system automatically detects and parses common log formats:

- **Syslog**: Standard system log format
- **Apache/Nginx**: Web server access and error logs
- **JSON**: Structured JSON log entries
- **Custom**: User-defined parsing rules

### Managing Log Sources

- **Edit Source**: Click the edit icon next to any configured source
- **Disable Source**: Toggle the enabled/disabled status
- **Remove Source**: Delete a log source configuration
- **Test Source**: Verify connectivity and permissions

## Setting Up Notifications

### Notification Channels

Configure multiple notification channels for high-priority events:

#### Email Notifications

1. **Configure SMTP Settings**:
   ```json
   {
     "smtp_server": "smtp.gmail.com",
     "smtp_port": 587,
     "username": "your-email@gmail.com",
     "password": "your-app-password",
     "use_tls": true
   }
   ```

2. **Add Email Recipients**:
   - Primary: `security-team@company.com`
   - Secondary: `admin@company.com`

#### Webhook Notifications

1. **Configure Webhook URL**:
   ```json
   {
     "webhook_url": "https://hooks.slack.com/services/...",
     "method": "POST",
     "headers": {
       "Content-Type": "application/json"
     }
   }
   ```

2. **Customize Payload**:
   ```json
   {
     "text": "Security Alert: {{event.category}} - {{event.severity}}",
     "details": "{{event.description}}"
   }
   ```

### Notification Rules

Create rules to determine when notifications are sent:

1. **Severity-Based Rules**:
   ```
   Rule Name: Critical Alerts
   Min Severity: 8
   Max Severity: 10
   Categories: All
   Channels: Email, Webhook
   ```

2. **Category-Based Rules**:
   ```
   Rule Name: Authentication Failures
   Severity: 5+
   Categories: Authentication, Access Control
   Channels: Email
   ```

### Testing Notifications

1. **Test Individual Channels**:
   - Use the "Test" button next to each configured channel
   - Verify delivery and formatting

2. **Test Notification Rules**:
   - Generate test events with different severities
   - Confirm rules trigger correctly

## Using the Real-Time Dashboard

### Dashboard Components

#### Event Stream
- **Live Events**: Real-time display of detected events
- **Auto-Refresh**: Automatic updates without page reload
- **Filtering**: Filter by severity, category, or time range
- **Sorting**: Sort by timestamp, severity, or source

#### System Status
- **Processing Rate**: Events processed per minute
- **Queue Status**: Current queue size and processing lag
- **Source Health**: Status of all monitored log sources
- **Connection Status**: WebSocket connection indicator

#### Metrics and Charts
- **Severity Distribution**: Real-time chart of event severities
- **Event Timeline**: Historical view of event patterns
- **Processing Performance**: System performance metrics

### Real-Time Features

#### WebSocket Connection
- **Auto-Connect**: Automatic connection on page load
- **Reconnection**: Automatic reconnection on connection loss
- **Status Indicator**: Visual connection status in header

#### Live Updates
- **Event Notifications**: Toast notifications for high-priority events
- **Counter Updates**: Real-time event counters
- **Status Changes**: Immediate updates to system status

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `R` | Refresh current view |
| `F` | Focus search/filter |
| `Esc` | Clear filters |
| `Space` | Pause/resume live updates |

## Monitoring System Health

### Health Indicators

#### System Components
- **File Monitor**: Status of file system monitoring
- **Processing Queue**: Queue health and performance
- **WebSocket Server**: Connection server status
- **Database**: Database connectivity and performance

#### Performance Metrics
- **Processing Latency**: Time from log detection to analysis
- **Queue Depth**: Number of pending log entries
- **Memory Usage**: System memory consumption
- **CPU Usage**: Processing load

### Health Dashboard

Access the health dashboard at Configuration → System Monitoring:

1. **Component Status**: Green/Yellow/Red indicators
2. **Performance Graphs**: Real-time performance charts
3. **Error Logs**: Recent errors and warnings
4. **Resource Usage**: System resource consumption

### Alerts and Warnings

The system provides automatic alerts for:

- **High Queue Depth**: When processing falls behind
- **Component Failures**: When system components fail
- **Resource Exhaustion**: When system resources are low
- **Configuration Errors**: When configuration is invalid

## Troubleshooting

### Common Issues

#### Log Sources Not Monitoring

**Symptoms**: No events from configured log sources

**Possible Causes**:
- File permission issues
- Incorrect file paths
- Log source disabled
- File system monitoring failure

**Solutions**:
1. **Check File Permissions**:
   ```bash
   ls -la /path/to/log/file
   # Ensure read permissions for ThreatLens user
   ```

2. **Verify File Path**:
   - Ensure the path exists and is accessible
   - Check for typos in configuration
   - Test with absolute paths

3. **Check Log Source Status**:
   - Navigate to Configuration → Log Sources
   - Verify source is enabled
   - Check last monitored timestamp

#### WebSocket Connection Issues

**Symptoms**: Dashboard not updating in real-time

**Possible Causes**:
- Network connectivity issues
- Firewall blocking WebSocket connections
- Server overload
- Browser compatibility

**Solutions**:
1. **Check Connection Status**:
   - Look for connection indicator in dashboard header
   - Check browser console for WebSocket errors

2. **Network Troubleshooting**:
   ```bash
   # Test WebSocket connection
   curl -i -N -H "Connection: Upgrade" \
        -H "Upgrade: websocket" \
        -H "Sec-WebSocket-Key: test" \
        -H "Sec-WebSocket-Version: 13" \
        http://localhost:8000/ws
   ```

3. **Browser Compatibility**:
   - Use modern browsers (Chrome, Firefox, Safari, Edge)
   - Disable browser extensions that might interfere
   - Clear browser cache and cookies

#### High Processing Latency

**Symptoms**: Delays between log detection and analysis

**Possible Causes**:
- High log volume
- Insufficient system resources
- Database performance issues
- AI analysis bottlenecks

**Solutions**:
1. **Monitor System Resources**:
   - Check CPU and memory usage
   - Monitor disk I/O performance
   - Review database query performance

2. **Optimize Configuration**:
   - Adjust batch processing sizes
   - Increase polling intervals for low-priority sources
   - Configure processing priorities

3. **Scale Resources**:
   - Increase system memory
   - Use faster storage (SSD)
   - Consider distributed processing

#### Notification Delivery Failures

**Symptoms**: Notifications not being sent or received

**Possible Causes**:
- Incorrect notification configuration
- Network connectivity issues
- Authentication failures
- Rate limiting

**Solutions**:
1. **Test Notification Channels**:
   - Use built-in test functionality
   - Verify SMTP/webhook credentials
   - Check network connectivity

2. **Review Notification Rules**:
   - Ensure rules match event criteria
   - Check severity thresholds
   - Verify channel assignments

3. **Check Notification History**:
   - Review delivery status in notification history
   - Look for error messages and retry attempts

### Diagnostic Tools

#### Log Analysis
```bash
# Check ThreatLens logs
tail -f logs/threatlens.log

# Filter for real-time monitoring logs
grep "realtime" logs/threatlens.log

# Check for errors
grep "ERROR" logs/threatlens.log
```

#### System Status API
```bash
# Get system health status
curl http://localhost:8000/api/health

# Get processing metrics
curl http://localhost:8000/api/metrics

# Get log source status
curl http://localhost:8000/api/log-sources/status
```

#### Database Queries
```sql
-- Check recent events
SELECT * FROM events ORDER BY timestamp DESC LIMIT 10;

-- Check processing metrics
SELECT * FROM processing_metrics ORDER BY timestamp DESC LIMIT 20;

-- Check notification history
SELECT * FROM notification_history ORDER BY sent_at DESC LIMIT 10;
```

### Getting Help

#### Support Resources
- **Documentation**: Check the complete API documentation
- **GitHub Issues**: Report bugs and feature requests
- **Community Forum**: Ask questions and share experiences
- **Email Support**: Contact the development team

#### Reporting Issues

When reporting issues, include:

1. **System Information**:
   - Operating system and version
   - Python version
   - ThreatLens version

2. **Configuration Details**:
   - Log source configurations
   - Notification settings
   - System resource specifications

3. **Error Information**:
   - Error messages and stack traces
   - Log file excerpts
   - Steps to reproduce the issue

4. **Performance Data**:
   - System resource usage
   - Processing metrics
   - Network connectivity information

## Best Practices

### Configuration
- Use descriptive names for log sources
- Test configurations before enabling
- Regularly review and update notification rules
- Monitor system performance and adjust settings

### Security
- Use least-privilege file permissions
- Secure notification credentials
- Regularly update system dependencies
- Monitor for unauthorized configuration changes

### Performance
- Balance polling intervals with resource usage
- Use appropriate batch sizes for processing
- Monitor queue depths and processing latency
- Scale resources based on log volume

### Maintenance
- Regularly review log source health
- Clean up old metrics and notification history
- Update documentation for configuration changes
- Test disaster recovery procedures