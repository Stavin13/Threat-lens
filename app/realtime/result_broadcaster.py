"""
Processing result broadcaster for real-time updates.

This module provides comprehensive broadcasting of processing results,
including success notifications, error alerts, and status updates.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from dataclasses import dataclass

from .ingestion_queue import LogEntry, ProcessingStatus
from .processing_pipeline import ProcessingResult, ValidationResult
from .websocket_server import EventUpdate, WebSocketManager
from .error_handler import ErrorHandler, ErrorRecord, ErrorSeverity
from .exceptions import BroadcastError

logger = logging.getLogger(__name__)


class ResultType(str, Enum):
    """Types of processing results."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    WARNING = "warning"
    INFO = "info"


class BroadcastPriority(int, Enum):
    """Priority levels for broadcasting."""
    CRITICAL = 10
    HIGH = 8
    MEDIUM = 5
    LOW = 3
    DEBUG = 1


@dataclass
class BroadcastResult:
    """Result of a broadcast operation."""
    
    success: bool
    message_id: str
    clients_reached: int
    clients_failed: int
    broadcast_time: float
    error: Optional[str] = None


class ProcessingResultBroadcaster:
    """
    Comprehensive broadcaster for processing results and status updates.
    
    Provides intelligent broadcasting with filtering, prioritization,
    and error handling for real-time processing updates.
    """
    
    def __init__(
        self,
        websocket_manager: WebSocketManager,
        error_handler: ErrorHandler
    ):
        """
        Initialize the result broadcaster.
        
        Args:
            websocket_manager: WebSocket manager for broadcasting
            error_handler: Error handler for error broadcasting
        """
        self.websocket_manager = websocket_manager
        self.error_handler = error_handler
        
        # Broadcasting statistics
        self.stats = {
            'total_broadcasts': 0,
            'successful_broadcasts': 0,
            'failed_broadcasts': 0,
            'broadcasts_by_type': {result_type.value: 0 for result_type in ResultType},
            'broadcasts_by_priority': {priority.name: 0 for priority in BroadcastPriority},
            'total_clients_reached': 0,
            'average_broadcast_time': 0.0,
            'broadcast_times': []
        }
        
        # Message filtering and throttling
        self.message_filters: Dict[str, Any] = {}
        self.throttle_rules: Dict[str, Dict[str, Any]] = {}
        self.last_broadcast_times: Dict[str, datetime] = {}
    
    async def broadcast_processing_result(
        self,
        entry: LogEntry,
        result: ProcessingResult,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> BroadcastResult:
        """
        Broadcast processing result with appropriate priority and formatting.
        
        Args:
            entry: LogEntry that was processed
            result: ProcessingResult from processing
            additional_data: Additional data to include in broadcast
            
        Returns:
            BroadcastResult with broadcast outcome
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Determine result type and priority
            result_type = self._determine_result_type(result)
            priority = self._determine_priority(result_type, result)
            
            # Check if broadcast should be throttled
            if self._should_throttle_broadcast(entry, result_type):
                logger.debug(f"Throttled broadcast for entry {entry.entry_id}")
                return BroadcastResult(
                    success=True,
                    message_id="throttled",
                    clients_reached=0,
                    clients_failed=0,
                    broadcast_time=0.0
                )
            
            # Create broadcast message
            message_data = self._create_result_message(entry, result, additional_data)
            
            # Create event update
            event_update = EventUpdate(
                event_type=f'processing_{result_type.value}',
                data=message_data,
                priority=priority.value
            )
            
            # Broadcast the event
            broadcast_start = datetime.now(timezone.utc)
            clients_reached = await self.websocket_manager.broadcast_event(event_update)
            broadcast_time = (datetime.now(timezone.utc) - broadcast_start).total_seconds()
            
            # Update statistics
            self._update_broadcast_statistics(result_type, priority, clients_reached, broadcast_time)
            
            # Update throttling timestamp
            self._update_throttle_timestamp(entry, result_type)
            
            logger.debug(f"Broadcast processing result for entry {entry.entry_id}: "
                        f"{result_type.value} to {clients_reached} clients")
            
            return BroadcastResult(
                success=True,
                message_id=event_update.data.get('message_id', 'unknown'),
                clients_reached=clients_reached,
                clients_failed=0,
                broadcast_time=broadcast_time
            )
            
        except Exception as e:
            broadcast_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            error_msg = f"Failed to broadcast processing result: {str(e)}"
            logger.error(error_msg)
            
            # Handle broadcast error
            await self.error_handler.handle_error(
                BroadcastError(error_msg),
                entry=entry,
                component="ProcessingResultBroadcaster",
                context={'result_type': result_type.value if 'result_type' in locals() else 'unknown'}
            )
            
            self.stats['failed_broadcasts'] += 1
            
            return BroadcastResult(
                success=False,
                message_id="error",
                clients_reached=0,
                clients_failed=1,
                broadcast_time=broadcast_time,
                error=error_msg
            )
    
    async def broadcast_processing_status(
        self,
        entry: LogEntry,
        status: ProcessingStatus,
        progress_info: Optional[Dict[str, Any]] = None
    ) -> BroadcastResult:
        """
        Broadcast processing status update.
        
        Args:
            entry: LogEntry being processed
            status: Current processing status
            progress_info: Additional progress information
            
        Returns:
            BroadcastResult with broadcast outcome
        """
        try:
            # Create status message
            message_data = {
                'entry_id': entry.entry_id,
                'source_name': entry.source_name,
                'source_path': entry.source_path,
                'status': status.value,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'progress': progress_info or {}
            }
            
            # Add entry metadata
            if hasattr(entry, 'metadata') and entry.metadata:
                message_data['metadata'] = entry.metadata
            
            # Determine priority based on status
            priority = BroadcastPriority.LOW
            if status == ProcessingStatus.FAILED:
                priority = BroadcastPriority.HIGH
            elif status == ProcessingStatus.PROCESSING:
                priority = BroadcastPriority.MEDIUM
            
            # Create and broadcast event
            event_update = EventUpdate(
                event_type='processing_status_update',
                data=message_data,
                priority=priority.value
            )
            
            clients_reached = await self.websocket_manager.broadcast_event(event_update)
            
            logger.debug(f"Broadcast status update for entry {entry.entry_id}: "
                        f"{status.value} to {clients_reached} clients")
            
            return BroadcastResult(
                success=True,
                message_id=entry.entry_id,
                clients_reached=clients_reached,
                clients_failed=0,
                broadcast_time=0.0
            )
            
        except Exception as e:
            error_msg = f"Failed to broadcast status update: {str(e)}"
            logger.error(error_msg)
            
            await self.error_handler.handle_error(
                BroadcastError(error_msg),
                entry=entry,
                component="ProcessingResultBroadcaster"
            )
            
            return BroadcastResult(
                success=False,
                message_id=entry.entry_id,
                clients_reached=0,
                clients_failed=1,
                broadcast_time=0.0,
                error=error_msg
            )
    
    async def broadcast_error_notification(
        self,
        error_record: ErrorRecord,
        include_details: bool = True
    ) -> BroadcastResult:
        """
        Broadcast error notification to clients.
        
        Args:
            error_record: ErrorRecord to broadcast
            include_details: Whether to include detailed error information
            
        Returns:
            BroadcastResult with broadcast outcome
        """
        try:
            # Create error message
            message_data = {
                'error_id': error_record.error_id,
                'severity': error_record.severity.value,
                'category': error_record.category.value,
                'message': error_record.message,
                'timestamp': error_record.timestamp.isoformat(),
                'component': error_record.source_component,
                'recovery_attempted': error_record.recovery_attempted,
                'recovery_successful': error_record.recovery_successful
            }
            
            # Add entry information if available
            if error_record.entry_id:
                message_data['entry_id'] = error_record.entry_id
            
            # Add detailed information if requested
            if include_details:
                message_data['context'] = error_record.context
                message_data['recovery_action'] = error_record.recovery_action.value if error_record.recovery_action else None
            
            # Determine priority based on severity
            priority = BroadcastPriority.MEDIUM
            if error_record.severity == ErrorSeverity.CRITICAL:
                priority = BroadcastPriority.CRITICAL
            elif error_record.severity == ErrorSeverity.HIGH:
                priority = BroadcastPriority.HIGH
            
            # Create and broadcast event
            event_update = EventUpdate(
                event_type='error_notification',
                data=message_data,
                priority=priority.value
            )
            
            clients_reached = await self.websocket_manager.broadcast_event(event_update)
            
            logger.info(f"Broadcast error notification {error_record.error_id}: "
                       f"{error_record.severity.value} to {clients_reached} clients")
            
            return BroadcastResult(
                success=True,
                message_id=error_record.error_id,
                clients_reached=clients_reached,
                clients_failed=0,
                broadcast_time=0.0
            )
            
        except Exception as e:
            error_msg = f"Failed to broadcast error notification: {str(e)}"
            logger.error(error_msg)
            
            return BroadcastResult(
                success=False,
                message_id=error_record.error_id,
                clients_reached=0,
                clients_failed=1,
                broadcast_time=0.0,
                error=error_msg
            )
    
    async def broadcast_system_status(
        self,
        status_data: Dict[str, Any],
        priority: BroadcastPriority = BroadcastPriority.LOW
    ) -> BroadcastResult:
        """
        Broadcast system status information.
        
        Args:
            status_data: System status data to broadcast
            priority: Broadcast priority
            
        Returns:
            BroadcastResult with broadcast outcome
        """
        try:
            # Add timestamp
            message_data = {
                **status_data,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message_type': 'system_status'
            }
            
            # Create and broadcast event
            event_update = EventUpdate(
                event_type='system_status_update',
                data=message_data,
                priority=priority.value
            )
            
            clients_reached = await self.websocket_manager.broadcast_event(event_update)
            
            logger.debug(f"Broadcast system status to {clients_reached} clients")
            
            return BroadcastResult(
                success=True,
                message_id="system_status",
                clients_reached=clients_reached,
                clients_failed=0,
                broadcast_time=0.0
            )
            
        except Exception as e:
            error_msg = f"Failed to broadcast system status: {str(e)}"
            logger.error(error_msg)
            
            return BroadcastResult(
                success=False,
                message_id="system_status",
                clients_reached=0,
                clients_failed=1,
                broadcast_time=0.0,
                error=error_msg
            )
    
    def _determine_result_type(self, result: ProcessingResult) -> ResultType:
        """Determine result type from processing result."""
        if not result.success:
            return ResultType.FAILURE
        elif result.errors:
            return ResultType.PARTIAL_SUCCESS
        elif result.warnings:
            return ResultType.WARNING
        else:
            return ResultType.SUCCESS
    
    def _determine_priority(self, result_type: ResultType, result: ProcessingResult) -> BroadcastPriority:
        """Determine broadcast priority."""
        if result_type == ResultType.FAILURE:
            return BroadcastPriority.HIGH
        elif result_type == ResultType.PARTIAL_SUCCESS:
            return BroadcastPriority.MEDIUM
        elif result_type == ResultType.WARNING:
            return BroadcastPriority.MEDIUM
        elif result.validation_result == ValidationResult.SUSPICIOUS:
            return BroadcastPriority.MEDIUM
        else:
            return BroadcastPriority.LOW
    
    def _should_throttle_broadcast(self, entry: LogEntry, result_type: ResultType) -> bool:
        """Check if broadcast should be throttled."""
        # Don't throttle failures or critical results
        if result_type in [ResultType.FAILURE, ResultType.PARTIAL_SUCCESS]:
            return False
        
        # Check throttle rules
        throttle_key = f"{entry.source_name}_{result_type.value}"
        throttle_rule = self.throttle_rules.get(throttle_key)
        
        if not throttle_rule:
            return False
        
        last_broadcast = self.last_broadcast_times.get(throttle_key)
        if not last_broadcast:
            return False
        
        time_since_last = (datetime.now(timezone.utc) - last_broadcast).total_seconds()
        return time_since_last < throttle_rule.get('min_interval', 0)
    
    def _update_throttle_timestamp(self, entry: LogEntry, result_type: ResultType) -> None:
        """Update throttle timestamp."""
        throttle_key = f"{entry.source_name}_{result_type.value}"
        self.last_broadcast_times[throttle_key] = datetime.now(timezone.utc)
    
    def _create_result_message(
        self,
        entry: LogEntry,
        result: ProcessingResult,
        additional_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create broadcast message from processing result."""
        import uuid
        
        message_data = {
            'message_id': str(uuid.uuid4()),
            'entry_id': entry.entry_id,
            'source_name': entry.source_name,
            'source_path': entry.source_path,
            'processing_time': result.processing_time,
            'validation_result': result.validation_result.value,
            'sanitized': result.sanitized,
            'success': result.success,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Add error information if present
        if result.errors:
            message_data['errors'] = result.errors
            message_data['error_count'] = len(result.errors)
        
        # Add warning information if present
        if result.warnings:
            message_data['warnings'] = result.warnings
            message_data['warning_count'] = len(result.warnings)
        
        # Add metadata if present
        if result.metadata:
            message_data['metadata'] = result.metadata
        
        # Add entry metadata
        if hasattr(entry, 'metadata') and entry.metadata:
            message_data['entry_metadata'] = entry.metadata
        
        # Add additional data
        if additional_data:
            message_data.update(additional_data)
        
        return message_data
    
    def _update_broadcast_statistics(
        self,
        result_type: ResultType,
        priority: BroadcastPriority,
        clients_reached: int,
        broadcast_time: float
    ) -> None:
        """Update broadcast statistics."""
        self.stats['total_broadcasts'] += 1
        self.stats['successful_broadcasts'] += 1
        self.stats['broadcasts_by_type'][result_type.value] += 1
        self.stats['broadcasts_by_priority'][priority.name] += 1
        self.stats['total_clients_reached'] += clients_reached
        
        # Update broadcast time statistics
        self.stats['broadcast_times'].append(broadcast_time)
        if len(self.stats['broadcast_times']) > 1000:
            self.stats['broadcast_times'] = self.stats['broadcast_times'][-500:]
        
        if self.stats['broadcast_times']:
            self.stats['average_broadcast_time'] = sum(self.stats['broadcast_times']) / len(self.stats['broadcast_times'])
    
    def add_throttle_rule(
        self,
        source_name: str,
        result_type: ResultType,
        min_interval_seconds: float
    ) -> None:
        """Add throttling rule for specific source and result type."""
        throttle_key = f"{source_name}_{result_type.value}"
        self.throttle_rules[throttle_key] = {
            'min_interval': min_interval_seconds,
            'source_name': source_name,
            'result_type': result_type.value
        }
        logger.info(f"Added throttle rule for {throttle_key}: {min_interval_seconds}s")
    
    def remove_throttle_rule(self, source_name: str, result_type: ResultType) -> None:
        """Remove throttling rule."""
        throttle_key = f"{source_name}_{result_type.value}"
        if throttle_key in self.throttle_rules:
            del self.throttle_rules[throttle_key]
            logger.info(f"Removed throttle rule for {throttle_key}")
    
    def get_broadcast_statistics(self) -> Dict[str, Any]:
        """Get comprehensive broadcast statistics."""
        stats = self.stats.copy()
        
        # Calculate rates
        if stats['total_broadcasts'] > 0:
            stats['success_rate'] = stats['successful_broadcasts'] / stats['total_broadcasts']
            stats['failure_rate'] = stats['failed_broadcasts'] / stats['total_broadcasts']
            stats['average_clients_per_broadcast'] = stats['total_clients_reached'] / stats['total_broadcasts']
        else:
            stats['success_rate'] = 0.0
            stats['failure_rate'] = 0.0
            stats['average_clients_per_broadcast'] = 0.0
        
        # Add throttle information
        stats['active_throttle_rules'] = len(self.throttle_rules)
        stats['throttle_rules'] = list(self.throttle_rules.keys())
        
        # Remove raw broadcast times
        del stats['broadcast_times']
        
        return stats
    
    def reset_statistics(self) -> None:
        """Reset broadcast statistics."""
        self.stats = {
            'total_broadcasts': 0,
            'successful_broadcasts': 0,
            'failed_broadcasts': 0,
            'broadcasts_by_type': {result_type.value: 0 for result_type in ResultType},
            'broadcasts_by_priority': {priority.name: 0 for priority in BroadcastPriority},
            'total_clients_reached': 0,
            'average_broadcast_time': 0.0,
            'broadcast_times': []
        }
        logger.info("Reset broadcast statistics")


# Convenience functions
async def broadcast_processing_result(
    broadcaster: ProcessingResultBroadcaster,
    entry: LogEntry,
    result: ProcessingResult,
    additional_data: Optional[Dict[str, Any]] = None
) -> BroadcastResult:
    """Broadcast processing result."""
    return await broadcaster.broadcast_processing_result(entry, result, additional_data)


async def broadcast_error_notification(
    broadcaster: ProcessingResultBroadcaster,
    error_record: ErrorRecord
) -> BroadcastResult:
    """Broadcast error notification."""
    return await broadcaster.broadcast_error_notification(error_record)