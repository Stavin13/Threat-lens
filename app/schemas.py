"""
Pydantic models for API requests and responses.
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timezone
from enum import Enum
import re
import json


class EventCategory(str, Enum):
    """Enumeration of event categories for log classification."""
    AUTH = "auth"
    SYSTEM = "system"
    NETWORK = "network"
    SECURITY = "security"
    APPLICATION = "application"
    KERNEL = "kernel"
    UNKNOWN = "unknown"


class SeverityLevel(int, Enum):
    """Severity levels for AI analysis scoring."""
    VERY_LOW = 1
    LOW = 2
    LOW_MEDIUM = 3
    MEDIUM = 4
    MEDIUM_HIGH = 5
    HIGH = 6
    HIGH_CRITICAL = 7
    CRITICAL = 8
    VERY_CRITICAL = 9
    MAXIMUM = 10


class IngestionRequest(BaseModel):
    """Request model for log ingestion endpoint."""
    content: str = Field(..., min_length=1, max_length=1000000, description="Raw log content to ingest")
    source: str = Field(..., min_length=1, max_length=255, description="Source identifier for the logs")
    
    @validator('content')
    def validate_content(cls, v):
        """Validate log content format and sanitize input."""
        if not v or not v.strip():
            raise ValueError("Log content cannot be empty")
        
        # Basic sanitization - remove null bytes and control characters except newlines/tabs
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', v)
        
        # Check for minimum meaningful content
        if len(sanitized.strip()) < 10:
            raise ValueError("Log content too short to be meaningful")
        
        return sanitized
    
    @validator('source')
    def validate_source(cls, v):
        """Validate source identifier format."""
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', v):
            raise ValueError("Source must contain only alphanumeric characters, underscores, hyphens, and dots")
        return v.lower()


class ParsedEvent(BaseModel):
    """Model for parsed security events."""
    id: str = Field(..., description="Unique event identifier")
    raw_log_id: str = Field(..., description="Reference to the raw log entry")
    timestamp: datetime = Field(..., description="Event timestamp")
    source: str = Field(..., min_length=1, max_length=255, description="Event source")
    message: str = Field(..., min_length=1, description="Parsed event message")
    category: EventCategory = Field(..., description="Event category classification")
    parsed_at: Optional[datetime] = Field(default=None, description="When the event was parsed")
    
    @validator('timestamp')
    def validate_timestamp(cls, v):
        """Validate timestamp is not in the future."""
        # Make comparison timezone-aware
        now = datetime.now(timezone.utc) if v.tzinfo else datetime.now()
        if v > now:
            raise ValueError("Event timestamp cannot be in the future")
        return v
    
    @validator('message')
    def validate_message(cls, v):
        """Validate and sanitize event message."""
        if not v or not v.strip():
            raise ValueError("Event message cannot be empty")
        
        # Sanitize message content
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', v)
        return sanitized.strip()


class AIAnalysisRequest(BaseModel):
    """Request model for AI analysis."""
    event_id: str = Field(..., description="Event ID to analyze")
    event_data: ParsedEvent = Field(..., description="Event data for analysis")


class AIAnalysis(BaseModel):
    """Model for AI-generated threat analysis."""
    id: str = Field(..., description="Unique analysis identifier")
    event_id: str = Field(..., description="Reference to the analyzed event")
    severity_score: int = Field(..., ge=1, le=10, description="Severity score from 1-10")
    explanation: str = Field(..., min_length=10, description="AI-generated explanation")
    recommendations: List[str] = Field(..., min_items=1, description="List of recommendations")
    analyzed_at: Optional[datetime] = Field(default=None, description="When the analysis was performed")
    
    @validator('severity_score')
    def validate_severity_score(cls, v):
        """Validate severity score is within valid range."""
        if not isinstance(v, int) or v < 1 or v > 10:
            raise ValueError("Severity score must be an integer between 1 and 10")
        return v
    
    @validator('explanation')
    def validate_explanation(cls, v):
        """Validate explanation content."""
        if not v or not v.strip():
            raise ValueError("Explanation cannot be empty")
        
        if len(v.strip()) < 10:
            raise ValueError("Explanation must be at least 10 characters long")
        
        return v.strip()
    
    @validator('recommendations')
    def validate_recommendations(cls, v):
        """Validate recommendations list."""
        if not v or len(v) == 0:
            raise ValueError("At least one recommendation is required")
        
        # Validate each recommendation
        validated_recommendations = []
        for rec in v:
            if not isinstance(rec, str) or not rec.strip():
                raise ValueError("Each recommendation must be a non-empty string")
            validated_recommendations.append(rec.strip())
        
        return validated_recommendations


class EventResponse(BaseModel):
    """Response model for event data with optional AI analysis."""
    id: str = Field(..., description="Event identifier")
    raw_log_id: str = Field(..., description="Reference to raw log")
    timestamp: datetime = Field(..., description="Event timestamp")
    source: str = Field(..., description="Event source")
    message: str = Field(..., description="Event message")
    category: EventCategory = Field(..., description="Event category")
    parsed_at: datetime = Field(..., description="Parse timestamp")
    ai_analysis: Optional[AIAnalysis] = Field(default=None, description="AI analysis if available")


class EventListResponse(BaseModel):
    """Response model for paginated event lists."""
    events: List[EventResponse] = Field(..., description="List of events")
    total: int = Field(..., ge=0, description="Total number of events")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, le=100, description="Events per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class EventFilters(BaseModel):
    """Model for event filtering parameters."""
    category: Optional[EventCategory] = Field(default=None, description="Filter by event category")
    min_severity: Optional[int] = Field(default=None, ge=1, le=10, description="Minimum severity score")
    max_severity: Optional[int] = Field(default=None, ge=1, le=10, description="Maximum severity score")
    start_date: Optional[datetime] = Field(default=None, description="Start date for filtering")
    end_date: Optional[datetime] = Field(default=None, description="End date for filtering")
    source: Optional[str] = Field(default=None, max_length=255, description="Filter by source")
    
    @validator('max_severity')
    def validate_severity_range(cls, v, values):
        """Validate that max_severity is greater than min_severity."""
        if v is not None and 'min_severity' in values and values['min_severity'] is not None:
            if v < values['min_severity']:
                raise ValueError("max_severity must be greater than or equal to min_severity")
        return v
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        """Validate that end_date is after start_date."""
        if v is not None and 'start_date' in values and values['start_date'] is not None:
            if v < values['start_date']:
                raise ValueError("end_date must be after start_date")
        return v


class IngestionResponse(BaseModel):
    """Response model for log ingestion."""
    raw_log_id: str = Field(..., description="ID of the ingested raw log")
    message: str = Field(..., description="Success message")
    events_parsed: int = Field(..., ge=0, description="Number of events parsed from the log")
    ingested_at: datetime = Field(..., description="Ingestion timestamp")


class ReportRequest(BaseModel):
    """Request model for report generation."""
    report_date: date = Field(..., description="Date for the report")
    include_details: bool = Field(default=True, description="Include detailed event information")
    min_severity: Optional[int] = Field(default=None, ge=1, le=10, description="Minimum severity for inclusion")
    
    @validator('report_date')
    def validate_report_date(cls, v):
        """Validate report date is not in the future."""
        if v > date.today():
            raise ValueError("Report date cannot be in the future")
        return v


class ReportResponse(BaseModel):
    """Response model for generated reports."""
    report_id: str = Field(..., description="Unique report identifier")
    report_date: date = Field(..., description="Report date")
    file_path: str = Field(..., description="Path to the generated PDF file")
    generated_at: datetime = Field(..., description="Report generation timestamp")
    events_included: int = Field(..., ge=0, description="Number of events included in the report")


class LogSourceConfigRequest(BaseModel):
    """Request model for log source configuration."""
    source_name: str = Field(..., min_length=1, max_length=255)
    path: str = Field(..., min_length=1, max_length=1000)
    source_type: str = Field(default="file", pattern="^(file|directory)$")
    enabled: bool = Field(default=True)
    recursive: bool = Field(default=False)
    file_pattern: Optional[str] = Field(default=None, max_length=255)
    polling_interval: float = Field(default=1.0, ge=0.1, le=3600.0)
    batch_size: int = Field(default=100, ge=1, le=10000)
    priority: int = Field(default=5, ge=1, le=10)
    description: Optional[str] = Field(default=None, max_length=1000)
    tags: List[str] = Field(default_factory=list)


class LogSourceConfigResponse(BaseModel):
    """Response model for log source configuration."""
    source_name: str
    path: str
    source_type: str
    enabled: bool
    recursive: bool
    file_pattern: Optional[str]
    polling_interval: float
    batch_size: int
    priority: int
    description: Optional[str]
    tags: List[str]
    status: str
    last_monitored: Optional[datetime]
    file_size: Optional[int]
    last_offset: Optional[int]
    error_message: Optional[str]


class NotificationRuleRequest(BaseModel):
    """Request model for notification rule configuration."""
    rule_name: str = Field(..., min_length=1, max_length=255)
    enabled: bool = Field(default=True)
    min_severity: int = Field(default=1, ge=1, le=10)
    max_severity: int = Field(default=10, ge=1, le=10)
    categories: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    channels: List[str] = Field(default_factory=list)
    throttle_minutes: int = Field(default=0, ge=0, le=1440)
    email_recipients: List[str] = Field(default_factory=list)
    webhook_url: Optional[str] = Field(default=None)
    slack_channel: Optional[str] = Field(default=None)


class NotificationRuleResponse(BaseModel):
    """Response model for notification rule configuration."""
    rule_name: str
    enabled: bool
    min_severity: int
    max_severity: int
    categories: List[str]
    sources: List[str]
    channels: List[str]
    throttle_minutes: int
    email_recipients: List[str]
    webhook_url: Optional[str]
    slack_channel: Optional[str]


class MonitoringConfigResponse(BaseModel):
    """Response model for monitoring configuration."""
    enabled: bool
    max_concurrent_sources: int
    processing_batch_size: int
    max_queue_size: int
    health_check_interval: int
    max_error_count: int
    retry_interval: int
    file_read_chunk_size: int
    websocket_max_connections: int
    log_sources: List[LogSourceConfigResponse]
    notification_rules: List[NotificationRuleResponse]
    config_version: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class ProcessingMetricsResponse(BaseModel):
    """Response model for processing metrics."""
    source_name: str
    timestamp: datetime
    entries_processed: int
    processing_time_ms: float
    queue_size: int
    error_count: int
    file_size_bytes: Optional[int]
    bytes_processed: int
    last_offset: int
    is_healthy: bool
    last_error: Optional[str]


class HealthCheckResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str = Field(..., description="Overall system status")
    database: Dict[str, Any] = Field(..., description="Database health information")
    realtime: Optional[Dict[str, Any]] = Field(default=None, description="Real-time components health information")
    timestamp: datetime = Field(..., description="Health check timestamp")


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    correlation_id: Optional[str] = Field(default=None, description="Request correlation ID")