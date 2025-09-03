"""
Comprehensive error handling and recovery system for real-time processing.

This module provides advanced error handling, retry logic, and recovery
mechanisms for the real-time log processing pipeline.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque

from .ingestion_queue import LogEntry, ProcessingStatus
from .processing_pipeline import ProcessingResult, ValidationResult
from .websocket_server import EventUpdate, WebSocketManager
from .exceptions import ProcessingError, ValidationError, BroadcastError

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ErrorCategory(str, Enum):
    """Error categories for classification."""
    PARSING_ERROR = "parsing_error"
    VALIDATION_ERROR = "validation_error"
    DATABASE_ERROR = "database_error"
    WEBSOCKET_ERROR = "websocket_error"
    ANALYSIS_ERROR = "analysis_error"
    SYSTEM_ERROR = "system_error"
    NETWORK_ERROR = "network_error"
    CONFIGURATION_ERROR = "configuration_error"


class RecoveryAction(str, Enum):
    """Recovery actions for different error types."""
    RETRY = "retry"
    SKIP = "skip"
    QUARANTINE = "quarantine"
    FALLBACK = "fallback"
    ESCALATE = "escalate"
    IGNORE = "ignore"


@dataclass
class ErrorRecord:
    """Record of an error occurrence."""
    
    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    entry_id: Optional[str] = None
    source_component: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_action: Optional[RecoveryAction] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False
    retry_count: int = 0
    max_retries: int = 3
    
    def can_retry(self) -> bool:
        """Check if error can be retried."""
        return self.retry_count < self.max_retries and self.recovery_action == RecoveryAction.RETRY


@dataclass
class RecoveryStrategy:
    """Strategy for recovering from specific error types."""
    
    error_category: ErrorCategory
    severity_threshold: ErrorSeverity
    recovery_action: RecoveryAction
    max_retries: int = 3
    retry_delay: float = 1.0
    escalation_threshold: int = 5
    custom_handler: Optional[Callable] = None


class ErrorHandler:
    """
    Comprehensive error handler with recovery mechanisms.
    
    Provides centralized error handling, classification, recovery,
    and notification for the real-time processing system.
    """
    
    def __init__(self, websocket_manager: Optional[WebSocketManager] = None):
        """
        Initialize the error handler.
        
        Args:
            websocket_manager: WebSocket manager for error broadcasting
        """
        self.websocket_manager = websocket_manager
        
        # Error tracking
        self.error_history: deque = deque(maxlen=10000)  # Keep last 10k errors
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.error_patterns: Dict[str, List[ErrorRecord]] = defaultdict(list)
        
        # Recovery strategies
        self.recovery_strategies: Dict[ErrorCategory, RecoveryStrategy] = {}
        self._setup_default_strategies()
        
        # Error callbacks
        self.error_callbacks: List[Callable[[ErrorRecord], None]] = []
        
        # Statistics
        self.stats = {
            'total_errors': 0,
            'errors_by_severity': {severity.value: 0 for severity in ErrorSeverity},
            'errors_by_category': {category.value: 0 for category in ErrorCategory},
            'recovery_attempts': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'escalated_errors': 0
        }
    
    def _setup_default_strategies(self) -> None:
        """Set up default recovery strategies."""
        self.recovery_strategies = {
            ErrorCategory.PARSING_ERROR: RecoveryStrategy(
                error_category=ErrorCategory.PARSING_ERROR,
                severity_threshold=ErrorSeverity.MEDIUM,
                recovery_action=RecoveryAction.FALLBACK,
                max_retries=2,
                retry_delay=0.5
            ),
            ErrorCategory.VALIDATION_ERROR: RecoveryStrategy(
                error_category=ErrorCategory.VALIDATION_ERROR,
                severity_threshold=ErrorSeverity.HIGH,
                recovery_action=RecoveryAction.QUARANTINE,
                max_retries=1
            ),
            ErrorCategory.DATABASE_ERROR: RecoveryStrategy(
                error_category=ErrorCategory.DATABASE_ERROR,
                severity_threshold=ErrorSeverity.HIGH,
                recovery_action=RecoveryAction.RETRY,
                max_retries=3,
                retry_delay=2.0
            ),
            ErrorCategory.WEBSOCKET_ERROR: RecoveryStrategy(
                error_category=ErrorCategory.WEBSOCKET_ERROR,
                severity_threshold=ErrorSeverity.MEDIUM,
                recovery_action=RecoveryAction.RETRY,
                max_retries=2,
                retry_delay=1.0
            ),
            ErrorCategory.ANALYSIS_ERROR: RecoveryStrategy(
                error_category=ErrorCategory.ANALYSIS_ERROR,
                severity_threshold=ErrorSeverity.MEDIUM,
                recovery_action=RecoveryAction.SKIP,
                max_retries=1
            ),
            ErrorCategory.SYSTEM_ERROR: RecoveryStrategy(
                error_category=ErrorCategory.SYSTEM_ERROR,
                severity_threshold=ErrorSeverity.CRITICAL,
                recovery_action=RecoveryAction.ESCALATE,
                max_retries=0
            )
        }
    
    async def handle_error(
        self,
        error: Exception,
        entry: Optional[LogEntry] = None,
        component: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ErrorRecord:
        """
        Handle an error with classification and recovery.
        
        Args:
            error: Exception that occurred
            entry: LogEntry being processed (if applicable)
            component: Component where error occurred
            context: Additional context information
            
        Returns:
            ErrorRecord with error details and recovery information
        """
        # Create error record
        error_record = self._create_error_record(error, entry, component, context)
        
        # Add to history and update statistics
        self.error_history.append(error_record)
        self._update_error_statistics(error_record)
        
        # Determine recovery strategy
        strategy = self.recovery_strategies.get(
            error_record.category,
            self._get_default_strategy(error_record)
        )
        
        error_record.recovery_action = strategy.recovery_action
        error_record.max_retries = strategy.max_retries
        
        # Attempt recovery
        if strategy.recovery_action != RecoveryAction.IGNORE:
            await self._attempt_recovery(error_record, strategy)
        
        # Broadcast error if severe enough
        if self._should_broadcast_error(error_record):
            await self._broadcast_error(error_record)
        
        # Call error callbacks
        for callback in self.error_callbacks:
            try:
                callback(error_record)
            except Exception as callback_error:
                logger.error(f"Error in error callback: {callback_error}")
        
        logger.error(f"Handled error {error_record.error_id}: {error_record.message}")
        return error_record
    
    def _create_error_record(
        self,
        error: Exception,
        entry: Optional[LogEntry],
        component: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> ErrorRecord:
        """Create an error record from an exception."""
        import uuid
        import traceback
        
        # Classify error
        category = self._classify_error(error)
        severity = self._determine_severity(error, category)
        
        # Create record
        error_record = ErrorRecord(
            error_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            severity=severity,
            category=category,
            message=str(error),
            entry_id=entry.entry_id if entry else None,
            source_component=component,
            stack_trace=traceback.format_exc(),
            context=context or {}
        )
        
        # Add entry context if available
        if entry:
            error_record.context.update({
                'source_name': entry.source_name,
                'source_path': entry.source_path,
                'content_length': len(entry.content),
                'entry_priority': entry.priority.name,
                'retry_count': entry.retry_count
            })
        
        return error_record
    
    def _classify_error(self, error: Exception) -> ErrorCategory:
        """Classify error by type and content."""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Classification by exception type
        if isinstance(error, ValidationError):
            return ErrorCategory.VALIDATION_ERROR
        elif isinstance(error, ProcessingError):
            return ErrorCategory.PARSING_ERROR
        elif isinstance(error, BroadcastError):
            return ErrorCategory.WEBSOCKET_ERROR
        elif 'database' in error_message or 'sql' in error_message:
            return ErrorCategory.DATABASE_ERROR
        elif 'websocket' in error_message or 'connection' in error_message:
            return ErrorCategory.WEBSOCKET_ERROR
        elif 'analysis' in error_message or 'ai' in error_message:
            return ErrorCategory.ANALYSIS_ERROR
        elif 'network' in error_message or 'timeout' in error_message:
            return ErrorCategory.NETWORK_ERROR
        elif 'config' in error_message or 'setting' in error_message:
            return ErrorCategory.CONFIGURATION_ERROR
        else:
            return ErrorCategory.SYSTEM_ERROR
    
    def _determine_severity(self, error: Exception, category: ErrorCategory) -> ErrorSeverity:
        """Determine error severity based on type and category."""
        error_message = str(error).lower()
        
        # Critical errors
        if category == ErrorCategory.SYSTEM_ERROR:
            return ErrorSeverity.CRITICAL
        elif 'critical' in error_message or 'fatal' in error_message:
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        elif category in [ErrorCategory.DATABASE_ERROR, ErrorCategory.CONFIGURATION_ERROR]:
            return ErrorSeverity.HIGH
        elif 'security' in error_message or 'breach' in error_message:
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        elif category in [ErrorCategory.PARSING_ERROR, ErrorCategory.ANALYSIS_ERROR]:
            return ErrorSeverity.MEDIUM
        elif 'warning' in error_message:
            return ErrorSeverity.MEDIUM
        
        # Low severity errors
        elif category in [ErrorCategory.WEBSOCKET_ERROR, ErrorCategory.NETWORK_ERROR]:
            return ErrorSeverity.LOW
        
        # Default to medium
        else:
            return ErrorSeverity.MEDIUM
    
    def _get_default_strategy(self, error_record: ErrorRecord) -> RecoveryStrategy:
        """Get default recovery strategy for unclassified errors."""
        return RecoveryStrategy(
            error_category=error_record.category,
            severity_threshold=ErrorSeverity.MEDIUM,
            recovery_action=RecoveryAction.RETRY,
            max_retries=2,
            retry_delay=1.0
        )
    
    async def _attempt_recovery(self, error_record: ErrorRecord, strategy: RecoveryStrategy) -> None:
        """Attempt recovery based on strategy."""
        self.stats['recovery_attempts'] += 1
        error_record.recovery_attempted = True
        
        try:
            if strategy.recovery_action == RecoveryAction.RETRY:
                # Retry will be handled by the calling component
                error_record.recovery_successful = True
                self.stats['successful_recoveries'] += 1
                
            elif strategy.recovery_action == RecoveryAction.SKIP:
                # Mark as handled by skipping
                error_record.recovery_successful = True
                self.stats['successful_recoveries'] += 1
                logger.info(f"Skipped processing for error {error_record.error_id}")
                
            elif strategy.recovery_action == RecoveryAction.QUARANTINE:
                # Quarantine the problematic entry
                await self._quarantine_entry(error_record)
                error_record.recovery_successful = True
                self.stats['successful_recoveries'] += 1
                
            elif strategy.recovery_action == RecoveryAction.FALLBACK:
                # Use fallback processing
                await self._apply_fallback(error_record)
                error_record.recovery_successful = True
                self.stats['successful_recoveries'] += 1
                
            elif strategy.recovery_action == RecoveryAction.ESCALATE:
                # Escalate to higher level handling
                await self._escalate_error(error_record)
                self.stats['escalated_errors'] += 1
                
        except Exception as recovery_error:
            logger.error(f"Recovery failed for error {error_record.error_id}: {recovery_error}")
            error_record.recovery_successful = False
            self.stats['failed_recoveries'] += 1
    
    async def _quarantine_entry(self, error_record: ErrorRecord) -> None:
        """Quarantine a problematic entry."""
        if error_record.entry_id:
            # In a real implementation, this would move the entry to a quarantine queue
            logger.warning(f"Quarantined entry {error_record.entry_id} due to error {error_record.error_id}")
            
            # Broadcast quarantine notification
            if self.websocket_manager:
                await self.websocket_manager.broadcast_event(EventUpdate(
                    event_type='entry_quarantined',
                    data={
                        'entry_id': error_record.entry_id,
                        'error_id': error_record.error_id,
                        'reason': error_record.message,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    },
                    priority=7
                ))
    
    async def _apply_fallback(self, error_record: ErrorRecord) -> None:
        """Apply fallback processing for an error."""
        logger.info(f"Applying fallback processing for error {error_record.error_id}")
        
        # Broadcast fallback notification
        if self.websocket_manager:
            await self.websocket_manager.broadcast_event(EventUpdate(
                event_type='fallback_processing',
                data={
                    'entry_id': error_record.entry_id,
                    'error_id': error_record.error_id,
                    'fallback_reason': error_record.message,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                priority=6
            ))
    
    async def _escalate_error(self, error_record: ErrorRecord) -> None:
        """Escalate error to higher level handling."""
        logger.critical(f"Escalating error {error_record.error_id}: {error_record.message}")
        
        # Broadcast escalation notification
        if self.websocket_manager:
            await self.websocket_manager.broadcast_event(EventUpdate(
                event_type='error_escalated',
                data={
                    'error_id': error_record.error_id,
                    'severity': error_record.severity.value,
                    'category': error_record.category.value,
                    'message': error_record.message,
                    'component': error_record.source_component,
                    'timestamp': error_record.timestamp.isoformat()
                },
                priority=10
            ))
    
    def _should_broadcast_error(self, error_record: ErrorRecord) -> bool:
        """Determine if error should be broadcast."""
        # Broadcast high and critical severity errors
        if error_record.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            return True
        
        # Broadcast if error pattern is detected
        pattern_key = f"{error_record.category.value}_{error_record.message[:50]}"
        if self.error_counts[pattern_key] >= 5:  # 5 similar errors
            return True
        
        return False
    
    async def _broadcast_error(self, error_record: ErrorRecord) -> None:
        """Broadcast error notification."""
        if not self.websocket_manager:
            return
        
        try:
            await self.websocket_manager.broadcast_event(EventUpdate(
                event_type='processing_error',
                data={
                    'error_id': error_record.error_id,
                    'severity': error_record.severity.value,
                    'category': error_record.category.value,
                    'message': error_record.message,
                    'entry_id': error_record.entry_id,
                    'component': error_record.source_component,
                    'recovery_action': error_record.recovery_action.value if error_record.recovery_action else None,
                    'timestamp': error_record.timestamp.isoformat()
                },
                priority=8 if error_record.severity == ErrorSeverity.CRITICAL else 6
            ))
        except Exception as broadcast_error:
            logger.error(f"Failed to broadcast error {error_record.error_id}: {broadcast_error}")
    
    def _update_error_statistics(self, error_record: ErrorRecord) -> None:
        """Update error statistics."""
        self.stats['total_errors'] += 1
        self.stats['errors_by_severity'][error_record.severity.value] += 1
        self.stats['errors_by_category'][error_record.category.value] += 1
        
        # Update error pattern tracking
        pattern_key = f"{error_record.category.value}_{error_record.message[:50]}"
        self.error_counts[pattern_key] += 1
        self.error_patterns[pattern_key].append(error_record)
        
        # Keep only recent patterns
        if len(self.error_patterns[pattern_key]) > 10:
            self.error_patterns[pattern_key] = self.error_patterns[pattern_key][-5:]
    
    def add_error_callback(self, callback: Callable[[ErrorRecord], None]) -> None:
        """Add callback to be called for each error."""
        self.error_callbacks.append(callback)
    
    def set_recovery_strategy(self, category: ErrorCategory, strategy: RecoveryStrategy) -> None:
        """Set custom recovery strategy for error category."""
        self.recovery_strategies[category] = strategy
        logger.info(f"Set recovery strategy for {category.value}: {strategy.recovery_action.value}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics."""
        stats = self.stats.copy()
        
        # Add pattern analysis
        stats['error_patterns'] = {
            pattern: len(errors) for pattern, errors in self.error_patterns.items()
        }
        
        # Add recent errors
        recent_errors = [
            {
                'error_id': error.error_id,
                'timestamp': error.timestamp.isoformat(),
                'severity': error.severity.value,
                'category': error.category.value,
                'message': error.message[:100],
                'recovery_successful': error.recovery_successful
            }
            for error in list(self.error_history)[-10:]  # Last 10 errors
        ]
        stats['recent_errors'] = recent_errors
        
        # Calculate rates
        if stats['total_errors'] > 0:
            stats['recovery_success_rate'] = stats['successful_recoveries'] / stats['recovery_attempts'] if stats['recovery_attempts'] > 0 else 0
            stats['critical_error_rate'] = stats['errors_by_severity']['critical'] / stats['total_errors']
        else:
            stats['recovery_success_rate'] = 0
            stats['critical_error_rate'] = 0
        
        return stats
    
    def get_error_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent error history."""
        return [
            {
                'error_id': error.error_id,
                'timestamp': error.timestamp.isoformat(),
                'severity': error.severity.value,
                'category': error.category.value,
                'message': error.message,
                'entry_id': error.entry_id,
                'component': error.source_component,
                'recovery_action': error.recovery_action.value if error.recovery_action else None,
                'recovery_successful': error.recovery_successful,
                'retry_count': error.retry_count
            }
            for error in list(self.error_history)[-limit:]
        ]
    
    def clear_error_history(self) -> None:
        """Clear error history and reset statistics."""
        self.error_history.clear()
        self.error_counts.clear()
        self.error_patterns.clear()
        self.stats = {
            'total_errors': 0,
            'errors_by_severity': {severity.value: 0 for severity in ErrorSeverity},
            'errors_by_category': {category.value: 0 for category in ErrorCategory},
            'recovery_attempts': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'escalated_errors': 0
        }
        logger.info("Cleared error history and reset statistics")
    
    async def start_automated_recovery(self) -> None:
        """Start automated error recovery monitoring."""
        logger.info("Starting automated error recovery monitoring")
        asyncio.create_task(self._automated_recovery_loop())
    
    async def _automated_recovery_loop(self) -> None:
        """Automated recovery monitoring loop."""
        while True:
            try:
                await self._check_error_patterns()
                await self._perform_automated_recovery()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in automated recovery loop: {e}")
                await asyncio.sleep(60)
    
    async def _check_error_patterns(self) -> None:
        """Check for error patterns that require automated intervention."""
        current_time = datetime.now(timezone.utc)
        
        # Check for error spikes
        recent_errors = [
            error for error in self.error_history
            if (current_time - error.timestamp).total_seconds() < 300  # Last 5 minutes
        ]
        
        if len(recent_errors) > 20:  # More than 20 errors in 5 minutes
            logger.warning(f"Error spike detected: {len(recent_errors)} errors in 5 minutes")
            await self._handle_error_spike(recent_errors)
        
        # Check for critical error patterns
        critical_errors = [
            error for error in recent_errors
            if error.severity == ErrorSeverity.CRITICAL
        ]
        
        if len(critical_errors) > 3:  # More than 3 critical errors in 5 minutes
            logger.critical(f"Critical error pattern detected: {len(critical_errors)} critical errors")
            await self._handle_critical_error_pattern(critical_errors)
    
    async def _handle_error_spike(self, recent_errors: List[ErrorRecord]) -> None:
        """Handle error spike with automated recovery."""
        # Analyze error categories
        category_counts = {}
        for error in recent_errors:
            category_counts[error.category] = category_counts.get(error.category, 0) + 1
        
        # Find dominant error category
        dominant_category = max(category_counts.items(), key=lambda x: x[1])[0]
        
        logger.warning(f"Error spike dominated by {dominant_category.value}: {category_counts[dominant_category]} errors")
        
        # Apply category-specific recovery
        if dominant_category == ErrorCategory.DATABASE_ERROR:
            await self._recover_database_issues()
        elif dominant_category == ErrorCategory.WEBSOCKET_ERROR:
            await self._recover_websocket_issues()
        elif dominant_category == ErrorCategory.PARSING_ERROR:
            await self._recover_parsing_issues()
        
        # Broadcast alert
        if self.websocket_manager:
            await self.websocket_manager.broadcast_event(EventUpdate(
                event_type='error_spike_detected',
                data={
                    'error_count': len(recent_errors),
                    'dominant_category': dominant_category.value,
                    'recovery_initiated': True,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                priority=9
            ))
    
    async def _handle_critical_error_pattern(self, critical_errors: List[ErrorRecord]) -> None:
        """Handle critical error pattern."""
        logger.critical("Initiating emergency recovery procedures")
        
        # Broadcast critical alert
        if self.websocket_manager:
            await self.websocket_manager.broadcast_event(EventUpdate(
                event_type='critical_error_pattern',
                data={
                    'critical_error_count': len(critical_errors),
                    'emergency_recovery': True,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'action_required': 'Immediate administrator intervention required'
                },
                priority=10
            ))
    
    async def _recover_database_issues(self) -> None:
        """Attempt to recover from database issues."""
        logger.info("Attempting database issue recovery")
        
        # In a real implementation, this would:
        # - Check database connection
        # - Restart connection pool
        # - Switch to backup database
        # - Implement circuit breaker
        
        # For now, just log the attempt
        logger.info("Database recovery procedures initiated")
    
    async def _recover_websocket_issues(self) -> None:
        """Attempt to recover from WebSocket issues."""
        logger.info("Attempting WebSocket issue recovery")
        
        # In a real implementation, this would:
        # - Restart WebSocket server
        # - Clear connection pool
        # - Reset message queues
        # - Notify clients of reconnection
        
        logger.info("WebSocket recovery procedures initiated")
    
    async def _recover_parsing_issues(self) -> None:
        """Attempt to recover from parsing issues."""
        logger.info("Attempting parsing issue recovery")
        
        # In a real implementation, this would:
        # - Reset format detection cache
        # - Reload parsing rules
        # - Switch to fallback parsing mode
        # - Clear problematic entries from queue
        
        logger.info("Parsing recovery procedures initiated")
    
    async def _perform_automated_recovery(self) -> None:
        """Perform automated recovery for failed components."""
        # Check for components with high failure rates
        component_failures = {}
        
        for error in list(self.error_history)[-100:]:  # Last 100 errors
            if error.source_component:
                component = error.source_component
                if component not in component_failures:
                    component_failures[component] = {'total': 0, 'failed_recovery': 0}
                
                component_failures[component]['total'] += 1
                if not error.recovery_successful:
                    component_failures[component]['failed_recovery'] += 1
        
        # Identify components needing intervention
        for component, failures in component_failures.items():
            if failures['total'] > 10 and failures['failed_recovery'] / failures['total'] > 0.5:
                logger.warning(f"Component {component} has high failure rate: {failures['failed_recovery']}/{failures['total']}")
                await self._attempt_component_recovery(component)
    
    async def _attempt_component_recovery(self, component: str) -> None:
        """Attempt to recover a failing component."""
        logger.info(f"Attempting recovery for component: {component}")
        
        # Component-specific recovery logic would go here
        # For now, just log the attempt and broadcast notification
        
        if self.websocket_manager:
            await self.websocket_manager.broadcast_event(EventUpdate(
                event_type='component_recovery_attempt',
                data={
                    'component': component,
                    'recovery_initiated': True,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                priority=7
            ))
    
    def get_recovery_recommendations(self) -> List[str]:
        """Get automated recovery recommendations based on error patterns."""
        recommendations = []
        
        # Analyze recent error patterns
        recent_errors = list(self.error_history)[-50:]  # Last 50 errors
        
        if not recent_errors:
            return ['No recent errors - system appears stable']
        
        # Category analysis
        category_counts = {}
        for error in recent_errors:
            category_counts[error.category] = category_counts.get(error.category, 0) + 1
        
        # Generate recommendations based on dominant categories
        for category, count in category_counts.items():
            if count > len(recent_errors) * 0.3:  # More than 30% of errors
                if category == ErrorCategory.DATABASE_ERROR:
                    recommendations.append('High database error rate - check database connectivity and performance')
                elif category == ErrorCategory.PARSING_ERROR:
                    recommendations.append('High parsing error rate - review log formats and parsing rules')
                elif category == ErrorCategory.WEBSOCKET_ERROR:
                    recommendations.append('High WebSocket error rate - check network stability and client connections')
                elif category == ErrorCategory.ANALYSIS_ERROR:
                    recommendations.append('High analysis error rate - check AI service availability and performance')
        
        # Recovery success analysis
        failed_recoveries = [error for error in recent_errors if not error.recovery_successful]
        if len(failed_recoveries) > len(recent_errors) * 0.4:  # More than 40% failed recovery
            recommendations.append('High recovery failure rate - review recovery strategies and system stability')
        
        # Severity analysis
        critical_errors = [error for error in recent_errors if error.severity == ErrorSeverity.CRITICAL]
        if len(critical_errors) > 0:
            recommendations.append('Critical errors detected - immediate investigation and resolution required')
        
        return recommendations if recommendations else ['System error patterns appear normal']


# Global error handler instance
error_handler = ErrorHandler()


async def handle_processing_error(
    error: Exception,
    entry: Optional[LogEntry] = None,
    component: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> ErrorRecord:
    """
    Handle a processing error with recovery.
    
    Args:
        error: Exception that occurred
        entry: LogEntry being processed
        component: Component where error occurred
        context: Additional context
        
    Returns:
        ErrorRecord with error details
    """
    return await error_handler.handle_error(error, entry, component, context)


def set_websocket_manager_for_errors(websocket_manager: WebSocketManager) -> None:
    """Set WebSocket manager for error broadcasting."""
    error_handler.websocket_manager = websocket_manager


def get_error_statistics() -> Dict[str, Any]:
    """Get error handling statistics."""
    return error_handler.get_error_statistics()