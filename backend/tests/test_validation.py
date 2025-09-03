"""
Unit tests for validation functions.
"""
import pytest
from datetime import datetime, timedelta
from app.validation import (
    validate_log_content, validate_event_timestamp, validate_event_category,
    validate_severity_score, validate_recommendations_list, validate_source_identifier,
    validate_parsed_event, validate_ai_analysis_data, sanitize_log_content,
    validate_file_upload
)


class TestValidateLogContent:
    """Test cases for log content validation."""
    
    def test_valid_log_content(self):
        """Test validation passes for valid log content."""
        content = "Jan 15 10:30:45 MacBook-Pro kernel[0]: Test log entry"
        is_valid, error = validate_log_content(content)
        assert is_valid is True
        assert error is None
    
    def test_empty_content(self):
        """Test validation fails for empty content."""
        is_valid, error = validate_log_content("")
        assert is_valid is False
        assert "non-empty string" in error
    
    def test_none_content(self):
        """Test validation fails for None content."""
        is_valid, error = validate_log_content(None)
        assert is_valid is False
        assert "non-empty string" in error
    
    def test_short_content(self):
        """Test validation fails for too short content."""
        is_valid, error = validate_log_content("short")
        assert is_valid is False
        assert "too short" in error
    
    def test_oversized_content(self):
        """Test validation fails for oversized content."""
        large_content = "x" * 1000001  # Over 1MB
        is_valid, error = validate_log_content(large_content)
        assert is_valid is False
        assert "exceeds maximum size" in error
    
    def test_null_bytes(self):
        """Test validation fails for content with null bytes."""
        content = "Valid content\x00with null byte"
        is_valid, error = validate_log_content(content)
        assert is_valid is False
        assert "null bytes" in error
    
    def test_excessive_control_characters(self):
        """Test validation fails for excessive control characters."""
        content = "Valid" + "\x01\x02\x03\x04\x05" * 100  # Many control chars
        is_valid, error = validate_log_content(content)
        assert is_valid is False
        assert "excessive control characters" in error


class TestValidateEventTimestamp:
    """Test cases for event timestamp validation."""
    
    def test_valid_timestamp(self):
        """Test validation passes for valid timestamp."""
        timestamp = datetime.now() - timedelta(hours=1)
        is_valid, error = validate_event_timestamp(timestamp)
        assert is_valid is True
        assert error is None
    
    def test_non_datetime_object(self):
        """Test validation fails for non-datetime object."""
        is_valid, error = validate_event_timestamp("2024-01-15")
        assert is_valid is False
        assert "datetime object" in error
    
    def test_future_timestamp(self):
        """Test validation fails for far future timestamp."""
        future_timestamp = datetime.now() + timedelta(hours=2)
        is_valid, error = validate_event_timestamp(future_timestamp)
        assert is_valid is False
        assert "too far in the future" in error
    
    def test_very_old_timestamp(self):
        """Test validation fails for very old timestamp."""
        old_timestamp = datetime.now() - timedelta(days=4000)
        is_valid, error = validate_event_timestamp(old_timestamp)
        assert is_valid is False
        assert "too far in the past" in error
    
    def test_clock_skew_tolerance(self):
        """Test validation allows for reasonable clock skew."""
        future_timestamp = datetime.now() + timedelta(minutes=30)
        is_valid, error = validate_event_timestamp(future_timestamp)
        assert is_valid is True
        assert error is None


class TestValidateEventCategory:
    """Test cases for event category validation."""
    
    def test_valid_categories(self):
        """Test validation passes for all valid categories."""
        valid_categories = ["auth", "system", "network", "security", "application", "kernel", "unknown"]
        for category in valid_categories:
            is_valid, error = validate_event_category(category)
            assert is_valid is True, f"Category {category} should be valid"
            assert error is None
    
    def test_case_insensitive(self):
        """Test validation is case insensitive."""
        is_valid, error = validate_event_category("AUTH")
        assert is_valid is True
        assert error is None
    
    def test_invalid_category(self):
        """Test validation fails for invalid category."""
        is_valid, error = validate_event_category("invalid")
        assert is_valid is False
        assert "Invalid category" in error
    
    def test_non_string_category(self):
        """Test validation fails for non-string category."""
        is_valid, error = validate_event_category(123)
        assert is_valid is False
        assert "must be a string" in error


class TestValidateSeverityScore:
    """Test cases for severity score validation."""
    
    def test_valid_scores(self):
        """Test validation passes for valid scores 1-10."""
        for score in range(1, 11):
            is_valid, error = validate_severity_score(score)
            assert is_valid is True, f"Score {score} should be valid"
            assert error is None
    
    def test_invalid_low_score(self):
        """Test validation fails for score below 1."""
        is_valid, error = validate_severity_score(0)
        assert is_valid is False
        assert "between 1 and 10" in error
    
    def test_invalid_high_score(self):
        """Test validation fails for score above 10."""
        is_valid, error = validate_severity_score(11)
        assert is_valid is False
        assert "between 1 and 10" in error
    
    def test_non_integer_score(self):
        """Test validation fails for non-integer score."""
        is_valid, error = validate_severity_score(5.5)
        assert is_valid is False
        assert "must be an integer" in error


class TestValidateRecommendationsList:
    """Test cases for recommendations list validation."""
    
    def test_valid_recommendations(self):
        """Test validation passes for valid recommendations."""
        recommendations = ["Monitor system logs", "Check for patterns", "Review security policies"]
        is_valid, error = validate_recommendations_list(recommendations)
        assert is_valid is True
        assert error is None
    
    def test_empty_list(self):
        """Test validation fails for empty list."""
        is_valid, error = validate_recommendations_list([])
        assert is_valid is False
        assert "At least one recommendation" in error
    
    def test_non_list_input(self):
        """Test validation fails for non-list input."""
        is_valid, error = validate_recommendations_list("not a list")
        assert is_valid is False
        assert "must be a list" in error
    
    def test_too_many_recommendations(self):
        """Test validation fails for too many recommendations."""
        recommendations = [f"Recommendation {i}" for i in range(11)]
        is_valid, error = validate_recommendations_list(recommendations)
        assert is_valid is False
        assert "Too many recommendations" in error
    
    def test_non_string_recommendation(self):
        """Test validation fails for non-string recommendation."""
        recommendations = ["Valid recommendation", 123]
        is_valid, error = validate_recommendations_list(recommendations)
        assert is_valid is False
        assert "must be a string" in error
    
    def test_empty_recommendation(self):
        """Test validation fails for empty recommendation."""
        recommendations = ["Valid recommendation", ""]
        is_valid, error = validate_recommendations_list(recommendations)
        assert is_valid is False
        assert "cannot be empty" in error
    
    def test_short_recommendation(self):
        """Test validation fails for too short recommendation."""
        recommendations = ["Valid recommendation", "Hi"]
        is_valid, error = validate_recommendations_list(recommendations)
        assert is_valid is False
        assert "too short" in error
    
    def test_long_recommendation(self):
        """Test validation fails for too long recommendation."""
        long_rec = "x" * 501
        recommendations = ["Valid recommendation", long_rec]
        is_valid, error = validate_recommendations_list(recommendations)
        assert is_valid is False
        assert "too long" in error


class TestValidateSourceIdentifier:
    """Test cases for source identifier validation."""
    
    def test_valid_sources(self):
        """Test validation passes for valid source identifiers."""
        valid_sources = ["kernel", "auth.log", "system-log", "app_name", "server.domain.com"]
        for source in valid_sources:
            is_valid, error = validate_source_identifier(source)
            assert is_valid is True, f"Source {source} should be valid"
            assert error is None
    
    def test_empty_source(self):
        """Test validation fails for empty source."""
        is_valid, error = validate_source_identifier("")
        assert is_valid is False
        assert "cannot be empty" in error
    
    def test_non_string_source(self):
        """Test validation fails for non-string source."""
        is_valid, error = validate_source_identifier(123)
        assert is_valid is False
        assert "must be a string" in error
    
    def test_long_source(self):
        """Test validation fails for too long source."""
        long_source = "x" * 256
        is_valid, error = validate_source_identifier(long_source)
        assert is_valid is False
        assert "too long" in error
    
    def test_invalid_characters(self):
        """Test validation fails for invalid characters."""
        is_valid, error = validate_source_identifier("invalid source!")
        assert is_valid is False
        assert "must contain only alphanumeric" in error


class TestSanitizeLogContent:
    """Test cases for log content sanitization."""
    
    def test_remove_null_bytes(self):
        """Test null bytes are removed."""
        content = "Valid content\x00with null"
        sanitized = sanitize_log_content(content)
        assert "\x00" not in sanitized
        assert sanitized == "Valid contentwith null"
    
    def test_remove_control_characters(self):
        """Test control characters are removed."""
        content = "Valid\x01content\x02here"
        sanitized = sanitize_log_content(content)
        assert "\x01" not in sanitized
        assert "\x02" not in sanitized
        assert sanitized == "Validcontenthere"
    
    def test_preserve_newlines_tabs(self):
        """Test newlines and tabs are preserved."""
        content = "Line 1\nLine 2\tTabbed"
        sanitized = sanitize_log_content(content)
        assert "Line 1\nLine 2 Tabbed" == sanitized
    
    def test_normalize_line_endings(self):
        """Test line endings are normalized."""
        content = "Line 1\r\nLine 2\rLine 3"
        sanitized = sanitize_log_content(content)
        assert sanitized == "Line 1\nLine 2\nLine 3"
    
    def test_clean_excessive_whitespace(self):
        """Test excessive whitespace is cleaned."""
        content = "Word1    Word2\t\t\tWord3"
        sanitized = sanitize_log_content(content)
        assert sanitized == "Word1 Word2 Word3"
    
    def test_non_string_input(self):
        """Test non-string input returns empty string."""
        assert sanitize_log_content(None) == ""
        assert sanitize_log_content(123) == ""


class TestValidateFileUpload:
    """Test cases for file upload validation."""
    
    def test_valid_file(self):
        """Test validation passes for valid file."""
        content = b"Jan 15 10:30:45 MacBook-Pro kernel[0]: Test log entry"
        is_valid, error = validate_file_upload(content, "test.log")
        assert is_valid is True
        assert error is None
    
    def test_empty_file(self):
        """Test validation fails for empty file."""
        is_valid, error = validate_file_upload(b"", "test.log")
        assert is_valid is False
        assert "File is empty" in error
    
    def test_oversized_file(self):
        """Test validation fails for oversized file."""
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        is_valid, error = validate_file_upload(large_content, "test.log")
        assert is_valid is False
        assert "File too large" in error
    
    def test_invalid_filename(self):
        """Test validation fails for invalid filename."""
        content = b"Valid content"
        is_valid, error = validate_file_upload(content, "")
        assert is_valid is False
        assert "Invalid filename" in error
    
    def test_dangerous_file_extension(self):
        """Test validation fails for dangerous file extensions."""
        content = b"Valid content"
        dangerous_files = ["malware.exe", "script.bat", "virus.com"]
        for filename in dangerous_files:
            is_valid, error = validate_file_upload(content, filename)
            assert is_valid is False, f"File {filename} should be rejected"
            assert "File type not allowed" in error