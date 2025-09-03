"""
Performance optimization utilities for real-time log processing.

This module provides performance optimizations including caching strategies,
connection pooling, resource management, and processing optimizations.
"""

import asyncio
import logging
import time
import weakref
from typing import Dict, Any, List, Optional, Callable, Set, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import threading
import gc
from functools import lru_cache, wraps
import psutil
import os

from .base import RealtimeComponent, HealthMonitorMixin
from .exceptions import PerformanceError

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics tracking."""
    
    # CPU and Memory
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    memory_available: int = 0
    
    # Processing metrics
    processing_rate: float = 0.0
    queue_throughput: float = 0.0
    avg_response_time: float = 0.0
    
    # Cache metrics
    cache_hit_rate: float = 0.0
    cache_size: int = 0
    cache_evictions: int = 0
    
    # Connection pool metrics
    active_connections: int = 0
    pool_utilization: float = 0.0
    connection_wait_time: float = 0.0
    
    # Resource metrics
    file_descriptors: int = 0
    thread_count: int = 0
    async_tasks: int = 0
    
    # Timestamps
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'memory_available': self.memory_available,
            'processing_rate': self.processing_rate,
            'queue_throughput': self.queue_throughput,
            'avg_response_time': self.avg_response_time,
            'cache_hit_rate': self.cache_hit_rate,
            'cache_size': self.cache_size,
            'cache_evictions': self.cache_evictions,
            'active_connections': self.active_connections,
            'pool_utilization': self.pool_utilization,
            'connection_wait_time': self.connection_wait_time,
            'file_descriptors': self.file_descriptors,
            'thread_count': self.thread_count,
            'async_tasks': self.async_tasks,
            'last_updated': self.last_updated.isoformat()
        }


class ConfigurationCache:
    """High-performance configuration caching with intelligent invalidation."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """
        Initialize configuration cache.
        
        Args:
            max_size: Maximum number of cached items
            ttl_seconds: Time-to-live for cached items
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._access_times: Dict[str, datetime] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            value, timestamp = self._cache[key]
            
            # Check TTL
            if datetime.now(timezone.utc) - timestamp > timedelta(seconds=self.ttl_seconds):
                del self._cache[key]
                self._access_times.pop(key, None)
                self._misses += 1
                return None
            
            # Update access time
            self._access_times[key] = datetime.now(timezone.utc)
            self._hits += 1
            return value
    
    def set(self, key: str, value: Any) -> None:
        """Set item in cache."""
        with self._lock:
            now = datetime.now(timezone.utc)
            
            # Evict if at capacity
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()
            
            self._cache[key] = (value, now)
            self._access_times[key] = now
    
    def invalidate(self, key: str) -> None:
        """Invalidate specific cache entry."""
        with self._lock:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern."""
        with self._lock:
            keys_to_remove = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]
                self._access_times.pop(key, None)
            return len(keys_to_remove)
    
    def clear(self) -> None:
        """Clear entire cache."""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
    
    def _evict_lru(self) -> None:
        """Evict least recently used item."""
        if not self._access_times:
            return
        
        lru_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        del self._cache[lru_key]
        del self._access_times[lru_key]
        self._evictions += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': hit_rate,
                'evictions': self._evictions,
                'ttl_seconds': self.ttl_seconds
            }


class ConnectionPool:
    """High-performance connection pool for database and external services."""
    
    def __init__(
        self,
        create_connection: Callable,
        max_connections: int = 20,
        min_connections: int = 5,
        max_idle_time: int = 300,
        connection_timeout: float = 30.0
    ):
        """
        Initialize connection pool.
        
        Args:
            create_connection: Function to create new connections
            max_connections: Maximum number of connections
            min_connections: Minimum number of connections to maintain
            max_idle_time: Maximum idle time before connection is closed
            connection_timeout: Timeout for acquiring connections
        """
        self.create_connection = create_connection
        self.max_connections = max_connections
        self.min_connections = min_connections
        self.max_idle_time = max_idle_time
        self.connection_timeout = connection_timeout
        
        self._pool: deque = deque()
        self._active_connections: Set[Any] = set()
        self._connection_times: Dict[Any, datetime] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_connections)
        
        # Statistics
        self._total_created = 0
        self._total_closed = 0
        self._wait_times: deque = deque(maxlen=100)
    
    async def acquire(self) -> Any:
        """Acquire a connection from the pool."""
        start_time = time.time()
        
        async with self._semaphore:
            async with self._lock:
                # Try to get from pool
                while self._pool:
                    conn = self._pool.popleft()
                    conn_time = self._connection_times.get(conn)
                    
                    # Check if connection is still valid
                    if conn_time and (datetime.now(timezone.utc) - conn_time).total_seconds() < self.max_idle_time:
                        if await self._validate_connection(conn):
                            self._active_connections.add(conn)
                            wait_time = time.time() - start_time
                            self._wait_times.append(wait_time)
                            return conn
                    
                    # Connection is stale, close it
                    await self._close_connection(conn)
                
                # Create new connection
                try:
                    conn = await self.create_connection()
                    self._total_created += 1
                    self._active_connections.add(conn)
                    self._connection_times[conn] = datetime.now(timezone.utc)
                    
                    wait_time = time.time() - start_time
                    self._wait_times.append(wait_time)
                    return conn
                
                except Exception as e:
                    logger.error(f"Failed to create connection: {e}")
                    raise
    
    async def release(self, conn: Any) -> None:
        """Release a connection back to the pool."""
        async with self._lock:
            if conn in self._active_connections:
                self._active_connections.remove(conn)
                
                # Return to pool if under max size
                if len(self._pool) < self.max_connections:
                    self._connection_times[conn] = datetime.now(timezone.utc)
                    self._pool.append(conn)
                else:
                    # Pool is full, close connection
                    await self._close_connection(conn)
    
    async def _validate_connection(self, conn: Any) -> bool:
        """Validate that a connection is still usable."""
        try:
            # Basic validation - can be overridden for specific connection types
            return hasattr(conn, 'ping') and await conn.ping() or True
        except Exception:
            return False
    
    async def _close_connection(self, conn: Any) -> None:
        """Close a connection."""
        try:
            if hasattr(conn, 'close'):
                await conn.close()
            self._total_closed += 1
            self._connection_times.pop(conn, None)
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")
    
    async def cleanup_idle_connections(self) -> int:
        """Clean up idle connections."""
        cleaned = 0
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=self.max_idle_time)
        
        async with self._lock:
            connections_to_remove = []
            
            for conn in list(self._pool):
                conn_time = self._connection_times.get(conn)
                if conn_time and conn_time < cutoff_time:
                    connections_to_remove.append(conn)
            
            for conn in connections_to_remove:
                self._pool.remove(conn)
                await self._close_connection(conn)
                cleaned += 1
        
        return cleaned
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        avg_wait_time = sum(self._wait_times) / len(self._wait_times) if self._wait_times else 0.0
        
        return {
            'pool_size': len(self._pool),
            'active_connections': len(self._active_connections),
            'max_connections': self.max_connections,
            'min_connections': self.min_connections,
            'total_created': self._total_created,
            'total_closed': self._total_closed,
            'avg_wait_time': avg_wait_time,
            'utilization': len(self._active_connections) / self.max_connections
        }
    
    @asynccontextmanager
    async def connection(self):
        """Context manager for acquiring and releasing connections."""
        conn = await self.acquire()
        try:
            yield conn
        finally:
            await self.release(conn)


class BatchProcessor:
    """Optimized batch processing with adaptive sizing."""
    
    def __init__(
        self,
        min_batch_size: int = 10,
        max_batch_size: int = 1000,
        target_processing_time: float = 1.0,
        adaptation_factor: float = 0.1
    ):
        """
        Initialize batch processor.
        
        Args:
            min_batch_size: Minimum batch size
            max_batch_size: Maximum batch size
            target_processing_time: Target processing time per batch
            adaptation_factor: Factor for batch size adaptation
        """
        self.min_batch_size = min_batch_size
        self.max_batch_size = max_batch_size
        self.target_processing_time = target_processing_time
        self.adaptation_factor = adaptation_factor
        
        self.current_batch_size = min_batch_size
        self._processing_times: deque = deque(maxlen=10)
        self._batch_sizes: deque = deque(maxlen=10)
    
    def get_optimal_batch_size(self) -> int:
        """Get the current optimal batch size."""
        return self.current_batch_size
    
    def record_batch_processing(self, batch_size: int, processing_time: float) -> None:
        """Record batch processing metrics and adapt batch size."""
        self._processing_times.append(processing_time)
        self._batch_sizes.append(batch_size)
        
        # Adapt batch size based on performance
        if len(self._processing_times) >= 3:
            avg_time = sum(self._processing_times) / len(self._processing_times)
            
            if avg_time < self.target_processing_time * 0.8:
                # Processing is fast, increase batch size
                new_size = min(
                    self.max_batch_size,
                    int(self.current_batch_size * (1 + self.adaptation_factor))
                )
            elif avg_time > self.target_processing_time * 1.2:
                # Processing is slow, decrease batch size
                new_size = max(
                    self.min_batch_size,
                    int(self.current_batch_size * (1 - self.adaptation_factor))
                )
            else:
                # Processing time is acceptable, keep current size
                new_size = self.current_batch_size
            
            if new_size != self.current_batch_size:
                logger.debug(f"Adapting batch size from {self.current_batch_size} to {new_size}")
                self.current_batch_size = new_size
    
    def get_stats(self) -> Dict[str, Any]:
        """Get batch processing statistics."""
        avg_time = sum(self._processing_times) / len(self._processing_times) if self._processing_times else 0.0
        avg_size = sum(self._batch_sizes) / len(self._batch_sizes) if self._batch_sizes else 0.0
        
        return {
            'current_batch_size': self.current_batch_size,
            'min_batch_size': self.min_batch_size,
            'max_batch_size': self.max_batch_size,
            'avg_processing_time': avg_time,
            'avg_batch_size': avg_size,
            'target_processing_time': self.target_processing_time
        }


class MemoryManager:
    """Memory management and optimization utilities."""
    
    def __init__(self, memory_threshold: float = 0.8, gc_interval: int = 60):
        """
        Initialize memory manager.
        
        Args:
            memory_threshold: Memory usage threshold to trigger cleanup
            gc_interval: Garbage collection interval in seconds
        """
        self.memory_threshold = memory_threshold
        self.gc_interval = gc_interval
        self._last_gc = time.time()
        self._memory_samples: deque = deque(maxlen=100)
    
    def check_memory_usage(self) -> float:
        """Check current memory usage."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            system_memory = psutil.virtual_memory()
            
            usage_ratio = memory_info.rss / system_memory.total
            self._memory_samples.append(usage_ratio)
            
            return usage_ratio
        except Exception as e:
            logger.warning(f"Failed to check memory usage: {e}")
            return 0.0
    
    def should_trigger_cleanup(self) -> bool:
        """Check if memory cleanup should be triggered."""
        current_usage = self.check_memory_usage()
        return current_usage > self.memory_threshold
    
    def perform_cleanup(self) -> Dict[str, Any]:
        """Perform memory cleanup operations."""
        start_memory = self.check_memory_usage()
        
        # Force garbage collection
        collected = gc.collect()
        
        # Update last GC time
        self._last_gc = time.time()
        
        end_memory = self.check_memory_usage()
        memory_freed = start_memory - end_memory
        
        logger.info(f"Memory cleanup: freed {memory_freed:.2%} memory, collected {collected} objects")
        
        return {
            'objects_collected': collected,
            'memory_before': start_memory,
            'memory_after': end_memory,
            'memory_freed': memory_freed,
            'cleanup_time': time.time() - self._last_gc
        }
    
    def should_perform_gc(self) -> bool:
        """Check if garbage collection should be performed."""
        return time.time() - self._last_gc > self.gc_interval
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            system_memory = psutil.virtual_memory()
            
            avg_usage = sum(self._memory_samples) / len(self._memory_samples) if self._memory_samples else 0.0
            
            return {
                'current_usage': memory_info.rss / system_memory.total,
                'avg_usage': avg_usage,
                'rss_bytes': memory_info.rss,
                'vms_bytes': memory_info.vms,
                'system_total': system_memory.total,
                'system_available': system_memory.available,
                'system_percent': system_memory.percent,
                'threshold': self.memory_threshold,
                'last_gc': self._last_gc
            }
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {'error': str(e)}


class PerformanceOptimizer(RealtimeComponent, HealthMonitorMixin):
    """
    Main performance optimization coordinator.
    
    Manages caching, connection pooling, batch processing optimization,
    and resource management for the real-time system.
    """
    
    def __init__(
        self,
        cache_size: int = 1000,
        cache_ttl: int = 300,
        max_connections: int = 20,
        memory_threshold: float = 0.8
    ):
        """
        Initialize performance optimizer.
        
        Args:
            cache_size: Maximum cache size
            cache_ttl: Cache time-to-live in seconds
            max_connections: Maximum database connections
            memory_threshold: Memory usage threshold for cleanup
        """
        RealtimeComponent.__init__(self, "PerformanceOptimizer")
        HealthMonitorMixin.__init__(self)
        
        # Initialize components
        self.config_cache = ConfigurationCache(cache_size, cache_ttl)
        self.batch_processor = BatchProcessor()
        self.memory_manager = MemoryManager(memory_threshold)
        
        # Connection pools (will be initialized when needed)
        self._connection_pools: Dict[str, ConnectionPool] = {}
        
        # Performance monitoring
        self._metrics = PerformanceMetrics()
        self._metrics_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Optimization settings
        self.optimization_interval = 30.0  # seconds
        self.cleanup_interval = 300.0  # seconds
    
    async def _start_impl(self) -> None:
        """Start the performance optimizer."""
        logger.info("Starting performance optimizer")
        
        # Start background tasks
        self._metrics_task = asyncio.create_task(self._update_metrics_continuously())
        self._cleanup_task = asyncio.create_task(self._cleanup_continuously())
        
        # Initialize health metrics
        self.update_health_metric("cache_hit_rate", 0.0)
        self.update_health_metric("memory_usage", 0.0)
        self.update_health_metric("connection_pool_utilization", 0.0)
    
    async def _stop_impl(self) -> None:
        """Stop the performance optimizer."""
        logger.info("Stopping performance optimizer")
        
        # Cancel background tasks
        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close connection pools
        for pool in self._connection_pools.values():
            await pool.cleanup_idle_connections()
    
    def get_connection_pool(self, pool_name: str, create_connection: Callable) -> ConnectionPool:
        """Get or create a connection pool."""
        if pool_name not in self._connection_pools:
            self._connection_pools[pool_name] = ConnectionPool(create_connection)
        return self._connection_pools[pool_name]
    
    def cache_get(self, key: str) -> Optional[Any]:
        """Get item from configuration cache."""
        return self.config_cache.get(key)
    
    def cache_set(self, key: str, value: Any) -> None:
        """Set item in configuration cache."""
        self.config_cache.set(key, value)
    
    def cache_invalidate(self, key: str) -> None:
        """Invalidate cache entry."""
        self.config_cache.invalidate(key)
    
    def get_optimal_batch_size(self) -> int:
        """Get optimal batch size for processing."""
        return self.batch_processor.get_optimal_batch_size()
    
    def record_batch_processing(self, batch_size: int, processing_time: float) -> None:
        """Record batch processing metrics."""
        self.batch_processor.record_batch_processing(batch_size, processing_time)
    
    def should_trigger_memory_cleanup(self) -> bool:
        """Check if memory cleanup should be triggered."""
        return self.memory_manager.should_trigger_cleanup()
    
    async def perform_memory_cleanup(self) -> Dict[str, Any]:
        """Perform memory cleanup."""
        return self.memory_manager.perform_cleanup()
    
    def get_performance_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        return self._metrics
    
    async def _update_metrics_continuously(self) -> None:
        """Continuously update performance metrics."""
        while not self._shutdown_event.is_set():
            try:
                await self._update_metrics()
                await asyncio.sleep(self.optimization_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error updating performance metrics: {e}")
                await asyncio.sleep(self.optimization_interval)
    
    async def _update_metrics(self) -> None:
        """Update performance metrics."""
        try:
            # System metrics
            process = psutil.Process()
            self._metrics.cpu_usage = process.cpu_percent()
            
            memory_info = process.memory_info()
            system_memory = psutil.virtual_memory()
            self._metrics.memory_usage = memory_info.rss / system_memory.total
            self._metrics.memory_available = system_memory.available
            
            # Cache metrics
            cache_stats = self.config_cache.get_stats()
            self._metrics.cache_hit_rate = cache_stats['hit_rate']
            self._metrics.cache_size = cache_stats['size']
            self._metrics.cache_evictions = cache_stats['evictions']
            
            # Connection pool metrics
            if self._connection_pools:
                total_active = sum(pool.get_stats()['active_connections'] for pool in self._connection_pools.values())
                total_max = sum(pool.get_stats()['max_connections'] for pool in self._connection_pools.values())
                self._metrics.active_connections = total_active
                self._metrics.pool_utilization = total_active / total_max if total_max > 0 else 0.0
                
                avg_wait_time = sum(pool.get_stats()['avg_wait_time'] for pool in self._connection_pools.values())
                self._metrics.connection_wait_time = avg_wait_time / len(self._connection_pools)
            
            # Resource metrics
            self._metrics.file_descriptors = process.num_fds() if hasattr(process, 'num_fds') else 0
            self._metrics.thread_count = process.num_threads()
            
            # Count async tasks
            try:
                loop = asyncio.get_event_loop()
                self._metrics.async_tasks = len([task for task in asyncio.all_tasks(loop) if not task.done()])
            except Exception:
                self._metrics.async_tasks = 0
            
            self._metrics.last_updated = datetime.now(timezone.utc)
            
            # Update health metrics
            self.update_health_metric("cpu_usage", self._metrics.cpu_usage)
            self.update_health_metric("memory_usage", self._metrics.memory_usage)
            self.update_health_metric("cache_hit_rate", self._metrics.cache_hit_rate)
            self.update_health_metric("pool_utilization", self._metrics.pool_utilization)
            
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
    
    async def _cleanup_continuously(self) -> None:
        """Continuously perform cleanup operations."""
        while not self._shutdown_event.is_set():
            try:
                await self._perform_cleanup()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                await asyncio.sleep(self.cleanup_interval)
    
    async def _perform_cleanup(self) -> None:
        """Perform periodic cleanup operations."""
        try:
            # Clean up idle connections
            for pool_name, pool in self._connection_pools.items():
                cleaned = await pool.cleanup_idle_connections()
                if cleaned > 0:
                    logger.debug(f"Cleaned up {cleaned} idle connections from pool {pool_name}")
            
            # Perform garbage collection if needed
            if self.memory_manager.should_perform_gc():
                cleanup_result = self.memory_manager.perform_cleanup()
                logger.debug(f"Garbage collection: {cleanup_result}")
            
            # Check memory usage and trigger cleanup if needed
            if self.memory_manager.should_trigger_cleanup():
                logger.warning("High memory usage detected, performing cleanup")
                await self.perform_memory_cleanup()
            
        except Exception as e:
            logger.error(f"Error during cleanup operations: {e}")
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """Get comprehensive optimization report."""
        return {
            'performance_metrics': self._metrics.to_dict(),
            'cache_stats': self.config_cache.get_stats(),
            'batch_processor_stats': self.batch_processor.get_stats(),
            'memory_stats': self.memory_manager.get_memory_stats(),
            'connection_pools': {
                name: pool.get_stats() 
                for name, pool in self._connection_pools.items()
            },
            'optimization_settings': {
                'optimization_interval': self.optimization_interval,
                'cleanup_interval': self.cleanup_interval,
                'cache_ttl': self.config_cache.ttl_seconds,
                'memory_threshold': self.memory_manager.memory_threshold
            }
        }


# Global performance optimizer instance
_performance_optimizer: Optional[PerformanceOptimizer] = None


def get_performance_optimizer() -> PerformanceOptimizer:
    """Get the global performance optimizer instance."""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer()
    return _performance_optimizer


def performance_cache(ttl: int = 300):
    """Decorator for caching function results with performance optimization."""
    def decorator(func: Callable) -> Callable:
        cache_key_prefix = f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            optimizer = get_performance_optimizer()
            cache_key = f"{cache_key_prefix}:{hash((args, tuple(sorted(kwargs.items()))))}"
            
            # Try cache first
            cached_result = optimizer.cache_get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            optimizer.cache_set(cache_key, result)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            optimizer = get_performance_optimizer()
            cache_key = f"{cache_key_prefix}:{hash((args, tuple(sorted(kwargs.items()))))}"
            
            # Try cache first
            cached_result = optimizer.cache_get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            optimizer.cache_set(cache_key, result)
            
            return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator