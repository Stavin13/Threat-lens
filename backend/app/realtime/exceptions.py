"""
Custom exceptions for real-time processing components.
"""


class RealtimeError(Exception):
    """Base exception for real-time processing errors."""
    pass


class MonitoringError(RealtimeError):
    """Exception raised when file monitoring encounters an error."""
    pass


class ProcessingError(RealtimeError):
    """Exception raised during real-time log processing."""
    pass


class ConfigurationError(RealtimeError):
    """Exception raised for configuration-related errors."""
    pass


class WebSocketError(RealtimeError):
    """Exception raised for WebSocket-related errors."""
    pass


class NotificationError(RealtimeError):
    """Exception raised for notification delivery errors."""
    pass


class QueueError(RealtimeError):
    """Exception raised for queue processing errors."""
    pass


class ValidationError(RealtimeError):
    """Exception raised for log entry validation errors."""
    pass


class InputValidationError(RealtimeError):
    """Exception raised for input validation errors."""
    pass


class BroadcastError(RealtimeError):
    """Exception raised for event broadcasting errors."""
    pass


class AuthenticationError(RealtimeError):
    """Exception raised for authentication failures."""
    pass


class AuthorizationError(RealtimeError):
    """Exception raised for authorization failures."""
    pass


class SecurityViolation(RealtimeError):
    """Exception raised for security violations."""
    pass


class PerformanceError(RealtimeError):
    """Exception raised for performance-related errors."""
    pass