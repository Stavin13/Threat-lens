"""
SQLAlchemy models for ThreatLens database tables.
"""
from sqlalchemy import Column, String, Text, Integer, DateTime, Date, ForeignKey, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional

Base = declarative_base()


class RawLog(Base):
    """Raw logs table for storing ingested log data."""
    __tablename__ = "raw_logs"
    
    id = Column(String, primary_key=True)
    content = Column(Text, nullable=False)
    source = Column(String, nullable=False)
    ingested_at = Column(DateTime, default=func.current_timestamp())
    
    # Relationship to events
    events = relationship("Event", back_populates="raw_log", cascade="all, delete-orphan")


class Event(Base):
    """Parsed events table for structured security events."""
    __tablename__ = "events"
    
    id = Column(String, primary_key=True)
    raw_log_id = Column(String, ForeignKey("raw_logs.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    source = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    category = Column(String, nullable=False)
    parsed_at = Column(DateTime, default=func.current_timestamp())
    
    # Real-time processing fields
    processing_time = Column(String, nullable=True)  # Store as string for flexibility
    realtime_processed = Column(Integer, default=0)  # SQLite boolean as integer
    notification_sent = Column(Integer, default=0)  # SQLite boolean as integer
    
    # Relationships
    raw_log = relationship("RawLog", back_populates="events")
    ai_analysis = relationship("AIAnalysis", back_populates="event", uselist=False, cascade="all, delete-orphan")


class AIAnalysis(Base):
    """AI analysis table for storing Claude-generated insights."""
    __tablename__ = "ai_analysis"
    
    id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=False)
    severity_score = Column(Integer, nullable=False)
    explanation = Column(Text, nullable=False)
    recommendations = Column(Text, nullable=False)  # JSON array stored as text
    analyzed_at = Column(DateTime, default=func.current_timestamp())
    
    # Add check constraint for severity score range
    __table_args__ = (
        CheckConstraint('severity_score >= 1 AND severity_score <= 10', name='severity_score_range'),
    )
    
    # Relationship
    event = relationship("Event", back_populates="ai_analysis")


class Report(Base):
    """Reports table for tracking generated PDF reports."""
    __tablename__ = "reports"
    
    id = Column(String, primary_key=True)
    report_date = Column(Date, nullable=False)
    file_path = Column(String, nullable=False)
    generated_at = Column(DateTime, default=func.current_timestamp())


class MonitoringConfigDB(Base):
    """Real-time monitoring configuration storage."""
    __tablename__ = "monitoring_config"
    
    id = Column(Integer, primary_key=True)
    config_data = Column(Text, nullable=False)  # JSON configuration
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())


class LogSource(Base):
    """Log source tracking for real-time monitoring."""
    __tablename__ = "log_sources"
    
    id = Column(Integer, primary_key=True)
    source_name = Column(String(255), unique=True, nullable=False)
    path = Column(String(1000), unique=True, nullable=False)
    enabled = Column(Integer, default=1)  # SQLite doesn't have native boolean
    last_monitored = Column(DateTime, nullable=True)
    file_size = Column(Integer, default=0)
    last_offset = Column(Integer, default=0)
    status = Column(String(50), default="inactive")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())


class ProcessingMetricsDB(Base):
    """Real-time processing metrics storage."""
    __tablename__ = "processing_metrics"
    
    id = Column(Integer, primary_key=True)
    source_name = Column(String(255), nullable=False)
    metric_type = Column(String(100), nullable=False)
    metric_value = Column(String, nullable=False)  # JSON value
    timestamp = Column(DateTime, default=func.current_timestamp())
    metric_metadata = Column(Text, nullable=True)  # JSON metadata


class NotificationHistory(Base):
    """Notification history tracking."""
    __tablename__ = "notification_history"
    
    id = Column(Integer, primary_key=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=False)
    notification_type = Column(String(100), nullable=False)
    channel = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)  # 'sent', 'failed', 'pending'
    sent_at = Column(DateTime, default=func.current_timestamp())
    error_message = Column(Text, nullable=True)
    
    # Relationship
    event = relationship("Event")


class AuditLog(Base):
    """Audit log for tracking all configuration changes and security events."""
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True)
    event_type = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)
    timestamp = Column(DateTime, default=func.current_timestamp())
    
    # User information
    user_id = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    user_role = Column(String(50), nullable=True)
    session_id = Column(String(255), nullable=True)
    
    # Request information
    client_ip = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    correlation_id = Column(String(255), nullable=True)
    
    # Event details
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(255), nullable=True)
    action = Column(String(100), nullable=True)
    description = Column(Text, nullable=False)
    
    # Change tracking (JSON stored as text)
    old_values = Column(Text, nullable=True)
    new_values = Column(Text, nullable=True)
    changes = Column(Text, nullable=True)  # JSON array of changed fields
    
    # Additional metadata
    event_metadata = Column(Text, nullable=True)  # JSON metadata
    tags = Column(Text, nullable=True)  # JSON array of tags
    
    # Status and outcome
    success = Column(Integer, default=1)  # SQLite boolean as integer
    error_message = Column(Text, nullable=True)


class User(Base):
    """User accounts for authentication."""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="viewer")
    enabled = Column(Integer, default=1)  # SQLite boolean as integer
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)


class UserSession(Base):
    """User sessions for authentication tracking."""
    __tablename__ = "user_sessions"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=func.current_timestamp())
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime, default=func.current_timestamp())
    client_ip = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    is_active = Column(Integer, default=1)  # SQLite boolean as integer
    
    # Relationship
    user = relationship("User")