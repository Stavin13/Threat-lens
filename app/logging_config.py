"""
Comprehensive logging configuration for ThreatLens.

This module provides structured logging with correlation IDs, JSON formatting,
and centralized configuration for the entire application.
"""
import logging
import logging.config
import json
import uuid
import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from contextvars import ContextVar
from pathlib import Path

# Context variable for request correlation IDs
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""
    
    def filter(self, record):
        record.correlation_id = correlation_id.get() or 'no-correlation-id'
        return True


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'correlation_id': getattr(record, 'correlation_id', 'no-correlation-id'),
            'process_id': record.process,
            'thread_id': record.thread,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info) if record.exc_info else None
            }
        
        # Add extra fields from the record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                'thread', 'threadName', 'processName', 'process', 'getMessage',
                'exc_info', 'exc_text', 'stack_info', 'correlation_id'
            }:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry['extra'] = extra_fields
        
        return json.dumps(log_entry, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter for development."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, '')
        reset = self.RESET
        
        # Format the basic message
        formatted = super().format(record)
        
        # Add correlation ID if available
        correlation_id_str = getattr(record, 'correlation_id', 'no-correlation-id')
        if correlation_id_str != 'no-correlation-id':
            formatted = f"[{correlation_id_str[:8]}] {formatted}"
        
        return f"{color}{formatted}{reset}"


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[str] = None,
    enable_console: bool = True
) -> None:
    """
    Setup comprehensive logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type ('json' or 'console')
        log_file: Optional log file path
        enable_console: Whether to enable console logging
    """
    # Ensure logs directory exists
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure handlers
    handlers = {}
    
    if enable_console:
        handlers['console'] = {
            'class': 'logging.StreamHandler',
            'level': log_level,
            'formatter': 'colored_console' if log_format == 'console' else 'json',
            'stream': 'ext://sys.stdout',
            'filters': ['correlation_id']
        }
    
    if log_file:
        handlers['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': log_level,
            'formatter': 'json',
            'filename': log_file,
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,
            'filters': ['correlation_id']
        }
    
    # Configure formatters
    formatters = {
        'json': {
            '()': JSONFormatter,
        },
        'colored_console': {
            '()': ColoredConsoleFormatter,
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    }
    
    # Configure filters
    filters = {
        'correlation_id': {
            '()': CorrelationIdFilter,
        }
    }
    
    # Main logging configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': formatters,
        'filters': filters,
        'handlers': handlers,
        'root': {
            'level': log_level,
            'handlers': list(handlers.keys())
        },
        'loggers': {
            # Application loggers
            'app': {
                'level': log_level,
                'handlers': list(handlers.keys()),
                'propagate': False
            },
            'main': {
                'level': log_level,
                'handlers': list(handlers.keys()),
                'propagate': False
            },
            # Third-party loggers (reduce noise)
            'uvicorn': {
                'level': 'WARNING',
                'handlers': list(handlers.keys()),
                'propagate': False
            },
            'uvicorn.access': {
                'level': 'WARNING',
                'handlers': list(handlers.keys()),
                'propagate': False
            },
            'sqlalchemy': {
                'level': 'WARNING',
                'handlers': list(handlers.keys()),
                'propagate': False
            },
            'groq': {
                'level': 'WARNING',
                'handlers': list(handlers.keys()),
                'propagate': False
            }
        }
    }
    
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_correlation_id(correlation_id_value: str) -> None:
    """
    Set correlation ID for the current context.
    
    Args:
        correlation_id_value: Correlation ID to set
    """
    correlation_id.set(correlation_id_value)


def get_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID.
    
    Returns:
        Current correlation ID or None
    """
    return correlation_id.get()


def generate_correlation_id() -> str:
    """
    Generate a new correlation ID.
    
    Returns:
        New UUID-based correlation ID
    """
    return str(uuid.uuid4())


def log_function_call(logger: logging.Logger, func_name: str, **kwargs):
    """
    Log function call with parameters.
    
    Args:
        logger: Logger instance
        func_name: Function name
        **kwargs: Function parameters to log
    """
    logger.debug(
        f"Function call: {func_name}",
        extra={
            'function_call': func_name,
            'parameters': {k: str(v) for k, v in kwargs.items()}
        }
    )


def log_function_result(logger: logging.Logger, func_name: str, result: Any, execution_time: float = None):
    """
    Log function result.
    
    Args:
        logger: Logger instance
        func_name: Function name
        result: Function result
        execution_time: Optional execution time in seconds
    """
    extra_data = {
        'function_result': func_name,
        'result_type': type(result).__name__
    }
    
    if execution_time is not None:
        extra_data['execution_time_seconds'] = execution_time
    
    logger.debug(
        f"Function result: {func_name}",
        extra=extra_data
    )


def log_error_with_context(
    logger: logging.Logger,
    error: Exception,
    context: Dict[str, Any] = None,
    user_message: str = None
):
    """
    Log error with additional context.
    
    Args:
        logger: Logger instance
        error: Exception that occurred
        context: Additional context information
        user_message: User-friendly error message
    """
    extra_data = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context or {}
    }
    
    if user_message:
        extra_data['user_message'] = user_message
    
    logger.error(
        f"Error occurred: {type(error).__name__}: {str(error)}",
        exc_info=True,
        extra=extra_data
    )


# Initialize logging on module import
def init_logging():
    """Initialize logging with environment-based configuration."""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_format = os.getenv('LOG_FORMAT', 'json').lower()
    log_file = os.getenv('LOG_FILE')
    enable_console = os.getenv('LOG_CONSOLE', 'true').lower() == 'true'
    
    setup_logging(
        log_level=log_level,
        log_format=log_format,
        log_file=log_file,
        enable_console=enable_console
    )


# Auto-initialize if running as main module or imported
if __name__ == '__main__' or 'pytest' not in sys.modules:
    init_logging()