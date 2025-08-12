"""
Enhanced background processor with real-time capabilities.

This module extends the existing BackgroundTaskManager to support
real-time processing of log entries from the ingestion queue.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_database_session
from app.models import RawLog, Event, AIAnalysis as AIAnalysisModel
from app.parser import parse_log_entries, ParsingError
from app.analyzer import analyze_event, AnalysisError
from app.schemas import ParsedEvent, EventCategory, EventResponse, AIAnalysis as AIAnalysisSchema
from app.background_tasks import BackgroundTaskManager

from .format_detector import LogFormatDetector, FormatPattern, parse_with_auto_detection
from .error_handler import ErrorHandler, handle_processing_error
from .result_broadcaster import ProcessingResultBroadcaster, ResultType
from .notifications import NotificationManager

from .ingestion_queue import LogEntry, RealtimeIngestionQueue, ProcessingStatus
from .processing_pipeline import process_log_entry, ProcessingResult, ValidationResult
from .base import RealtimeComponent, HealthMonitorMixin
from .exceptions import ProcessingError

logger = logging.getLogger(__name__)


class RealtimeProcessingMetrics:
    """Metrics collection for real-time processing."""
    
    def __init__(self):
        """Initialize metrics."""
        self.reset_metrics()
    
    def reset_metrics(self):
        """Reset all metrics."""
        self.metrics = {
            # Processing counts
            'entries_processed': 0,
            'entries_parsed': 0,
            'entries_analyzed': 0,
            'entries_failed': 0,
            'entries_retried': 0,
            
            # Validation metrics
            'validation_passed': 0,
            'validation_failed': 0,
            'entries_sanitized': 0,
            'suspicious_entries': 0,
            
            # Performance metrics
            'total_processing_time': 0.0,
            'avg_processing_time': 0.0,
            'min_processing_time': float('inf'),
            'max_processing_time': 0.0,
            'processing_times': [],
            
            # Queue metrics
            'batches_processed': 0,
            'avg_batch_size': 0.0,
            'batch_processing_times': [],
            
            # Error tracking
            'parsing_errors': 0,
            'analysis_errors': 0,
            'database_errors': 0,
            'validation_errors': 0,
            
            # Notification metrics
            'notifications_triggered': 0,
            'notifications_sent': 0,
            'notifications_failed': 0,
            'notification_rules_matched': 0,
            'high_severity_events': 0,
            
            # Timestamps
            'last_processed': None,
            'last_notification_sent': None,
            'metrics_start_time': datetime.now(timezone.utc)
        }
    
    def record_entry_processed(self, processing_time: float, success: bool):
        """Record processing of an entry."""
        self.metrics['entries_processed'] += 1
        
        if success:
            self.metrics['total_processing_time'] += processing_time
            self.metrics['processing_times'].append(processing_time)
            
            # Update min/max
            self.metrics['min_processing_time'] = min(
                self.metrics['min_processing_time'], processing_time
            )
            self.metrics['max_processing_time'] = max(
                self.metrics['max_processing_time'], processing_time
            )
            
            # Calculate average
            if self.metrics['entries_processed'] > 0:
                self.metrics['avg_processing_time'] = (
                    self.metrics['total_processing_time'] / self.metrics['entries_processed']
                )
        else:
            self.metrics['entries_failed'] += 1
        
        self.metrics['last_processed'] = datetime.now(timezone.utc)
        
        # Keep only recent processing times
        if len(self.metrics['processing_times']) > 1000:
            self.metrics['processing_times'] = self.metrics['processing_times'][-500:]
    
    def record_batch_processed(self, batch_size: int, processing_time: float):
        """Record processing of a batch."""
        self.metrics['batches_processed'] += 1
        self.metrics['batch_processing_times'].append(processing_time)
        
        # Calculate average batch size
        total_entries = self.metrics['entries_processed']
        if self.metrics['batches_processed'] > 0:
            self.metrics['avg_batch_size'] = total_entries / self.metrics['batches_processed']
        
        # Keep only recent batch times
        if len(self.metrics['batch_processing_times']) > 100:
            self.metrics['batch_processing_times'] = self.metrics['batch_processing_times'][-50:]
    
    def record_validation_result(self, result: ValidationResult, sanitized: bool):
        """Record validation result."""
        if result == ValidationResult.VALID:
            self.metrics['validation_passed'] += 1
        elif result == ValidationResult.INVALID:
            self.metrics['validation_failed'] += 1
            self.metrics['validation_errors'] += 1
        elif result == ValidationResult.SUSPICIOUS:
            self.metrics['suspicious_entries'] += 1
        
        if sanitized:
            self.metrics['entries_sanitized'] += 1
    
    def record_parsing_result(self, success: bool, events_count: int = 0):
        """Record parsing result."""
        if success:
            self.metrics['entries_parsed'] += 1
            # Note: events_count would be used if we track individual events
        else:
            self.metrics['parsing_errors'] += 1
    
    def record_analysis_result(self, success: bool):
        """Record analysis result."""
        if success:
            self.metrics['entries_analyzed'] += 1
        else:
            self.metrics['analysis_errors'] += 1
    
    def record_database_error(self):
        """Record database error."""
        self.metrics['database_errors'] += 1
    
    def record_retry(self):
        """Record retry attempt."""
        self.metrics['entries_retried'] += 1
    
    def record_notification_triggered(self, rules_matched: int, high_severity: bool):
        """Record notification trigger event."""
        self.metrics['notifications_triggered'] += 1
        self.metrics['notification_rules_matched'] += rules_matched
        if high_severity:
            self.metrics['high_severity_events'] += 1
    
    def record_notification_result(self, success: bool):
        """Record notification delivery result."""
        if success:
            self.metrics['notifications_sent'] += 1
            self.metrics['last_notification_sent'] = datetime.now(timezone.utc)
        else:
            self.metrics['notifications_failed'] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        metrics = self.metrics.copy()
        
        # Calculate rates
        uptime = (datetime.now(timezone.utc) - self.metrics['metrics_start_time']).total_seconds()
        if uptime > 0:
            metrics['processing_rate'] = self.metrics['entries_processed'] / uptime
            metrics['success_rate'] = (
                (self.metrics['entries_processed'] - self.metrics['entries_failed']) / 
                max(self.metrics['entries_processed'], 1)
            )
        else:
            metrics['processing_rate'] = 0.0
            metrics['success_rate'] = 0.0
        
        # Add uptime
        metrics['uptime_seconds'] = uptime
        
        # Remove raw processing times from output
        del metrics['processing_times']
        del metrics['batch_processing_times']
        
        # Format timestamps
        if metrics['last_processed']:
            metrics['last_processed'] = metrics['last_processed'].isoformat()
        if metrics['last_notification_sent']:
            metrics['last_notification_sent'] = metrics['last_notification_sent'].isoformat()
        metrics['metrics_start_time'] = metrics['metrics_start_time'].isoformat()
        
        return metrics


class EnhancedBackgroundProcessor(RealtimeComponent, HealthMonitorMixin):
    """
    Enhanced background processor with real-time capabilities.
    
    Extends the existing background processing system to handle
    real-time log entries from the ingestion queue.
    """
    
    def __init__(
        self,
        ingestion_queue: RealtimeIngestionQueue,
        websocket_manager: Optional[Any] = None,
        notification_manager: Optional[NotificationManager] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize the enhanced processor.
        
        Args:
            ingestion_queue: RealtimeIngestionQueue instance
            websocket_manager: WebSocket manager for real-time updates (optional)
            notification_manager: NotificationManager for sending alerts (optional)
            max_retries: Maximum retry attempts for failed processing
            retry_delay: Base delay between retries in seconds
        """
        RealtimeComponent.__init__(self, "EnhancedBackgroundProcessor")
        HealthMonitorMixin.__init__(self)
        
        self.ingestion_queue = ingestion_queue
        self.websocket_manager = websocket_manager
        self.notification_manager = notification_manager
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Use existing background task manager for compatibility
        self.background_manager = BackgroundTaskManager(max_retries, retry_delay)
        
        # Real-time processing metrics
        self.metrics = RealtimeProcessingMetrics()
        
        # Format detection and adaptive parsing
        self.format_detector = LogFormatDetector()
        self.learned_patterns: Dict[str, FormatPattern] = {}
        
        # Error handling and result broadcasting
        self.error_handler = ErrorHandler(websocket_manager)
        self.result_broadcaster = ProcessingResultBroadcaster(
            websocket_manager, self.error_handler
        ) if websocket_manager else None
        
        # Processing control
        self._processing_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        
        # Callbacks for processing events
        self._processing_callbacks: List[Callable[[LogEntry, ProcessingResult], None]] = []
    
    async def _start_impl(self) -> None:
        """Start the enhanced processor."""
        logger.info("Starting enhanced background processor")
        
        # Set up queue batch processor
        self.ingestion_queue.set_batch_processor(self._process_batch)
        self.ingestion_queue.set_error_handler(self._handle_processing_error)
        
        # Start metrics collection
        self._metrics_task = asyncio.create_task(self._update_metrics_continuously())
        
        # Initialize health metrics
        self.update_health_metric("processing_rate", 0.0)
        self.update_health_metric("success_rate", 0.0)
        self.update_health_metric("queue_integration", True)
    
    async def _stop_impl(self) -> None:
        """Stop the enhanced processor."""
        logger.info("Stopping enhanced background processor")
        
        # Cancel metrics task
        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass
    
    def add_processing_callback(self, callback: Callable[[LogEntry, ProcessingResult], None]):
        """Add a callback to be called after processing each entry."""
        self._processing_callbacks.append(callback)
    
    def get_notification_metrics(self) -> Dict[str, Any]:
        """Get comprehensive notification metrics.
        
        Returns:
            Dictionary with notification metrics and statistics
        """
        processor_metrics = {
            'notifications_triggered': self.metrics.metrics['notifications_triggered'],
            'notifications_sent': self.metrics.metrics['notifications_sent'],
            'notifications_failed': self.metrics.metrics['notifications_failed'],
            'notification_rules_matched': self.metrics.metrics['notification_rules_matched'],
            'high_severity_events': self.metrics.metrics['high_severity_events'],
            'last_notification_sent': self.metrics.metrics['last_notification_sent']
        }
        
        # Get notification manager statistics if available
        if self.notification_manager:
            manager_stats = self.notification_manager.get_notification_stats()
            processor_metrics.update({
                'manager_stats': manager_stats,
                'active_rules': len([r for r in self.notification_manager.rules if r.enabled]),
                'active_channels': len([c for c in self.notification_manager.channels.values() if c.enabled]),
                'configured_rules': self.notification_manager.get_rules_summary(),
                'channel_status': self.notification_manager.get_channel_status()
            })
        
        return processor_metrics
    
    async def _process_batch(self, batch: List[LogEntry]) -> None:
        """
        Process a batch of log entries.
        
        Args:
            batch: List of LogEntry objects to process
        """
        batch_start_time = time.time()
        logger.debug(f"Processing batch of {len(batch)} entries")
        
        # Process each entry in the batch
        for entry in batch:
            await self._process_single_entry(entry)
        
        # Record batch metrics
        batch_time = time.time() - batch_start_time
        self.metrics.record_batch_processed(len(batch), batch_time)
        
        logger.debug(f"Completed batch of {len(batch)} entries in {batch_time:.2f}s")
    
    async def _process_single_entry(self, entry: LogEntry) -> None:
        """
        Process a single log entry through the complete pipeline with comprehensive error handling.
        
        Args:
            entry: LogEntry to process
        """
        start_time = time.time()
        processing_result = None
        
        try:
            # Broadcast processing started status
            if self.result_broadcaster:
                await self.result_broadcaster.broadcast_processing_status(
                    entry, ProcessingStatus.PROCESSING
                )
            
            # Step 1: Validate and sanitize the entry
            processing_result = process_log_entry(entry)
            
            # Record validation metrics
            self.metrics.record_validation_result(
                processing_result.validation_result,
                processing_result.sanitized
            )
            
            if not processing_result.success:
                self.metrics.record_entry_processed(
                    processing_result.processing_time, False
                )
                
                # Handle validation failure
                await self.error_handler.handle_error(
                    ValidationError(f"Entry validation failed: {processing_result.errors}"),
                    entry=entry,
                    component="EnhancedBackgroundProcessor",
                    context={'validation_result': processing_result.validation_result.value}
                )
                
                # Broadcast validation failure
                if self.result_broadcaster:
                    await self.result_broadcaster.broadcast_processing_result(
                        entry, processing_result
                    )
                
                logger.warning(f"Entry {entry.entry_id} failed validation: {processing_result.errors}")
                return
            
            # Step 2: Parse the log content
            try:
                parsed_events = await self._parse_log_content(entry)
                if not parsed_events:
                    self.metrics.record_parsing_result(False)
                    self.metrics.record_entry_processed(time.time() - start_time, False)
                    
                    # Handle parsing failure
                    await self.error_handler.handle_error(
                        ProcessingError("No events could be parsed from log content"),
                        entry=entry,
                        component="EnhancedBackgroundProcessor",
                        context={'content_length': len(entry.content)}
                    )
                    
                    return
                
                self.metrics.record_parsing_result(True, len(parsed_events))
                
            except Exception as parse_error:
                self.metrics.record_parsing_result(False)
                
                # Handle parsing error with recovery
                error_record = await self.error_handler.handle_error(
                    parse_error,
                    entry=entry,
                    component="EnhancedBackgroundProcessor",
                    context={'parsing_stage': 'log_content_parsing'}
                )
                
                # Try to create fallback processing result
                processing_result = ProcessingResult(
                    entry_id=entry.entry_id,
                    success=False,
                    processing_time=time.time() - start_time,
                    validation_result=ValidationResult.INVALID,
                    errors=[f"Parsing failed: {str(parse_error)}"]
                )
                
                if self.result_broadcaster:
                    await self.result_broadcaster.broadcast_processing_result(
                        entry, processing_result
                    )
                
                return
            
            # Step 3: Store and analyze events
            try:
                analysis_success = await self._store_and_analyze_events(entry, parsed_events)
                self.metrics.record_analysis_result(analysis_success)
                
                if not analysis_success:
                    # Handle analysis failure
                    await self.error_handler.handle_error(
                        ProcessingError("Failed to store and analyze events"),
                        entry=entry,
                        component="EnhancedBackgroundProcessor",
                        context={'events_count': len(parsed_events)}
                    )
                
            except Exception as analysis_error:
                self.metrics.record_analysis_result(False)
                
                # Handle analysis error
                await self.error_handler.handle_error(
                    analysis_error,
                    entry=entry,
                    component="EnhancedBackgroundProcessor",
                    context={'analysis_stage': 'store_and_analyze', 'events_count': len(parsed_events)}
                )
                
                analysis_success = False
            
            # Create final processing result
            processing_time = time.time() - start_time
            final_result = ProcessingResult(
                entry_id=entry.entry_id,
                success=analysis_success,
                processing_time=processing_time,
                validation_result=processing_result.validation_result,
                sanitized=processing_result.sanitized,
                metadata={
                    'events_parsed': len(parsed_events),
                    'parsing_method': self._get_parsing_method_used(entry, entry.source_name in self.learned_patterns),
                    'processed_at': datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Record processing metrics
            self.metrics.record_entry_processed(processing_time, analysis_success)
            
            # Broadcast final result
            if self.result_broadcaster:
                await self.result_broadcaster.broadcast_processing_result(
                    entry, final_result, {
                        'events_parsed': len(parsed_events),
                        'events_analyzed': len(parsed_events) if analysis_success else 0
                    }
                )
            
            # Call processing callbacks
            for callback in self._processing_callbacks:
                try:
                    callback(entry, final_result)
                except Exception as callback_error:
                    await self.error_handler.handle_error(
                        callback_error,
                        entry=entry,
                        component="ProcessingCallback",
                        context={'callback_name': getattr(callback, '__name__', 'unknown')}
                    )
            
            logger.debug(f"Successfully processed entry {entry.entry_id} in {processing_time:.2f}s")
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.metrics.record_entry_processed(processing_time, False)
            
            # Handle unexpected error
            await self.error_handler.handle_error(
                e,
                entry=entry,
                component="EnhancedBackgroundProcessor",
                context={'processing_stage': 'unexpected_error'}
            )
            
            # Create failure result if not already created
            if not processing_result:
                processing_result = ProcessingResult(
                    entry_id=entry.entry_id,
                    success=False,
                    processing_time=processing_time,
                    validation_result=ValidationResult.INVALID,
                    errors=[f"Unexpected processing error: {str(e)}"]
                )
            
            # Broadcast failure result
            if self.result_broadcaster:
                await self.result_broadcaster.broadcast_processing_result(
                    entry, processing_result
                )
            
            logger.error(f"Error processing entry {entry.entry_id}: {e}")
            raise
    
    async def _parse_log_content(self, entry: LogEntry) -> List[ParsedEvent]:
        """
        Parse log content into structured events with automatic format detection.
        
        Args:
            entry: LogEntry to parse
            
        Returns:
            List of ParsedEvent objects
        """
        try:
            # Create a temporary raw log ID for parsing
            temp_raw_log_id = f"realtime_{entry.entry_id}"
            
            # Try to use learned pattern for this source first
            source_pattern_key = f"source_{entry.source_name}"
            learned_pattern = self.learned_patterns.get(source_pattern_key)
            
            parsed_events = []
            
            if learned_pattern:
                # Use learned pattern
                logger.debug(f"Using learned pattern for source {entry.source_name}")
                try:
                    parsed_events = self.format_detector.parse_with_detected_format(
                        entry.content, temp_raw_log_id, learned_pattern
                    )
                except Exception as e:
                    logger.warning(f"Learned pattern failed for {entry.source_name}: {e}")
                    parsed_events = []
            
            if not parsed_events:
                # Try automatic format detection
                logger.debug(f"Attempting automatic format detection for entry {entry.entry_id}")
                try:
                    parsed_events = parse_with_auto_detection(entry.content, temp_raw_log_id)
                    
                    # Learn from successful detection
                    if parsed_events:
                        detected_patterns = self.format_detector.get_detected_patterns()
                        if detected_patterns:
                            # Store the best pattern for this source
                            best_pattern = max(detected_patterns, key=lambda p: (p.confidence.value, p.frequency))
                            self.learned_patterns[source_pattern_key] = best_pattern
                            logger.info(f"Learned new pattern '{best_pattern.name}' for source {entry.source_name}")
                
                except Exception as e:
                    logger.warning(f"Auto-detection failed for entry {entry.entry_id}: {e}")
                    parsed_events = []
            
            if not parsed_events:
                # Fallback to existing parser
                logger.debug(f"Falling back to existing parser for entry {entry.entry_id}")
                try:
                    parsed_events = parse_log_entries(entry.content, temp_raw_log_id)
                except ParsingError as e:
                    logger.error(f"Fallback parsing failed for entry {entry.entry_id}: {e}")
                    # Create a raw unparsed event as last resort
                    parsed_events = self._create_unparsed_event(entry, temp_raw_log_id)
            
            # Update source information for real-time context
            for event in parsed_events:
                event.source = entry.source_name
                # Add real-time metadata
                if not hasattr(event, 'metadata'):
                    event.metadata = {}
                event.metadata.update({
                    'realtime_processed': True,
                    'source_path': entry.source_path,
                    'file_offset': entry.file_offset,
                    'entry_priority': entry.priority.name,
                    'parsing_method': self._get_parsing_method_used(entry, learned_pattern is not None)
                })
            
            return parsed_events
            
        except Exception as e:
            logger.error(f"Unexpected error parsing entry {entry.entry_id}: {e}")
            # Return unparsed event as fallback
            return self._create_unparsed_event(entry, f"realtime_{entry.entry_id}")
    
    def _create_unparsed_event(self, entry: LogEntry, raw_log_id: str) -> List[ParsedEvent]:
        """
        Create an unparsed event as a fallback when all parsing methods fail.
        
        Args:
            entry: LogEntry that couldn't be parsed
            raw_log_id: Raw log ID
            
        Returns:
            List containing a single unparsed ParsedEvent
        """
        try:
            import uuid
            
            unparsed_event = ParsedEvent(
                id=str(uuid.uuid4()),
                raw_log_id=raw_log_id,
                timestamp=entry.timestamp,
                source=entry.source_name,
                message=entry.content[:1000] + '...' if len(entry.content) > 1000 else entry.content,
                category=EventCategory.UNKNOWN,
                parsed_at=datetime.now(timezone.utc)
            )
            
            # Add metadata indicating this is unparsed
            if not hasattr(unparsed_event, 'metadata'):
                unparsed_event.metadata = {}
            unparsed_event.metadata.update({
                'unparsed': True,
                'parsing_failed': True,
                'original_content_length': len(entry.content)
            })
            
            logger.warning(f"Created unparsed event for entry {entry.entry_id}")
            return [unparsed_event]
            
        except Exception as e:
            logger.error(f"Failed to create unparsed event: {e}")
            return []
    
    def _get_parsing_method_used(self, entry: LogEntry, used_learned_pattern: bool) -> str:
        """
        Determine which parsing method was used.
        
        Args:
            entry: LogEntry that was parsed
            used_learned_pattern: Whether a learned pattern was used
            
        Returns:
            String describing the parsing method
        """
        if used_learned_pattern:
            return "learned_pattern"
        elif entry.source_name in self.learned_patterns:
            return "auto_detection"
        else:
            return "fallback_parser"
    
    async def _store_and_analyze_events(
        self, 
        entry: LogEntry, 
        parsed_events: List[ParsedEvent]
    ) -> bool:
        """
        Store parsed events and run AI analysis.
        
        Args:
            entry: Original LogEntry
            parsed_events: List of parsed events
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_database_session() as db:
                events_with_analysis = []
                
                for event in parsed_events:
                    # Store event in database
                    db_event = Event(
                        id=event.id,
                        raw_log_id=f"realtime_{entry.entry_id}",  # Use entry ID as raw log reference
                        timestamp=event.timestamp,
                        source=event.source,
                        message=event.message,
                        category=event.category.value,
                        parsed_at=event.parsed_at or datetime.now(timezone.utc)
                    )
                    db.add(db_event)
                    
                    # Run AI analysis
                    ai_analysis = None
                    try:
                        ai_analysis = analyze_event(event)
                        
                        # Store AI analysis
                        db_analysis = AIAnalysisModel(
                            id=ai_analysis.id,
                            event_id=ai_analysis.event_id,
                            severity_score=ai_analysis.severity_score,
                            explanation=ai_analysis.explanation,
                            recommendations=str(ai_analysis.recommendations),
                            analyzed_at=ai_analysis.analyzed_at or datetime.now(timezone.utc)
                        )
                        db.add(db_analysis)
                        
                        # Store for notification processing
                        events_with_analysis.append((event, ai_analysis))
                        
                    except AnalysisError as e:
                        logger.warning(f"Failed to analyze event {event.id}: {e}")
                        # Store event without analysis for potential notification
                        events_with_analysis.append((event, None))
                        continue
                
                # Commit all changes
                db.commit()
                
                # Process notifications after successful database commit
                await self._process_notifications_for_events(events_with_analysis)
                
                return True
                
        except SQLAlchemyError as e:
            self.metrics.record_database_error()
            logger.error(f"Database error storing events for entry {entry.entry_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error storing events for entry {entry.entry_id}: {e}")
            return False
    
    async def _process_notifications_for_events(
        self, 
        events_with_analysis: List[tuple[ParsedEvent, Optional[AIAnalysisSchema]]]
    ) -> None:
        """
        Process notifications for events based on AI analysis results.
        
        Args:
            events_with_analysis: List of tuples containing (event, ai_analysis)
        """
        if not self.notification_manager:
            logger.debug("No notification manager configured, skipping notifications")
            return
        
        for event, ai_analysis in events_with_analysis:
            try:
                # Convert ParsedEvent to EventResponse for notification system
                event_response = EventResponse(
                    id=event.id,
                    raw_log_id=f"realtime_{event.id}",
                    timestamp=event.timestamp,
                    source=event.source,
                    message=event.message,
                    category=event.category.value,
                    parsed_at=event.parsed_at or datetime.now(timezone.utc)
                )
                
                # Check if this event should trigger notifications
                should_notify = self._should_trigger_notification(event_response, ai_analysis)
                
                if should_notify:
                    # Record notification trigger metrics
                    high_severity = ai_analysis and ai_analysis.severity_score >= 7
                    self.metrics.record_notification_triggered(1, high_severity)
                    
                    # Send notifications with retry logic
                    notification_results = await self.notification_manager.send_notification_with_retry(
                        event_response, ai_analysis, max_retries=2, retry_delay=0.5
                    )
                    
                    # Record notification results
                    successful_notifications = sum(1 for success in notification_results.values() if success)
                    failed_notifications = len(notification_results) - successful_notifications
                    
                    for _ in range(successful_notifications):
                        self.metrics.record_notification_result(True)
                    for _ in range(failed_notifications):
                        self.metrics.record_notification_result(False)
                    
                    logger.info(
                        f"Sent notifications for event {event.id}: "
                        f"{successful_notifications} successful, {failed_notifications} failed"
                    )
                    
                    # Broadcast notification status via WebSocket
                    if self.websocket_manager:
                        await self._broadcast_notification_status(
                            event_response, ai_analysis, notification_results
                        )
                
            except Exception as e:
                logger.error(f"Error processing notifications for event {event.id}: {e}")
                self.metrics.record_notification_result(False)
    
    def _should_trigger_notification(
        self, 
        event: EventResponse, 
        ai_analysis: Optional[AIAnalysisSchema]
    ) -> bool:
        """
        Determine if an event should trigger notifications based on configured rules.
        
        Args:
            event: Event to evaluate
            ai_analysis: AI analysis results (optional)
            
        Returns:
            True if notifications should be triggered
        """
        if not self.notification_manager or not self.notification_manager.rules:
            return False
        
        # Find matching rules using the notification manager's logic
        matching_rules = self.notification_manager._find_matching_rules(event, ai_analysis)
        
        # Check if any enabled rules match
        enabled_matching_rules = [rule for rule in matching_rules if rule.enabled]
        
        if enabled_matching_rules:
            logger.debug(
                f"Event {event.id} matches {len(enabled_matching_rules)} notification rules"
            )
            return True
        
        return False
    
    async def _broadcast_notification_status(
        self,
        event: EventResponse,
        ai_analysis: Optional[AIAnalysisSchema],
        notification_results: Dict[str, bool]
    ) -> None:
        """
        Broadcast notification status via WebSocket.
        
        Args:
            event: Event that triggered notifications
            ai_analysis: AI analysis results
            notification_results: Results of notification attempts
        """
        try:
            # Create notification status message
            status_data = {
                'type': 'notification_status',
                'event_id': event.id,
                'event_source': event.source,
                'event_category': event.category,
                'severity_score': ai_analysis.severity_score if ai_analysis else None,
                'notification_results': notification_results,
                'successful_channels': [
                    channel for channel, success in notification_results.items() if success
                ],
                'failed_channels': [
                    channel for channel, success in notification_results.items() if not success
                ],
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Broadcast to all connected clients
            await self.websocket_manager.broadcast_event(status_data)
            
        except Exception as e:
            logger.error(f"Error broadcasting notification status: {e}")
    
    async def _broadcast_processing_update(
        self, 
        entry: LogEntry, 
        parsed_events: List[ParsedEvent]
    ) -> None:
        """
        Broadcast processing update via WebSocket.
        
        Args:
            entry: Processed LogEntry
            parsed_events: List of parsed events
        """
        if not self.websocket_manager:
            return
        
        try:
            # Create update message
            update_data = {
                'type': 'realtime_processing_complete',
                'entry_id': entry.entry_id,
                'source_name': entry.source_name,
                'source_path': entry.source_path,
                'timestamp': entry.timestamp.isoformat(),
                'events_count': len(parsed_events),
                'events': [
                    {
                        'id': event.id,
                        'timestamp': event.timestamp.isoformat(),
                        'source': event.source,
                        'category': event.category.value,
                        'message': event.message[:200] + '...' if len(event.message) > 200 else event.message
                    }
                    for event in parsed_events[:5]  # Limit to first 5 events
                ],
                'processed_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Broadcast to all connected clients
            await self.websocket_manager.broadcast_event(update_data)
            
        except Exception as e:
            logger.error(f"Error broadcasting processing update: {e}")
    
    def _handle_processing_error(self, entry: LogEntry, error: Exception) -> None:
        """
        Handle processing errors from the queue.
        
        Args:
            entry: LogEntry that failed processing
            error: Exception that occurred
        """
        logger.error(f"Processing error for entry {entry.entry_id}: {error}")
        
        # Record retry if applicable
        if entry.can_retry():
            self.metrics.record_retry()
        
        # Could implement additional error handling here
        # such as alerting, special logging, etc.
    
    async def _update_metrics_continuously(self) -> None:
        """Continuously update health metrics."""
        while not self._shutdown_event.is_set():
            try:
                # Get current metrics
                current_metrics = self.metrics.get_metrics()
                
                # Update health metrics
                self.update_health_metric("processing_rate", current_metrics['processing_rate'])
                self.update_health_metric("success_rate", current_metrics['success_rate'])
                self.update_health_metric("entries_processed", current_metrics['entries_processed'])
                self.update_health_metric("entries_failed", current_metrics['entries_failed'])
                self.update_health_metric("avg_processing_time", current_metrics['avg_processing_time'])
                
                await asyncio.sleep(30.0)  # Update every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._handle_error(e, "during metrics update")
                await asyncio.sleep(30.0)
    
    async def process_realtime_entry(self, entry: LogEntry) -> Dict[str, Any]:
        """
        Process a single real-time entry (for direct processing).
        
        Args:
            entry: LogEntry to process
            
        Returns:
            Dictionary with processing results
        """
        try:
            await self._process_single_entry(entry)
            return {
                'success': True,
                'entry_id': entry.entry_id,
                'message': 'Entry processed successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'entry_id': entry.entry_id,
                'error': str(e)
            }
    
    def get_processing_metrics(self) -> Dict[str, Any]:
        """Get comprehensive processing metrics."""
        metrics = self.metrics.get_metrics()
        
        # Add queue metrics if available
        if hasattr(self.ingestion_queue, 'get_queue_stats'):
            try:
                queue_stats = asyncio.create_task(self.ingestion_queue.get_queue_stats())
                # Note: In a real implementation, you'd want to handle this async call properly
                metrics['queue_stats'] = "Available via async call"
            except Exception:
                metrics['queue_stats'] = "Unavailable"
        
        # Add background manager stats
        try:
            bg_stats = self.background_manager.get_stats()
            metrics['background_manager'] = bg_stats
        except Exception:
            metrics['background_manager'] = "Unavailable"
        
        return metrics
    
    def reset_metrics(self) -> None:
        """Reset processing metrics."""
        self.metrics.reset_metrics()
        logger.info("Processing metrics reset")
    
    def get_learned_patterns(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about learned format patterns.
        
        Returns:
            Dictionary with learned pattern information
        """
        patterns_info = {}
        
        for source_key, pattern in self.learned_patterns.items():
            source_name = source_key.replace("source_", "")
            patterns_info[source_name] = {
                'pattern_name': pattern.name,
                'confidence': pattern.confidence.value,
                'frequency': pattern.frequency,
                'timestamp_format': pattern.timestamp_format,
                'delimiter': pattern.delimiter,
                'field_count': len(pattern.field_mapping),
                'sample_lines': pattern.sample_lines[:2]  # First 2 sample lines
            }
        
        return patterns_info
    
    def clear_learned_patterns(self, source_name: Optional[str] = None) -> None:
        """
        Clear learned patterns for a specific source or all sources.
        
        Args:
            source_name: Specific source to clear (None for all)
        """
        if source_name:
            source_key = f"source_{source_name}"
            if source_key in self.learned_patterns:
                del self.learned_patterns[source_key]
                logger.info(f"Cleared learned pattern for source: {source_name}")
        else:
            self.learned_patterns.clear()
            self.format_detector.clear_detected_patterns()
            logger.info("Cleared all learned patterns")
    
    def get_format_detection_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive format detection statistics.
        
        Returns:
            Dictionary with format detection statistics
        """
        detector_stats = self.format_detector.get_detection_statistics()
        
        return {
            'learned_patterns_count': len(self.learned_patterns),
            'learned_sources': list(self.learned_patterns.keys()),
            'detector_statistics': detector_stats,
            'patterns_by_source': self.get_learned_patterns()
        }
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive error handling statistics.
        
        Returns:
            Dictionary with error statistics
        """
        return self.error_handler.get_error_statistics()
    
    def get_broadcast_statistics(self) -> Dict[str, Any]:
        """
        Get broadcast statistics.
        
        Returns:
            Dictionary with broadcast statistics
        """
        if self.result_broadcaster:
            return self.result_broadcaster.get_broadcast_statistics()
        else:
            return {'error': 'No result broadcaster configured'}
    
    def add_error_callback(self, callback: Callable) -> None:
        """
        Add callback for error notifications.
        
        Args:
            callback: Function to call when errors occur
        """
        self.error_handler.add_error_callback(callback)
    
    def add_broadcast_throttle_rule(
        self,
        source_name: str,
        result_type: str,
        min_interval_seconds: float
    ) -> None:
        """
        Add throttling rule for broadcast messages.
        
        Args:
            source_name: Source name to throttle
            result_type: Result type to throttle
            min_interval_seconds: Minimum interval between broadcasts
        """
        if self.result_broadcaster:
            from .result_broadcaster import ResultType
            try:
                result_type_enum = ResultType(result_type)
                self.result_broadcaster.add_throttle_rule(
                    source_name, result_type_enum, min_interval_seconds
                )
            except ValueError:
                logger.error(f"Invalid result type: {result_type}")
        else:
            logger.warning("No result broadcaster configured for throttle rule")


# Integration functions for backward compatibility
async def create_enhanced_processor(
    ingestion_queue: RealtimeIngestionQueue,
    websocket_manager: Optional[Any] = None
) -> EnhancedBackgroundProcessor:
    """
    Create and start an enhanced background processor.
    
    Args:
        ingestion_queue: RealtimeIngestionQueue instance
        websocket_manager: Optional WebSocket manager
        
    Returns:
        Started EnhancedBackgroundProcessor instance
    """
    processor = EnhancedBackgroundProcessor(ingestion_queue, websocket_manager)
    await processor.start()
    return processor


def integrate_with_existing_background_tasks(processor: EnhancedBackgroundProcessor) -> None:
    """
    Integrate enhanced processor with existing background task system.
    
    Args:
        processor: EnhancedBackgroundProcessor instance
    """
    # This function can be used to set up integration points
    # with the existing background task system
    
    def log_processing_result(entry: LogEntry, result: ProcessingResult):
        """Log processing results for monitoring."""
        logger.info(f"Processed entry {entry.entry_id}: "
                   f"success={result.success}, time={result.processing_time:.2f}s")
    
    processor.add_processing_callback(log_processing_result)
    
    logger.info("Enhanced processor integrated with existing background tasks")