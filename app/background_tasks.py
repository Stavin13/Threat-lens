"""
Background task system for automated processing pipeline.

This module provides background task functionality for automatic log processing,
including parsing and AI analysis with error handling and retry logic.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_database_session
from app.models import RawLog, Event, AIAnalysis as AIAnalysisModel
from app.parser import parse_log_entries, ParsingError
from app.analyzer import analyze_event, AnalysisError
from app.schemas import ParsedEvent

# Configure logging
logger = logging.getLogger(__name__)


class ProcessingError(Exception):
    """Custom exception for processing pipeline errors."""
    pass


class BackgroundTaskManager:
    """Manager for background processing tasks with retry logic."""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize the background task manager.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries in seconds
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'retried_tasks': 0,
            'processing_times': []
        }
        self.realtime_stats = {
            'websocket_updates_sent': 0,
            'websocket_update_failures': 0,
            'last_broadcast_time': None
        }
        
        # Real-time processing extensions
        self.realtime_stats = {
            'realtime_entries_processed': 0,
            'realtime_processing_times': [],
            'websocket_updates_sent': 0,
            'websocket_update_failures': 0,
            'last_realtime_processing': None
        }
        
        # WebSocket manager for real-time updates (optional)
        self.websocket_manager = None
        
        # Processing callbacks for real-time integration
        self.processing_callbacks = []
    
    async def process_raw_log_with_retry(self, raw_log_id: str) -> Dict[str, Any]:
        """
        Process raw log with retry logic and comprehensive error handling.
        
        Args:
            raw_log_id: ID of the raw log to process
            
        Returns:
            Dictionary with processing results and statistics
        """
        self.stats['total_tasks'] += 1
        start_time = time.time()
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await self._process_raw_log_attempt(raw_log_id, attempt)
                
                # Record success
                processing_time = time.time() - start_time
                self.stats['processing_times'].append(processing_time)
                self.stats['successful_tasks'] += 1
                
                if attempt > 0:
                    self.stats['retried_tasks'] += 1
                
                logger.info(f"Successfully processed raw log {raw_log_id} in {processing_time:.2f}s (attempt {attempt + 1})")
                
                return {
                    'success': True,
                    'raw_log_id': raw_log_id,
                    'attempt': attempt + 1,
                    'processing_time': processing_time,
                    'events_parsed': result.get('events_parsed', 0),
                    'events_analyzed': result.get('events_analyzed', 0),
                    'errors': result.get('errors', [])
                }
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed for raw log {raw_log_id}: {str(e)}")
                
                if attempt < self.max_retries:
                    # Calculate exponential backoff delay
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)
                else:
                    # All attempts failed
                    processing_time = time.time() - start_time
                    self.stats['failed_tasks'] += 1
                    
                    logger.error(f"All attempts failed for raw log {raw_log_id} after {processing_time:.2f}s")
                    
                    return {
                        'success': False,
                        'raw_log_id': raw_log_id,
                        'attempts': self.max_retries + 1,
                        'processing_time': processing_time,
                        'error': str(e),
                        'events_parsed': 0,
                        'events_analyzed': 0
                    }
        
        # This should never be reached, but just in case
        return {
            'success': False,
            'raw_log_id': raw_log_id,
            'error': 'Unexpected processing failure'
        }
    
    async def _process_raw_log_attempt(self, raw_log_id: str, attempt: int) -> Dict[str, Any]:
        """
        Single attempt to process a raw log.
        
        Args:
            raw_log_id: ID of the raw log to process
            attempt: Current attempt number (0-based)
            
        Returns:
            Dictionary with processing results
            
        Raises:
            ProcessingError: If processing fails
        """
        events_parsed = 0
        events_analyzed = 0
        errors = []
        
        try:
            with get_database_session() as db:
                # Get raw log
                raw_log = db.query(RawLog).filter(RawLog.id == raw_log_id).first()
                if not raw_log:
                    raise ProcessingError(f"Raw log {raw_log_id} not found")
                
                logger.info(f"Processing raw log {raw_log_id} (attempt {attempt + 1})")
                
                # Parse the log
                try:
                    parsed_events = parse_log_entries(raw_log.content, raw_log_id)
                    events_parsed = len(parsed_events)
                    logger.info(f"Parsed {events_parsed} events from raw log {raw_log_id}")
                    
                except ParsingError as e:
                    error_msg = f"Failed to parse raw log {raw_log_id}: {str(e)}"
                    errors.append(error_msg)
                    raise ProcessingError(error_msg)
                
                # Process each parsed event
                for event in parsed_events:
                    try:
                        # Store event in database
                        db_event = Event(
                            id=event.id,
                            raw_log_id=event.raw_log_id,
                            timestamp=event.timestamp,
                            source=event.source,
                            message=event.message,
                            category=event.category.value,
                            parsed_at=event.parsed_at or datetime.now(timezone.utc)
                        )
                        db.add(db_event)
                        
                        # Analyze event with AI
                        try:
                            ai_analysis = analyze_event(event)
                            
                            # Store AI analysis
                            db_analysis = AIAnalysisModel(
                                id=ai_analysis.id,
                                event_id=ai_analysis.event_id,
                                severity_score=ai_analysis.severity_score,
                                explanation=ai_analysis.explanation,
                                recommendations=str(ai_analysis.recommendations),  # Store as JSON string
                                analyzed_at=ai_analysis.analyzed_at or datetime.now(timezone.utc)
                            )
                            db.add(db_analysis)
                            events_analyzed += 1
                            
                        except AnalysisError as e:
                            error_msg = f"Failed to analyze event {event.id}: {str(e)}"
                            errors.append(error_msg)
                            logger.warning(error_msg)
                            # Continue with other events - analysis failure shouldn't stop processing
                            continue
                    
                    except SQLAlchemyError as e:
                        error_msg = f"Database error processing event {event.id}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                        # Continue with other events
                        continue
                
                # Commit all changes
                db.commit()
                
                # Broadcast events via WebSocket if available
                await self._broadcast_processed_events(db, raw_log_id, parsed_events)
                
                logger.info(f"Successfully processed raw log {raw_log_id}: "
                           f"{events_parsed} parsed, {events_analyzed} analyzed")
                
                return {
                    'events_parsed': events_parsed,
                    'events_analyzed': events_analyzed,
                    'errors': errors
                }
                
        except SQLAlchemyError as e:
            error_msg = f"Database error processing raw log {raw_log_id}: {str(e)}"
            logger.error(error_msg)
            raise ProcessingError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error processing raw log {raw_log_id}: {str(e)}"
            logger.error(error_msg)
            raise ProcessingError(error_msg)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get processing statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        stats = self.stats.copy()
        
        # Calculate average processing time
        if stats['processing_times']:
            stats['avg_processing_time'] = sum(stats['processing_times']) / len(stats['processing_times'])
            stats['min_processing_time'] = min(stats['processing_times'])
            stats['max_processing_time'] = max(stats['processing_times'])
        else:
            stats['avg_processing_time'] = 0
            stats['min_processing_time'] = 0
            stats['max_processing_time'] = 0
        
        # Calculate success rate
        if stats['total_tasks'] > 0:
            stats['success_rate'] = stats['successful_tasks'] / stats['total_tasks']
        else:
            stats['success_rate'] = 0
        
        # Add real-time metrics
        stats['realtime_metrics'] = self.get_realtime_metrics()
        
        return stats
    
    def reset_stats(self):
        """Reset processing statistics."""
        self.stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'retried_tasks': 0,
            'processing_times': []
        }
        self.realtime_stats = {
            'websocket_updates_sent': 0,
            'websocket_update_failures': 0,
            'last_broadcast_time': None
        }
    
    def set_websocket_manager(self, websocket_manager):
        """
        Set WebSocket manager for real-time updates.
        
        Args:
            websocket_manager: WebSocket manager instance
        """
        self.websocket_manager = websocket_manager
        logger.info("WebSocket manager configured for real-time updates")
    
    async def _broadcast_processed_events(self, db: Session, raw_log_id: str, parsed_events: List[ParsedEvent]):
        """
        Broadcast processed events via WebSocket.
        
        Args:
            db: Database session
            raw_log_id: Raw log ID
            parsed_events: List of parsed events
        """
        try:
            # Import here to avoid circular imports
            from app.realtime.event_loop import realtime_manager
            
            websocket_api = realtime_manager.get_websocket_api()
            if not websocket_api:
                logger.debug("WebSocket API not available for broadcasting")
                return
            
            # Broadcast each event with its analysis
            for event in parsed_events:
                try:
                    # Get the stored event with analysis
                    db_event = db.query(Event).filter(Event.id == event.id).first()
                    if not db_event:
                        continue
                    
                    db_analysis = db.query(AIAnalysisModel).filter(AIAnalysisModel.event_id == event.id).first()
                    if not db_analysis:
                        continue
                    
                    # Parse recommendations JSON
                    try:
                        import json
                        recommendations = json.loads(db_analysis.recommendations)
                    except:
                        recommendations = [db_analysis.recommendations] if db_analysis.recommendations else []
                    
                    # Create security event data
                    from app.realtime.websocket_api import SecurityEventData
                    
                    event_data = SecurityEventData(
                        event_id=db_event.id,
                        severity=db_analysis.severity_score,
                        category=db_event.category,
                        source=db_event.source,
                        message=db_event.message,
                        timestamp=db_event.timestamp,
                        analysis={
                            'explanation': db_analysis.explanation,
                            'severity_score': db_analysis.severity_score,
                            'analyzed_at': db_analysis.analyzed_at.isoformat()
                        },
                        recommendations=recommendations
                    )
                    
                    # Broadcast the event
                    result = await websocket_api.broadcast_security_event(event_data)
                    
                    if result.get('status') == 'success':
                        self.realtime_stats['websocket_updates_sent'] += 1
                        logger.debug(f"Broadcasted security event {event.id} to {result.get('messages_sent', 0)} clients")
                    else:
                        self.realtime_stats['websocket_update_failures'] += 1
                        logger.warning(f"Failed to broadcast security event {event.id}: {result}")
                        
                except Exception as e:
                    self.realtime_stats['websocket_update_failures'] += 1
                    logger.error(f"Error broadcasting event {event.id}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in WebSocket broadcasting for raw log {raw_log_id}: {e}")

    def add_processing_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """
        Add callback to be called after processing completion.
        
        Args:
            callback: Function to call with (raw_log_id, result) parameters
        """
        self.processing_callbacks.append(callback)
        logger.debug(f"Added processing callback: {callback.__name__}")
    
    async def process_realtime_log_entry(self, log_content: str, source_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a real-time log entry with immediate WebSocket updates.
        
        Args:
            log_content: Raw log content to process
            source_info: Information about the log source (path, name, etc.)
            
        Returns:
            Dictionary with processing results
        """
        start_time = time.time()
        entry_id = f"realtime_{int(time.time() * 1000000)}"  # Microsecond timestamp
        
        try:
            logger.info(f"Processing real-time log entry from {source_info.get('source_name', 'unknown')}")
            
            # Send processing started update
            if self.websocket_manager:
                await self._send_processing_update({
                    'type': 'processing_started',
                    'entry_id': entry_id,
                    'source_info': source_info,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
            
            # Parse the log content with automatic format detection
            try:
                # Try automatic format detection first
                from app.realtime.format_detector import parse_with_auto_detection
                
                try:
                    parsed_events = parse_with_auto_detection(log_content, entry_id)
                    parsing_method = "auto_detection"
                    logger.info(f"Used automatic format detection for real-time entry")
                except Exception as auto_detect_error:
                    logger.debug(f"Auto-detection failed, falling back to standard parser: {auto_detect_error}")
                    # Fallback to standard parser
                    parsed_events = parse_log_entries(log_content, entry_id)
                    parsing_method = "standard_parser"
                
                events_parsed = len(parsed_events)
                logger.info(f"Parsed {events_parsed} events from real-time entry using {parsing_method}")
                
                # Send parsing complete update
                if self.websocket_manager:
                    await self._send_processing_update({
                        'type': 'parsing_complete',
                        'entry_id': entry_id,
                        'events_parsed': events_parsed,
                        'parsing_method': parsing_method,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                
            except ParsingError as e:
                error_msg = f"Failed to parse real-time log entry: {str(e)}"
                logger.error(error_msg)
                
                # Send parsing error update
                if self.websocket_manager:
                    await self._send_processing_update({
                        'type': 'parsing_error',
                        'entry_id': entry_id,
                        'error': error_msg,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                
                return {
                    'success': False,
                    'entry_id': entry_id,
                    'error': error_msg,
                    'processing_time': time.time() - start_time
                }
            
            # Process and store events
            events_analyzed = 0
            stored_events = []
            
            try:
                with get_database_session() as db:
                    for event in parsed_events:
                        # Store event in database
                        db_event = Event(
                            id=event.id,
                            raw_log_id=entry_id,
                            timestamp=event.timestamp,
                            source=event.source,
                            message=event.message,
                            category=event.category.value,
                            parsed_at=event.parsed_at or datetime.now(timezone.utc)
                        )
                        db.add(db_event)
                        
                        # Run AI analysis
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
                            events_analyzed += 1
                            
                            # Prepare event data for WebSocket update
                            stored_events.append({
                                'id': event.id,
                                'timestamp': event.timestamp.isoformat(),
                                'source': event.source,
                                'category': event.category.value,
                                'message': event.message[:200] + '...' if len(event.message) > 200 else event.message,
                                'severity_score': ai_analysis.severity_score,
                                'explanation': ai_analysis.explanation[:100] + '...' if len(ai_analysis.explanation) > 100 else ai_analysis.explanation
                            })
                            
                        except AnalysisError as e:
                            logger.warning(f"Failed to analyze event {event.id}: {e}")
                            # Continue with other events
                            continue
                    
                    # Commit all changes
                    db.commit()
                    
                    # Send analysis complete update
                    if self.websocket_manager:
                        await self._send_processing_update({
                            'type': 'analysis_complete',
                            'entry_id': entry_id,
                            'events_analyzed': events_analyzed,
                            'events': stored_events[:5],  # Send first 5 events
                            'total_events': len(stored_events),
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        })
                
            except SQLAlchemyError as e:
                error_msg = f"Database error processing real-time entry: {str(e)}"
                logger.error(error_msg)
                
                # Send database error update
                if self.websocket_manager:
                    await self._send_processing_update({
                        'type': 'database_error',
                        'entry_id': entry_id,
                        'error': error_msg,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                
                return {
                    'success': False,
                    'entry_id': entry_id,
                    'error': error_msg,
                    'processing_time': time.time() - start_time
                }
            
            # Record successful processing
            processing_time = time.time() - start_time
            self.realtime_stats['realtime_entries_processed'] += 1
            self.realtime_stats['realtime_processing_times'].append(processing_time)
            self.realtime_stats['last_realtime_processing'] = datetime.now(timezone.utc)
            
            # Keep only recent processing times
            if len(self.realtime_stats['realtime_processing_times']) > 100:
                self.realtime_stats['realtime_processing_times'] = self.realtime_stats['realtime_processing_times'][-50:]
            
            result = {
                'success': True,
                'entry_id': entry_id,
                'processing_time': processing_time,
                'events_parsed': events_parsed,
                'events_analyzed': events_analyzed,
                'source_info': source_info
            }
            
            # Call processing callbacks
            for callback in self.processing_callbacks:
                try:
                    callback(entry_id, result)
                except Exception as e:
                    logger.error(f"Error in processing callback: {e}")
            
            # Send final processing complete update
            if self.websocket_manager:
                await self._send_processing_update({
                    'type': 'processing_complete',
                    'entry_id': entry_id,
                    'result': result,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
            
            logger.info(f"Successfully processed real-time entry {entry_id} in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Unexpected error processing real-time entry: {str(e)}"
            logger.error(error_msg)
            
            # Send unexpected error update
            if self.websocket_manager:
                await self._send_processing_update({
                    'type': 'processing_error',
                    'entry_id': entry_id,
                    'error': error_msg,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
            
            return {
                'success': False,
                'entry_id': entry_id,
                'error': error_msg,
                'processing_time': processing_time
            }
    
    async def _send_processing_update(self, update_data: Dict[str, Any]) -> None:
        """
        Send processing status update via WebSocket.
        
        Args:
            update_data: Update data to send
        """
        if not self.websocket_manager:
            return
        
        try:
            # Create EventUpdate for broadcasting
            from app.realtime.websocket_server import EventUpdate
            
            event_update = EventUpdate(
                event_type='realtime_processing_update',
                data=update_data,
                priority=7  # High priority for processing updates
            )
            
            await self.websocket_manager.broadcast_event(event_update)
            self.realtime_stats['websocket_updates_sent'] += 1
            
        except Exception as e:
            self.realtime_stats['websocket_update_failures'] += 1
            logger.error(f"Failed to send WebSocket update: {e}")
    
    def get_realtime_metrics(self) -> Dict[str, Any]:
        """
        Get real-time processing metrics.
        
        Returns:
            Dictionary with real-time processing metrics
        """
        metrics = self.realtime_stats.copy()
        
        # Calculate WebSocket broadcast success rate
        total_broadcasts = metrics['websocket_updates_sent'] + metrics['websocket_update_failures']
        if total_broadcasts > 0:
            metrics['websocket_success_rate'] = metrics['websocket_updates_sent'] / total_broadcasts
        else:
            metrics['websocket_success_rate'] = 0
        
        # Calculate WebSocket success rate
        total_updates = metrics['websocket_updates_sent'] + metrics['websocket_update_failures']
        if total_updates > 0:
            metrics['websocket_success_rate'] = metrics['websocket_updates_sent'] / total_updates
        else:
            metrics['websocket_success_rate'] = 0
        
        # Format timestamp
        if metrics['last_realtime_processing']:
            metrics['last_realtime_processing'] = metrics['last_realtime_processing'].isoformat()
        
        # Remove raw processing times from output
        del metrics['realtime_processing_times']
        
        return metrics


# Global task manager instance
task_manager = BackgroundTaskManager()


async def process_raw_log(raw_log_id: str) -> Dict[str, Any]:
    """
    Process a raw log with automated parsing and AI analysis.
    
    This is the main entry point for the automated processing pipeline.
    It handles the complete workflow from raw log to analyzed events.
    
    Args:
        raw_log_id: ID of the raw log to process
        
    Returns:
        Dictionary with processing results
    """
    return await task_manager.process_raw_log_with_retry(raw_log_id)


def trigger_log_parsing(raw_log_id: str) -> bool:
    """
    Trigger log parsing for a raw log entry.
    
    Args:
        raw_log_id: ID of the raw log to parse
        
    Returns:
        True if parsing was triggered successfully, False otherwise
    """
    try:
        with get_database_session() as db:
            raw_log = db.query(RawLog).filter(RawLog.id == raw_log_id).first()
            if not raw_log:
                logger.error(f"Raw log {raw_log_id} not found for parsing trigger")
                return False
            
            # Parse the log synchronously for immediate trigger
            parsed_events = parse_log_entries(raw_log.content, raw_log_id)
            
            # Store parsed events
            for event in parsed_events:
                db_event = Event(
                    id=event.id,
                    raw_log_id=event.raw_log_id,
                    timestamp=event.timestamp,
                    source=event.source,
                    message=event.message,
                    category=event.category.value,
                    parsed_at=event.parsed_at or datetime.now(timezone.utc)
                )
                db.add(db_event)
            
            db.commit()
            logger.info(f"Triggered parsing for raw log {raw_log_id}: {len(parsed_events)} events")
            return True
            
    except Exception as e:
        logger.error(f"Failed to trigger parsing for raw log {raw_log_id}: {str(e)}")
        return False


def trigger_ai_analysis(event_ids: List[str]) -> Dict[str, bool]:
    """
    Trigger AI analysis for specific events.
    
    Args:
        event_ids: List of event IDs to analyze
        
    Returns:
        Dictionary mapping event IDs to success status
    """
    results = {}
    
    try:
        with get_database_session() as db:
            for event_id in event_ids:
                try:
                    # Get the event
                    db_event = db.query(Event).filter(Event.id == event_id).first()
                    if not db_event:
                        logger.error(f"Event {event_id} not found for analysis trigger")
                        results[event_id] = False
                        continue
                    
                    # Convert to ParsedEvent for analysis
                    from app.schemas import EventCategory
                    parsed_event = ParsedEvent(
                        id=db_event.id,
                        raw_log_id=db_event.raw_log_id,
                        timestamp=db_event.timestamp,
                        source=db_event.source,
                        message=db_event.message,
                        category=EventCategory(db_event.category),
                        parsed_at=db_event.parsed_at
                    )
                    
                    # Analyze the event
                    ai_analysis = analyze_event(parsed_event)
                    
                    # Store or update AI analysis
                    existing_analysis = db.query(AIAnalysisModel).filter(
                        AIAnalysisModel.event_id == event_id
                    ).first()
                    
                    if existing_analysis:
                        # Update existing analysis
                        existing_analysis.severity_score = ai_analysis.severity_score
                        existing_analysis.explanation = ai_analysis.explanation
                        existing_analysis.recommendations = str(ai_analysis.recommendations)
                        existing_analysis.analyzed_at = datetime.now(timezone.utc)
                    else:
                        # Create new analysis
                        db_analysis = AIAnalysisModel(
                            id=ai_analysis.id,
                            event_id=ai_analysis.event_id,
                            severity_score=ai_analysis.severity_score,
                            explanation=ai_analysis.explanation,
                            recommendations=str(ai_analysis.recommendations),
                            analyzed_at=ai_analysis.analyzed_at or datetime.now(timezone.utc)
                        )
                        db.add(db_analysis)
                    
                    results[event_id] = True
                    logger.info(f"Triggered AI analysis for event {event_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to analyze event {event_id}: {str(e)}")
                    results[event_id] = False
            
            db.commit()
            
    except Exception as e:
        logger.error(f"Failed to trigger AI analysis: {str(e)}")
        # Mark all as failed
        for event_id in event_ids:
            if event_id not in results:
                results[event_id] = False
    
    return results


def get_processing_stats() -> Dict[str, Any]:
    """
    Get comprehensive processing pipeline statistics.
    
    Returns:
        Dictionary with processing statistics
    """
    return task_manager.get_stats()


def reset_processing_stats():
    """Reset processing pipeline statistics."""
    task_manager.reset_stats()


def set_websocket_manager_for_realtime(websocket_manager):
    """
    Configure WebSocket manager for real-time processing updates.
    
    Args:
        websocket_manager: WebSocket manager instance
    """
    task_manager.set_websocket_manager(websocket_manager)


def add_processing_callback(callback: Callable[[str, Dict[str, Any]], None]):
    """
    Add callback for processing completion events.
    
    Args:
        callback: Function to call with (entry_id, result) parameters
    """
    task_manager.add_processing_callback(callback)


async def process_realtime_log_entry(log_content: str, source_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a real-time log entry with immediate WebSocket updates.
    
    Args:
        log_content: Raw log content to process
        source_info: Information about the log source
        
    Returns:
        Dictionary with processing results
    """
    return await task_manager.process_realtime_log_entry(log_content, source_info)


def get_realtime_processing_metrics() -> Dict[str, Any]:
    """
    Get real-time processing metrics.
    
    Returns:
        Dictionary with real-time processing metrics
    """
    return task_manager.get_realtime_metrics()