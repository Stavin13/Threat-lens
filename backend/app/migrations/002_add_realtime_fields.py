"""
Migration 002: Add real-time processing fields to existing tables
Extends Event model with real-time processing metadata and adds performance indexes.
"""

VERSION = "002_add_realtime_fields"
DESCRIPTION = "Add real-time processing fields to events table and create performance indexes"

FORWARD_SQL = """
-- Add real-time processing fields to events table
-- Note: SQLite doesn't support ADD COLUMN IF NOT EXISTS, so we need to check first
-- These will be handled by the migration manager's column_exists check

-- Add processing_time field (stored as string for flexibility)
ALTER TABLE events ADD COLUMN processing_time VARCHAR(50) NULL;

-- Add realtime_processed field (SQLite boolean as integer)
ALTER TABLE events ADD COLUMN realtime_processed INTEGER DEFAULT 0;

-- Add notification_sent field (SQLite boolean as integer)  
ALTER TABLE events ADD COLUMN notification_sent INTEGER DEFAULT 0;

-- Create indexes for efficient real-time queries
CREATE INDEX IF NOT EXISTS idx_events_realtime_processed ON events(realtime_processed);
CREATE INDEX IF NOT EXISTS idx_events_notification_sent ON events(notification_sent);
CREATE INDEX IF NOT EXISTS idx_events_processing_time ON events(processing_time);

-- Composite indexes for common real-time query patterns
CREATE INDEX IF NOT EXISTS idx_events_timestamp_realtime ON events(timestamp, realtime_processed);
CREATE INDEX IF NOT EXISTS idx_events_category_realtime ON events(category, realtime_processed);
CREATE INDEX IF NOT EXISTS idx_events_severity_realtime ON events(id) WHERE realtime_processed = 1;

-- Index for notification queries
CREATE INDEX IF NOT EXISTS idx_events_notification_pending ON events(id) 
WHERE realtime_processed = 1 AND notification_sent = 0;
"""

ROLLBACK_SQL = """
-- Drop indexes first
DROP INDEX IF EXISTS idx_events_notification_pending;
DROP INDEX IF EXISTS idx_events_severity_realtime;
DROP INDEX IF EXISTS idx_events_category_realtime;
DROP INDEX IF EXISTS idx_events_timestamp_realtime;
DROP INDEX IF EXISTS idx_events_processing_time;
DROP INDEX IF EXISTS idx_events_notification_sent;
DROP INDEX IF EXISTS idx_events_realtime_processed;

-- Note: SQLite doesn't support DROP COLUMN, so we would need to recreate the table
-- For now, we'll leave the columns but mark them as deprecated in rollback
-- In a production system, you might want to recreate the table without these columns
"""