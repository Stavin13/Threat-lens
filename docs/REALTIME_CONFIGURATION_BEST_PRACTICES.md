# ThreatLens Real-Time Monitoring Configuration Best Practices

## Overview

This document provides comprehensive best practices for configuring ThreatLens real-time monitoring to ensure optimal performance, security, and reliability. It covers configuration strategies, performance tuning, security hardening, and operational excellence.

## Table of Contents

1. [Configuration Management](#configuration-management)
2. [Performance Optimization](#performance-optimization)
3. [Security Best Practices](#security-best-practices)
4. [Monitoring and Alerting](#monitoring-and-alerting)
5. [Log Source Configuration](#log-source-configuration)
6. [Notification Configuration](#notification-configuration)
7. [Database Configuration](#database-configuration)
8. [Network Configuration](#network-configuration)
9. [Operational Best Practices](#operational-best-practices)
10. [Troubleshooting Guidelines](#troubleshooting-guidelines)

## Configuration Management

### Environment-Based Configuration

```bash
# Use environment-specific configuration files
.env.development    # Development settings
.env.staging       # Staging environment
.env.production    # Production environment

# Load appropriate configuration based on environment
export ENVIRONMENT=production
source .env.${ENVIRONMENT}
```

### Configuration Validation

```python
# Implement configuration validation
def validate_configuration():
    """Validate all configuration parameters before startup."""
    required_vars = [
        'DATABASE_URL',
        'SECRET_KEY',
        'API_KEY'
    ]
    
    for var in required_vars:
        if not os.getenv(var):
            raise ValueError(f"Required environment variable {var} not set")
    
    # Validate numeric values
    batch_size = int(os.getenv('PROCESSING_BATCH_SIZE', 100))
    if batch_size < 1 or batch_size > 1000:
        raise ValueError("PROCESSING_BATCH_SIZE must be between 1 and 1000")
    
    # Validate file paths
    log_path = os.getenv('LOG_PATH', '/var/log/threatlens')
    if not os.path.exists(log_path):
        os.makedirs(log_path, exist_ok=True)
```

### Configuration Versioning

```bash
# Version control configuration files
git add .env.example config/
git commit -m "Update configuration for v2.1.0"
git tag -a config-v2.1.0 -m "Configuration version 2.1.0"

# Track configuration changes
cat > config/CHANGELOG.md << 'EOF'
# Configuration Changelog

## v2.1.0 - 2024-01-15
- Added WebSocket connection limits
- Increased default batch size to 200
- Added new notification channels

## v2.0.0 - 2024-01-01
- Breaking: Changed database schema
- Added real-time processing configuration
- Updated security settings
EOF
```

### Configuration Templates

```bash
# Create configuration templates for different deployment sizes
templates/
├── small-org.env          # < 10K events/day
├── medium-org.env         # 10K-100K events/day
├── large-org.env          # 100K-1M events/day
└── enterprise.env         # > 1M events/day

# Small organization template
cat > templates/small-org.env << 'EOF'
# Small Organization Configuration (< 10K events/day)
PROCESSING_BATCH_SIZE=50
MAX_QUEUE_SIZE=5000
PROCESSING_WORKERS=2
DB_CONNECTION_POOL_SIZE=5
WEBSOCKET_MAX_CONNECTIONS=50
NOTIFICATION_RATE_LIMIT=10
EOF
```

## Performance Optimization

### Processing Configuration

```bash
# Optimize processing parameters based on system resources
# Formula: workers = min(cpu_cores, max_concurrent_events / events_per_worker)

# For 4-core system processing 100 events/second:
PROCESSING_WORKERS=4
PROCESSING_BATCH_SIZE=100
MAX_QUEUE_SIZE=10000

# Adjust based on memory constraints
# Memory per worker ≈ 100MB + (batch_size * 2KB)
# For 8GB system: max_workers = (8GB - 2GB) / 200MB = 30 workers
```

### Database Optimization

```bash
# SQLite optimization
DATABASE_URL="sqlite:///data/threatlens.db?cache=shared&mode=rwc"
SQLITE_CACHE_SIZE=10000      # 10MB cache
SQLITE_TEMP_STORE=memory     # Use memory for temp tables
SQLITE_SYNCHRONOUS=normal    # Balance safety and performance
SQLITE_WAL_MODE=true         # Enable WAL mode for concurrency

# PostgreSQL optimization
DATABASE_URL="postgresql://user:pass@host:5432/db?sslmode=require"
DB_CONNECTION_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
```

### Memory Management

```bash
# Configure memory limits and garbage collection
MEMORY_LIMIT_MB=4096
MEMORY_WARNING_THRESHOLD=0.8
MEMORY_CRITICAL_THRESHOLD=0.9

# Python garbage collection tuning
PYTHONHASHSEED=0
PYTHONOPTIMIZE=1
PYTHONDONTWRITEBYTECODE=1

# Enable memory profiling in development
ENABLE_MEMORY_PROFILING=false
MEMORY_PROFILE_INTERVAL=300
```

### Caching Configuration

```bash
# Configure caching for better performance
CACHE_ENABLED=true
CACHE_TYPE=memory           # memory, redis, memcached
CACHE_DEFAULT_TIMEOUT=3600
CACHE_MAX_SIZE=1000

# Redis caching (for multi-node deployments)
REDIS_URL=redis://localhost:6379/0
REDIS_CONNECTION_POOL_SIZE=10
REDIS_SOCKET_TIMEOUT=5
```

## Security Best Practices

### Authentication and Authorization

```bash
# Strong authentication configuration
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Session configuration
SESSION_TIMEOUT=3600        # 1 hour
MAX_SESSIONS_PER_USER=5
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=strict
```

### Encryption Configuration

```bash
# Enable encryption at rest and in transit
ENCRYPTION_ENABLED=true
ENCRYPTION_ALGORITHM=AES-256-GCM
ENCRYPTION_KEY_ROTATION_DAYS=90

# TLS configuration
TLS_ENABLED=true
TLS_VERSION=1.2
TLS_CIPHER_SUITES="ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256"
TLS_CERT_PATH=/etc/ssl/certs/threatlens.crt
TLS_KEY_PATH=/etc/ssl/private/threatlens.key
```

### Input Validation

```bash
# Configure strict input validation
INPUT_VALIDATION_ENABLED=true
MAX_REQUEST_SIZE=10485760   # 10MB
MAX_JSON_PAYLOAD_SIZE=1048576  # 1MB
MAX_LOG_ENTRY_SIZE=65536    # 64KB

# File path validation
ALLOWED_LOG_PATHS="/var/log,/opt/app/logs,/home/user/logs"
BLOCKED_LOG_PATHS="/etc,/proc,/sys,/dev"
```

### Rate Limiting

```bash
# Configure rate limiting to prevent abuse
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STORAGE=memory   # memory, redis
RATE_LIMIT_STRATEGY=fixed-window

# API rate limits
API_RATE_LIMIT_PER_MINUTE=1000
API_RATE_LIMIT_PER_HOUR=10000
API_RATE_LIMIT_PER_DAY=100000

# WebSocket rate limits
WEBSOCKET_RATE_LIMIT_PER_MINUTE=100
WEBSOCKET_MAX_CONNECTIONS_PER_IP=10
```

## Monitoring and Alerting

### Health Check Configuration

```bash
# Configure comprehensive health checks
HEALTH_CHECK_ENABLED=true
HEALTH_CHECK_INTERVAL=30
HEALTH_CHECK_TIMEOUT=10

# Component health checks
HEALTH_CHECK_DATABASE=true
HEALTH_CHECK_FILE_MONITOR=true
HEALTH_CHECK_WEBSOCKET=true
HEALTH_CHECK_QUEUE=true
HEALTH_CHECK_EXTERNAL_APIS=true
```

### Metrics Configuration

```bash
# Enable metrics collection
METRICS_ENABLED=true
METRICS_INTERVAL=60
METRICS_RETENTION_DAYS=30

# Prometheus metrics
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090
PROMETHEUS_PATH=/metrics

# Custom metrics
ENABLE_CUSTOM_METRICS=true
METRICS_INCLUDE_SYSTEM=true
METRICS_INCLUDE_APPLICATION=true
```

### Logging Configuration

```bash
# Configure structured logging
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json             # json, text
LOG_INCLUDE_TIMESTAMP=true
LOG_INCLUDE_LEVEL=true
LOG_INCLUDE_MODULE=true

# Log rotation
LOG_ROTATION_ENABLED=true
LOG_MAX_SIZE=100MB
LOG_BACKUP_COUNT=10
LOG_ROTATION_INTERVAL=daily

# Sensitive data filtering
LOG_FILTER_SENSITIVE_DATA=true
LOG_SENSITIVE_PATTERNS="password,token,key,secret"
```

## Log Source Configuration

### File Monitoring Best Practices

```json
{
  "log_sources": [
    {
      "path": "/var/log/syslog",
      "source_name": "System Logs",
      "enabled": true,
      "polling_interval": 1.0,
      "file_pattern": "*",
      "recursive": false,
      "priority": "normal",
      "max_file_size": 1073741824,
      "ignore_older_than": "7d",
      "filters": {
        "exclude_patterns": [
          ".*DEBUG.*",
          ".*heartbeat.*",
          ".*keepalive.*"
        ],
        "include_patterns": [
          ".*ERROR.*",
          ".*WARN.*",
          ".*CRITICAL.*",
          ".*security.*",
          ".*authentication.*"
        ]
      },
      "parser_config": {
        "format": "syslog",
        "timestamp_format": "%b %d %H:%M:%S",
        "multiline_pattern": null,
        "encoding": "utf-8"
      },
      "error_handling": {
        "on_parse_error": "log_and_continue",
        "on_file_error": "retry_with_backoff",
        "max_retries": 3,
        "retry_delay": 5.0
      }
    }
  ]
}
```

### Performance Optimization for Log Sources

```json
{
  "performance_settings": {
    "batch_processing": {
      "enabled": true,
      "batch_size": 100,
      "max_wait_time": 5.0,
      "parallel_processing": true
    },
    "file_handling": {
      "use_mmap": true,
      "buffer_size": 65536,
      "read_ahead": true,
      "cache_file_handles": true
    },
    "memory_management": {
      "max_memory_per_source": 104857600,
      "cleanup_interval": 300,
      "force_gc_threshold": 0.8
    }
  }
}
```

### Log Source Security

```json
{
  "security_settings": {
    "file_access": {
      "validate_paths": true,
      "follow_symlinks": false,
      "check_permissions": true,
      "sandbox_enabled": true
    },
    "content_filtering": {
      "mask_sensitive_data": true,
      "sensitive_patterns": [
        "\\b\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}\\b",
        "\\b\\d{3}-\\d{2}-\\d{4}\\b",
        "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b"
      ],
      "replacement_text": "***MASKED***"
    }
  }
}
```

## Notification Configuration

### Email Notification Best Practices

```json
{
  "email_notifications": {
    "smtp_settings": {
      "server": "smtp.gmail.com",
      "port": 587,
      "use_tls": true,
      "use_ssl": false,
      "timeout": 30,
      "connection_pool_size": 5,
      "max_retries": 3,
      "retry_delay": 5.0
    },
    "message_settings": {
      "from_address": "ThreatLens Security <alerts@company.com>",
      "reply_to": "security-team@company.com",
      "subject_prefix": "[ThreatLens]",
      "include_logo": true,
      "include_system_info": true
    },
    "rate_limiting": {
      "max_per_minute": 10,
      "max_per_hour": 100,
      "max_per_day": 500,
      "burst_limit": 5,
      "cooldown_period": 300
    },
    "content_optimization": {
      "html_enabled": true,
      "text_fallback": true,
      "compress_attachments": true,
      "max_attachment_size": 10485760
    }
  }
}
```

### Webhook Notification Best Practices

```json
{
  "webhook_notifications": {
    "connection_settings": {
      "timeout": 10,
      "max_retries": 3,
      "retry_delay": 5.0,
      "exponential_backoff": true,
      "verify_ssl": true,
      "follow_redirects": true
    },
    "payload_settings": {
      "format": "json",
      "compression": "gzip",
      "include_metadata": true,
      "include_raw_log": false,
      "max_payload_size": 1048576
    },
    "security_settings": {
      "sign_requests": true,
      "signature_algorithm": "HMAC-SHA256",
      "include_timestamp": true,
      "validate_response": true
    }
  }
}
```

### Notification Rules Optimization

```json
{
  "notification_rules": [
    {
      "name": "Critical Security Events",
      "priority": 1,
      "enabled": true,
      "conditions": {
        "severity_range": [9, 10],
        "categories": ["security", "breach", "malware"],
        "time_window": null,
        "source_patterns": ["auth.*", "security.*"],
        "content_patterns": ["failed.*login", "unauthorized.*access"]
      },
      "actions": {
        "channels": ["email_executives", "slack_security", "sms_oncall"],
        "immediate": true,
        "escalation": {
          "enabled": true,
          "delay": 300,
          "channels": ["phone_oncall"]
        }
      },
      "throttling": {
        "enabled": false,
        "reason": "Critical events should never be throttled"
      }
    },
    {
      "name": "High Priority Alerts",
      "priority": 2,
      "enabled": true,
      "conditions": {
        "severity_range": [7, 8],
        "categories": ["security", "system", "application"],
        "time_restrictions": {
          "business_hours_only": false,
          "timezone": "UTC"
        }
      },
      "actions": {
        "channels": ["email_security_team", "slack_alerts"],
        "immediate": false,
        "batch_window": 300
      },
      "throttling": {
        "enabled": true,
        "max_notifications": 20,
        "time_window": 3600,
        "summary_enabled": true
      }
    }
  ]
}
```

## Database Configuration

### SQLite Best Practices

```bash
# SQLite configuration for optimal performance
DATABASE_URL="sqlite:///data/threatlens.db"

# SQLite pragma settings
SQLITE_PRAGMAS="
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=10000;
PRAGMA temp_store=memory;
PRAGMA mmap_size=268435456;
PRAGMA optimize;
"

# Connection settings
SQLITE_TIMEOUT=30.0
SQLITE_CHECK_SAME_THREAD=false
SQLITE_ISOLATION_LEVEL=null
```

### PostgreSQL Best Practices

```bash
# PostgreSQL configuration
DATABASE_URL="postgresql://threatlens:password@localhost:5432/threatlens"

# Connection pool settings
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
DB_POOL_PRE_PING=true

# Query optimization
DB_ECHO=false
DB_ECHO_POOL=false
DB_QUERY_TIMEOUT=30.0
DB_STATEMENT_TIMEOUT=60.0
```

### Database Maintenance

```bash
# Automated maintenance tasks
DB_MAINTENANCE_ENABLED=true
DB_MAINTENANCE_SCHEDULE="0 2 * * *"  # Daily at 2 AM

# Cleanup settings
DB_CLEANUP_ENABLED=true
DB_RETENTION_DAYS=365
DB_ARCHIVE_OLD_DATA=true
DB_COMPRESS_ARCHIVES=true

# Performance monitoring
DB_SLOW_QUERY_THRESHOLD=1.0
DB_LOG_SLOW_QUERIES=true
DB_ANALYZE_FREQUENCY=daily
DB_VACUUM_FREQUENCY=weekly
```

## Network Configuration

### WebSocket Configuration

```bash
# WebSocket server settings
WEBSOCKET_ENABLED=true
WEBSOCKET_HOST=0.0.0.0
WEBSOCKET_PORT=8000
WEBSOCKET_PATH=/ws

# Connection limits
WEBSOCKET_MAX_CONNECTIONS=1000
WEBSOCKET_MAX_CONNECTIONS_PER_IP=10
WEBSOCKET_CONNECTION_TIMEOUT=300

# Message settings
WEBSOCKET_MAX_MESSAGE_SIZE=65536
WEBSOCKET_PING_INTERVAL=30
WEBSOCKET_PING_TIMEOUT=10
WEBSOCKET_CLOSE_TIMEOUT=10

# Compression
WEBSOCKET_COMPRESSION_ENABLED=true
WEBSOCKET_COMPRESSION_LEVEL=6
WEBSOCKET_COMPRESSION_THRESHOLD=1024
```

### HTTP Configuration

```bash
# HTTP server settings
HTTP_HOST=0.0.0.0
HTTP_PORT=8000
HTTP_WORKERS=4
HTTP_WORKER_CLASS=gevent
HTTP_WORKER_CONNECTIONS=1000

# Request limits
HTTP_MAX_REQUEST_SIZE=10485760
HTTP_REQUEST_TIMEOUT=30
HTTP_KEEPALIVE_TIMEOUT=5
HTTP_MAX_REQUESTS=1000
HTTP_MAX_REQUESTS_JITTER=100

# Security headers
HTTP_SECURITY_HEADERS=true
HTTP_HSTS_MAX_AGE=31536000
HTTP_CONTENT_SECURITY_POLICY="default-src 'self'"
```

### CORS Configuration

```bash
# CORS settings for web interface
CORS_ENABLED=true
CORS_ORIGINS="https://yourdomain.com,https://app.yourdomain.com"
CORS_METHODS="GET,POST,PUT,DELETE,OPTIONS"
CORS_HEADERS="Authorization,Content-Type,X-Requested-With"
CORS_CREDENTIALS=true
CORS_MAX_AGE=3600
```

## Operational Best Practices

### Backup Configuration

```bash
# Automated backup settings
BACKUP_ENABLED=true
BACKUP_SCHEDULE="0 1 * * *"  # Daily at 1 AM
BACKUP_RETENTION_DAYS=30
BACKUP_COMPRESSION=true
BACKUP_ENCRYPTION=true

# Backup locations
BACKUP_LOCAL_PATH=/opt/threatlens/backups
BACKUP_REMOTE_ENABLED=true
BACKUP_REMOTE_TYPE=s3  # s3, gcs, azure
BACKUP_REMOTE_BUCKET=threatlens-backups
BACKUP_REMOTE_PREFIX=production/

# Backup verification
BACKUP_VERIFY_ENABLED=true
BACKUP_TEST_RESTORE=weekly
```

### Update Management

```bash
# Update configuration
AUTO_UPDATE_ENABLED=false
UPDATE_CHECK_ENABLED=true
UPDATE_CHECK_INTERVAL=daily
UPDATE_NOTIFICATION_ENABLED=true

# Maintenance windows
MAINTENANCE_WINDOW_ENABLED=true
MAINTENANCE_WINDOW_START="02:00"
MAINTENANCE_WINDOW_END="04:00"
MAINTENANCE_WINDOW_TIMEZONE="UTC"
MAINTENANCE_WINDOW_DAYS="0,6"  # Sunday and Saturday
```

### Resource Management

```bash
# Resource limits
MAX_CPU_USAGE=80
MAX_MEMORY_USAGE=85
MAX_DISK_USAGE=90
MAX_NETWORK_USAGE=80

# Cleanup settings
CLEANUP_ENABLED=true
CLEANUP_INTERVAL=3600
CLEANUP_OLD_LOGS=true
CLEANUP_TEMP_FILES=true
CLEANUP_CACHE_FILES=true

# Process management
PROCESS_RESTART_ON_FAILURE=true
PROCESS_MAX_RESTARTS=5
PROCESS_RESTART_DELAY=10
PROCESS_HEALTH_CHECK_INTERVAL=60
```

## Troubleshooting Guidelines

### Logging for Troubleshooting

```bash
# Enable debug logging for troubleshooting
LOG_LEVEL=DEBUG
ENABLE_TRACE_LOGGING=true
LOG_SQL_QUERIES=true
LOG_WEBSOCKET_MESSAGES=true
LOG_FILE_OPERATIONS=true

# Performance logging
ENABLE_PERFORMANCE_LOGGING=true
LOG_SLOW_OPERATIONS=true
SLOW_OPERATION_THRESHOLD=1.0
LOG_MEMORY_USAGE=true
LOG_CPU_USAGE=true
```

### Diagnostic Configuration

```bash
# Enable diagnostic features
DIAGNOSTICS_ENABLED=true
DIAGNOSTICS_ENDPOINT=/api/diagnostics
DIAGNOSTICS_AUTH_REQUIRED=true

# Health check details
HEALTH_CHECK_DETAILED=true
HEALTH_CHECK_INCLUDE_METRICS=true
HEALTH_CHECK_INCLUDE_SYSTEM_INFO=true
HEALTH_CHECK_INCLUDE_DEPENDENCIES=true

# Error reporting
ERROR_REPORTING_ENABLED=true
ERROR_REPORTING_INCLUDE_STACK_TRACE=true
ERROR_REPORTING_INCLUDE_ENVIRONMENT=true
ERROR_REPORTING_INCLUDE_REQUEST_DATA=false  # Security consideration
```

### Performance Monitoring

```bash
# Performance monitoring configuration
PERFORMANCE_MONITORING_ENABLED=true
PERFORMANCE_SAMPLING_RATE=0.1  # 10% sampling
PERFORMANCE_INCLUDE_SQL=true
PERFORMANCE_INCLUDE_HTTP=true
PERFORMANCE_INCLUDE_WEBSOCKET=true

# Profiling (development only)
PROFILING_ENABLED=false
PROFILING_OUTPUT_DIR=/tmp/threatlens-profiles
PROFILING_INCLUDE_MEMORY=true
PROFILING_INCLUDE_CPU=true
```

### Configuration Validation Script

```bash
#!/bin/bash
# Configuration validation script

echo "Validating ThreatLens configuration..."

# Check required environment variables
required_vars=(
    "DATABASE_URL"
    "SECRET_KEY"
    "API_KEY"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "ERROR: Required variable $var is not set"
        exit 1
    fi
done

# Validate numeric values
if [ "$PROCESSING_BATCH_SIZE" -lt 1 ] || [ "$PROCESSING_BATCH_SIZE" -gt 1000 ]; then
    echo "ERROR: PROCESSING_BATCH_SIZE must be between 1 and 1000"
    exit 1
fi

# Check file permissions
if [ ! -r "$DATABASE_URL" ] && [[ "$DATABASE_URL" == sqlite* ]]; then
    db_path=$(echo "$DATABASE_URL" | sed 's/sqlite:\/\/\///')
    db_dir=$(dirname "$db_path")
    if [ ! -w "$db_dir" ]; then
        echo "ERROR: Database directory $db_dir is not writable"
        exit 1
    fi
fi

# Validate log paths
IFS=',' read -ra PATHS <<< "$ALLOWED_LOG_PATHS"
for path in "${PATHS[@]}"; do
    if [ ! -d "$path" ]; then
        echo "WARNING: Log path $path does not exist"
    elif [ ! -r "$path" ]; then
        echo "ERROR: Log path $path is not readable"
        exit 1
    fi
done

echo "Configuration validation completed successfully"
```

This comprehensive best practices guide should help you configure ThreatLens for optimal performance, security, and reliability in any environment. Remember to regularly review and update your configuration as your requirements evolve.