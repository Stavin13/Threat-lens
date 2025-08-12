"""
Tests for error handling and logging functionality.
"""
import pytest
import json
import logging
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

from app.error_handling import (
    ThreatLensError,
    ValidationError as CustomValidationError,
    DatabaseError,
    ExternalServiceError,
    AuthenticationError,
    RateLimitError,
    ConfigurationError,
    ProcessingError,
    create_error_response,
    handle_database_error,
    handle_external_service_error,
    handle_processing_error,
    ErrorRecoveryManager,
    with_error_handling
)
from app.logging_config import (
    setup_logging,
    get_logger,
    set_correlation_id,
    get_correlation_id,
    generate_correlation_id,
    log_error_with_context,
    JSONFormatter,
    CorrelationIdFilter
)
from app.middleware import (
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    MetricsMiddleware
)


class TestThreatLensErrors:
    """Test custom exception classes."""
    
    def test_base_error_creation(self):
        """Test ThreatLensError creation with all parameters."""
        error = ThreatLensError(
            message="Test error",
            error_code="TEST_ERROR",
            details={"key": "value"},
            user_message="User-friendly message"
        )
        
        assert str(error) == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert error.details == {"key": "value"}
        assert error.user_message == "User-friendly message"
    
    def test_base_error_defaults(self):
        """Test ThreatLensError with default values."""
        error = ThreatLensError("Test error")
        
        assert str(error) == "Test error"
        assert error.error_code == "ThreatLensError"
        assert error.details == {}
        assert error.user_message == "Test error"
    
    def test_specific_error_types(self):
        """Test specific error type creation."""
        validation_error = CustomValidationError("Invalid input")
        assert validation_error.error_code == "ValidationError"
        
        db_error = DatabaseError("Database connection failed")
        assert db_error.error_code == "DatabaseError"
        
        service_error = ExternalServiceError("API unavailable")
        assert service_error.error_code == "ExternalServiceError"


class TestErrorResponseCreation:
    """Test error response creation utilities."""
    
    def test_create_error_response_basic(self):
        """Test basic error response creation."""
        error = Exception("Test error")
        
        with patch('app.error_handling.get_correlation_id', return_value='test-correlation-id'):
            response = create_error_response(error)
        
        assert response.error == "Exception"
        assert response.message == "Test error"
        assert response.correlation_id == "test-correlation-id"
        assert isinstance(response.timestamp, datetime)
    
    def test_create_error_response_with_request(self):
        """Test error response creation with request context."""
        error = Exception("Test error")
        
        # Mock request object
        mock_request = Mock()
        mock_request.url.path = "/test/path"
        mock_request.method = "GET"
        
        with patch('app.error_handling.get_correlation_id', return_value='test-correlation-id'):
            response = create_error_response(error, request=mock_request, include_details=True)
        
        assert response.details is not None
        assert response.details['path'] == "/test/path"
        assert response.details['method'] == "GET"
    
    def test_create_error_response_threatlens_error(self):
        """Test error response creation with ThreatLensError."""
        error = ThreatLensError(
            message="Internal error",
            user_message="Something went wrong",
            details={"context": "test"}
        )
        
        with patch('app.error_handling.get_correlation_id', return_value='test-correlation-id'):
            response = create_error_response(error, include_details=True)
        
        assert response.message == "Something went wrong"
        assert response.details == {"context": "test"}


class TestErrorHandlers:
    """Test error handling utility functions."""
    
    def test_handle_database_error(self):
        """Test database error handling."""
        original_error = SQLAlchemyError("Connection failed")
        
        with patch('app.error_handling.log_error_with_context') as mock_log:
            result = handle_database_error(original_error, "user query")
        
        assert isinstance(result, DatabaseError)
        assert "user query" in result.message
        assert result.user_message is not None
        assert result.details['operation'] == "user query"
        mock_log.assert_called_once()
    
    def test_handle_external_service_error(self):
        """Test external service error handling."""
        original_error = Exception("Service unavailable")
        
        with patch('app.error_handling.log_error_with_context') as mock_log:
            result = handle_external_service_error(original_error, "Groq API", "analysis")
        
        assert isinstance(result, ExternalServiceError)
        assert "Groq API" in result.message
        assert result.details['service_name'] == "Groq API"
        assert result.details['operation'] == "analysis"
        mock_log.assert_called_once()
    
    def test_handle_processing_error(self):
        """Test processing error handling."""
        original_error = Exception("Processing failed")
        
        with patch('app.error_handling.log_error_with_context') as mock_log:
            result = handle_processing_error(original_error, "log parsing", "log-123")
        
        assert isinstance(result, ProcessingError)
        assert "log parsing" in result.message
        assert result.details['process_type'] == "log parsing"
        assert result.details['item_id'] == "log-123"
        mock_log.assert_called_once()


class TestErrorRecoveryManager:
    """Test error recovery management."""
    
    def test_register_recovery_strategy(self):
        """Test registering recovery strategies."""
        manager = ErrorRecoveryManager()
        
        def recovery_func(error, context):
            return True
        
        manager.register_recovery_strategy(ValueError, recovery_func)
        
        assert ValueError in manager.recovery_strategies
        assert manager.recovery_strategies[ValueError] == recovery_func
    
    def test_attempt_recovery_success(self):
        """Test successful error recovery."""
        manager = ErrorRecoveryManager()
        
        def recovery_func(error, context):
            return True
        
        manager.register_recovery_strategy(ValueError, recovery_func)
        
        error = ValueError("Test error")
        result = manager.attempt_recovery(error, {"test": "context"})
        
        assert result is True
    
    def test_attempt_recovery_failure(self):
        """Test failed error recovery."""
        manager = ErrorRecoveryManager()
        
        def recovery_func(error, context):
            return False
        
        manager.register_recovery_strategy(ValueError, recovery_func)
        
        error = ValueError("Test error")
        result = manager.attempt_recovery(error)
        
        assert result is False
    
    def test_attempt_recovery_no_strategy(self):
        """Test recovery attempt with no registered strategy."""
        manager = ErrorRecoveryManager()
        
        error = ValueError("Test error")
        result = manager.attempt_recovery(error)
        
        assert result is False
    
    def test_attempt_recovery_strategy_exception(self):
        """Test recovery when strategy itself raises exception."""
        manager = ErrorRecoveryManager()
        
        def failing_recovery_func(error, context):
            raise Exception("Recovery failed")
        
        manager.register_recovery_strategy(ValueError, failing_recovery_func)
        
        error = ValueError("Test error")
        result = manager.attempt_recovery(error)
        
        assert result is False


class TestWithErrorHandlingDecorator:
    """Test error handling decorator."""
    
    def test_decorator_success(self):
        """Test decorator with successful function execution."""
        @with_error_handling("test_operation")
        def test_function():
            return "success"
        
        result = test_function()
        assert result == "success"
    
    def test_decorator_with_error(self):
        """Test decorator with function that raises error."""
        @with_error_handling("test_operation")
        def test_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            test_function()
    
    def test_decorator_with_recovery(self):
        """Test decorator with successful error recovery."""
        call_count = 0
        
        @with_error_handling("test_operation")
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Test error")
            return "success after recovery"
        
        # Mock recovery manager to return success
        with patch('app.error_handling.error_recovery_manager') as mock_manager:
            mock_manager.attempt_recovery.return_value = True
            
            result = test_function()
            assert result == "success after recovery"
            assert call_count == 2  # Function called twice due to retry


class TestLoggingConfiguration:
    """Test logging configuration and utilities."""
    
    def test_setup_logging_basic(self):
        """Test basic logging setup."""
        with patch('logging.config.dictConfig') as mock_config:
            setup_logging(log_level="DEBUG", log_format="json")
            mock_config.assert_called_once()
    
    def test_correlation_id_management(self):
        """Test correlation ID context management."""
        # Test generation
        correlation_id = generate_correlation_id()
        assert isinstance(correlation_id, str)
        assert len(correlation_id) > 0
        
        # Test setting and getting
        set_correlation_id(correlation_id)
        assert get_correlation_id() == correlation_id
    
    def test_json_formatter(self):
        """Test JSON log formatter."""
        formatter = JSONFormatter()
        
        # Create a log record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.correlation_id = "test-correlation-id"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data['level'] == 'INFO'
        assert log_data['message'] == 'Test message'
        assert log_data['correlation_id'] == 'test-correlation-id'
        assert 'timestamp' in log_data
    
    def test_correlation_id_filter(self):
        """Test correlation ID filter."""
        filter_instance = CorrelationIdFilter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Test with no correlation ID set
        result = filter_instance.filter(record)
        assert result is True
        assert record.correlation_id == 'no-correlation-id'
        
        # Test with correlation ID set
        set_correlation_id("test-correlation-id")
        result = filter_instance.filter(record)
        assert result is True
        assert record.correlation_id == 'test-correlation-id'
    
    def test_log_error_with_context(self):
        """Test error logging with context."""
        logger = get_logger("test_logger")
        error = ValueError("Test error")
        context = {"key": "value"}
        
        with patch.object(logger, 'error') as mock_error:
            log_error_with_context(logger, error, context, "User message")
            
            mock_error.assert_called_once()
            call_args = mock_error.call_args
            assert "ValueError" in call_args[0][0]
            assert call_args[1]['exc_info'] is True
            assert call_args[1]['extra']['context'] == context
            assert call_args[1]['extra']['user_message'] == "User message"


class TestMiddleware:
    """Test middleware components."""
    
    def test_correlation_id_middleware(self):
        """Test correlation ID middleware."""
        app = Mock()
        middleware = CorrelationIdMiddleware(app)
        
        # Mock request and response
        request = Mock()
        request.headers = {}
        
        response = Mock()
        response.headers = {}
        
        async def mock_call_next(request):
            return response
        
        # Test with no existing correlation ID
        async def test_no_correlation_id():
            result = await middleware.dispatch(request, mock_call_next)
            assert 'X-Correlation-ID' in result.headers
            assert len(result.headers['X-Correlation-ID']) > 0
        
        import asyncio
        asyncio.run(test_no_correlation_id())
    
    def test_security_headers_middleware(self):
        """Test security headers middleware."""
        app = Mock()
        middleware = SecurityHeadersMiddleware(app)
        
        request = Mock()
        response = Mock()
        response.headers = {}
        
        async def mock_call_next(request):
            return response
        
        async def test_security_headers():
            result = await middleware.dispatch(request, mock_call_next)
            
            # Check that security headers are added
            assert 'X-Content-Type-Options' in result.headers
            assert 'X-Frame-Options' in result.headers
            assert 'X-XSS-Protection' in result.headers
            assert result.headers['X-Content-Type-Options'] == 'nosniff'
        
        import asyncio
        asyncio.run(test_security_headers())
    
    def test_metrics_middleware(self):
        """Test metrics collection middleware."""
        app = Mock()
        middleware = MetricsMiddleware(app)
        
        request = Mock()
        request.method = "GET"
        request.url.path = "/test"
        
        response = Mock()
        response.status_code = 200
        response.headers = {}
        
        async def mock_call_next(request):
            return response
        
        async def test_metrics():
            result = await middleware.dispatch(request, mock_call_next)
            
            # Check that metrics are updated
            metrics = middleware.get_metrics()
            assert metrics['total_requests'] == 1
            assert metrics['total_errors'] == 0
            assert 'GET /test' in metrics['endpoint_metrics']
        
        import asyncio
        asyncio.run(test_metrics())


class TestHealthCheckErrorHandling:
    """Test health check error handling."""
    
    def test_create_health_check_error(self):
        """Test health check error creation."""
        from app.error_handling import create_health_check_error
        
        error = Exception("Component failed")
        result = create_health_check_error("test_component", error)
        
        assert result['status'] == 'unhealthy'
        assert result['error'] == 'Exception'
        assert result['message'] == 'Component failed'
        assert result['component'] == 'test_component'
        assert 'timestamp' in result


@pytest.fixture
def mock_logger():
    """Fixture for mocked logger."""
    return Mock(spec=logging.Logger)


@pytest.fixture
def sample_error():
    """Fixture for sample error."""
    return ValueError("Test error message")


class TestIntegrationErrorHandling:
    """Integration tests for error handling system."""
    
    def test_end_to_end_error_handling(self, mock_logger, sample_error):
        """Test complete error handling flow."""
        # Test that error goes through all layers
        with patch('app.error_handling.get_correlation_id', return_value='test-correlation-id'):
            # Create error response
            response = create_error_response(sample_error)
            
            # Verify response structure
            assert response.error == "ValueError"
            assert response.message == "Test error message"
            assert response.correlation_id == "test-correlation-id"
            
            # Test error logging
            log_error_with_context(
                mock_logger,
                sample_error,
                context={"test": "context"},
                user_message="User-friendly message"
            )
            
            # Verify logging was called
            mock_logger.error.assert_called_once()
    
    def test_error_recovery_integration(self):
        """Test error recovery integration."""
        manager = ErrorRecoveryManager()
        
        # Register a recovery strategy
        def recovery_strategy(error, context):
            return context.get('can_recover', False)
        
        manager.register_recovery_strategy(ValueError, recovery_strategy)
        
        # Test successful recovery
        error = ValueError("Recoverable error")
        result = manager.attempt_recovery(error, {'can_recover': True})
        assert result is True
        
        # Test failed recovery
        result = manager.attempt_recovery(error, {'can_recover': False})
        assert result is False