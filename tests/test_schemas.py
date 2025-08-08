"""
Unit tests for Pydantic schemas and data models.
"""
import pytest
from datetime import datetime, date, timedelta
from pydantic import ValidationError
from app.schemas import (
    IngestionRequest, ParsedEvent, AIAnalysis, EventResponse,
    EventFilters, EventCategory, SeverityLevel, ReportRequest
)


class TestIngestionRequest:
    """Test cases for IngestionRequest model."""
    
    def test_valid_ingestion_request(self):
        """Test valid ingestion request creation."""
        request = IngestionRequest(
            content="Jan 15 10:30:45 MacBook-Pro kernel[0]: Test log entry",
            source="test-system"
        )
        assert request.content == "Jan 15 10:30:45 MacBook-Pro kernel[0]: Test log entry"
        assert request.source == "test-system"
    
    def test_empty_content_validation(self):
        """Test validation fails for empty content."""
        with pytest.raises(ValidationError) as exc_info:
            IngestionRequest(content="", source="test")
        assert "String should have at least 1 character" in str(exc_info.value)
    
    def test_short_content_validation(self):
        """Test validation fails for too short content."""
        with pytest.raises(ValidationError) as exc_info:
            IngestionRequest(content="short", source="test")
        assert "Log content too short" in str(exc_info.value)
    
    def test_invalid_source_characters(self):
        """Test validation fails for invalid source characters."""
        with pytest.raises(ValidationError) as exc_info:
            IngestionRequest(
                content="Valid log content here for testing purposes",
                source="invalid source!"
            )
        assert "Source must contain only alphanumeric" in str(exc_info.value)
    
    def test_source_normalization(self):
        """Test source is normalized to lowercase."""
        request = IngestionRequest(
            content="Valid log content here for testing purposes",
            source="TEST-System"
        )
        assert request.source == "test-system"


class TestParsedEvent:
    """Test cases for ParsedEvent model."""
    
    def test_valid_parsed_event(self):
        """Test valid parsed event creation."""
        event = ParsedEvent(
            id="event-123",
            raw_log_id="log-456",
            timestamp=datetime(2024, 1, 15, 10, 30, 45),
            source="kernel",
            message="Test log entry",
            category=EventCategory.SYSTEM
        )
        assert event.id == "event-123"
        assert event.category == EventCategory.SYSTEM
    
    def test_future_timestamp_validation(self):
        """Test validation fails for future timestamps."""
        future_time = datetime.now() + timedelta(days=1)
        with pytest.raises(ValidationError) as exc_info:
            ParsedEvent(
                id="event-123",
                raw_log_id="log-456",
                timestamp=future_time,
                source="kernel",
                message="Test message",
                category=EventCategory.SYSTEM
            )
        assert "timestamp cannot be in the future" in str(exc_info.value)
    
    def test_empty_message_validation(self):
        """Test validation fails for empty message."""
        with pytest.raises(ValidationError) as exc_info:
            ParsedEvent(
                id="event-123",
                raw_log_id="log-456",
                timestamp=datetime.now(),
                source="kernel",
                message="",
                category=EventCategory.SYSTEM
            )
        assert "String should have at least 1 character" in str(exc_info.value)


class TestAIAnalysis:
    """Test cases for AIAnalysis model."""
    
    def test_valid_ai_analysis(self):
        """Test valid AI analysis creation."""
        analysis = AIAnalysis(
            id="analysis-123",
            event_id="event-456",
            severity_score=7,
            explanation="This event indicates a potential security issue",
            recommendations=["Monitor system logs", "Check for patterns"]
        )
        assert analysis.severity_score == 7
        assert len(analysis.recommendations) == 2
    
    def test_invalid_severity_score_low(self):
        """Test validation fails for severity score below 1."""
        with pytest.raises(ValidationError) as exc_info:
            AIAnalysis(
                id="analysis-123",
                event_id="event-456",
                severity_score=0,
                explanation="Valid explanation",
                recommendations=["Valid recommendation"]
            )
        assert "Input should be greater than or equal to 1" in str(exc_info.value)
    
    def test_invalid_severity_score_high(self):
        """Test validation fails for severity score above 10."""
        with pytest.raises(ValidationError) as exc_info:
            AIAnalysis(
                id="analysis-123",
                event_id="event-456",
                severity_score=11,
                explanation="Valid explanation",
                recommendations=["Valid recommendation"]
            )
        assert "Input should be less than or equal to 10" in str(exc_info.value)
    
    def test_short_explanation_validation(self):
        """Test validation fails for too short explanation."""
        with pytest.raises(ValidationError) as exc_info:
            AIAnalysis(
                id="analysis-123",
                event_id="event-456",
                severity_score=5,
                explanation="Short",
                recommendations=["Valid recommendation"]
            )
        assert "String should have at least 10 characters" in str(exc_info.value)
    
    def test_empty_recommendations_validation(self):
        """Test validation fails for empty recommendations."""
        with pytest.raises(ValidationError) as exc_info:
            AIAnalysis(
                id="analysis-123",
                event_id="event-456",
                severity_score=5,
                explanation="Valid explanation here",
                recommendations=[]
            )
        assert "List should have at least 1 item" in str(exc_info.value)
    
    def test_invalid_recommendation_type(self):
        """Test validation fails for non-string recommendations."""
        with pytest.raises(ValidationError) as exc_info:
            AIAnalysis(
                id="analysis-123",
                event_id="event-456",
                severity_score=5,
                explanation="Valid explanation here",
                recommendations=["Valid recommendation", 123]
            )
        assert "Input should be a valid string" in str(exc_info.value)


class TestEventFilters:
    """Test cases for EventFilters model."""
    
    def test_valid_event_filters(self):
        """Test valid event filters creation."""
        filters = EventFilters(
            category=EventCategory.AUTH,
            min_severity=3,
            max_severity=8,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31)
        )
        assert filters.category == EventCategory.AUTH
        assert filters.min_severity == 3
        assert filters.max_severity == 8
    
    def test_invalid_severity_range(self):
        """Test validation fails when max_severity < min_severity."""
        with pytest.raises(ValidationError) as exc_info:
            EventFilters(
                min_severity=8,
                max_severity=3
            )
        assert "max_severity must be greater than or equal to min_severity" in str(exc_info.value)
    
    def test_invalid_date_range(self):
        """Test validation fails when end_date < start_date."""
        with pytest.raises(ValidationError) as exc_info:
            EventFilters(
                start_date=datetime(2024, 1, 31),
                end_date=datetime(2024, 1, 1)
            )
        assert "end_date must be after start_date" in str(exc_info.value)
    
    def test_optional_filters(self):
        """Test that all filters are optional."""
        filters = EventFilters()
        assert filters.category is None
        assert filters.min_severity is None
        assert filters.max_severity is None


class TestReportRequest:
    """Test cases for ReportRequest model."""
    
    def test_valid_report_request(self):
        """Test valid report request creation."""
        request = ReportRequest(
            report_date=date(2024, 1, 15),
            include_details=True,
            min_severity=5
        )
        assert request.report_date == date(2024, 1, 15)
        assert request.include_details is True
        assert request.min_severity == 5
    
    def test_future_date_validation(self):
        """Test validation fails for future report dates."""
        future_date = date.today() + timedelta(days=1)
        with pytest.raises(ValidationError) as exc_info:
            ReportRequest(report_date=future_date)
        assert "Report date cannot be in the future" in str(exc_info.value)
    
    def test_default_values(self):
        """Test default values are set correctly."""
        request = ReportRequest(report_date=date.today())
        assert request.include_details is True
        assert request.min_severity is None


class TestEnums:
    """Test cases for enum classes."""
    
    def test_event_category_values(self):
        """Test EventCategory enum values."""
        assert EventCategory.AUTH == "auth"
        assert EventCategory.SYSTEM == "system"
        assert EventCategory.NETWORK == "network"
        assert EventCategory.SECURITY == "security"
        assert EventCategory.APPLICATION == "application"
        assert EventCategory.KERNEL == "kernel"
        assert EventCategory.UNKNOWN == "unknown"
    
    def test_severity_level_values(self):
        """Test SeverityLevel enum values."""
        assert SeverityLevel.VERY_LOW == 1
        assert SeverityLevel.LOW == 2
        assert SeverityLevel.MEDIUM == 4
        assert SeverityLevel.HIGH == 6
        assert SeverityLevel.CRITICAL == 8
        assert SeverityLevel.MAXIMUM == 10