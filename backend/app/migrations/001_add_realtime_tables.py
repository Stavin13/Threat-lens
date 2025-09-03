"""
Migration 001: Add real-time monitoring tables
Creates monitoring_config, log_sources, processing_metrics, and notification_history tables.
"""

VERSION = "001_add_realtime_tables"
DESCRIPTION = "Add real-time monitoring tables for log sources, metrics, and notifications"

FORWARD_SQL = """
-- Create monitoring_config table for storing real-time monitoring configuration
CREATE TABLE IF NOT EXISTS monitoring_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create log_sources table for tracking monitored log sources
CREATE TABLE IF NOT EXISTS log_sources (
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

-- Create processing_metrics table for storing real-time processing metrics
CREATE TABLE IF NOT EXISTS processing_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name VARCHAR(255) NOT NULL,
    metric_type VARCHAR(100) NOT NULL,
    metric_value TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metric_metadata TEXT NULL
);

-- Create notification_history table for tracking sent notifications
CREATE TABLE IF NOT EXISTS notification_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id VARCHAR(255) NOT NULL,
    notification_type VARCHAR(100) NOT NULL,
    channel VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT NULL,
    FOREIGN KEY (event_id) REFERENCES events (id)
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_log_sources_name ON log_sources(source_name);
CREATE INDEX IF NOT EXISTS idx_log_sources_path ON log_sources(path);
CREATE INDEX IF NOT EXISTS idx_log_sources_enabled ON log_sources(enabled);
CREATE INDEX IF NOT EXISTS idx_log_sources_status ON log_sources(status);

CREATE INDEX IF NOT EXISTS idx_processing_metrics_timestamp ON processing_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_processing_metrics_source ON processing_metrics(source_name);
CREATE INDEX IF NOT EXISTS idx_processing_metrics_type ON processing_metrics(metric_type);

CREATE INDEX IF NOT EXISTS idx_notification_history_event ON notification_history(event_id);
CREATE INDEX IF NOT EXISTS idx_notification_history_status ON notification_history(status);
CREATE INDEX IF NOT EXISTS idx_notification_history_sent_at ON notification_history(sent_at);
"""

ROLLBACK_SQL = """
-- Drop indexes first
DROP INDEX IF EXISTS idx_notification_history_sent_at;
DROP INDEX IF EXISTS idx_notification_history_status;
DROP INDEX IF EXISTS idx_notification_history_event;

DROP INDEX IF EXISTS idx_processing_metrics_type;
DROP INDEX IF EXISTS idx_processing_metrics_source;
DROP INDEX IF EXISTS idx_processing_metrics_timestamp;

DROP INDEX IF EXISTS idx_log_sources_status;
DROP INDEX IF EXISTS idx_log_sources_enabled;
DROP INDEX IF EXISTS idx_log_sources_path;
DROP INDEX IF EXISTS idx_log_sources_name;

-- Drop tables
DROP TABLE IF EXISTS notification_history;
DROP TABLE IF EXISTS processing_metrics;
DROP TABLE IF EXISTS log_sources;
DROP TABLE IF EXISTS monitoring_config;
"""