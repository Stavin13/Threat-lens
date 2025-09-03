"""
Centralized error handling middleware and utilities for ThreatLens.

This module provides comprehensive error handling, custom exceptions,
and middleware for FastAPI applications.
"""
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
import logging

from app.logging_config import get_logger, log_error_with_context, get_correlation_id
from app.schemas import ErrorResponse

logger = get_logger(__name__)


class ThreatLensError(Exception):
    """Base exception class for ThreatLens application."""
    
    def __init__(
        self,
        message: str,
        error_code: str = None,
        details: Dict[str, Any] = None,
        user_message: str = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.user_message = user_message or message


class ValidationError(ThreatLensError):
    """Validation error for input data."""
    pass


class DatabaseError(ThreatLensError):
    """Database operation error."""
    pass


class ExternalServiceError(ThreatLensError):
    """External service integration error."""
    pass


class AuthenticationError(ThreatLensError):
    """Authentication and authorization errors."""
    pass


class RateLimitError(ThreatLensError):
    """Rate limiting error."""
    pass


class ConfigurationError(ThreatLensError):
    """Configuration or setup error."""
    pass


class ProcessingError(ThreatLensError):
    """Data processing error."""
    pass


# Error code mappings to HTTP status codes
ERROR_STATUS_MAPPING = {
    'ValidationError': status.HTTP_400_BAD_REQUEST,
    'IngestionError': status.HTTP_400_BAD_REQUEST,
    'ParsingError': status.HTTP_422_UNPROCESSABLE_ENTITY,
    'AnalysisError': status.HTTP_500_INTERNAL_SERVER_ERROR,
    'DatabaseError': status.HTTP_500_INTERNAL_SERVER_ERROR,
    'ExternalServiceError': status.HTTP_503_SERVICE_UNAVAILABLE,
    'AuthenticationError': status.HTTP_401_UNAUTHORIZED,
    'RateLimitError': status.HTTP_429_TOO_MANY_REQUESTS,
    'ConfigurationError': status.HTTP_500_INTERNAL_SERVER_ERROR,
    'ProcessingError': status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def get_error_status_code(error: Exception) -> int:
    """
    Get HTTP status code for an error.
    
    Args:
        error: Exception instance
        
    Returns:
        HTTP status code
    """
    error_type = type(error).__name__
    return ERROR_STATUS_MAPPING.get(error_type, status.HTTP_500_INTERNAL_SERVER_ERROR)


def create_error_response(
    error: Exception,
    request: Request = None,
    include_details: bool = False
) -> ErrorResponse:
    """
    Create standardized error response.
    
    Args:
        error: Exception that occurred
        request: Optional FastAPI request object
        include_details: Whether to include detailed error information
        
    Returns:
        ErrorResponse object
    """
    error_type = type(error).__name__
    correlation_id = get_correlation_id()
    
    # Base error information
    error_data = {
        'error': error_type,
        'message': str(error),
        'timestamp': datetime.now(timezone.utc),
        'correlation_id': correlation_id
    }
    
    # Add request information if available
    if request:
        error_data['path'] = str(request.url.path)
        error_data['method'] = request.method
    
    # Add detailed information for ThreatLens errors
    if isinstance(error, ThreatLensError):
        if error.user_message:
            error_data['message'] = error.user_message
        
        if include_details and error.details:
            error_data['details'] = error.details
    
    # Add validation details for Pydantic errors
    elif isinstance(error, (ValidationError, RequestValidationError)):
        if hasattr(error, 'errors'):
            error_data['details'] = {
                'validation_errors': error.errors()
            }
    
    # Add details for development/debugging
    if include_details:
        error_data['details'] = error_data.get('details', {})
        error_data['details'].update({
            'error_type': error_type,
            'traceback': traceback.format_exc() if logger.isEnabledFor(logging.DEBUG) else None
        })
    
    return ErrorResponse(**error_data)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for all unhandled exceptions.
    
    Args:
        request: FastAPI request object
        exc: Exception that occurred
        
    Returns:
        JSON error response
    """
    # Log the error with context
    context = {
        'path': str(request.url.path),
        'method': request.method,
        'query_params': dict(request.query_params),
        'client_host': request.client.host if request.client else None,
        'user_agent': request.headers.get('user-agent'),
    }
    
    log_error_with_context(
        logger,
        exc,
        context=context,
        user_message="Unhandled exception in API request"
    )
    
    # Create error response
    include_details = logger.isEnabledFor(logging.DEBUG)
    error_response = create_error_response(exc, request, include_details)
    status_code = get_error_status_code(exc)
    
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(error_response)
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handler for HTTP exceptions.
    
    Args:
        request: FastAPI request object
        exc: HTTP exception
        
    Returns:
        JSON error response
    """
    # Log HTTP exceptions (but not 4xx client errors unless debug)
    if exc.status_code >= 500 or logger.isEnabledFor(logging.DEBUG):
        context = {
            'path': str(request.url.path),
            'method': request.method,
            'status_code': exc.status_code,
        }
        
        log_error_with_context(
            logger,
            exc,
            context=context,
            user_message=f"HTTP {exc.status_code} error"
        )
    
    # Create standardized error response
    error_response = ErrorResponse(
        error="HTTPException",
        message=exc.detail,
        timestamp=datetime.now(timezone.utc),
        correlation_id=get_correlation_id(),
        details={
            'status_code': exc.status_code,
            'path': str(request.url.path),
            'method': request.method
        } if logger.isEnabledFor(logging.DEBUG) else None
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(error_response)
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handler for request validation errors.
    
    Args:
        request: FastAPI request object
        exc: Validation error
        
    Returns:
        JSON error response
    """
    # Log validation errors
    context = {
        'path': str(request.url.path),
        'method': request.method,
        'validation_errors': exc.errors(),
    }
    
    logger.warning(
        f"Request validation failed: {len(exc.errors())} errors",
        extra=context
    )
    
    # Create user-friendly error message
    error_count = len(exc.errors())
    user_message = f"Request validation failed with {error_count} error{'s' if error_count != 1 else ''}"
    
    # Create error response
    error_response = ErrorResponse(
        error="ValidationError",
        message=user_message,
        timestamp=datetime.now(timezone.utc),
        correlation_id=get_correlation_id(),
        details={
            'validation_errors': exc.errors(),
            'path': str(request.url.path),
            'method': request.method
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder(error_response)
    )


def handle_database_error(error: Exception, operation: str = "database operation") -> DatabaseError:
    """
    Handle database errors with appropriate logging and user messages.
    
    Args:
        error: Original database error
        operation: Description of the operation that failed
        
    Returns:
        DatabaseError with user-friendly message
    """
    error_message = f"Database error during {operation}: {str(error)}"
    user_message = f"A database error occurred during {operation}. Please try again later."
    
    log_error_with_context(
        logger,
        error,
        context={'operation': operation},
        user_message=user_message
    )
    
    return DatabaseError(
        message=error_message,
        user_message=user_message,
        details={'operation': operation, 'original_error': str(error)}
    )


def handle_external_service_error(
    error: Exception,
    service_name: str,
    operation: str = "external service call"
) -> ExternalServiceError:
    """
    Handle external service errors.
    
    Args:
        error: Original service error
        service_name: Name of the external service
        operation: Description of the operation
        
    Returns:
        ExternalServiceError with user-friendly message
    """
    error_message = f"External service error ({service_name}) during {operation}: {str(error)}"
    user_message = f"The {service_name} service is currently unavailable. Please try again later."
    
    log_error_with_context(
        logger,
        error,
        context={'service_name': service_name, 'operation': operation},
        user_message=user_message
    )
    
    return ExternalServiceError(
        message=error_message,
        user_message=user_message,
        details={
            'service_name': service_name,
            'operation': operation,
            'original_error': str(error)
        }
    )


def handle_processing_error(
    error: Exception,
    process_type: str,
    item_id: str = None
) -> ProcessingError:
    """
    Handle data processing errors.
    
    Args:
        error: Original processing error
        process_type: Type of processing that failed
        item_id: Optional ID of the item being processed
        
    Returns:
        ProcessingError with user-friendly message
    """
    error_message = f"Processing error during {process_type}: {str(error)}"
    user_message = f"An error occurred during {process_type}. Please check your input and try again."
    
    context = {'process_type': process_type}
    if item_id:
        context['item_id'] = item_id
        error_message += f" (item: {item_id})"
    
    log_error_with_context(
        logger,
        error,
        context=context,
        user_message=user_message
    )
    
    return ProcessingError(
        message=error_message,
        user_message=user_message,
        details=context
    )


class ErrorRecoveryManager:
    """Manager for error recovery strategies."""
    
    def __init__(self):
        self.recovery_strategies = {}
        self.logger = get_logger(f"{__name__}.ErrorRecoveryManager")
    
    def register_recovery_strategy(self, error_type: type, strategy_func):
        """
        Register a recovery strategy for a specific error type.
        
        Args:
            error_type: Exception type to handle
            strategy_func: Function to call for recovery
        """
        self.recovery_strategies[error_type] = strategy_func
        self.logger.info(f"Registered recovery strategy for {error_type.__name__}")
    
    def attempt_recovery(self, error: Exception, context: Dict[str, Any] = None) -> bool:
        """
        Attempt to recover from an error.
        
        Args:
            error: Exception that occurred
            context: Additional context for recovery
            
        Returns:
            True if recovery was successful, False otherwise
        """
        error_type = type(error)
        strategy = self.recovery_strategies.get(error_type)
        
        if not strategy:
            self.logger.debug(f"No recovery strategy for {error_type.__name__}")
            return False
        
        try:
            self.logger.info(f"Attempting recovery for {error_type.__name__}")
            result = strategy(error, context or {})
            
            if result:
                self.logger.info(f"Recovery successful for {error_type.__name__}")
            else:
                self.logger.warning(f"Recovery failed for {error_type.__name__}")
            
            return result
            
        except Exception as recovery_error:
            self.logger.error(
                f"Recovery strategy failed for {error_type.__name__}: {recovery_error}",
                exc_info=True
            )
            return False


# Global error recovery manager instance
error_recovery_manager = ErrorRecoveryManager()


def with_error_handling(operation_name: str = None):
    """
    Decorator for adding error handling to functions.
    
    Args:
        operation_name: Optional name for the operation (defaults to function name)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Attempt recovery first
                if error_recovery_manager.attempt_recovery(e, {'operation': op_name}):
                    # Retry the operation once after successful recovery
                    try:
                        return func(*args, **kwargs)
                    except Exception as retry_error:
                        log_error_with_context(
                            logger,
                            retry_error,
                            context={'operation': op_name, 'retry_after_recovery': True}
                        )
                        raise
                else:
                    # Log and re-raise the original error
                    log_error_with_context(
                        logger,
                        e,
                        context={'operation': op_name}
                    )
                    raise
        
        return wrapper
    return decorator


# Health check error handling
def create_health_check_error(component: str, error: Exception) -> Dict[str, Any]:
    """
    Create health check error information.
    
    Args:
        component: Component name
        error: Error that occurred
        
    Returns:
        Health check error dictionary
    """
    return {
        'status': 'unhealthy',
        'error': type(error).__name__,
        'message': str(error),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'component': component
    }