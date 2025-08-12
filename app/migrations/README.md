# ThreatLens Database Migration System

This directory contains the database migration system for ThreatLens, providing structured schema updates and maintenance utilities for the real-time log detection feature.

## Overview

The migration system provides:
- Version-controlled database schema changes
- Rollback capabilities for migrations
- Database cleanup and maintenance utilities
- Performance optimization tools
- Health monitoring and reporting

## Components

### Migration Manager (`migration_manager.py`)
Core migration functionality with version tracking and rollback support.

**Key Features:**
- Migration tracking table for applied versions
- Forward and rollback SQL execution
- Transaction safety with automatic rollback on errors
- Column and table existence checking

### Migration Runner (`runner.py`)
Command-line interface for running migrations and validation.

**Usage:**
```bash
# Run all pending migrations
python -m app.migrations.runner

# Show migration status
python -m app.migrations.runner --status

# Validate database schema
python -m app.migrations.runner --validate

# Rollback a specific migration
python -m app.migrations.runner --rollback 001_add_realtime_tables
```

### Database Cleanup (`cleanup.py`)
Automated cleanup utilities for maintaining database performance.

**Features:**
- Old processing metrics cleanup
- Notification history cleanup
- Orphaned record removal
- Database VACUUM and ANALYZE operations
- Size reporting and statistics

**Usage:**
```bash
# Run full cleanup with default settings
python -m app.migrations.cleanup

# Cleanup with custom retention periods
python -m app.migrations.cleanup --metrics-days 15 --notification-days 60

# Show database size information
python -m app.migrations.cleanup --size-info
```

### Database Utilities (`../database_utils.py`)
Comprehensive database monitoring and maintenance utilities.

**Features:**
- Real-time processing statistics
- Log source status monitoring
- Notification delivery metrics
- Health report generation
- Performance optimization

**Usage:**
```bash
# Generate health report
python -m app.database_utils --health-report

# Show real-time processing stats
python -m app.database_utils --realtime-stats

# Show log source status
python -m app.database_utils --log-sources

# Run database optimization
python -m app.database_utils --optimize
```

## Migration Files

### 001_add_realtime_tables.py
Creates the core real-time monitoring tables:
- `monitoring_config`: Configuration storage
- `log_sources`: Log source tracking
- `processing_metrics`: Performance metrics
- `notification_history`: Notification tracking

### 002_add_realtime_fields.py
Extends the existing `events` table with real-time processing fields:
- `processing_time`: Processing duration tracking
- `realtime_processed`: Real-time processing flag
- `notification_sent`: Notification status flag

### 003_optimize_realtime_indexes.py
Adds performance indexes for real-time queries:
- Composite indexes for common query patterns
- Partial indexes for filtered queries
- Time-series indexes for metrics

## Database Schema

### New Tables

**monitoring_config**
```sql
CREATE TABLE monitoring_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**log_sources**
```sql
CREATE TABLE log_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name VARCHAR(255) UNIQUE NOT NULL,
    path VARCHAR(1000) UNIQUE NOT NULL,
    enabled INTEGER DEFAULT 1,
    last_monitored TIMESTAMP NULL,
    file_size INTEGER DEFAULT 0,
    last_offset INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'inactive',
    error_message TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**processing_metrics**
```sql
CREATE TABLE processing_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name VARCHAR(255) NOT NULL,
    metric_type VARCHAR(100) NOT NULL,
    metric_value TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metric_metadata TEXT NULL
);
```

**notification_history**
```sql
CREATE TABLE notification_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id VARCHAR(255) NOT NULL,
    notification_type VARCHAR(100) NOT NULL,
    channel VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT NULL,
    FOREIGN KEY (event_id) REFERENCES events (id)
);
```

### Extended Tables

**events** (added fields)
- `processing_time VARCHAR(50)`: Processing duration
- `realtime_processed INTEGER`: Real-time processing flag
- `notification_sent INTEGER`: Notification status

## Performance Indexes

The migration system creates optimized indexes for:
- Real-time event queries
- Log source monitoring
- Processing metrics time-series
- Notification history analysis
- Cross-table joins and filtering

## Maintenance Operations

### Automated Cleanup
- Processing metrics older than 30 days (configurable)
- Notification history older than 90 days (configurable)
- Old events older than 365 days (configurable)
- Orphaned records cleanup

### Performance Optimization
- Database VACUUM for space reclamation
- ANALYZE for query planner statistics
- Index optimization recommendations

### Health Monitoring
- Real-time processing statistics
- Database size and growth tracking
- Error rate monitoring
- Performance metrics analysis

## Integration

The migration system is integrated with the main application:

1. **Automatic Migration**: Migrations run automatically during `init_database()`
2. **Health Checks**: Database health endpoints use migration utilities
3. **Background Tasks**: Cleanup operations can be scheduled
4. **Monitoring**: Real-time metrics feed into the migration system

## Best Practices

1. **Version Control**: All schema changes go through migrations
2. **Rollback Safety**: Always provide rollback SQL for migrations
3. **Testing**: Test migrations in development before production
4. **Monitoring**: Use health reports to track database performance
5. **Cleanup**: Schedule regular cleanup operations
6. **Backup**: Always backup before running migrations in production

## Troubleshooting

### Common Issues

1. **Migration Failures**: Check logs for SQL errors, verify table dependencies
2. **Performance Issues**: Run ANALYZE, check index usage
3. **Space Issues**: Run cleanup operations, check retention policies
4. **Lock Issues**: Ensure no long-running transactions during migrations

### Recovery Procedures

1. **Failed Migration**: Use rollback functionality
2. **Corrupted Data**: Restore from backup, replay migrations
3. **Performance Degradation**: Run optimization operations
4. **Space Exhaustion**: Emergency cleanup, increase storage

## Requirements Satisfied

This migration system satisfies the following requirements from the specification:

- **3.1, 5.4, 6.1**: Database schema for monitoring configuration, notifications, and health tracking
- **2.1, 2.2, 6.3**: Real-time processing fields and performance indexes
- **Backward Compatibility**: Safe migration with rollback procedures
- **Performance**: Optimized indexes for real-time queries
- **Maintenance**: Automated cleanup and optimization utilities