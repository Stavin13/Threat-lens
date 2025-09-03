"""
ThreatLens application package.
"""
from .models import Base, RawLog, Event, AIAnalysis, Report, MonitoringConfigDB, LogSource, ProcessingMetricsDB, NotificationHistory
from .database import (
    get_database_session,
    get_db_session,
    init_database,
    check_database_health,
    get_database_stats,
    close_database_connections
)
from .schemas import (
    IngestionRequest, ParsedEvent, AIAnalysis as AIAnalysisSchema,
    EventResponse, EventListResponse, EventFilters, EventCategory,
    SeverityLevel, ReportRequest, ReportResponse, HealthCheckResponse,
    ErrorResponse
)
from .validation import (
    validate_log_content, validate_event_timestamp, validate_event_category,
    validate_severity_score, validate_recommendations_list, validate_source_identifier,
    validate_parsed_event, validate_ai_analysis_data, sanitize_log_content,
    validate_file_upload
)

__all__ = [
    # Database models
    "Base",
    "RawLog", 
    "Event",
    "AIAnalysis",
    "Report",
    "MonitoringConfigDB",
    "LogSource",
    "ProcessingMetricsDB",
    "NotificationHistory",
    # Database functions
    "get_database_session",
    "get_db_session", 
    "init_database",
    "check_database_health",
    "get_database_stats",
    "close_database_connections",
    # Pydantic schemas
    "IngestionRequest",
    "ParsedEvent",
    "AIAnalysisSchema",
    "EventResponse",
    "EventListResponse", 
    "EventFilters",
    "EventCategory",
    "SeverityLevel",
    "ReportRequest",
    "ReportResponse",
    "HealthCheckResponse",
    "ErrorResponse",
    # Validation functions
    "validate_log_content",
    "validate_event_timestamp",
    "validate_event_category",
    "validate_severity_score",
    "validate_recommendations_list",
    "validate_source_identifier",
    "validate_parsed_event",
    "validate_ai_analysis_data",
    "sanitize_log_content",
    "validate_file_upload"
]