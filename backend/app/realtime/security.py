"""
Security measures and input validation for real-time features.

This module provides comprehensive input validation, file path sandboxing,
rate limiting, and security measures for real-time log monitoring.
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Union
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, Request
from ipaddress import ip_address, ip_network, AddressValueError

from ..logging_config import get_logger
from .audit import get_audit_logger, AuditEventType, AuditSeverity

logger = get_logger(__name__)


class SecurityLevel(str, Enum):
    """Security levels for validation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    STRICT = "strict"


from .exceptions import InputValidationError as ValidationError, SecurityViolation


class InputValidator:
    """
    Comprehensive input validation for real-time features.
    
    Provides validation for file paths, configuration inputs, and user data
    with configurable security levels and sanitization.
    """
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.MEDIUM):
        self.security_level = security_level
        self.audit_logger = get_audit_logger()
        
        # Dangerous patterns to detect
        self.dangerous_patterns = {
            'path_traversal': [
                r'\.\./',
                r'\.\.\\'
                r'\.\.%2f',
                r'\.\.%5c',
                r'%2e%2e%2f',
                r'%2e%2e%5c'
            ],
            'command_injection': [
                r'[;&|`$]',
                r'\$\(',
                r'`[^`]*`',
                r'\|\s*\w+',
                r';\s*\w+',
                r'&&\s*\w+',
                r'\|\|\s*\w+'
            ],
            'script_injection': [
                r'<script[^>]*>',
                r'javascript:',
                r'vbscript:',
                r'on\w+\s*=',
                r'expression\s*\(',
                r'@import',
                r'<iframe[^>]*>',
                r'<object[^>]*>',
                r'<embed[^>]*>'
            ],
            'sql_injection': [
                r'union\s+select',
                r'drop\s+table',
                r'delete\s+from',
                r'insert\s+into',
                r'update\s+\w+\s+set',
                r'exec\s*\(',
                r'sp_\w+',
                r'xp_\w+'
            ]
        }
        
        # Allowed file extensions for log files
        self.allowed_log_extensions = {
            '.log', '.txt', '.out', '.err', '.trace', '.audit',
            '.access', '.error', '.debug', '.info', '.warn'
        }
        
        # Maximum sizes
        self.max_path_length = 1000
        self.max_filename_length = 255
        self.max_config_value_length = 10000
        self.max_description_length = 2000
    
    def validate_file_path(self, file_path: str, allow_relative: bool = False) -> str:
        """
        Validate and sanitize file path.
        
        Args:
            file_path: File path to validate
            allow_relative: Whether to allow relative paths
            
        Returns:
            Sanitized file path
            
        Raises:
            ValidationError: If path is invalid or dangerous
        """
        try:
            if not file_path or not isinstance(file_path, str):
                raise ValidationError("File path must be a non-empty string")
            
            # Check length
            if len(file_path) > self.max_path_length:
                raise ValidationError(f"File path too long (max {self.max_path_length} characters)")
            
            # Check for dangerous patterns
            self._check_dangerous_patterns(file_path, 'path_traversal')
            self._check_dangerous_patterns(file_path, 'command_injection')
            
            # Normalize path
            normalized_path = os.path.normpath(file_path)
            
            # Check for path traversal after normalization
            if '..' in normalized_path:
                raise ValidationError("Path traversal detected in file path")
            
            # Convert to Path object for validation
            path_obj = Path(normalized_path)
            
            # Check if path is absolute or relative
            if not allow_relative and not path_obj.is_absolute():
                raise ValidationError("Relative paths not allowed")
            
            # Check file extension for log files
            if path_obj.suffix.lower() not in self.allowed_log_extensions:
                if self.security_level in [SecurityLevel.HIGH, SecurityLevel.STRICT]:
                    raise ValidationError(f"File extension not allowed: {path_obj.suffix}")
                else:
                    logger.warning(f"Unusual file extension for log file: {path_obj.suffix}")
            
            # Additional checks for strict security
            if self.security_level == SecurityLevel.STRICT:
                # Check for hidden files
                if any(part.startswith('.') for part in path_obj.parts):
                    raise ValidationError("Hidden files/directories not allowed in strict mode")
                
                # Check for system directories
                system_dirs = {'/etc', '/sys', '/proc', '/dev', '/boot', '/root'}
                if any(str(path_obj).startswith(sys_dir) for sys_dir in system_dirs):
                    raise ValidationError("Access to system directories not allowed")
            
            return str(path_obj)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating file path '{file_path}': {e}")
            raise ValidationError(f"Invalid file path: {e}")
    
    def validate_log_source_name(self, name: str) -> str:
        """
        Validate log source name.
        
        Args:
            name: Log source name to validate
            
        Returns:
            Sanitized log source name
            
        Raises:
            ValidationError: If name is invalid
        """
        try:
            if not name or not isinstance(name, str):
                raise ValidationError("Log source name must be a non-empty string")
            
            # Check length
            if len(name) > self.max_filename_length:
                raise ValidationError(f"Log source name too long (max {self.max_filename_length} characters)")
            
            # Check for dangerous patterns
            self._check_dangerous_patterns(name, 'command_injection')
            self._check_dangerous_patterns(name, 'script_injection')
            
            # Check for valid characters (alphanumeric, underscore, hyphen, dot)
            if not re.match(r'^[a-zA-Z0-9_\-\.]+$', name):
                raise ValidationError("Log source name contains invalid characters")
            
            # Check for reserved names
            reserved_names = {'con', 'prn', 'aux', 'nul', 'com1', 'com2', 'com3', 'com4', 
                            'com5', 'com6', 'com7', 'com8', 'com9', 'lpt1', 'lpt2', 'lpt3', 
                            'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'}
            if name.lower() in reserved_names:
                raise ValidationError(f"Reserved name not allowed: {name}")
            
            return name.strip()
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating log source name '{name}': {e}")
            raise ValidationError(f"Invalid log source name: {e}")
    
    def validate_notification_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate notification configuration.
        
        Args:
            config: Notification configuration to validate
            
        Returns:
            Sanitized configuration
            
        Raises:
            ValidationError: If configuration is invalid
        """
        try:
            if not isinstance(config, dict):
                raise ValidationError("Notification config must be a dictionary")
            
            sanitized_config = {}
            
            for key, value in config.items():
                # Validate key
                if not isinstance(key, str) or len(key) > 100:
                    raise ValidationError(f"Invalid configuration key: {key}")
                
                # Check for dangerous patterns in key
                self._check_dangerous_patterns(key, 'script_injection')
                self._check_dangerous_patterns(key, 'command_injection')
                
                # Validate value based on key
                if key in ['email', 'webhook_url', 'slack_webhook']:
                    sanitized_value = self._validate_url_or_email(value)
                elif key in ['message', 'description', 'template']:
                    sanitized_value = self._validate_text_content(value)
                elif key in ['enabled', 'active']:
                    sanitized_value = bool(value)
                elif key in ['timeout', 'retry_count', 'max_retries']:
                    sanitized_value = self._validate_numeric_value(value, 0, 3600)
                else:
                    # Generic validation for other values
                    sanitized_value = self._validate_generic_value(value)
                
                sanitized_config[key] = sanitized_value
            
            return sanitized_config
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating notification config: {e}")
            raise ValidationError(f"Invalid notification configuration: {e}")
    
    def validate_monitoring_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate monitoring configuration.
        
        Args:
            config: Monitoring configuration to validate
            
        Returns:
            Sanitized configuration
            
        Raises:
            ValidationError: If configuration is invalid
        """
        try:
            if not isinstance(config, dict):
                raise ValidationError("Monitoring config must be a dictionary")
            
            sanitized_config = {}
            
            # Define expected configuration keys and their validation rules
            config_rules = {
                'polling_interval': {'type': 'numeric', 'min': 1, 'max': 3600},
                'batch_size': {'type': 'numeric', 'min': 1, 'max': 1000},
                'max_queue_size': {'type': 'numeric', 'min': 10, 'max': 100000},
                'max_concurrent_sources': {'type': 'numeric', 'min': 1, 'max': 100},
                'enabled': {'type': 'boolean'},
                'debug_mode': {'type': 'boolean'},
                'log_level': {'type': 'string', 'allowed': ['DEBUG', 'INFO', 'WARNING', 'ERROR']},
                'timeout': {'type': 'numeric', 'min': 1, 'max': 300},
                'retry_attempts': {'type': 'numeric', 'min': 0, 'max': 10}
            }
            
            for key, value in config.items():
                # Validate key
                if not isinstance(key, str) or len(key) > 100:
                    raise ValidationError(f"Invalid configuration key: {key}")
                
                # Check for dangerous patterns
                self._check_dangerous_patterns(key, 'script_injection')
                self._check_dangerous_patterns(key, 'command_injection')
                
                # Apply validation rules
                if key in config_rules:
                    rule = config_rules[key]
                    if rule['type'] == 'numeric':
                        sanitized_value = self._validate_numeric_value(
                            value, rule.get('min', 0), rule.get('max', float('inf'))
                        )
                    elif rule['type'] == 'boolean':
                        sanitized_value = bool(value)
                    elif rule['type'] == 'string':
                        sanitized_value = self._validate_string_value(
                            value, rule.get('allowed')
                        )
                    else:
                        sanitized_value = self._validate_generic_value(value)
                else:
                    # Generic validation for unknown keys
                    sanitized_value = self._validate_generic_value(value)
                
                sanitized_config[key] = sanitized_value
            
            return sanitized_config
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating monitoring config: {e}")
            raise ValidationError(f"Invalid monitoring configuration: {e}")
    
    def _check_dangerous_patterns(self, text: str, pattern_type: str) -> None:
        """
        Check text for dangerous patterns.
        
        Args:
            text: Text to check
            pattern_type: Type of patterns to check
            
        Raises:
            ValidationError: If dangerous pattern found
        """
        if pattern_type not in self.dangerous_patterns:
            return
        
        text_lower = text.lower()
        for pattern in self.dangerous_patterns[pattern_type]:
            if re.search(pattern, text_lower, re.IGNORECASE):
                self.audit_logger.log_security_event(
                    AuditEventType.SECURITY_VIOLATION,
                    f"Dangerous pattern detected: {pattern_type} in '{text[:100]}'",
                    AuditSeverity.HIGH
                )
                raise ValidationError(f"Dangerous pattern detected: {pattern_type}")
    
    def _validate_url_or_email(self, value: str) -> str:
        """Validate URL or email address."""
        if not isinstance(value, str):
            raise ValidationError("URL/Email must be a string")
        
        if len(value) > 500:
            raise ValidationError("URL/Email too long")
        
        # Check for dangerous patterns
        self._check_dangerous_patterns(value, 'script_injection')
        
        # Basic URL/email validation
        if '@' in value:
            # Email validation
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
                raise ValidationError("Invalid email format")
        else:
            # URL validation
            if not re.match(r'^https?://[a-zA-Z0-9.-]+', value):
                raise ValidationError("Invalid URL format")
        
        return value.strip()
    
    def _validate_text_content(self, value: str) -> str:
        """Validate text content."""
        if not isinstance(value, str):
            raise ValidationError("Text content must be a string")
        
        if len(value) > self.max_description_length:
            raise ValidationError(f"Text content too long (max {self.max_description_length} characters)")
        
        # Check for dangerous patterns
        self._check_dangerous_patterns(value, 'script_injection')
        
        return value.strip()
    
    def _validate_numeric_value(self, value: Union[int, float, str], min_val: float, max_val: float) -> Union[int, float]:
        """Validate numeric value."""
        try:
            if isinstance(value, str):
                # Try to convert string to number
                if '.' in value:
                    num_value = float(value)
                else:
                    num_value = int(value)
            else:
                num_value = value
            
            if not isinstance(num_value, (int, float)):
                raise ValidationError("Value must be numeric")
            
            if num_value < min_val or num_value > max_val:
                raise ValidationError(f"Value must be between {min_val} and {max_val}")
            
            return num_value
            
        except (ValueError, TypeError):
            raise ValidationError("Invalid numeric value")
    
    def _validate_string_value(self, value: str, allowed_values: Optional[List[str]] = None) -> str:
        """Validate string value."""
        if not isinstance(value, str):
            raise ValidationError("Value must be a string")
        
        if len(value) > 1000:
            raise ValidationError("String value too long")
        
        # Check for dangerous patterns
        self._check_dangerous_patterns(value, 'script_injection')
        self._check_dangerous_patterns(value, 'command_injection')
        
        if allowed_values and value not in allowed_values:
            raise ValidationError(f"Value must be one of: {', '.join(allowed_values)}")
        
        return value.strip()
    
    def _validate_generic_value(self, value: Any) -> Any:
        """Generic validation for unknown value types."""
        if isinstance(value, str):
            if len(value) > self.max_config_value_length:
                raise ValidationError(f"Value too long (max {self.max_config_value_length} characters)")
            
            # Check for dangerous patterns
            self._check_dangerous_patterns(value, 'script_injection')
            self._check_dangerous_patterns(value, 'command_injection')
            
            return value.strip()
        elif isinstance(value, (int, float, bool)):
            return value
        elif isinstance(value, (list, dict)):
            # Recursively validate complex types
            if isinstance(value, list):
                return [self._validate_generic_value(item) for item in value]
            else:
                return {k: self._validate_generic_value(v) for k, v in value.items()}
        else:
            raise ValidationError(f"Unsupported value type: {type(value)}")


class FilePathSandbox:
    """
    File path sandboxing for secure log file access.
    
    Provides secure file path validation and access control to prevent
    unauthorized file system access outside allowed directories.
    """
    
    def __init__(self, allowed_paths: List[str], security_level: SecurityLevel = SecurityLevel.MEDIUM):
        self.security_level = security_level
        self.allowed_paths = [Path(p).resolve() for p in allowed_paths]
        self.audit_logger = get_audit_logger()
        
        # Blocked paths (system directories)
        self.blocked_paths = [
            Path('/etc'), Path('/sys'), Path('/proc'), Path('/dev'),
            Path('/boot'), Path('/root'), Path('/usr/bin'), Path('/usr/sbin'),
            Path('/bin'), Path('/sbin')
        ]
        
        logger.info(f"File sandbox initialized with {len(self.allowed_paths)} allowed paths")
    
    def validate_path(self, file_path: str) -> Path:
        """
        Validate file path against sandbox rules.
        
        Args:
            file_path: File path to validate
            
        Returns:
            Resolved Path object if valid
            
        Raises:
            SecurityViolation: If path violates sandbox rules
        """
        try:
            # Convert to Path and resolve
            path = Path(file_path).resolve()
            
            # Check if path exists (for stricter validation)
            if self.security_level == SecurityLevel.STRICT and not path.exists():
                raise SecurityViolation(f"File does not exist: {path}")
            
            # Check against blocked paths
            for blocked_path in self.blocked_paths:
                try:
                    path.relative_to(blocked_path)
                    self.audit_logger.log_security_event(
                        AuditEventType.SECURITY_VIOLATION,
                        f"Attempt to access blocked path: {path}",
                        AuditSeverity.CRITICAL
                    )
                    raise SecurityViolation(f"Access to blocked path denied: {blocked_path}")
                except ValueError:
                    # Path is not under blocked path, continue
                    continue
            
            # Check against allowed paths
            for allowed_path in self.allowed_paths:
                try:
                    path.relative_to(allowed_path)
                    # Path is under an allowed path
                    logger.debug(f"Path validated: {path} (under {allowed_path})")
                    return path
                except ValueError:
                    # Path is not under this allowed path, try next
                    continue
            
            # Path is not under any allowed path
            self.audit_logger.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                f"Attempt to access path outside sandbox: {path}",
                AuditSeverity.HIGH
            )
            raise SecurityViolation(f"Path outside allowed directories: {path}")
            
        except SecurityViolation:
            raise
        except Exception as e:
            logger.error(f"Error validating path '{file_path}': {e}")
            raise SecurityViolation(f"Path validation failed: {e}")
    
    def is_path_allowed(self, file_path: str) -> bool:
        """
        Check if path is allowed without raising exceptions.
        
        Args:
            file_path: File path to check
            
        Returns:
            True if path is allowed, False otherwise
        """
        try:
            self.validate_path(file_path)
            return True
        except SecurityViolation:
            return False
    
    def add_allowed_path(self, path: str) -> None:
        """
        Add a new allowed path to the sandbox.
        
        Args:
            path: Path to add
        """
        try:
            resolved_path = Path(path).resolve()
            if resolved_path not in self.allowed_paths:
                self.allowed_paths.append(resolved_path)
                logger.info(f"Added allowed path: {resolved_path}")
        except Exception as e:
            logger.error(f"Error adding allowed path '{path}': {e}")
    
    def remove_allowed_path(self, path: str) -> None:
        """
        Remove an allowed path from the sandbox.
        
        Args:
            path: Path to remove
        """
        try:
            resolved_path = Path(path).resolve()
            if resolved_path in self.allowed_paths:
                self.allowed_paths.remove(resolved_path)
                logger.info(f"Removed allowed path: {resolved_path}")
        except Exception as e:
            logger.error(f"Error removing allowed path '{path}': {e}")


class RateLimiter:
    """
    Advanced rate limiting for API endpoints and WebSocket connections.
    
    Provides multiple rate limiting strategies including token bucket,
    sliding window, and adaptive rate limiting based on client behavior.
    """
    
    def __init__(self):
        self.client_buckets: Dict[str, Dict[str, Any]] = {}
        self.client_history: Dict[str, List[datetime]] = {}
        self.blocked_clients: Dict[str, datetime] = {}
        self.suspicious_clients: Set[str] = set()
        self.audit_logger = get_audit_logger()
        
        # Rate limiting configuration
        self.default_limits = {
            'requests_per_minute': 60,
            'burst_limit': 10,
            'websocket_connections_per_ip': 5,
            'config_changes_per_hour': 20
        }
        
        # Adaptive limits for suspicious clients
        self.suspicious_limits = {
            'requests_per_minute': 10,
            'burst_limit': 3,
            'websocket_connections_per_ip': 2,
            'config_changes_per_hour': 5
        }
    
    def check_rate_limit(self, client_id: str, endpoint: str, request: Optional[Request] = None) -> bool:
        """
        Check if client is within rate limits.
        
        Args:
            client_id: Client identifier
            endpoint: Endpoint being accessed
            request: Optional HTTP request object
            
        Returns:
            True if within limits, False if rate limited
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            # Check if client is blocked
            if client_id in self.blocked_clients:
                if current_time < self.blocked_clients[client_id]:
                    return False
                else:
                    # Unblock client
                    del self.blocked_clients[client_id]
            
            # Get limits based on client status
            limits = self.suspicious_limits if client_id in self.suspicious_clients else self.default_limits
            
            # Initialize client bucket if not exists
            if client_id not in self.client_buckets:
                self.client_buckets[client_id] = {
                    'tokens': limits['requests_per_minute'],
                    'last_refill': current_time,
                    'request_count': 0,
                    'window_start': current_time
                }
            
            bucket = self.client_buckets[client_id]
            
            # Refill tokens (token bucket algorithm)
            time_passed = (current_time - bucket['last_refill']).total_seconds()
            tokens_to_add = time_passed * (limits['requests_per_minute'] / 60.0)
            bucket['tokens'] = min(limits['requests_per_minute'], bucket['tokens'] + tokens_to_add)
            bucket['last_refill'] = current_time
            
            # Check if tokens available
            if bucket['tokens'] < 1:
                self._handle_rate_limit_violation(client_id, endpoint, "Token bucket exhausted")
                return False
            
            # Check burst limit (sliding window)
            window_duration = timedelta(seconds=10)
            if current_time - bucket['window_start'] > window_duration:
                bucket['request_count'] = 0
                bucket['window_start'] = current_time
            
            if bucket['request_count'] >= limits['burst_limit']:
                self._handle_rate_limit_violation(client_id, endpoint, "Burst limit exceeded")
                return False
            
            # Consume token and increment request count
            bucket['tokens'] -= 1
            bucket['request_count'] += 1
            
            # Track request history
            if client_id not in self.client_history:
                self.client_history[client_id] = []
            
            self.client_history[client_id].append(current_time)
            
            # Clean old history (keep last hour)
            cutoff_time = current_time - timedelta(hours=1)
            self.client_history[client_id] = [
                req_time for req_time in self.client_history[client_id] 
                if req_time > cutoff_time
            ]
            
            # Check for suspicious behavior
            self._check_suspicious_behavior(client_id, endpoint, request)
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit for {client_id}: {e}")
            return True  # Allow request on error to avoid blocking legitimate users
    
    def check_websocket_limit(self, client_ip: str) -> bool:
        """
        Check WebSocket connection limit for IP address.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            True if within limits, False if limit exceeded
        """
        try:
            # This would need to be integrated with WebSocket manager
            # to track active connections per IP
            limits = self.suspicious_limits if client_ip in self.suspicious_clients else self.default_limits
            
            # For now, return True - would need WebSocket manager integration
            return True
            
        except Exception as e:
            logger.error(f"Error checking WebSocket limit for {client_ip}: {e}")
            return True
    
    def _handle_rate_limit_violation(self, client_id: str, endpoint: str, reason: str) -> None:
        """Handle rate limit violation."""
        try:
            # Log violation
            self.audit_logger.log_security_event(
                AuditEventType.RATE_LIMIT_EXCEEDED,
                f"Rate limit exceeded for {client_id} on {endpoint}: {reason}",
                AuditSeverity.MEDIUM,
                metadata={
                    'client_id': client_id,
                    'endpoint': endpoint,
                    'reason': reason
                }
            )
            
            # Mark client as suspicious after multiple violations
            if client_id not in self.client_history:
                self.client_history[client_id] = []
            
            recent_violations = len([
                req_time for req_time in self.client_history[client_id]
                if req_time > datetime.now(timezone.utc) - timedelta(minutes=10)
            ])
            
            if recent_violations > 5:
                self.suspicious_clients.add(client_id)
                logger.warning(f"Client marked as suspicious: {client_id}")
            
            # Block client after excessive violations
            if recent_violations > 20:
                block_until = datetime.now(timezone.utc) + timedelta(minutes=30)
                self.blocked_clients[client_id] = block_until
                
                self.audit_logger.log_security_event(
                    AuditEventType.SUSPICIOUS_ACTIVITY,
                    f"Client blocked due to excessive rate limit violations: {client_id}",
                    AuditSeverity.HIGH,
                    metadata={
                        'client_id': client_id,
                        'block_until': block_until.isoformat(),
                        'violation_count': recent_violations
                    }
                )
                
                logger.error(f"Client blocked until {block_until}: {client_id}")
            
        except Exception as e:
            logger.error(f"Error handling rate limit violation: {e}")
    
    def _check_suspicious_behavior(self, client_id: str, endpoint: str, request: Optional[Request]) -> None:
        """Check for suspicious client behavior patterns."""
        try:
            if client_id not in self.client_history:
                return
            
            current_time = datetime.now(timezone.utc)
            recent_requests = [
                req_time for req_time in self.client_history[client_id]
                if req_time > current_time - timedelta(minutes=5)
            ]
            
            # Check for rapid-fire requests
            if len(recent_requests) > 50:
                self.suspicious_clients.add(client_id)
                self.audit_logger.log_security_event(
                    AuditEventType.SUSPICIOUS_ACTIVITY,
                    f"Rapid-fire requests detected from client: {client_id}",
                    AuditSeverity.MEDIUM,
                    metadata={
                        'client_id': client_id,
                        'request_count': len(recent_requests),
                        'endpoint': endpoint
                    }
                )
            
            # Check for unusual request patterns
            if request:
                user_agent = request.headers.get('user-agent', '')
                
                # Check for bot-like user agents
                bot_patterns = ['bot', 'crawler', 'spider', 'scraper', 'curl', 'wget']
                if any(pattern in user_agent.lower() for pattern in bot_patterns):
                    self.suspicious_clients.add(client_id)
                    logger.info(f"Bot-like user agent detected: {client_id} - {user_agent}")
            
        except Exception as e:
            logger.error(f"Error checking suspicious behavior: {e}")
    
    def get_client_status(self, client_id: str) -> Dict[str, Any]:
        """Get status information for a client."""
        try:
            current_time = datetime.now(timezone.utc)
            
            status = {
                'client_id': client_id,
                'is_suspicious': client_id in self.suspicious_clients,
                'is_blocked': client_id in self.blocked_clients,
                'block_expires': None,
                'tokens_remaining': 0,
                'recent_requests': 0
            }
            
            if client_id in self.blocked_clients:
                status['block_expires'] = self.blocked_clients[client_id].isoformat()
            
            if client_id in self.client_buckets:
                bucket = self.client_buckets[client_id]
                status['tokens_remaining'] = int(bucket['tokens'])
            
            if client_id in self.client_history:
                recent_requests = [
                    req_time for req_time in self.client_history[client_id]
                    if req_time > current_time - timedelta(minutes=5)
                ]
                status['recent_requests'] = len(recent_requests)
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting client status: {e}")
            return {'error': str(e)}
    
    def clear_client_history(self, client_id: str) -> None:
        """Clear history for a client (admin function)."""
        try:
            if client_id in self.client_buckets:
                del self.client_buckets[client_id]
            
            if client_id in self.client_history:
                del self.client_history[client_id]
            
            if client_id in self.blocked_clients:
                del self.blocked_clients[client_id]
            
            self.suspicious_clients.discard(client_id)
            
            logger.info(f"Cleared rate limit history for client: {client_id}")
            
        except Exception as e:
            logger.error(f"Error clearing client history: {e}")


# Global instances
input_validator = InputValidator()
rate_limiter = RateLimiter()

# Default sandbox paths (can be configured)
default_sandbox_paths = [
    '/var/log',
    '/tmp/logs',
    './logs',
    './data/sample_logs'
]

file_sandbox = FilePathSandbox(default_sandbox_paths)


def get_input_validator() -> InputValidator:
    """Get the global input validator instance."""
    return input_validator


def get_file_sandbox() -> FilePathSandbox:
    """Get the global file sandbox instance."""
    return file_sandbox


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return rate_limiter