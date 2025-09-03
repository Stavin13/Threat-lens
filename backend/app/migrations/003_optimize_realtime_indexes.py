"""
Migration 003: Optimize indexes for real-time queries
Adds additional indexes for better performance of real-time monitoring queries.
"""

VERSION = "003_optimize_realtime_indexes"
DESCRIPTION = "Add optimized indexes for real-time monitoring performance"

FORWARD_SQL = """
-- Additional composite indexes for common real-time query patterns
CREATE INDEX IF NOT EXISTS idx_events_timestamp_severity ON events(timestamp) 
WHERE realtime_processed = 1;

CREATE INDEX IF NOT EXISTS idx_events_category_timestamp_realtime ON events(category, timestamp) 
WHERE realtime_processed = 1;

-- Index for finding events that need notifications
CREATE INDEX IF NOT EXISTS idx_events_notification_queue ON events(realtime_processed, notification_sent, timestamp)
WHERE realtime_processed = 1 AND notification_sent = 0;

-- Index for log source monitoring queries
CREATE INDEX IF NOT EXISTS idx_log_sources_enabled_status ON log_sources(enabled, status);

CREATE INDEX IF NOT EXISTS idx_log_sources_last_monitored ON log_sources(last_monitored) 
WHERE enabled = 1;

-- Index for processing metrics time-series queries
CREATE INDEX IF NOT EXISTS idx_processing_metrics_source_type_time ON processing_metrics(source_name, metric_type, timestamp);

-- Index for notification history analysis
CREATE INDEX IF NOT EXISTS idx_notification_history_type_status ON notification_history(notification_type, status);

CREATE INDEX IF NOT EXISTS idx_notification_history_channel_sent_at ON notification_history(channel, sent_at);

-- Partial index for failed notifications
CREATE INDEX IF NOT EXISTS idx_notification_history_failed ON notification_history(event_id, sent_at) 
WHERE status = 'failed';

-- Index for AI analysis severity queries
CREATE INDEX IF NOT EXISTS idx_ai_analysis_severity_analyzed ON ai_analysis(severity_score, analyzed_at);
"""

ROLLBACK_SQL = """
-- Drop the additional indexes
DROP INDEX IF EXISTS idx_ai_analysis_severity_analyzed;
DROP INDEX IF EXISTS idx_notification_history_failed;
DROP INDEX IF EXISTS idx_notification_history_channel_sent_at;
DROP INDEX IF EXISTS idx_notification_history_type_status;
DROP INDEX IF EXISTS idx_processing_metrics_source_type_time;
DROP INDEX IF EXISTS idx_log_sources_last_monitored;
DROP INDEX IF EXISTS idx_log_sources_enabled_status;
DROP INDEX IF EXISTS idx_events_notification_queue;
DROP INDEX IF EXISTS idx_events_category_timestamp_realtime;
DROP INDEX IF EXISTS idx_events_timestamp_severity;
"""