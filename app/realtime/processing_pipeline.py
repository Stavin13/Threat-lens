"""
Processing pipeline for real-time log entries.

This module provides validation, sanitization, and processing status tracking
for log entries in the real-time ingestion system.
"""

import logging
import re
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from .ingestion_queue import LogEntry, ProcessingStatus, LogEntryPriority
from .exceptions import ProcessingError, ValidationError

logger = logging.getLogger(__name__)


class ValidationResult(str, Enum):
    """Result of log entry validation."""
    VALID = "valid"
    INVALID = "invalid"
    SUSPICIOUS = "suspicious"
    REQUIRES_SANITIZATION = "requires_sanitization"


@dataclass
class ProcessingResult:
    """Result of processing a log entry."""
    
    entry_id: str
    success: bool
    processing_time: float
    validation_result: ValidationResult
    sanitized: bool = False
    errors: List[str] = None
    warnings: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.metadata is None:
            self.metadata = {}


class LogEntryValidator:
    """
    Validator for log entries with security and content checks.
    
    Provides comprehensive validation including content sanitization,
    security checks, and format validation.
    """
    
    def __init__(self):
        """Initialize the validator with security patterns."""
        # Suspicious patterns that might indicate attacks or malicious content
        self.suspicious_patterns = [
            # SQL injection patterns
            r'(?i)(union\s+select|drop\s+table|delete\s+from|insert\s+into)',
            r'(?i)(or\s+1\s*=\s*1|and\s+1\s*=\s*1)',
            
            # XSS patterns
            r'(?i)(<script|javascript:|on\w+\s*=)',
            r'(?i)(alert\s*\(|confirm\s*\(|prompt\s*\()',
            
            # Path traversal
            r'\.\.[\\/]',
            r'(?i)(etc[\\/]passwd|windows[\\/]system32)',
            
            # Command injection
            r'(?i)(\|\s*\w+|\&\&\s*\w+|\;\s*\w+)',
            r'(?i)(curl\s+|wget\s+|nc\s+|netcat\s+)',
            
            # Encoded attacks
            r'%[0-9a-fA-F]{2}',  # URL encoding
            r'\\x[0-9a-fA-F]{2}',  # Hex encoding
        ]
        
        # Compile patterns for efficiency
        self.compiled_patterns = [re.compile(pattern) for pattern in self.suspicious_patterns]
        
        # Content size limits
        self.max_content_length = 1024 * 1024  # 1MB
        self.max_line_length = 32768  # 32KB per line
        
        # Character validation
        self.allowed_chars = set(range(32, 127))  # Printable ASCII
        self.allowed_chars.update([9, 10, 13])  # Tab, LF, CR
    
    def validate_entry(self, entry: LogEntry) -> ValidationResult:
        """
        Validate a log entry for security and content issues.
        
        Args:
            entry: LogEntry to validate
            
        Returns:
            ValidationResult indicating the validation outcome
        """
        try:
            # Basic content validation
            if not entry.content:
                return ValidationResult.INVALID
            
            # Size validation
            if len(entry.content) > self.max_content_length:
                logger.warning(f"Entry {entry.entry_id} exceeds maximum content length")
                return ValidationResult.INVALID
            
            # Line length validation
            lines = entry.content.split('\n')
            for i, line in enumerate(lines):
                if len(line) > self.max_line_length:
                    logger.warning(f"Entry {entry.entry_id} line {i+1} exceeds maximum length")
                    return ValidationResult.REQUIRES_SANITIZATION
            
            # Character validation
            if not self._validate_characters(entry.content):
                logger.warning(f"Entry {entry.entry_id} contains invalid characters")
                return ValidationResult.REQUIRES_SANITIZATION
            
            # Security pattern detection
            if self._detect_suspicious_patterns(entry.content):
                logger.warning(f"Entry {entry.entry_id} contains suspicious patterns")
                return ValidationResult.SUSPICIOUS
            
            # Source validation
            if not self._validate_source_info(entry):
                return ValidationResult.INVALID
            
            return ValidationResult.VALID
            
        except Exception as e:
            logger.error(f"Error validating entry {entry.entry_id}: {e}")
            return ValidationResult.INVALID
    
    def _validate_characters(self, content: str) -> bool:
        """Validate that content contains only allowed characters."""
        for char in content:
            if ord(char) not in self.allowed_chars:
                return False
        return True
    
    def _detect_suspicious_patterns(self, content: str) -> bool:
        """Detect suspicious patterns in content."""
        for pattern in self.compiled_patterns:
            if pattern.search(content):
                return True
        return False
    
    def _validate_source_info(self, entry: LogEntry) -> bool:
        """Validate source information."""
        # Check source name
        if not entry.source_name or len(entry.source_name) > 255:
            return False
        
        # Check source path
        if not entry.source_path or len(entry.source_path) > 1000:
            return False
        
        # Basic path validation
        if '..' in entry.source_path or entry.source_path.startswith('/'):
            # Allow absolute paths but be cautious
            pass
        
        return True


class LogEntrySanitizer:
    """
    Sanitizer for log entries to clean potentially harmful content.
    
    Provides content sanitization while preserving log integrity
    and maintaining audit trails.
    """
    
    def __init__(self):
        """Initialize the sanitizer."""
        # Characters to replace or remove
        self.replacement_char = '?'
        self.max_consecutive_replacements = 10
    
    def sanitize_entry(self, entry: LogEntry) -> Tuple[LogEntry, bool]:
        """
        Sanitize a log entry by cleaning potentially harmful content.
        
        Args:
            entry: LogEntry to sanitize
            
        Returns:
            Tuple of (sanitized_entry, was_modified)
        """
        original_content = entry.content
        sanitized_content = original_content
        was_modified = False
        
        try:
            # Remove or replace invalid characters
            sanitized_content, char_modified = self._sanitize_characters(sanitized_content)
            was_modified = was_modified or char_modified
            
            # Truncate overly long lines
            sanitized_content, length_modified = self._sanitize_line_lengths(sanitized_content)
            was_modified = was_modified or length_modified
            
            # Escape potentially dangerous sequences
            sanitized_content, escape_modified = self._escape_dangerous_sequences(sanitized_content)
            was_modified = was_modified or escape_modified
            
            if was_modified:
                # Create new entry with sanitized content
                sanitized_entry = LogEntry(
                    content=sanitized_content,
                    source_path=entry.source_path,
                    source_name=entry.source_name,
                    timestamp=entry.timestamp,
                    priority=entry.priority,
                    file_offset=entry.file_offset,
                    entry_id=entry.entry_id,
                    status=entry.status,
                    created_at=entry.created_at,
                    processing_started_at=entry.processing_started_at,
                    processing_completed_at=entry.processing_completed_at,
                    retry_count=entry.retry_count,
                    max_retries=entry.max_retries,
                    last_error=entry.last_error,
                    error_count=entry.error_count,
                    metadata=entry.metadata.copy()
                )
                
                # Add sanitization metadata
                sanitized_entry.metadata['sanitized'] = True
                sanitized_entry.metadata['original_length'] = len(original_content)
                sanitized_entry.metadata['sanitized_length'] = len(sanitized_content)
                sanitized_entry.metadata['sanitized_at'] = datetime.now(timezone.utc).isoformat()
                
                return sanitized_entry, True
            else:
                return entry, False
                
        except Exception as e:
            logger.error(f"Error sanitizing entry {entry.entry_id}: {e}")
            # Return original entry if sanitization fails
            return entry, False
    
    def _sanitize_characters(self, content: str) -> Tuple[str, bool]:
        """Sanitize invalid characters."""
        sanitized = []
        was_modified = False
        consecutive_replacements = 0
        
        allowed_chars = set(range(32, 127))  # Printable ASCII
        allowed_chars.update([9, 10, 13])  # Tab, LF, CR
        
        for char in content:
            if ord(char) in allowed_chars:
                sanitized.append(char)
                consecutive_replacements = 0
            else:
                if consecutive_replacements < self.max_consecutive_replacements:
                    sanitized.append(self.replacement_char)
                    consecutive_replacements += 1
                was_modified = True
        
        return ''.join(sanitized), was_modified
    
    def _sanitize_line_lengths(self, content: str) -> Tuple[str, bool]:
        """Sanitize overly long lines."""
        max_line_length = 32768
        lines = content.split('\n')
        sanitized_lines = []
        was_modified = False
        
        for line in lines:
            if len(line) > max_line_length:
                truncated_line = line[:max_line_length] + ' [TRUNCATED]'
                sanitized_lines.append(truncated_line)
                was_modified = True
            else:
                sanitized_lines.append(line)
        
        return '\n'.join(sanitized_lines), was_modified
    
    def _escape_dangerous_sequences(self, content: str) -> Tuple[str, bool]:
        """Escape potentially dangerous sequences."""
        # For now, just log detection - actual escaping can be added later
        dangerous_patterns = [
            r'(?i)(<script|javascript:)',
            r'(?i)(union\s+select|drop\s+table)',
        ]
        
        was_modified = False
        sanitized_content = content
        
        for pattern in dangerous_patterns:
            if re.search(pattern, content):
                logger.warning(f"Detected dangerous pattern in content: {pattern}")
                # Could implement actual escaping here if needed
        
        return sanitized_content, was_modified


class ProcessingStatusTracker:
    """
    Tracker for processing status and metrics.
    
    Provides comprehensive tracking of processing status,
    performance metrics, and error handling.
    """
    
    def __init__(self):
        """Initialize the status tracker."""
        self.processing_history: Dict[str, List[ProcessingResult]] = {}
        self.current_processing: Dict[str, datetime] = {}
        self.performance_metrics = {
            'total_processed': 0,
            'successful_processed': 0,
            'failed_processed': 0,
            'validation_failures': 0,
            'sanitization_count': 0,
            'avg_processing_time': 0.0,
            'processing_times': []
        }
    
    def start_processing(self, entry: LogEntry) -> None:
        """Mark entry as processing started."""
        self.current_processing[entry.entry_id] = datetime.now(timezone.utc)
        entry.mark_processing_started()
    
    def complete_processing(
        self, 
        entry: LogEntry, 
        result: ProcessingResult
    ) -> None:
        """Mark entry as processing completed."""
        entry.mark_processing_completed()
        
        # Remove from current processing
        if entry.entry_id in self.current_processing:
            del self.current_processing[entry.entry_id]
        
        # Add to history
        if entry.entry_id not in self.processing_history:
            self.processing_history[entry.entry_id] = []
        self.processing_history[entry.entry_id].append(result)
        
        # Update metrics
        self._update_metrics(result)
    
    def fail_processing(
        self, 
        entry: LogEntry, 
        error: str, 
        processing_time: float = 0.0
    ) -> None:
        """Mark entry as processing failed."""
        entry.mark_processing_failed(error)
        
        # Remove from current processing
        if entry.entry_id in self.current_processing:
            del self.current_processing[entry.entry_id]
        
        # Create failure result
        result = ProcessingResult(
            entry_id=entry.entry_id,
            success=False,
            processing_time=processing_time,
            validation_result=ValidationResult.INVALID,
            errors=[error]
        )
        
        # Add to history
        if entry.entry_id not in self.processing_history:
            self.processing_history[entry.entry_id] = []
        self.processing_history[entry.entry_id].append(result)
        
        # Update metrics
        self._update_metrics(result)
    
    def _update_metrics(self, result: ProcessingResult) -> None:
        """Update performance metrics."""
        self.performance_metrics['total_processed'] += 1
        
        if result.success:
            self.performance_metrics['successful_processed'] += 1
        else:
            self.performance_metrics['failed_processed'] += 1
        
        if result.validation_result == ValidationResult.INVALID:
            self.performance_metrics['validation_failures'] += 1
        
        if result.sanitized:
            self.performance_metrics['sanitization_count'] += 1
        
        # Update processing time metrics
        self.performance_metrics['processing_times'].append(result.processing_time)
        
        # Keep only recent processing times
        if len(self.performance_metrics['processing_times']) > 1000:
            self.performance_metrics['processing_times'] = \
                self.performance_metrics['processing_times'][-500:]
        
        # Calculate average processing time
        times = self.performance_metrics['processing_times']
        if times:
            self.performance_metrics['avg_processing_time'] = sum(times) / len(times)
    
    def get_processing_status(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Get processing status for an entry."""
        status = {}
        
        # Current processing status
        if entry_id in self.current_processing:
            start_time = self.current_processing[entry_id]
            status['currently_processing'] = True
            status['processing_started_at'] = start_time.isoformat()
            status['processing_duration'] = (datetime.now(timezone.utc) - start_time).total_seconds()
        else:
            status['currently_processing'] = False
        
        # Processing history
        if entry_id in self.processing_history:
            history = self.processing_history[entry_id]
            status['processing_attempts'] = len(history)
            status['last_result'] = history[-1].success if history else None
            status['total_errors'] = sum(len(result.errors) for result in history)
        else:
            status['processing_attempts'] = 0
            status['last_result'] = None
            status['total_errors'] = 0
        
        return status
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        metrics = self.performance_metrics.copy()
        
        # Calculate additional metrics
        if metrics['total_processed'] > 0:
            metrics['success_rate'] = metrics['successful_processed'] / metrics['total_processed']
            metrics['failure_rate'] = metrics['failed_processed'] / metrics['total_processed']
            metrics['validation_failure_rate'] = metrics['validation_failures'] / metrics['total_processed']
            metrics['sanitization_rate'] = metrics['sanitization_count'] / metrics['total_processed']
        else:
            metrics['success_rate'] = 0.0
            metrics['failure_rate'] = 0.0
            metrics['validation_failure_rate'] = 0.0
            metrics['sanitization_rate'] = 0.0
        
        # Processing time statistics
        times = metrics['processing_times']
        if times:
            metrics['min_processing_time'] = min(times)
            metrics['max_processing_time'] = max(times)
            metrics['median_processing_time'] = sorted(times)[len(times) // 2]
        else:
            metrics['min_processing_time'] = 0.0
            metrics['max_processing_time'] = 0.0
            metrics['median_processing_time'] = 0.0
        
        # Remove raw processing times from output
        del metrics['processing_times']
        
        return metrics
    
    def clear_old_history(self, max_age_hours: int = 24) -> int:
        """Clear old processing history."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        cleared_count = 0
        
        for entry_id, history in list(self.processing_history.items()):
            # Keep only recent results
            recent_results = []
            for result in history:
                # Assume results have a timestamp in metadata
                result_time = result.metadata.get('processed_at')
                if result_time:
                    try:
                        result_datetime = datetime.fromisoformat(result_time.replace('Z', '+00:00'))
                        if result_datetime >= cutoff_time:
                            recent_results.append(result)
                        else:
                            cleared_count += 1
                    except ValueError:
                        # Keep result if timestamp is invalid
                        recent_results.append(result)
                else:
                    # Keep result if no timestamp
                    recent_results.append(result)
            
            if recent_results:
                self.processing_history[entry_id] = recent_results
            else:
                del self.processing_history[entry_id]
        
        return cleared_count


# Global instances
validator = LogEntryValidator()
sanitizer = LogEntrySanitizer()
status_tracker = ProcessingStatusTracker()


def validate_log_entry(entry: LogEntry) -> ValidationResult:
    """Validate a log entry."""
    return validator.validate_entry(entry)


def sanitize_log_entry(entry: LogEntry) -> Tuple[LogEntry, bool]:
    """Sanitize a log entry."""
    return sanitizer.sanitize_entry(entry)


def process_log_entry(entry: LogEntry) -> ProcessingResult:
    """
    Process a single log entry through validation and sanitization.
    
    Args:
        entry: LogEntry to process
        
    Returns:
        ProcessingResult with processing outcome
    """
    start_time = datetime.now(timezone.utc)
    
    try:
        # Start processing tracking
        status_tracker.start_processing(entry)
        
        # Validate entry
        validation_result = validate_log_entry(entry)
        
        if validation_result == ValidationResult.INVALID:
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            result = ProcessingResult(
                entry_id=entry.entry_id,
                success=False,
                processing_time=processing_time,
                validation_result=validation_result,
                errors=["Entry failed validation"]
            )
            status_tracker.complete_processing(entry, result)
            return result
        
        # Sanitize if needed
        sanitized_entry = entry
        was_sanitized = False
        
        if validation_result in [ValidationResult.REQUIRES_SANITIZATION, ValidationResult.SUSPICIOUS]:
            sanitized_entry, was_sanitized = sanitize_log_entry(entry)
        
        # Calculate processing time
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        # Create success result
        result = ProcessingResult(
            entry_id=entry.entry_id,
            success=True,
            processing_time=processing_time,
            validation_result=validation_result,
            sanitized=was_sanitized,
            metadata={
                'processed_at': datetime.now(timezone.utc).isoformat(),
                'original_content_length': len(entry.content),
                'final_content_length': len(sanitized_entry.content)
            }
        )
        
        if validation_result == ValidationResult.SUSPICIOUS:
            result.warnings.append("Entry contains suspicious patterns")
        
        # Complete processing tracking
        status_tracker.complete_processing(sanitized_entry, result)
        
        return result
        
    except Exception as e:
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        error_msg = f"Error processing entry: {str(e)}"
        
        status_tracker.fail_processing(entry, error_msg, processing_time)
        
        return ProcessingResult(
            entry_id=entry.entry_id,
            success=False,
            processing_time=processing_time,
            validation_result=ValidationResult.INVALID,
            errors=[error_msg]
        )


def get_processing_metrics() -> Dict[str, Any]:
    """Get comprehensive processing metrics."""
    return status_tracker.get_performance_metrics()


def get_entry_processing_status(entry_id: str) -> Optional[Dict[str, Any]]:
    """Get processing status for a specific entry."""
    return status_tracker.get_processing_status(entry_id)