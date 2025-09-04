# macOS Console Integration Guide

This guide explains how to integrate macOS Console logs with ThreatLens for real-time security monitoring.

## Overview

ThreatLens now supports macOS Console logs with enhanced parsing capabilities for:
- Console app logs with microsecond timestamps
- System logs with timezone information
- Process-specific log filtering
- Security-focused log analysis

## Quick Start

### 1. Basic Console Log Analysis

Capture and analyze recent Console logs (last hour):

```bash
python scripts/console_integration.py
```

### 2. Security-Focused Analysis

Capture security-related logs from the last 24 hours:

```bash
python scripts/console_integration.py --mode security --hours 24
```

### 3. Process-Specific Analysis

Monitor logs for a specific process:

```bash
python scripts/console_integration.py --mode process --process sshd --hours 2
```

## Available Tools

### Console Log Exporter (`scripts/console_log_exporter.py`)

Exports Console logs to files for manual analysis:

```bash
# Export recent logs
python scripts/console_log_exporter.py --mode recent --hours 2

# Export security logs
python scripts/console_log_exporter.py --mode security --hours 24

# Export process logs
python scripts/console_log_exporter.py --mode process --process loginwindow --hours 1

# Custom filtering
python scripts/console_log_exporter.py --mode custom --predicate 'eventMessage CONTAINS "failed"' --hours 6
```

### Console Integration (`scripts/console_integration.py`)

Direct integration with ThreatLens API:

```bash
# Basic integration
python scripts/console_integration.py --mode recent --hours 1

# Security monitoring
python scripts/console_integration.py --mode security --hours 12

# Process monitoring
python scripts/console_integration.py --mode process --process sudo --hours 4

# Custom API endpoint
python scripts/console_integration.py --api-url http://your-server:8000
```

## Console Log Format Support

ThreatLens now parses Console logs with the format:
```
11:28:24.138308+0200 process_name message content
11:28:24.234174+0200 process_name[pid] message content
```

Features:
- **Microsecond precision**: Full timestamp accuracy
- **Timezone support**: Automatic UTC conversion
- **Process identification**: Automatic source tagging
- **PID extraction**: Process ID when available

## Security Use Cases

### 1. Authentication Monitoring

Monitor login attempts and authentication events:

```bash
python scripts/console_integration.py --mode security --hours 24
```

This captures logs containing:
- Login/logout events
- Password attempts
- SSH connections
- Sudo usage
- Authentication failures

### 2. System Security Events

Monitor system-level security events:

```bash
python scripts/console_log_exporter.py --mode custom \
  --predicate 'subsystem == "com.apple.security" OR eventMessage CONTAINS "denied"' \
  --hours 12
```

### 3. Process Monitoring

Monitor specific security-critical processes:

```bash
# Monitor SSH daemon
python scripts/console_integration.py --mode process --process sshd --hours 6

# Monitor sudo usage
python scripts/console_integration.py --mode process --process sudo --hours 2
```

## Integration with ThreatLens

### Automatic Analysis Pipeline

1. **Log Capture**: Console logs are captured using macOS `log` command
2. **Ingestion**: Logs are sent to ThreatLens ingestion API
3. **Parsing**: Enhanced parser handles Console format
4. **Analysis**: AI-powered threat detection
5. **Alerting**: Real-time notifications for threats

### Manual Integration

You can also manually copy Console logs:

1. Open Console app
2. Filter logs as needed
3. Copy log content
4. Paste into ThreatLens web interface text input

## Configuration Options

### Log Levels
- `default`: Standard system logs
- `info`: Informational messages
- `debug`: Detailed debugging information

### Time Ranges
- Use `--hours N` to specify lookback period
- Maximum recommended: 24 hours for performance

### Custom Predicates

Advanced filtering using macOS log predicates:

```bash
# Authentication events
--predicate 'eventMessage CONTAINS "authentication" OR process == "loginwindow"'

# Network events
--predicate 'subsystem == "com.apple.network" OR eventMessage CONTAINS "connection"'

# Error events
--predicate 'eventType == "logEvent" AND messageType == "Error"'
```

## Troubleshooting

### Common Issues

1. **No logs captured**
   - Increase `--hours` value
   - Check system permissions
   - Verify Console app has logs for the time period

2. **Connection errors**
   - Ensure ThreatLens is running: `python main.py`
   - Check API URL: default is `http://localhost:8000`
   - Verify network connectivity

3. **Parsing errors**
   - Check log format compatibility
   - Review ThreatLens logs for parsing details
   - Try with smaller log samples first

### Performance Tips

1. **Limit time ranges**: Use shorter `--hours` values for better performance
2. **Filter by process**: Use `--mode process` for focused analysis
3. **Security mode**: Use `--mode security` for threat-focused logs only

## Real-time Monitoring

For continuous monitoring, you can set up scheduled captures:

```bash
# Add to crontab for hourly security monitoring
0 * * * * /path/to/python /path/to/scripts/console_integration.py --mode security --hours 1
```

## API Integration

The Console integration uses these ThreatLens API endpoints:

- `POST /api/ingest/text`: Ingest log content
- `POST /api/parse/{raw_log_id}`: Parse ingested logs
- `POST /api/analyze/{raw_log_id}`: Analyze parsed events
- `GET /api/events/{raw_log_id}`: Get analysis results

## Next Steps

1. **Set up automated monitoring**: Use cron jobs for regular log capture
2. **Configure alerts**: Set up notifications for security events
3. **Dashboard monitoring**: Use ThreatLens web interface for real-time monitoring
4. **Custom rules**: Create custom threat detection rules for your environment

For more advanced configuration, see the [Real-time System Documentation](REALTIME_SYSTEM_REQUIREMENTS.md).