"""
Real-time ingestion queue system for log processing.

This module provides priority-based queuing for real-time log entries
with batch processing, backpressure handling, and performance monitoring.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import heapq
import json

from .base import RealtimeComponent, HealthMonitorMixin
from .exceptions import QueueError, ProcessingError

logger = logging.getLogger(__name__)


class LogEntryPriority(int, Enum):
    """Priority levels for log entries."""
    CRITICAL = 1    # Highest priority
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BULK = 5        # Lowest priority


class ProcessingStatus(str, Enum):
    """Status of log entry processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class LogEntry:
    """
    Individual log entry with metadata and priority.
    
    Represents a single log entry in the ingestion queue with all
    necessary metadata for processing and tracking.
    """
    
    # Core data
    content: str
    source_path: str
    source_name: str
    timestamp: datetime
    
    # Processing metadata
    priority: LogEntryPriority = LogEntryPriority.MEDIUM
    file_offset: int = 0
    entry_id: Optional[str] = None
    
    # Status tracking
    status: ProcessingStatus = ProcessingStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Error handling
    last_error: Optional[str] = None
    error_count: int = 0
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize entry ID if not provided."""
        if self.entry_id is None:
            # Generate unique ID based on source, timestamp, and offset
            timestamp_str = self.timestamp.strftime("%Y%m%d_%H%M%S_%f")
            self.entry_id = f"{self.source_name}_{timestamp_str}_{self.file_offset}"
    
    def __lt__(self, other):
        """Compare entries for priority queue ordering."""
        if not isinstance(other, LogEntry):
            return NotImplemented
        
        # Lower priority number = higher priority in queue
        if self.priority != other.priority:
            return self.priority.value < other.priority.value
        
        # If same priority, older entries first
        return self.timestamp < other.timestamp
    
    def mark_processing_started(self):
        """Mark entry as processing started."""
        self.status = ProcessingStatus.PROCESSING
        self.processing_started_at = datetime.now(timezone.utc)
    
    def mark_processing_completed(self):
        """Mark entry as processing completed."""
        self.status = ProcessingStatus.COMPLETED
        self.processing_completed_at = datetime.now(timezone.utc)
    
    def mark_processing_failed(self, error: str):
        """Mark entry as processing failed."""
        self.status = ProcessingStatus.FAILED
        self.last_error = error
        self.error_count += 1
        self.processing_completed_at = datetime.now(timezone.utc)
    
    def can_retry(self) -> bool:
        """Check if entry can be retried."""
        return self.retry_count < self.max_retries and self.status == ProcessingStatus.FAILED
    
    def mark_for_retry(self):
        """Mark entry for retry."""
        if self.can_retry():
            self.status = ProcessingStatus.RETRYING
            self.retry_count += 1
            self.processing_started_at = None
            self.processing_completed_at = None
    
    def get_processing_time(self) -> Optional[float]:
        """Get processing time in seconds."""
        if self.processing_started_at and self.processing_completed_at:
            return (self.processing_completed_at - self.processing_started_at).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'entry_id': self.entry_id,
            'content': self.content,
            'source_path': self.source_path,
            'source_name': self.source_name,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority.value,
            'file_offset': self.file_offset,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'processing_started_at': self.processing_started_at.isoformat() if self.processing_started_at else None,
            'processing_completed_at': self.processing_completed_at.isoformat() if self.processing_completed_at else None,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'last_error': self.last_error,
            'error_count': self.error_count,
            'metadata': self.metadata
        }


@dataclass
class QueueStats:
    """Statistics for queue performance monitoring."""
    
    # Queue size metrics
    total_entries: int = 0
    pending_entries: int = 0
    processing_entries: int = 0
    completed_entries: int = 0
    failed_entries: int = 0
    
    # Priority distribution
    priority_distribution: Dict[str, int] = field(default_factory=dict)
    
    # Performance metrics
    avg_processing_time: float = 0.0
    min_processing_time: float = 0.0
    max_processing_time: float = 0.0
    throughput_per_second: float = 0.0
    
    # Error metrics
    total_errors: int = 0
    error_rate: float = 0.0
    retry_count: int = 0
    
    # Timing
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_entries': self.total_entries,
            'pending_entries': self.pending_entries,
            'processing_entries': self.processing_entries,
            'completed_entries': self.completed_entries,
            'failed_entries': self.failed_entries,
            'priority_distribution': self.priority_distribution,
            'avg_processing_time': self.avg_processing_time,
            'min_processing_time': self.min_processing_time,
            'max_processing_time': self.max_processing_time,
            'throughput_per_second': self.throughput_per_second,
            'total_errors': self.total_errors,
            'error_rate': self.error_rate,
            'retry_count': self.retry_count,
            'last_updated': self.last_updated.isoformat()
        }


class RealtimeIngestionQueue(RealtimeComponent, HealthMonitorMixin):
    """
    Async priority queue for real-time log ingestion with batch processing.
    
    Provides priority-based queuing, batch processing for efficiency,
    backpressure handling, and comprehensive monitoring.
    """
    
    def __init__(
        self,
        max_queue_size: int = 10000,
        batch_size: int = 100,
        batch_timeout: float = 5.0,
        max_concurrent_batches: int = 5,
        backpressure_threshold: float = 0.8,
        stats_update_interval: float = 30.0
    ):
        """
        Initialize the real-time ingestion queue.
        
        Args:
            max_queue_size: Maximum number of entries in queue
            batch_size: Number of entries to process in a batch
            batch_timeout: Maximum time to wait for batch to fill (seconds)
            max_concurrent_batches: Maximum concurrent batch processing
            backpressure_threshold: Queue size ratio to trigger backpressure (0.0-1.0)
            stats_update_interval: Interval for updating statistics (seconds)
        """
        RealtimeComponent.__init__(self, "RealtimeIngestionQueue")
        HealthMonitorMixin.__init__(self)
        
        # Configuration
        self.max_queue_size = max_queue_size
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_concurrent_batches = max_concurrent_batches
        self.backpressure_threshold = backpressure_threshold
        self.stats_update_interval = stats_update_interval
        
        # Queue storage (priority queue using heapq)
        self._queue: List[LogEntry] = []
        self._queue_lock = asyncio.Lock()
        
        # Entry tracking
        self._entries_by_id: Dict[str, LogEntry] = {}
        self._entries_by_status: Dict[ProcessingStatus, List[LogEntry]] = defaultdict(list)
        
        # Processing control
        self._processing_semaphore = asyncio.Semaphore(max_concurrent_batches)
        self._processor_task: Optional[asyncio.Task] = None
        self._stats_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._stats = QueueStats()
        self._processing_times: List[float] = []
        self._completed_count = 0
        self._last_stats_update = time.time()
        
        # Callbacks
        self._batch_processor: Optional[Callable[[List[LogEntry]], Any]] = None
        self._error_handler: Optional[Callable[[LogEntry, Exception], None]] = None
        
        # Backpressure handling
        self._backpressure_active = False
        self._dropped_entries = 0
    
    async def _start_impl(self) -> None:
        """Start the queue processor."""
        logger.info("Starting real-time ingestion queue")
        
        # Start background tasks
        self._processor_task = asyncio.create_task(self._process_queue_continuously())
        self._stats_task = asyncio.create_task(self._update_stats_continuously())
        
        # Initialize health metrics
        self.update_health_metric("queue_size", 0)
        self.update_health_metric("backpressure_active", False)
        self.update_health_metric("processing_rate", 0.0)
    
    async def _stop_impl(self) -> None:
        """Stop the queue processor."""
        logger.info("Stopping real-time ingestion queue")
        
        # Cancel background tasks
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        if self._stats_task:
            self._stats_task.cancel()
            try:
                await self._stats_task
            except asyncio.CancelledError:
                pass
        
        # Process remaining entries if possible
        if self._queue and self._batch_processor:
            logger.info(f"Processing {len(self._queue)} remaining entries")
            try:
                await self._process_batch(self._queue[:self.batch_size])
            except Exception as e:
                logger.error(f"Error processing remaining entries: {e}")
    
    def set_batch_processor(self, processor: Callable[[List[LogEntry]], Any]) -> None:
        """Set the batch processor function."""
        self._batch_processor = processor
    
    def set_error_handler(self, handler: Callable[[LogEntry, Exception], None]) -> None:
        """Set the error handler function."""
        self._error_handler = handler
    
    async def enqueue_log_entry(self, entry: LogEntry) -> bool:
        """
        Add a log entry to the queue.
        
        Args:
            entry: LogEntry to add to the queue
            
        Returns:
            True if entry was added, False if rejected due to backpressure
            
        Raises:
            QueueError: If queue is full or entry is invalid
        """
        if not self.is_running:
            raise QueueError("Queue is not running")
        
        # Validate entry
        if not entry.content or not entry.source_name:
            raise QueueError("Invalid log entry: content and source_name are required")
        
        async with self._queue_lock:
            # Check for backpressure
            current_size = len(self._queue)
            backpressure_limit = int(self.max_queue_size * self.backpressure_threshold)
            
            if current_size >= self.max_queue_size:
                # Queue is full - reject entry
                self._dropped_entries += 1
                logger.warning(f"Queue full, dropping entry from {entry.source_name}")
                return False
            
            elif current_size >= backpressure_limit:
                # Activate backpressure
                if not self._backpressure_active:
                    self._backpressure_active = True
                    logger.warning(f"Backpressure activated at {current_size}/{self.max_queue_size} entries")
                    self.update_health_metric("backpressure_active", True)
                
                # For backpressure, only accept high priority entries
                if entry.priority.value > LogEntryPriority.HIGH.value:
                    self._dropped_entries += 1
                    logger.debug(f"Backpressure: dropping low priority entry from {entry.source_name}")
                    return False
            
            else:
                # Deactivate backpressure if it was active
                if self._backpressure_active:
                    self._backpressure_active = False
                    logger.info("Backpressure deactivated")
                    self.update_health_metric("backpressure_active", False)
            
            # Add entry to queue
            heapq.heappush(self._queue, entry)
            self._entries_by_id[entry.entry_id] = entry
            self._entries_by_status[entry.status].append(entry)
            
            # Update metrics
            self.update_health_metric("queue_size", len(self._queue))
            
            logger.debug(f"Enqueued entry {entry.entry_id} from {entry.source_name} "
                        f"(priority: {entry.priority.name}, queue size: {len(self._queue)})")
            
            return True
    
    async def get_queue_stats(self) -> QueueStats:
        """Get current queue statistics."""
        async with self._queue_lock:
            return self._calculate_stats()
    
    def _calculate_stats(self) -> QueueStats:
        """Calculate current statistics."""
        stats = QueueStats()
        
        # Count entries by status
        stats.total_entries = len(self._entries_by_id)
        stats.pending_entries = len([e for e in self._queue if e.status == ProcessingStatus.PENDING])
        stats.processing_entries = len(self._entries_by_status[ProcessingStatus.PROCESSING])
        stats.completed_entries = len(self._entries_by_status[ProcessingStatus.COMPLETED])
        stats.failed_entries = len(self._entries_by_status[ProcessingStatus.FAILED])
        
        # Priority distribution
        priority_counts = defaultdict(int)
        for entry in self._queue:
            priority_counts[entry.priority.name] += 1
        stats.priority_distribution = dict(priority_counts)
        
        # Processing time metrics
        if self._processing_times:
            stats.avg_processing_time = sum(self._processing_times) / len(self._processing_times)
            stats.min_processing_time = min(self._processing_times)
            stats.max_processing_time = max(self._processing_times)
        
        # Throughput calculation
        time_elapsed = time.time() - self._last_stats_update
        if time_elapsed > 0:
            stats.throughput_per_second = self._completed_count / time_elapsed
        
        # Error metrics
        stats.total_errors = sum(entry.error_count for entry in self._entries_by_id.values())
        if stats.total_entries > 0:
            stats.error_rate = stats.total_errors / stats.total_entries
        stats.retry_count = sum(entry.retry_count for entry in self._entries_by_id.values())
        
        return stats
    
    async def _process_queue_continuously(self) -> None:
        """Continuously process queue entries in batches."""
        logger.info("Starting continuous queue processing")
        
        while not self._shutdown_event.is_set():
            try:
                # Wait for entries or timeout
                batch = await self._collect_batch()
                
                if batch:
                    # Process batch with concurrency control
                    async with self._processing_semaphore:
                        await self._process_batch(batch)
                else:
                    # No entries available, short sleep
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                logger.info("Queue processing cancelled")
                break
            except Exception as e:
                self._handle_error(e, "during continuous processing")
                await asyncio.sleep(1.0)  # Brief pause on error
    
    async def _collect_batch(self) -> List[LogEntry]:
        """Collect a batch of entries for processing."""
        batch = []
        batch_start_time = time.time()
        
        while len(batch) < self.batch_size:
            async with self._queue_lock:
                if not self._queue:
                    break
                
                # Get highest priority entry
                entry = heapq.heappop(self._queue)
                batch.append(entry)
                
                # Update entry status
                entry.mark_processing_started()
                self._entries_by_status[ProcessingStatus.PENDING].remove(entry)
                self._entries_by_status[ProcessingStatus.PROCESSING].append(entry)
            
            # Check timeout
            if time.time() - batch_start_time >= self.batch_timeout:
                break
        
        return batch
    
    async def _process_batch(self, batch: List[LogEntry]) -> None:
        """Process a batch of log entries."""
        if not batch or not self._batch_processor:
            return
        
        batch_start_time = time.time()
        logger.debug(f"Processing batch of {len(batch)} entries")
        
        try:
            # Call the batch processor
            await self._batch_processor(batch)
            
            # Mark all entries as completed
            async with self._queue_lock:
                for entry in batch:
                    entry.mark_processing_completed()
                    self._entries_by_status[ProcessingStatus.PROCESSING].remove(entry)
                    self._entries_by_status[ProcessingStatus.COMPLETED].append(entry)
                    
                    # Record processing time
                    processing_time = entry.get_processing_time()
                    if processing_time:
                        self._processing_times.append(processing_time)
                        
                        # Keep only recent processing times for stats
                        if len(self._processing_times) > 1000:
                            self._processing_times = self._processing_times[-500:]
            
            batch_time = time.time() - batch_start_time
            self._completed_count += len(batch)
            
            logger.debug(f"Completed batch of {len(batch)} entries in {batch_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            
            # Mark entries as failed and handle retries
            async with self._queue_lock:
                for entry in batch:
                    entry.mark_processing_failed(str(e))
                    self._entries_by_status[ProcessingStatus.PROCESSING].remove(entry)
                    
                    # Check if entry can be retried
                    if entry.can_retry():
                        entry.mark_for_retry()
                        heapq.heappush(self._queue, entry)  # Re-queue for retry
                        self._entries_by_status[ProcessingStatus.RETRYING].append(entry)
                        logger.info(f"Re-queued entry {entry.entry_id} for retry {entry.retry_count}")
                    else:
                        self._entries_by_status[ProcessingStatus.FAILED].append(entry)
                        logger.error(f"Entry {entry.entry_id} failed permanently after {entry.retry_count} retries")
            
            # Call error handler if available
            if self._error_handler:
                for entry in batch:
                    try:
                        self._error_handler(entry, e)
                    except Exception as handler_error:
                        logger.error(f"Error in error handler: {handler_error}")
    
    async def _update_stats_continuously(self) -> None:
        """Continuously update statistics."""
        while not self._shutdown_event.is_set():
            try:
                async with self._queue_lock:
                    self._stats = self._calculate_stats()
                
                # Update health metrics
                self.update_health_metric("queue_size", len(self._queue))
                self.update_health_metric("processing_rate", self._stats.throughput_per_second)
                self.update_health_metric("error_rate", self._stats.error_rate)
                self.update_health_metric("backpressure_active", self._backpressure_active)
                self.update_health_metric("dropped_entries", self._dropped_entries)
                
                # Reset counters for next interval
                self._completed_count = 0
                self._last_stats_update = time.time()
                
                await asyncio.sleep(self.stats_update_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._handle_error(e, "during stats update")
                await asyncio.sleep(self.stats_update_interval)
    
    async def get_entry_by_id(self, entry_id: str) -> Optional[LogEntry]:
        """Get an entry by its ID."""
        async with self._queue_lock:
            return self._entries_by_id.get(entry_id)
    
    async def get_entries_by_status(self, status: ProcessingStatus) -> List[LogEntry]:
        """Get all entries with a specific status."""
        async with self._queue_lock:
            return self._entries_by_status[status].copy()
    
    async def clear_completed_entries(self, max_age_hours: int = 24) -> int:
        """
        Clear completed entries older than specified age.
        
        Args:
            max_age_hours: Maximum age in hours for completed entries
            
        Returns:
            Number of entries cleared
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        cleared_count = 0
        
        async with self._queue_lock:
            completed_entries = self._entries_by_status[ProcessingStatus.COMPLETED].copy()
            
            for entry in completed_entries:
                if entry.processing_completed_at and entry.processing_completed_at < cutoff_time:
                    # Remove from tracking
                    self._entries_by_status[ProcessingStatus.COMPLETED].remove(entry)
                    del self._entries_by_id[entry.entry_id]
                    cleared_count += 1
        
        if cleared_count > 0:
            logger.info(f"Cleared {cleared_count} completed entries older than {max_age_hours} hours")
        
        return cleared_count
    
    def get_queue_info(self) -> Dict[str, Any]:
        """Get comprehensive queue information."""
        return {
            'name': self.name,
            'is_running': self.is_running,
            'configuration': {
                'max_queue_size': self.max_queue_size,
                'batch_size': self.batch_size,
                'batch_timeout': self.batch_timeout,
                'max_concurrent_batches': self.max_concurrent_batches,
                'backpressure_threshold': self.backpressure_threshold,
                'stats_update_interval': self.stats_update_interval
            },
            'current_state': {
                'queue_size': len(self._queue),
                'backpressure_active': self._backpressure_active,
                'dropped_entries': self._dropped_entries,
                'has_batch_processor': self._batch_processor is not None,
                'has_error_handler': self._error_handler is not None
            },
            'health_status': self.get_health_status(),
            'health_metrics': self.get_health_metrics()
        }