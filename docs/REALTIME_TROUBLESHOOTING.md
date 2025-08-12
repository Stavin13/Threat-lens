# ThreatLens Real-Time Monitoring Troubleshooting Guide

## Overview

This guide provides comprehensive troubleshooting procedures for ThreatLens real-time monitoring features, including common issues, diagnostic steps, and solutions.

## Table of Contents

1. [Quick Diagnostic Checklist](#quick-diagnostic-checklist)
2. [Log Source Issues](#log-source-issues)
3. [WebSocket Connection Problems](#websocket-connection-problems)
4. [Processing Performance Issues](#processing-performance-issues)
5. [Notification Delivery Problems](#notification-delivery-problems)
6. [System Health Issues](#system-health-issues)
7. [Database and Storage Issues](#database-and-storage-issues)
8. [Configuration Problems](#configuration-problems)
9. [Diagnostic Tools and Commands](#diagnostic-tools-and-commands)
10. [Advanced Troubleshooting](#advanced-troubleshooting)

## Quick Diagnostic Checklist

Before diving into specific issues, run through this quick checklist:

### System Status Check

1. **Check ThreatLens Service Status**:
   ```bash
   # Check if the main process is running
   ps aux | grep python | grep main.py
   
   # Check system health via API
   curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/api/health
   ```

2. **Verify File Permissions**:
   ```bash
   # Check log file permissions
   ls -la /path/to/log/files/
   
   # Test file readability
   cat /path/to/log/file | head -5
   ```

3. **Check Network Connectivity**:
   ```bash
   # Test HTTP API
   curl -I http://localhost:8000/api/health
   
   # Test WebSocket (requires websocat or similar)
   echo '{"type":"ping"}' | websocat ws://localhost:8000/ws?token=YOUR_API_KEY
   ```

4. **Review Recent Logs**:
   ```bash
   # Check ThreatLens logs
   tail -50 logs/threatlens.log
   
   # Filter for errors
   grep -i error logs/threatlens.log | tail -10
   ```

## Log Source Issues

### Issue: Log Sources Not Being Monitored

**Symptoms**:
- No new events appearing in dashboard
- Log source status shows "inactive" or "error"
- Last monitored timestamp not updating

**Diagnostic Steps**:

1. **Check Log Source Configuration**:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        http://localhost:8000/api/log-sources
   ```

2. **Verify File Accessibility**:
   ```bash
   # Check if file exists and is readable
   test -r /path/to/log/file && echo "Readable" || echo "Not readable"
   
   # Check file permissions
   ls -la /path/to/log/file
   
   # Check file size and recent modifications
   stat /path/to/log/file
   ```

3. **Test Log Source**:
   ```bash
   curl -X POST \
        -H "Authorization: Bearer YOUR_API_KEY" \
        http://localhost:8000/api/log-sources/1/test
   ```

**Common Causes and Solutions**:

| Cause | Solution |
|-------|----------|
| **File Permission Denied** | `chmod 644 /path/to/log/file` or add ThreatLens user to appropriate group |
| **File Path Incorrect** | Verify path exists: `ls -la /path/to/log/file` |
| **Log Source Disabled** | Enable via API or web interface |
| **File System Monitoring Failure** | Restart ThreatLens service, check system resources |
| **Log Rotation Issues** | Configure log rotation handling in source settings |

**Detailed Solutions**:

1. **Fix File Permissions**:
   ```bash
   # Option 1: Make file readable by all
   sudo chmod 644 /path/to/log/file
   
   # Option 2: Add ThreatLens user to log group
   sudo usermod -a -G adm threatlens_user
   
   # Option 3: Use ACLs for specific access
   sudo setfacl -m u:threatlens_user:r /path/to/log/file
   ```

2. **Handle Log Rotation**:
   ```bash
   # Configure logrotate to maintain permissions
   sudo vim /etc/logrotate.d/myapp
   
   # Add these lines:
   /path/to/log/file {
       daily
       rotate 7
       compress
       delaycompress
       missingok
       notifempty
       create 644 myapp adm
       postrotate
           # Signal ThreatLens to reopen file handles
           pkill -USR1 -f "python.*main.py"
       endscript
   }
   ```

### Issue: High Log Volume Causing Delays

**Symptoms**:
- Processing queue growing continuously
- High memory usage
- Delayed event processing

**Diagnostic Steps**:

1. **Check Queue Status**:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        http://localhost:8000/api/metrics | jq '.metrics[] | select(.metric_type=="queue_depth")'
   ```

2. **Monitor Processing Rate**:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        http://localhost:8000/api/metrics | jq '.metrics[] | select(.metric_type=="processing_rate")'
   ```

**Solutions**:

1. **Optimize Processing Configuration**:
   ```python
   # In configuration file or environment variables
   PROCESSING_BATCH_SIZE=200  # Increase batch size
   MAX_QUEUE_SIZE=50000       # Increase queue capacity
   PROCESSING_WORKERS=4       # Add more processing workers
   ```

2. **Implement Log Filtering**:
   ```python
   # Add filters to reduce noise
   LOG_FILTERS = {
       "exclude_patterns": [
           r".*DEBUG.*",
           r".*health.*check.*"
       ],
       "include_only_severity": ["ERROR", "WARN", "CRITICAL"]
   }
   ```

## WebSocket Connection Problems

### Issue: Dashboard Not Updating in Real-Time

**Symptoms**:
- Events not appearing automatically
- Connection status shows "disconnected"
- Browser console shows WebSocket errors

**Diagnostic Steps**:

1. **Check WebSocket Server Status**:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        http://localhost:8000/api/health | jq '.components.websocket_server'
   ```

2. **Test WebSocket Connection**:
   ```bash
   # Using websocat (install with: cargo install websocat)
   echo '{"type":"ping"}' | websocat ws://localhost:8000/ws?token=YOUR_API_KEY
   ```

3. **Check Browser Console**:
   - Open browser developer tools (F12)
   - Look for WebSocket connection errors
   - Check network tab for failed WebSocket upgrade

**Common Causes and Solutions**:

| Cause | Solution |
|-------|----------|
| **Firewall Blocking WebSocket** | Configure firewall to allow WebSocket connections |
| **Proxy Issues** | Configure proxy to support WebSocket upgrade |
| **Authentication Failure** | Verify API key is correct and has WebSocket permissions |
| **Server Overload** | Check server resources and scale if necessary |
| **Browser Compatibility** | Use modern browser, disable interfering extensions |

**Detailed Solutions**:

1. **Configure Nginx Proxy for WebSocket**:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location /ws {
           proxy_pass http://localhost:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_read_timeout 86400;
       }
   }
   ```

2. **Debug WebSocket Connection**:
   ```javascript
   // Add to browser console for debugging
   const ws = new WebSocket('ws://localhost:8000/ws?token=YOUR_API_KEY');
   
   ws.onopen = () => console.log('WebSocket connected');
   ws.onclose = (event) => console.log('WebSocket closed:', event.code, event.reason);
   ws.onerror = (error) => console.error('WebSocket error:', error);
   ws.onmessage = (event) => console.log('Message received:', event.data);
   ```

### Issue: Frequent WebSocket Disconnections

**Symptoms**:
- Connection drops every few minutes
- Automatic reconnection attempts
- Intermittent real-time updates

**Diagnostic Steps**:

1. **Check Connection Stability**:
   ```bash
   # Monitor WebSocket connections
   netstat -an | grep :8000 | grep ESTABLISHED
   
   # Check for connection timeouts in logs
   grep -i "websocket.*timeout\|websocket.*disconnect" logs/threatlens.log
   ```

2. **Monitor Network Quality**:
   ```bash
   # Test network stability
   ping -c 100 localhost
   
   # Check for packet loss
   mtr localhost
   ```

**Solutions**:

1. **Adjust WebSocket Timeouts**:
   ```python
   # In WebSocket server configuration
   WEBSOCKET_PING_INTERVAL = 30  # Send ping every 30 seconds
   WEBSOCKET_PING_TIMEOUT = 10   # Wait 10 seconds for pong
   WEBSOCKET_CLOSE_TIMEOUT = 10  # Wait 10 seconds for close
   ```

2. **Implement Robust Reconnection**:
   ```javascript
   class RobustWebSocket {
     constructor(url, options = {}) {
       this.url = url;
       this.options = {
         maxReconnectAttempts: 10,
         reconnectInterval: 5000,
         ...options
       };
       this.reconnectAttempts = 0;
       this.connect();
     }
   
     connect() {
       this.ws = new WebSocket(this.url);
       
       this.ws.onopen = () => {
         console.log('WebSocket connected');
         this.reconnectAttempts = 0;
       };
       
       this.ws.onclose = (event) => {
         if (this.reconnectAttempts < this.options.maxReconnectAttempts) {
           setTimeout(() => {
             this.reconnectAttempts++;
             console.log(`Reconnecting... (${this.reconnectAttempts}/${this.options.maxReconnectAttempts})`);
             this.connect();
           }, this.options.reconnectInterval);
         }
       };
     }
   }
   ```

## Processing Performance Issues

### Issue: Slow Event Processing

**Symptoms**:
- High processing latency (>5 seconds)
- Growing processing queue
- High CPU or memory usage

**Diagnostic Steps**:

1. **Check Processing Metrics**:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        http://localhost:8000/api/metrics | jq '.summary'
   ```

2. **Monitor System Resources**:
   ```bash
   # Check CPU usage
   top -p $(pgrep -f "python.*main.py")
   
   # Check memory usage
   ps -o pid,ppid,cmd,%mem,%cpu -p $(pgrep -f "python.*main.py")
   
   # Check I/O wait
   iostat -x 1 5
   ```

3. **Profile Processing Pipeline**:
   ```bash
   # Enable detailed logging
   export LOG_LEVEL=DEBUG
   
   # Check processing times in logs
   grep "processing_time" logs/threatlens.log | tail -20
   ```

**Solutions**:

1. **Optimize Processing Configuration**:
   ```python
   # Increase processing parallelism
   PROCESSING_WORKERS = 4
   PROCESSING_BATCH_SIZE = 100
   
   # Optimize AI analysis
   AI_ANALYSIS_TIMEOUT = 5.0
   AI_ANALYSIS_BATCH_SIZE = 10
   
   # Database optimization
   DB_CONNECTION_POOL_SIZE = 20
   DB_QUERY_TIMEOUT = 10.0
   ```

2. **Implement Processing Priorities**:
   ```python
   # Configure priority-based processing
   PRIORITY_QUEUES = {
       "critical": {"max_size": 1000, "workers": 2},
       "high": {"max_size": 5000, "workers": 2},
       "normal": {"max_size": 10000, "workers": 1}
   }
   ```

### Issue: Memory Leaks in Long-Running Processes

**Symptoms**:
- Continuously increasing memory usage
- System becomes unresponsive over time
- Out of memory errors

**Diagnostic Steps**:

1. **Monitor Memory Usage Over Time**:
   ```bash
   # Create memory monitoring script
   cat > monitor_memory.sh << 'EOF'
   #!/bin/bash
   while true; do
       echo "$(date): $(ps -o pid,ppid,cmd,%mem -p $(pgrep -f 'python.*main.py'))"
       sleep 60
   done
   EOF
   
   chmod +x monitor_memory.sh
   ./monitor_memory.sh > memory_usage.log &
   ```

2. **Profile Memory Usage**:
   ```python
   # Add memory profiling to code
   import tracemalloc
   import psutil
   import os
   
   def log_memory_usage():
       process = psutil.Process(os.getpid())
       memory_info = process.memory_info()
       print(f"RSS: {memory_info.rss / 1024 / 1024:.2f} MB")
       print(f"VMS: {memory_info.vms / 1024 / 1024:.2f} MB")
       
       if tracemalloc.is_tracing():
           snapshot = tracemalloc.take_snapshot()
           top_stats = snapshot.statistics('lineno')
           for stat in top_stats[:10]:
               print(stat)
   ```

**Solutions**:

1. **Implement Memory Management**:
   ```python
   # Add garbage collection
   import gc
   
   def cleanup_memory():
       gc.collect()
       
   # Schedule regular cleanup
   import schedule
   schedule.every(30).minutes.do(cleanup_memory)
   ```

2. **Optimize Data Structures**:
   ```python
   # Use generators instead of lists for large datasets
   def process_log_entries():
       for entry in log_entry_generator():
           yield process_entry(entry)
   
   # Implement LRU cache for frequently accessed data
   from functools import lru_cache
   
   @lru_cache(maxsize=1000)
   def get_cached_analysis(log_hash):
       return expensive_analysis(log_hash)
   ```

## Notification Delivery Problems

### Issue: Notifications Not Being Sent

**Symptoms**:
- High-severity events not triggering notifications
- Notification history shows "failed" status
- No notification delivery confirmations

**Diagnostic Steps**:

1. **Check Notification Configuration**:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        http://localhost:8000/api/notifications/channels
   ```

2. **Test Notification Channels**:
   ```bash
   curl -X POST \
        -H "Authorization: Bearer YOUR_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"test_message": "Test notification"}' \
        http://localhost:8000/api/notifications/channels/1/test
   ```

3. **Review Notification History**:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        "http://localhost:8000/api/notifications/history?status=failed"
   ```

**Common Solutions**:

1. **Fix Email Configuration**:
   ```python
   # Verify SMTP settings
   import smtplib
   from email.mime.text import MIMEText
   
   def test_smtp_connection():
       try:
           server = smtplib.SMTP('smtp.gmail.com', 587)
           server.starttls()
           server.login('your-email@gmail.com', 'your-app-password')
           server.quit()
           print("SMTP connection successful")
       except Exception as e:
           print(f"SMTP connection failed: {e}")
   ```

2. **Debug Webhook Notifications**:
   ```bash
   # Test webhook endpoint manually
   curl -X POST \
        -H "Content-Type: application/json" \
        -d '{"text": "Test message from ThreatLens"}' \
        https://hooks.slack.com/services/YOUR/WEBHOOK/URL
   ```

### Issue: Notification Rate Limiting

**Symptoms**:
- Notifications stop after initial burst
- "Rate limit exceeded" errors in logs
- Delayed notification delivery

**Solutions**:

1. **Configure Notification Throttling**:
   ```python
   NOTIFICATION_THROTTLING = {
       "max_notifications_per_hour": 100,
       "max_notifications_per_channel": 50,
       "burst_limit": 10,
       "burst_window": 300  # 5 minutes
   }
   ```

2. **Implement Smart Notification Grouping**:
   ```python
   def group_similar_notifications(notifications):
       groups = {}
       for notification in notifications:
           key = (notification.category, notification.severity)
           if key not in groups:
               groups[key] = []
           groups[key].append(notification)
       
       return groups
   ```

## System Health Issues

### Issue: Component Health Checks Failing

**Symptoms**:
- Health API returns "unhealthy" status
- Specific components showing as "failed"
- System performance degradation

**Diagnostic Steps**:

1. **Check Individual Component Health**:
   ```bash
   # Get detailed health status
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        http://localhost:8000/api/health | jq '.components'
   ```

2. **Review Component Logs**:
   ```bash
   # Check for component-specific errors
   grep -E "(file_monitor|processing_queue|websocket_server|database)" logs/threatlens.log | tail -20
   ```

**Solutions by Component**:

1. **File Monitor Issues**:
   ```bash
   # Check file system events support
   python -c "
   import watchdog
   from watchdog.observers import Observer
   print('Watchdog version:', watchdog.__version__)
   observer = Observer()
   print('Observer created successfully')
   "
   
   # Restart file monitoring
   curl -X POST \
        -H "Authorization: Bearer YOUR_API_KEY" \
        http://localhost:8000/api/system/restart-component/file_monitor
   ```

2. **Database Connection Issues**:
   ```bash
   # Test database connectivity
   python -c "
   import sqlite3
   conn = sqlite3.connect('data/threatlens.db')
   cursor = conn.cursor()
   cursor.execute('SELECT COUNT(*) FROM events')
   print('Database accessible, events count:', cursor.fetchone()[0])
   conn.close()
   "
   ```

## Database and Storage Issues

### Issue: Database Performance Degradation

**Symptoms**:
- Slow query responses
- High disk I/O
- Database connection timeouts

**Diagnostic Steps**:

1. **Check Database Size and Growth**:
   ```bash
   # Check database file size
   ls -lh data/threatlens.db
   
   # Check table sizes
   sqlite3 data/threatlens.db "
   SELECT name, COUNT(*) as row_count 
   FROM sqlite_master sm 
   JOIN (SELECT name as table_name FROM sqlite_master WHERE type='table') t 
   ON sm.name = t.table_name 
   GROUP BY name;
   "
   ```

2. **Analyze Query Performance**:
   ```sql
   -- Enable query logging in SQLite
   PRAGMA query_only = ON;
   
   -- Check for missing indexes
   EXPLAIN QUERY PLAN SELECT * FROM events WHERE timestamp > datetime('now', '-1 hour');
   ```

**Solutions**:

1. **Database Optimization**:
   ```sql
   -- Optimize database
   VACUUM;
   ANALYZE;
   
   -- Add missing indexes
   CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
   CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
   CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
   ```

2. **Implement Database Cleanup**:
   ```python
   # Automated cleanup script
   def cleanup_old_data():
       # Remove events older than 90 days
       cursor.execute("""
           DELETE FROM events 
           WHERE timestamp < datetime('now', '-90 days')
       """)
       
       # Remove old metrics
       cursor.execute("""
           DELETE FROM processing_metrics 
           WHERE timestamp < datetime('now', '-30 days')
       """)
       
       # Remove old notification history
       cursor.execute("""
           DELETE FROM notification_history 
           WHERE sent_at < datetime('now', '-30 days')
       """)
   ```

## Configuration Problems

### Issue: Invalid Configuration Causing Startup Failures

**Symptoms**:
- ThreatLens fails to start
- Configuration validation errors
- Missing required settings

**Diagnostic Steps**:

1. **Validate Configuration**:
   ```bash
   # Check configuration file syntax
   python -c "
   import json
   with open('config/monitoring_config.json') as f:
       config = json.load(f)
   print('Configuration is valid JSON')
   "
   ```

2. **Check Required Environment Variables**:
   ```bash
   # List required environment variables
   env | grep -E "(THREATLENS|LOG_|DB_|NOTIFICATION_)"
   ```

**Solutions**:

1. **Reset to Default Configuration**:
   ```bash
   # Backup current configuration
   cp config/monitoring_config.json config/monitoring_config.json.backup
   
   # Reset to defaults
   python -c "
   import json
   default_config = {
       'log_sources': [],
       'processing_batch_size': 100,
       'max_queue_size': 10000,
       'notification_rules': [],
       'health_check_interval': 60
   }
   with open('config/monitoring_config.json', 'w') as f:
       json.dump(default_config, f, indent=2)
   print('Configuration reset to defaults')
   "
   ```

2. **Validate Configuration Schema**:
   ```python
   # Configuration validation script
   import json
   import jsonschema
   
   schema = {
       "type": "object",
       "properties": {
           "log_sources": {"type": "array"},
           "processing_batch_size": {"type": "integer", "minimum": 1},
           "max_queue_size": {"type": "integer", "minimum": 100}
       },
       "required": ["log_sources", "processing_batch_size", "max_queue_size"]
   }
   
   with open('config/monitoring_config.json') as f:
       config = json.load(f)
   
   jsonschema.validate(config, schema)
   print("Configuration is valid")
   ```

## Diagnostic Tools and Commands

### System Information Collection

```bash
#!/bin/bash
# ThreatLens diagnostic information collector

echo "=== ThreatLens Diagnostic Report ==="
echo "Generated: $(date)"
echo

echo "=== System Information ==="
uname -a
python --version
pip list | grep -E "(fastapi|watchdog|websockets|sqlite)"
echo

echo "=== Process Information ==="
ps aux | grep -E "(python.*main.py|threatlens)" | grep -v grep
echo

echo "=== Network Information ==="
netstat -tlnp | grep :8000
echo

echo "=== File Permissions ==="
ls -la logs/
ls -la data/
ls -la config/
echo

echo "=== Disk Usage ==="
df -h
du -sh data/ logs/ config/
echo

echo "=== Recent Logs ==="
tail -50 logs/threatlens.log
echo

echo "=== Configuration ==="
cat config/monitoring_config.json 2>/dev/null || echo "Configuration file not found"
echo

echo "=== API Health Check ==="
curl -s -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/api/health | jq . 2>/dev/null || echo "API not accessible"
```

### Performance Monitoring Script

```bash
#!/bin/bash
# Performance monitoring script

LOG_FILE="performance_monitor.log"

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Get process info
    PROCESS_INFO=$(ps -o pid,ppid,cmd,%mem,%cpu -p $(pgrep -f "python.*main.py") 2>/dev/null)
    
    # Get system load
    LOAD_AVG=$(uptime | awk -F'load average:' '{print $2}')
    
    # Get memory info
    MEMORY_INFO=$(free -m | grep '^Mem:')
    
    # Get disk I/O
    DISK_IO=$(iostat -d 1 1 | tail -n +4 | head -1)
    
    # Log everything
    echo "[$TIMESTAMP] Process: $PROCESS_INFO" >> $LOG_FILE
    echo "[$TIMESTAMP] Load: $LOAD_AVG" >> $LOG_FILE
    echo "[$TIMESTAMP] Memory: $MEMORY_INFO" >> $LOG_FILE
    echo "[$TIMESTAMP] Disk I/O: $DISK_IO" >> $LOG_FILE
    echo "[$TIMESTAMP] ---" >> $LOG_FILE
    
    sleep 60
done
```

## Advanced Troubleshooting

### Debugging with Python Debugger

```python
# Add to problematic code sections
import pdb; pdb.set_trace()

# Or use remote debugging
import ptvsd
ptvsd.enable_attach(address=('localhost', 5678))
ptvsd.wait_for_attach()
```

### Memory Profiling

```python
# Memory profiling script
import tracemalloc
import psutil
import os
import time

def profile_memory():
    tracemalloc.start()
    
    # Your code here
    time.sleep(60)  # Run for 1 minute
    
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')
    
    print("Top 10 memory allocations:")
    for index, stat in enumerate(top_stats[:10], 1):
        print(f"{index}. {stat}")
    
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    print(f"\nTotal memory usage: {memory_info.rss / 1024 / 1024:.2f} MB")
```

### Network Debugging

```bash
# Monitor network connections
watch -n 1 'netstat -an | grep :8000'

# Capture WebSocket traffic
tcpdump -i lo -A -s 0 'port 8000'

# Test WebSocket with detailed output
websocat -v ws://localhost:8000/ws?token=YOUR_API_KEY
```

### Database Debugging

```sql
-- Enable SQLite logging
PRAGMA query_only = ON;

-- Check database integrity
PRAGMA integrity_check;

-- Analyze query performance
EXPLAIN QUERY PLAN SELECT * FROM events WHERE severity > 7;

-- Check database statistics
PRAGMA database_list;
PRAGMA table_info(events);
```

## Getting Additional Help

### Log Collection for Support

When contacting support, collect these logs:

```bash
# Create support bundle
mkdir threatlens_support_$(date +%Y%m%d_%H%M%S)
cd threatlens_support_$(date +%Y%m%d_%H%M%S)

# Copy logs
cp ../logs/threatlens.log .
cp ../config/monitoring_config.json .

# System information
uname -a > system_info.txt
python --version >> system_info.txt
pip list > pip_list.txt

# Process information
ps aux | grep python > process_info.txt

# Network information
netstat -tlnp > network_info.txt

# API health check
curl -s -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/api/health > api_health.json

# Create archive
cd ..
tar -czf threatlens_support_$(date +%Y%m%d_%H%M%S).tar.gz threatlens_support_$(date +%Y%m%d_%H%M%S)/
```

### Support Channels

- **GitHub Issues**: https://github.com/your-org/threatlens/issues
- **Documentation**: https://docs.threatlens.com
- **Community Forum**: https://community.threatlens.com
- **Email Support**: support@threatlens.com

When reporting issues, include:
- ThreatLens version
- Operating system and version
- Python version
- Complete error messages
- Steps to reproduce
- Support bundle (if requested)

This troubleshooting guide should help resolve most common issues with ThreatLens real-time monitoring. For issues not covered here, please contact support with detailed information about your specific problem.