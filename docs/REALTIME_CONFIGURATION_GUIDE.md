# ThreatLens Real-Time Monitoring Configuration Guide

## Overview

This guide provides comprehensive configuration instructions, examples, and best practices for ThreatLens real-time monitoring. It covers all aspects of system configuration from basic setup to advanced enterprise deployments.

## Table of Contents

1. [Configuration Overview](#configuration-overview)
2. [Environment Configuration](#environment-configuration)
3. [Log Source Configuration](#log-source-configuration)
4. [Notification Configuration](#notification-configuration)
5. [Performance Configuration](#performance-configuration)
6. [Security Configuration](#security-configuration)
7. [Monitoring Configuration](#monitoring-configuration)
8. [Best Practices](#best-practices)
9. [Configuration Examples](#configuration-examples)
10. [Troubleshooting Configuration](#troubleshooting-configuration)

## Configuration Overview

ThreatLens uses multiple configuration methods:

1. **Environment Variables** (`.env` file): Core system settings
2. **JSON Configuration Files**: Dynamic monitoring settings
3. **Database Configuration**: Runtime settings stored in database
4. **API Configuration**: Settings managed via REST API

### Configuration Hierarchy

Settings are applied in the following order (later overrides earlier):

1. Default values (hardcoded)
2. Configuration files
3. Environment variables
4. Database settings
5. API/Runtime settings

## Environment Configuration

### Basic Environment Setup

Create and configure the `.env` file:

```bash
# Core Application Settings
DEBUG=false
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
SECRET_KEY=your-secret-key-here

# Database Configuration
DATABASE_URL=sqlite:///data/threatlens.db
DB_CONNECTION_POOL_SIZE=10
DB_QUERY_TIMEOUT=30.0

# Real-time Monitoring
REALTIME_ENABLED=true
WEBSOCKET_ENABLED=true
FILE_MONITORING_ENABLED=true

# Processing Configuration
PROCESSING_BATCH_SIZE=100
MAX_QUEUE_SIZE=10000
PROCESSING_WORKERS=2
PROCESSING_TIMEOUT=30.0

# AI Analysis Configuration
AI_ANALYSIS_ENABLED=true
AI_ANALYSIS_TIMEOUT=10.0
GROQ_API_KEY=your_groq_api_key_here

# Notification Configuration
NOTIFICATION_ENABLED=true
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=alerts@company.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true

# Security Configuration
API_KEY=your-api-key-here
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
RATE_LIMIT_ENABLED=true
MAX_REQUESTS_PER_MINUTE=1000

# Monitoring and Metrics
PROMETHEUS_ENABLED=false
PROMETHEUS_PORT=9090
HEALTH_CHECK_INTERVAL=60
METRICS_RETENTION_DAYS=30
```

### Environment-Specific Configurations

#### Development Environment

```bash
# .env.development
DEBUG=true
LOG_LEVEL=DEBUG
HOST=127.0.0.1
PORT=8000

# Relaxed security for development
CORS_ORIGINS=*
RATE_LIMIT_ENABLED=false

# Smaller batch sizes for testing
PROCESSING_BATCH_SIZE=10
MAX_QUEUE_SIZE=1000

# Enable detailed logging
ENABLE_PERFORMANCE_LOGGING=true
ENABLE_DEBUG_ENDPOINTS=true
```

#### Production Environment

```bash
# .env.production
DEBUG=false
LOG_LEVEL=WARNING
HOST=0.0.0.0
PORT=8000

# Strong security settings
SECRET_KEY=complex-secret-key-here
API_KEY=secure-api-key-here
CORS_ORIGINS=https://yourdomain.com

# Optimized for performance
PROCESSING_BATCH_SIZE=200
MAX_QUEUE_SIZE=50000
PROCESSING_WORKERS=4
DB_CONNECTION_POOL_SIZE=20

# Production monitoring
PROMETHEUS_ENABLED=true
HEALTH_CHECK_INTERVAL=30
```

#### High-Volume Environment

```bash
# .env.high-volume
# Optimized for high log volume processing

# Increased processing capacity
PROCESSING_BATCH_SIZE=500
MAX_QUEUE_SIZE=100000
PROCESSING_WORKERS=8
PROCESSING_TIMEOUT=60.0

# Database optimization
DB_CONNECTION_POOL_SIZE=50
DB_QUERY_TIMEOUT=60.0

# Memory management
MEMORY_LIMIT_MB=4096
ENABLE_MEMORY_MONITORING=true

# Aggressive cleanup
CLEANUP_INTERVAL_HOURS=6
MAX_EVENT_AGE_DAYS=7
```

## Log Source Configuration

### Basic Log Source Configuration

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
      "filters": {
        "include_patterns": [],
        "exclude_patterns": [".*DEBUG.*"],
        "min_severity": "INFO"
      }
    }
  ]
}
```

### Advanced Log Source Examples

#### Web Server Logs

```json
{
  "path": "/var/log/nginx",
  "source_name": "Nginx Logs",
  "enabled": true,
  "polling_interval": 0.5,
  "file_pattern": "*.log",
  "recursive": true,
  "priority": "high",
  "parser_config": {
    "format": "nginx_combined",
    "timestamp_format": "%d/%b/%Y:%H:%M:%S %z",
    "fields": {
      "remote_addr": "client_ip",
      "request": "http_request",
      "status": "http_status",
      "body_bytes_sent": "response_size"
    }
  },
  "filters": {
    "exclude_patterns": [
      ".*health.*check.*",
      ".*robots\\.txt.*"
    ],
    "include_status_codes": [400, 401, 403, 404, 500, 502, 503]
  }
}
```

#### Application Logs

```json
{
  "path": "/opt/myapp/logs",
  "source_name": "Application Logs",
  "enabled": true,
  "polling_interval": 1.0,
  "file_pattern": "app-*.log",
  "recursive": false,
  "priority": "high",
  "parser_config": {
    "format": "json",
    "timestamp_field": "timestamp",
    "level_field": "level",
    "message_field": "message"
  },
  "filters": {
    "min_level": "WARN",
    "include_patterns": [
      ".*ERROR.*",
      ".*FATAL.*",
      ".*security.*"
    ]
  },
  "rotation_handling": {
    "detect_rotation": true,
    "follow_rotated": true,
    "max_rotated_files": 5
  }
}
```

#### Security Logs

```json
{
  "path": "/var/log/auth.log",
  "source_name": "Authentication Logs",
  "enabled": true,
  "polling_interval": 0.5,
  "file_pattern": "*",
  "recursive": false,
  "priority": "critical",
  "parser_config": {
    "format": "syslog",
    "extract_fields": {
      "user": "\\buser\\s+(\\w+)",
      "ip": "\\bfrom\\s+([0-9.]+)",
      "service": "^\\w+\\s+\\d+\\s+\\d+:\\d+:\\d+\\s+\\w+\\s+(\\w+)"
    }
  },
  "filters": {
    "include_patterns": [
      ".*Failed password.*",
      ".*Invalid user.*",
      ".*authentication failure.*",
      ".*sudo.*COMMAND.*"
    ]
  },
  "alert_rules": {
    "failed_login_threshold": 5,
    "time_window_minutes": 5,
    "auto_severity": "high"
  }
}
```

#### Database Logs

```json
{
  "path": "/var/log/mysql",
  "source_name": "MySQL Logs",
  "enabled": true,
  "polling_interval": 2.0,
  "file_pattern": "*.log",
  "recursive": false,
  "priority": "normal",
  "parser_config": {
    "format": "mysql",
    "slow_query_threshold": 1.0,
    "extract_queries": true
  },
  "filters": {
    "include_patterns": [
      ".*ERROR.*",
      ".*Warning.*",
      ".*Aborted.*",
      ".*Access denied.*"
    ],
    "exclude_patterns": [
      ".*Quit.*",
      ".*Connect.*"
    ]
  }
}
```

### Log Source Best Practices

#### Performance Optimization

```json
{
  "performance_settings": {
    "batch_processing": {
      "enabled": true,
      "batch_size": 100,
      "max_wait_time": 5.0
    },
    "caching": {
      "enabled": true,
      "cache_size": 1000,
      "cache_ttl": 300
    },
    "compression": {
      "enabled": true,
      "algorithm": "gzip",
      "level": 6
    }
  }
}
```

#### Error Handling

```json
{
  "error_handling": {
    "retry_policy": {
      "max_retries": 3,
      "retry_delay": 5.0,
      "exponential_backoff": true
    },
    "fallback_behavior": {
      "on_parse_error": "store_raw",
      "on_file_error": "log_and_continue",
      "on_permission_error": "alert_admin"
    },
    "dead_letter_queue": {
      "enabled": true,
      "max_size": 10000,
      "retention_hours": 24
    }
  }
}
```

## Notification Configuration

### Email Notifications

#### Basic Email Configuration

```json
{
  "name": "Primary Email Alerts",
  "type": "email",
  "enabled": true,
  "configuration": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "alerts@company.com",
    "password": "app-specific-password",
    "use_tls": true,
    "use_ssl": false,
    "timeout": 30,
    "recipients": [
      "security-team@company.com",
      "admin@company.com"
    ],
    "cc_recipients": [],
    "bcc_recipients": [],
    "from_address": "ThreatLens <alerts@company.com>",
    "reply_to": "no-reply@company.com"
  },
  "template": {
    "subject": "[ThreatLens] {{severity_text}} Alert: {{category}}",
    "body_html": "templates/email_alert.html",
    "body_text": "templates/email_alert.txt"
  },
  "rate_limiting": {
    "max_per_hour": 50,
    "max_per_day": 200,
    "burst_limit": 5
  }
}
```

#### Advanced Email Configuration

```json
{
  "name": "Executive Alerts",
  "type": "email",
  "enabled": true,
  "configuration": {
    "smtp_server": "mail.company.com",
    "smtp_port": 465,
    "username": "threatlens@company.com",
    "password": "secure-password",
    "use_ssl": true,
    "auth_method": "login",
    "recipients": [
      "ciso@company.com",
      "cto@company.com"
    ]
  },
  "filters": {
    "min_severity": 9,
    "categories": ["security", "breach", "critical"],
    "time_restrictions": {
      "business_hours_only": false,
      "timezone": "UTC"
    }
  },
  "template": {
    "subject": "🚨 CRITICAL SECURITY ALERT: {{description}}",
    "body_html": """
    <h2>Critical Security Alert</h2>
    <p><strong>Severity:</strong> {{severity}}/10</p>
    <p><strong>Category:</strong> {{category}}</p>
    <p><strong>Time:</strong> {{timestamp}}</p>
    <p><strong>Source:</strong> {{source}}</p>
    <p><strong>Description:</strong> {{description}}</p>
    <p><strong>Raw Log:</strong></p>
    <pre>{{raw_log}}</pre>
    <p><strong>AI Analysis:</strong></p>
    <ul>
    {{#ai_analysis.indicators}}
    <li>{{.}}</li>
    {{/ai_analysis.indicators}}
    </ul>
    """
  }
}
```

### Webhook Notifications

#### Slack Integration

```json
{
  "name": "Slack Security Channel",
  "type": "webhook",
  "enabled": true,
  "configuration": {
    "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json"
    },
    "timeout": 10,
    "retry_policy": {
      "max_retries": 3,
      "retry_delay": 5
    }
  },
  "payload_template": {
    "text": "Security Alert: {{description}}",
    "attachments": [
      {
        "color": "{{#if (gt severity 7)}}danger{{else}}warning{{/if}}",
        "fields": [
          {
            "title": "Severity",
            "value": "{{severity}}/10",
            "short": true
          },
          {
            "title": "Category",
            "value": "{{category}}",
            "short": true
          },
          {
            "title": "Source",
            "value": "{{source}}",
            "short": true
          },
          {
            "title": "Time",
            "value": "{{timestamp}}",
            "short": true
          }
        ]
      }
    ]
  }
}
```

#### Microsoft Teams Integration

```json
{
  "name": "Teams Security Alerts",
  "type": "webhook",
  "enabled": true,
  "configuration": {
    "webhook_url": "https://outlook.office.com/webhook/...",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json"
    }
  },
  "payload_template": {
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "{{#if (gt severity 7)}}FF0000{{else}}FFA500{{/if}}",
    "summary": "ThreatLens Security Alert",
    "sections": [
      {
        "activityTitle": "Security Alert Detected",
        "activitySubtitle": "{{description}}",
        "facts": [
          {
            "name": "Severity",
            "value": "{{severity}}/10"
          },
          {
            "name": "Category",
            "value": "{{category}}"
          },
          {
            "name": "Source",
            "value": "{{source}}"
          },
          {
            "name": "Time",
            "value": "{{timestamp}}"
          }
        ]
      }
    ]
  }
}
```

### Notification Rules

#### Severity-Based Rules

```json
{
  "rules": [
    {
      "name": "Critical Alerts",
      "enabled": true,
      "conditions": {
        "min_severity": 9,
        "max_severity": 10,
        "categories": ["security", "breach", "malware"],
        "time_window": null
      },
      "channels": ["email_executives", "slack_security", "teams_security"],
      "throttling": {
        "enabled": false
      },
      "escalation": {
        "enabled": true,
        "escalation_time": 300,
        "escalation_channels": ["sms_oncall"]
      }
    },
    {
      "name": "High Priority Alerts",
      "enabled": true,
      "conditions": {
        "min_severity": 7,
        "max_severity": 8,
        "categories": ["security", "authentication", "access_control"]
      },
      "channels": ["email_security_team", "slack_security"],
      "throttling": {
        "enabled": true,
        "max_notifications": 10,
        "time_window": 3600
      }
    },
    {
      "name": "Business Hours Alerts",
      "enabled": true,
      "conditions": {
        "min_severity": 5,
        "time_restrictions": {
          "days_of_week": [1, 2, 3, 4, 5],
          "start_time": "09:00",
          "end_time": "17:00",
          "timezone": "America/New_York"
        }
      },
      "channels": ["email_security_team"],
      "throttling": {
        "enabled": true,
        "max_notifications": 20,
        "time_window": 3600
      }
    }
  ]
}
```

#### Category-Based Rules

```json
{
  "rules": [
    {
      "name": "Authentication Failures",
      "enabled": true,
      "conditions": {
        "categories": ["authentication"],
        "patterns": ["failed.*login", "invalid.*user", "authentication.*failure"],
        "min_severity": 4
      },
      "channels": ["email_security_team"],
      "aggregation": {
        "enabled": true,
        "time_window": 300,
        "max_events": 10,
        "summary_template": "{{count}} authentication failures detected in the last 5 minutes"
      }
    },
    {
      "name": "Database Security Events",
      "enabled": true,
      "conditions": {
        "sources": ["mysql_logs", "postgres_logs"],
        "patterns": ["access.*denied", "unauthorized.*access", "sql.*injection"],
        "min_severity": 6
      },
      "channels": ["email_dba_team", "slack_database"],
      "enrichment": {
        "add_context": true,
        "lookup_user_info": true,
        "geo_location": true
      }
    }
  ]
}
```

## Performance Configuration

### Processing Optimization

```json
{
  "processing": {
    "batch_processing": {
      "enabled": true,
      "batch_size": 200,
      "max_wait_time": 5.0,
      "parallel_batches": 4
    },
    "queue_management": {
      "max_queue_size": 50000,
      "priority_queues": {
        "critical": {
          "max_size": 5000,
          "workers": 2
        },
        "high": {
          "max_size": 15000,
          "workers": 2
        },
        "normal": {
          "max_size": 30000,
          "workers": 1
        }
      },
      "backpressure": {
        "enabled": true,
        "threshold": 0.8,
        "action": "drop_low_priority"
      }
    },
    "worker_configuration": {
      "total_workers": 6,
      "worker_types": {
        "parser": 2,
        "analyzer": 2,
        "notifier": 1,
        "cleanup": 1
      }
    }
  }
}
```

### Memory Management

```json
{
  "memory_management": {
    "limits": {
      "max_memory_mb": 4096,
      "warning_threshold": 0.8,
      "critical_threshold": 0.9
    },
    "garbage_collection": {
      "enabled": true,
      "interval_seconds": 300,
      "aggressive_mode": false
    },
    "caching": {
      "enabled": true,
      "max_cache_size_mb": 512,
      "cache_ttl_seconds": 3600,
      "cache_types": {
        "parsed_logs": true,
        "ai_analysis": true,
        "user_sessions": true
      }
    }
  }
}
```

### Database Optimization

```json
{
  "database": {
    "connection_pool": {
      "min_connections": 5,
      "max_connections": 50,
      "connection_timeout": 30,
      "idle_timeout": 300
    },
    "query_optimization": {
      "enable_query_cache": true,
      "slow_query_threshold": 1.0,
      "explain_slow_queries": true
    },
    "maintenance": {
      "auto_vacuum": true,
      "analyze_frequency": "daily",
      "reindex_frequency": "weekly"
    },
    "partitioning": {
      "enabled": true,
      "partition_by": "timestamp",
      "partition_interval": "monthly",
      "retention_months": 12
    }
  }
}
```

## Security Configuration

### Authentication and Authorization

```json
{
  "security": {
    "authentication": {
      "api_key_required": true,
      "api_key_header": "Authorization",
      "api_key_prefix": "Bearer ",
      "session_timeout": 3600,
      "max_sessions_per_user": 5
    },
    "authorization": {
      "rbac_enabled": true,
      "roles": {
        "admin": {
          "permissions": ["*"]
        },
        "security_analyst": {
          "permissions": [
            "events:read",
            "events:analyze",
            "notifications:read",
            "notifications:create"
          ]
        },
        "viewer": {
          "permissions": [
            "events:read",
            "dashboard:read"
          ]
        }
      }
    },
    "rate_limiting": {
      "enabled": true,
      "global_limit": 1000,
      "per_user_limit": 100,
      "time_window": 3600,
      "whitelist_ips": ["127.0.0.1", "10.0.0.0/8"]
    }
  }
}
```

### Data Protection

```json
{
  "data_protection": {
    "encryption": {
      "at_rest": {
        "enabled": true,
        "algorithm": "AES-256-GCM",
        "key_rotation_days": 90
      },
      "in_transit": {
        "tls_enabled": true,
        "tls_version": "1.2",
        "cipher_suites": [
          "ECDHE-RSA-AES256-GCM-SHA384",
          "ECDHE-RSA-AES128-GCM-SHA256"
        ]
      }
    },
    "data_masking": {
      "enabled": true,
      "patterns": {
        "credit_card": "\\b\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}\\b",
        "ssn": "\\b\\d{3}-\\d{2}-\\d{4}\\b",
        "email": "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b",
        "ip_address": "\\b(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\b"
      },
      "replacement": "***MASKED***"
    },
    "audit_logging": {
      "enabled": true,
      "log_all_access": true,
      "log_configuration_changes": true,
      "retention_days": 365
    }
  }
}
```

### Network Security

```json
{
  "network_security": {
    "cors": {
      "enabled": true,
      "allowed_origins": [
        "https://yourdomain.com",
        "https://app.yourdomain.com"
      ],
      "allowed_methods": ["GET", "POST", "PUT", "DELETE"],
      "allowed_headers": ["Authorization", "Content-Type"],
      "max_age": 3600
    },
    "firewall": {
      "enabled": true,
      "allowed_ips": ["10.0.0.0/8", "192.168.0.0/16"],
      "blocked_ips": [],
      "geo_blocking": {
        "enabled": false,
        "allowed_countries": ["US", "CA", "GB"]
      }
    },
    "ddos_protection": {
      "enabled": true,
      "max_requests_per_second": 100,
      "burst_limit": 200,
      "ban_duration": 3600
    }
  }
}
```

## Monitoring Configuration

### Health Checks

```json
{
  "health_monitoring": {
    "checks": {
      "database": {
        "enabled": true,
        "interval": 30,
        "timeout": 10,
        "critical_threshold": 5000
      },
      "file_monitor": {
        "enabled": true,
        "interval": 60,
        "check_file_access": true,
        "check_disk_space": true
      },
      "processing_queue": {
        "enabled": true,
        "interval": 30,
        "max_queue_depth": 10000,
        "max_processing_time": 30
      },
      "websocket_server": {
        "enabled": true,
        "interval": 60,
        "max_connections": 1000,
        "check_connectivity": true
      }
    },
    "alerting": {
      "enabled": true,
      "alert_channels": ["email_admin", "slack_ops"],
      "escalation_time": 300
    }
  }
}
```

### Metrics Collection

```json
{
  "metrics": {
    "collection": {
      "enabled": true,
      "interval": 60,
      "retention_days": 30
    },
    "exporters": {
      "prometheus": {
        "enabled": true,
        "port": 9090,
        "path": "/metrics"
      },
      "statsd": {
        "enabled": false,
        "host": "localhost",
        "port": 8125
      }
    },
    "custom_metrics": [
      {
        "name": "events_processed_total",
        "type": "counter",
        "description": "Total number of events processed"
      },
      {
        "name": "processing_duration_seconds",
        "type": "histogram",
        "description": "Time spent processing events"
      },
      {
        "name": "queue_depth",
        "type": "gauge",
        "description": "Current queue depth"
      }
    ]
  }
}
```

## Best Practices

### Configuration Management

1. **Version Control**: Store all configuration files in version control
2. **Environment Separation**: Use different configurations for dev/staging/prod
3. **Secret Management**: Use environment variables or secret management systems
4. **Validation**: Validate configurations before deployment
5. **Documentation**: Document all configuration changes

### Security Best Practices

1. **Principle of Least Privilege**: Grant minimum necessary permissions
2. **Regular Key Rotation**: Rotate API keys and certificates regularly
3. **Audit Logging**: Enable comprehensive audit logging
4. **Network Segmentation**: Isolate ThreatLens in appropriate network segments
5. **Regular Updates**: Keep all dependencies updated

### Performance Best Practices

1. **Resource Monitoring**: Monitor CPU, memory, and disk usage
2. **Capacity Planning**: Plan for peak load scenarios
3. **Optimization**: Regularly review and optimize configurations
4. **Load Testing**: Test system under expected load
5. **Scaling Strategy**: Plan for horizontal and vertical scaling

### Operational Best Practices

1. **Backup Strategy**: Regular backups of configuration and data
2. **Disaster Recovery**: Plan for system recovery scenarios
3. **Monitoring**: Comprehensive monitoring and alerting
4. **Documentation**: Maintain up-to-date operational documentation
5. **Change Management**: Controlled change management process

## Configuration Examples

### Small Organization (< 1000 events/day)

```json
{
  "processing": {
    "batch_size": 50,
    "max_queue_size": 5000,
    "workers": 2
  },
  "log_sources": [
    {
      "path": "/var/log/syslog",
      "source_name": "System Logs",
      "polling_interval": 5.0
    }
  ],
  "notifications": {
    "channels": [
      {
        "name": "Admin Email",
        "type": "email",
        "recipients": ["admin@company.com"]
      }
    ],
    "rules": [
      {
        "name": "High Severity",
        "min_severity": 7,
        "channels": ["Admin Email"]
      }
    ]
  }
}
```

### Medium Organization (1000-10000 events/day)

```json
{
  "processing": {
    "batch_size": 100,
    "max_queue_size": 20000,
    "workers": 4
  },
  "log_sources": [
    {
      "path": "/var/log/syslog",
      "source_name": "System Logs",
      "polling_interval": 2.0
    },
    {
      "path": "/var/log/nginx",
      "source_name": "Web Server Logs",
      "polling_interval": 1.0,
      "recursive": true
    },
    {
      "path": "/opt/app/logs",
      "source_name": "Application Logs",
      "polling_interval": 1.0
    }
  ],
  "notifications": {
    "channels": [
      {
        "name": "Security Team Email",
        "type": "email",
        "recipients": ["security@company.com"]
      },
      {
        "name": "Slack Alerts",
        "type": "webhook",
        "webhook_url": "https://hooks.slack.com/..."
      }
    ],
    "rules": [
      {
        "name": "Critical Alerts",
        "min_severity": 8,
        "channels": ["Security Team Email", "Slack Alerts"]
      },
      {
        "name": "High Priority",
        "min_severity": 6,
        "channels": ["Slack Alerts"]
      }
    ]
  }
}
```

### Large Organization (> 10000 events/day)

```json
{
  "processing": {
    "batch_size": 500,
    "max_queue_size": 100000,
    "workers": 8,
    "priority_queues": {
      "critical": {"workers": 3},
      "high": {"workers": 3},
      "normal": {"workers": 2}
    }
  },
  "log_sources": [
    {
      "path": "/var/log/syslog",
      "source_name": "System Logs",
      "polling_interval": 0.5,
      "priority": "high"
    },
    {
      "path": "/var/log/nginx",
      "source_name": "Web Server Logs",
      "polling_interval": 0.5,
      "recursive": true,
      "priority": "normal"
    },
    {
      "path": "/var/log/auth.log",
      "source_name": "Authentication Logs",
      "polling_interval": 0.5,
      "priority": "critical"
    },
    {
      "path": "/opt/apps/*/logs",
      "source_name": "Application Logs",
      "polling_interval": 1.0,
      "recursive": true,
      "priority": "normal"
    }
  ],
  "notifications": {
    "channels": [
      {
        "name": "Executive Alerts",
        "type": "email",
        "recipients": ["ciso@company.com", "cto@company.com"]
      },
      {
        "name": "Security Team",
        "type": "email",
        "recipients": ["security-team@company.com"]
      },
      {
        "name": "Slack Security",
        "type": "webhook",
        "webhook_url": "https://hooks.slack.com/security"
      },
      {
        "name": "Teams Operations",
        "type": "webhook",
        "webhook_url": "https://outlook.office.com/webhook/ops"
      }
    ],
    "rules": [
      {
        "name": "Critical Security Events",
        "min_severity": 9,
        "categories": ["security", "breach"],
        "channels": ["Executive Alerts", "Security Team", "Slack Security"]
      },
      {
        "name": "High Priority Security",
        "min_severity": 7,
        "categories": ["security", "authentication"],
        "channels": ["Security Team", "Slack Security"]
      },
      {
        "name": "Operational Issues",
        "min_severity": 6,
        "categories": ["system", "application"],
        "channels": ["Teams Operations"]
      }
    ]
  },
  "performance": {
    "database": {
      "connection_pool_size": 50,
      "partitioning": true
    },
    "memory_management": {
      "max_memory_mb": 8192,
      "aggressive_gc": true
    }
  }
}
```

## Troubleshooting Configuration

### Common Configuration Issues

1. **Invalid JSON Syntax**: Use JSON validators
2. **Missing Required Fields**: Check schema documentation
3. **Incorrect File Paths**: Verify paths exist and are accessible
4. **Permission Issues**: Ensure proper file permissions
5. **Network Connectivity**: Test webhook URLs and SMTP servers

### Configuration Validation

```bash
# Validate JSON syntax
python -m json.tool config/monitoring_config.json

# Test configuration
python -c "
import json
from app.config_manager import ConfigManager
config = ConfigManager()
config.validate_configuration('config/monitoring_config.json')
print('Configuration is valid')
"

# Test log source accessibility
python -c "
import os
log_path = '/var/log/syslog'
if os.path.exists(log_path) and os.access(log_path, os.R_OK):
    print(f'{log_path} is accessible')
else:
    print(f'{log_path} is not accessible')
"
```

This comprehensive configuration guide should help you set up ThreatLens real-time monitoring for any environment, from small organizations to large enterprises. Remember to regularly review and update your configuration as your needs evolve.