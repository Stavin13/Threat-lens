"""
Optimized real-time ingestion queue with performance enhancements.

This module provides an optimized version of the ingestion queue with
improved memory management, adaptive batching, and resource optimization.
"""

import asyncio
import logging
import time
import heapq
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple, Deque
from dataclasses import dataclass, field
from collections import defaultdict, deque
import weakref
import gc

from .ingestion_queue import (
    RealtimeIngestionQueue, LogEntry, LogEntryPriority, 
    ProcessingStatus, QueueStats
)
from .performance_optimizer import get_performance_optimizer
from .exceptions import QueueError

logger = logging.getLogger(__name__)


class OptimizedRealtimeIngestionQueue(RealtimeIngestionQueue):
    """
    Optimized real-time ingestion queue with performance enhancements.
    
    Includes adaptive batching, memory management, connection pooling,
    and intelligent resource optimization.
    """
    
    def __init__(
        self,
        max_queue_size: int = 10000,
        batch_size: int = 100,
        batch_timeout: float = 5.0,
        max_concurrent_batches: int = 5,
        backpressure_threshold: float = 0.8,
        stats_update_interval: float = 30.0,
        memory_optimization: bool = True,
        adaptive_batching: bool = True
    ):
        """
        Initialize the optimized ingestion queue.
        
        Args:
            max_queue_size: Maximum number of entries in queue
            batch_size: Initial batch size (will be adapted if adaptive_batching=True)
            batch_timeout: Maximum time to wait for batch to fill
            max_concurrent_batches: Maximum concurrent batch processing
            backpressure_threshold: Queue size ratio to trigger backpressure
            stats_update_interval: Interval for updating statistics
            memory_optimization: Enable memory optimization features
            adaptive_batching: Enable adaptive batch sizing
        """
        super().__init__(
            max_queue_size, batch_size, batch_timeout, max_concurrent_batches,
            backpressure_threshold, stats_update_interval
        )
        
        # Performance optimizer integration
        self.performance_optimizer = get_performance_optimizer()
        
        # Optimization settings
        self.memory_optimization = memory_optimization
        self.adaptive_batching = adaptive_batching
        
        # Memory management
        self._memory_check_interval = 30.0  # seconds
        self._memory_cleanup_threshold = 0.85  # 85% memory usage
        self._last_memory_check = time.time()
        
        # Adaptive batching
        self._batch_performance_history: Deque[Tuple[int, float]] = deque(maxlen=50)
        self._optimal_batch_size = batch_size
        self._batch_adaptation_factor = 0.1
        self._min_batch_size = max(1, batch_size // 4)
        self._max_batch_size = batch_size * 4
        
        # Entry pooling for memory efficiency
        self._entry_pool: List[LogEntry] = []
        self._pool_size_limit = 1000
        
        # Priority queue optimization
        self._priority_queues: Dict[LogEntryPriority, List[LogEntry]] = {
            priority: [] for priority in LogEntryPriority
        }
        self._queue_locks: Dict[LogEntryPriority, asyncio.Lock] = {
            priority: asyncio.Lock() for priority in LogEntryPriority
        }
        
        # Batch processing optimization
        self._batch_cache: Dict[str, Any] = {}
        self._batch_cache_ttl = 60  # seconds
        
        # Resource monitoring
        self._resource_monitor_task: Optional[asyncio.Task] = None
    
    async def _start_impl(self) -> None:
        """Start the optimized queue processor."""
        await super()._start_impl()
        
        # Start resource monitoring
        if self.memory_optimization:
            self._resource_monitor_task = asyncio.create_task(self._monitor_resources_continuously())
        
        logger.info("Optimized ingestion queue started with performance enhancements")
    
    async def _stop_impl(self) -> None:
        """Stop the optimized queue processor."""
        # Cancel resource monitoring
        if self._resource_monitor_task:
            self._resource_monitor_task.cancel()
            try:
                await self._resource_monitor_task
            except asyncio.CancelledError:
                pass
        
        await super()._stop_impl()
    
    async def enqueue_log_entry(self, entry: LogEntry) -> bool:
        """
        Add a log entry to the queue with optimizations.
        
        Args:
            entry: LogEntry to add to the queue
            
        Returns:
            True if entry was added, False if rejected due to backpressure
        """
        if not self.is_running:
            raise QueueError("Queue is not running")
        
        # Validate entry
        if not entry.content or not entry.source_name:
            raise QueueError("Invalid log entry: content and source_name are required")
        
        # Use priority-specific queue for better performance
        priority_queue = self._priority_queues[entry.priority]
        priority_lock = self._queue_locks[entry.priority]
        
        async with priority_lock:
            # Check for backpressure
            total_size = sum(len(q) for q in self._priority_queues.values())
            backpressure_limit = int(self.max_queue_size * self.backpressure_threshold)
            
            if total_size >= self.max_queue_size:
                # Queue is full - reject entry
                self._dropped_entries += 1
                logger.warning(f"Queue full, dropping entry from {entry.source_name}")
                return False
            
            elif total_size >= backpressure_limit:
                # Activate backpressure
                if not self._backpressure_active:
                    self._backpressure_active = True
                    logger.warning(f"Backpressure activated at {total_size}/{self.max_queue_size} entries")
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
            
            # Add entry to priority-specific queue
            heapq.heappush(priority_queue, entry)
            self._entries_by_id[entry.entry_id] = entry
            self._entries_by_status[entry.status].append(entry)
            
            # Update metrics
            self.update_health_metric("queue_size", total_size + 1)
            
            logger.debug(f"Enqueued entry {entry.entry_id} from {entry.source_name} "
                        f"(priority: {entry.priority.name}, queue size: {total_size + 1})")
            
            return True
    
    async def _collect_batch(self) -> List[LogEntry]:
        """Collect a batch of entries with priority-aware selection."""
        batch = []
        batch_start_time = time.time()
        
        # Use adaptive batch size if enabled
        target_batch_size = self._get_optimal_batch_size()
        
        # Collect entries from priority queues in order
        for priority in LogEntryPriority:
            if len(batch) >= target_batch_size:
                break
            
            priority_queue = self._priority_queues[priority]
            priority_lock = self._queue_locks[priority]
            
            async with priority_lock:
                # Take entries from this priority level
                entries_needed = target_batch_size - len(batch)
                entries_taken = 0
                
                while priority_queue and entries_taken < entries_needed:
                    entry = heapq.heappop(priority_queue)
                    batch.append(entry)
                    entries_taken += 1
                    
                    # Update entry status
                    entry.mark_processing_started()
                    self._entries_by_status[ProcessingStatus.PENDING].remove(entry)
                    self._entries_by_status[ProcessingStatus.PROCESSING].append(entry)
            
            # Check timeout
            if time.time() - batch_start_time >= self.batch_timeout:
                break
        
        return batch
    
    def _get_optimal_batch_size(self) -> int:
        """Get optimal batch size based on performance history."""
        if not self.adaptive_batching:
            return self.batch_size
        
        # Use performance optimizer's recommendation
        optimizer_size = self.performance_optimizer.get_optimal_batch_size()
        
        # Combine with our own analysis
        if self._batch_performance_history:
            # Analyze recent performance
            recent_batches = list(self._batch_performance_history)[-10:]
            
            # Find the batch size with best throughput
            throughput_by_size = defaultdict(list)
            for size, duration in recent_batches:
                if duration > 0:
                    throughput = size / duration
                    throughput_by_size[size].append(throughput)
            
            if throughput_by_size:
                # Get average throughput for each size
                avg_throughput_by_size = {
                    size: sum(throughputs) / len(throughputs)
                    for size, throughputs in throughput_by_size.items()
                }
                
                # Find best performing size
                best_size = max(avg_throughput_by_size.keys(), 
                              key=lambda s: avg_throughput_by_size[s])
                
                # Adapt towards best size
                current_size = self._optimal_batch_size
                if best_size > current_size:
                    self._optimal_batch_size = min(
                        self._max_batch_size,
                        int(current_size * (1 + self._batch_adaptation_factor))
                    )
                elif best_size < current_size:
                    self._optimal_batch_size = max(
                        self._min_batch_size,
                        int(current_size * (1 - self._batch_adaptation_factor))
                    )
        
        # Use the better of optimizer recommendation or our analysis
        return max(optimizer_size, self._optimal_batch_size)
    
    async def _process_batch(self, batch: List[LogEntry]) -> None:
        """Process a batch with performance tracking and optimization."""
        if not batch or not self._batch_processor:
            return
        
        batch_start_time = time.time()
        batch_size = len(batch)
        
        logger.debug(f"Processing optimized batch of {batch_size} entries")
        
        try:
            # Check memory before processing if optimization is enabled
            if self.memory_optimization and self._should_check_memory():
                await self._check_and_optimize_memory()
            
            # Use cached batch processing if available
            batch_key = self._get_batch_cache_key(batch)
            cached_result = self._get_cached_batch_result(batch_key)
            
            if cached_result:
                logger.debug(f"Using cached result for batch {batch_key}")
                # Apply cached result
                await self._apply_cached_batch_result(batch, cached_result)
            else:
                # Process batch normally
                await self._batch_processor(batch)
                
                # Cache result if beneficial
                if self._should_cache_batch_result(batch):
                    result = self._extract_batch_result(batch)
                    self._cache_batch_result(batch_key, result)
            
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
            self._completed_count += batch_size
            
            # Record batch performance for adaptive sizing
            self._batch_performance_history.append((batch_size, batch_time))
            
            # Update performance optimizer
            self.performance_optimizer.record_batch_processing(batch_size, batch_time)
            
            logger.debug(f"Completed optimized batch of {batch_size} entries in {batch_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error processing optimized batch: {e}")
            
            # Handle batch failure with optimization
            await self._handle_batch_failure(batch, e)
    
    def _should_check_memory(self) -> bool:
        """Check if memory should be checked."""
        return time.time() - self._last_memory_check > self._memory_check_interval
    
    async def _check_and_optimize_memory(self) -> None:
        """Check memory usage and optimize if needed."""
        try:
            self._last_memory_check = time.time()
            
            if self.performance_optimizer.should_trigger_memory_cleanup():
                logger.info("High memory usage detected, performing optimization")
                
                # Perform memory cleanup
                cleanup_result = await self.performance_optimizer.perform_memory_cleanup()
                
                # Clear completed entries
                await self.clear_completed_entries(max_age_hours=1)
                
                # Clear batch cache
                self._clear_old_batch_cache()
                
                # Optimize entry pool
                self._optimize_entry_pool()
                
                logger.info(f"Memory optimization completed: {cleanup_result}")
        
        except Exception as e:
            logger.error(f"Error during memory optimization: {e}")
    
    def _get_batch_cache_key(self, batch: List[LogEntry]) -> str:
        """Generate cache key for batch."""
        # Simple hash based on entry IDs and content hashes
        content_hash = hash(tuple(
            (entry.entry_id, hash(entry.content[:100]))  # Use first 100 chars
            for entry in batch[:10]  # Use first 10 entries
        ))
        return f"batch_{len(batch)}_{content_hash}"
    
    def _get_cached_batch_result(self, batch_key: str) -> Optional[Any]:
        """Get cached batch result."""
        if batch_key in self._batch_cache:
            result, timestamp = self._batch_cache[batch_key]
            if time.time() - timestamp < self._batch_cache_ttl:
                return result
            else:
                del self._batch_cache[batch_key]
        return None
    
    def _should_cache_batch_result(self, batch: List[LogEntry]) -> bool:
        """Check if batch result should be cached."""
        # Cache results for batches with similar content patterns
        return len(batch) > 5 and len(self._batch_cache) < 100
    
    def _cache_batch_result(self, batch_key: str, result: Any) -> None:
        """Cache batch processing result."""
        self._batch_cache[batch_key] = (result, time.time())
    
    def _extract_batch_result(self, batch: List[LogEntry]) -> Any:
        """Extract result from processed batch for caching."""
        # This would extract relevant processing results
        # Implementation depends on what results need to be cached
        return {"processed": True, "count": len(batch)}
    
    async def _apply_cached_batch_result(self, batch: List[LogEntry], cached_result: Any) -> None:
        """Apply cached result to batch."""
        # This would apply the cached processing result
        # Implementation depends on what results were cached
        pass
    
    def _clear_old_batch_cache(self) -> None:
        """Clear old entries from batch cache."""
        current_time = time.time()
        keys_to_remove = []
        
        for key, (result, timestamp) in self._batch_cache.items():
            if current_time - timestamp > self._batch_cache_ttl:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._batch_cache[key]
    
    def _optimize_entry_pool(self) -> None:
        """Optimize the entry pool for memory efficiency."""
        # Keep pool size within limits
        if len(self._entry_pool) > self._pool_size_limit:
            self._entry_pool = self._entry_pool[:self._pool_size_limit // 2]
    
    async def _handle_batch_failure(self, batch: List[LogEntry], error: Exception) -> None:
        """Handle batch processing failure with optimization."""
        async with self._queue_lock:
            for entry in batch:
                entry.mark_processing_failed(str(error))
                self._entries_by_status[ProcessingStatus.PROCESSING].remove(entry)
                
                # Check if entry can be retried
                if entry.can_retry():
                    entry.mark_for_retry()
                    
                    # Re-queue to appropriate priority queue
                    priority_queue = self._priority_queues[entry.priority]
                    heapq.heappush(priority_queue, entry)
                    self._entries_by_status[ProcessingStatus.RETRYING].append(entry)
                    
                    logger.info(f"Re-queued entry {entry.entry_id} for retry {entry.retry_count}")
                else:
                    self._entries_by_status[ProcessingStatus.FAILED].append(entry)
                    logger.error(f"Entry {entry.entry_id} failed permanently after {entry.retry_count} retries")
        
        # Call error handler if available
        if self._error_handler:
            for entry in batch:
                try:
                    self._error_handler(entry, error)
                except Exception as handler_error:
                    logger.error(f"Error in error handler: {handler_error}")
    
    async def _monitor_resources_continuously(self) -> None:
        """Continuously monitor and optimize resource usage."""
        while not self._shutdown_event.is_set():
            try:
                # Check memory usage
                if self._should_check_memory():
                    await self._check_and_optimize_memory()
                
                # Clean up completed entries periodically
                if time.time() % 300 < 30:  # Every 5 minutes
                    cleared = await self.clear_completed_entries(max_age_hours=2)
                    if cleared > 0:
                        logger.debug(f"Cleared {cleared} old completed entries")
                
                # Update optimization metrics
                self._update_optimization_metrics()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                await asyncio.sleep(30)
    
    def _update_optimization_metrics(self) -> None:
        """Update optimization-specific metrics."""
        # Update health metrics with optimization info
        self.update_health_metric("optimal_batch_size", self._optimal_batch_size)
        self.update_health_metric("batch_cache_size", len(self._batch_cache))
        self.update_health_metric("entry_pool_size", len(self._entry_pool))
        
        # Update performance metrics
        total_queue_size = sum(len(q) for q in self._priority_queues.values())
        self.update_health_metric("priority_queue_distribution", {
            priority.name: len(queue) 
            for priority, queue in self._priority_queues.items()
        })
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization-specific statistics."""
        return {
            'adaptive_batching': {
                'enabled': self.adaptive_batching,
                'optimal_batch_size': self._optimal_batch_size,
                'min_batch_size': self._min_batch_size,
                'max_batch_size': self._max_batch_size,
                'performance_history_size': len(self._batch_performance_history)
            },
            'memory_optimization': {
                'enabled': self.memory_optimization,
                'last_memory_check': self._last_memory_check,
                'cleanup_threshold': self._memory_cleanup_threshold,
                'entry_pool_size': len(self._entry_pool),
                'pool_size_limit': self._pool_size_limit
            },
            'batch_caching': {
                'cache_size': len(self._batch_cache),
                'cache_ttl': self._batch_cache_ttl,
                'cache_hit_rate': self._calculate_cache_hit_rate()
            },
            'priority_queues': {
                priority.name: len(queue)
                for priority, queue in self._priority_queues.items()
            },
            'resource_usage': {
                'total_queue_size': sum(len(q) for q in self._priority_queues.values()),
                'backpressure_active': self._backpressure_active,
                'dropped_entries': self._dropped_entries
            }
        }
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate batch cache hit rate."""
        # This would track cache hits/misses
        # For now, return a placeholder
        return 0.0