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