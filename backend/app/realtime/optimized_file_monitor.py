"""
Optimized file system monitoring with performance enhancements.

This module provides an optimized version of the file monitor with
caching, connection pooling, and resource management optimizations.
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable, Any
from datetime import datetime, timezone
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import fnmatch

from .file_monitor import LogFileMonitor, LogEntry, FileChangeHandler
from .models import LogSourceConfig, LogSourceType, MonitoringStatus
from .performance_optimizer import get_performance_optimizer, performance_cache
from .exceptions import MonitoringError

logger = logging.getLogger(__name__)


class OptimizedFileChangeHandler(FileChangeHandler):
    """Optimized file change handler with batching and caching."""
    
    def __init__(self, monitor: 'OptimizedLogFileMonitor'):
        super().__init__(monitor)
        self.monitor = monitor
        self._pending_changes: Dict[str, float] = {}  # file_path -> timestamp
        self._batch_delay = 0.1  # seconds to batch file changes
        self._batch_task: Optional[asyncio.Task] = None
    
    def on_modified(self, event):
        """Handle file modification events with batching."""
        if event.is_directory:
            return
        
        # Batch file changes to avoid processing rapid successive changes
        self._pending_changes[event.src_path] = time.time()
        
        if self._batch_task is None or self._batch_task.done():
            try:
                loop = asyncio.get_event_loop()
                self._batch_task = loop.call_later(
                    self._batch_delay,
                    lambda: asyncio.create_task(self._process_batched_changes())
                )
            except RuntimeError:
                # No event loop, process immediately
                self.monitor._handle_file_change(event.src_path, 'modified')
    
    def on_created(self, event):
        """Handle file creation events with batching."""
        if event.is_directory:
            return
        
        # File creation is processed immediately as it's less frequent
        try:
            self.monitor._handle_file_change(event.src_path, 'created')
        except Exception as e:
            self.logger.error(f"Error handling file creation {event.src_path}: {e}")
    
    async def _process_batched_changes(self):
        """Process batched file changes."""
        if not self._pending_changes:
            return
        
        changes_to_process = self._pending_changes.copy()
        self._pending_changes.clear()
        
        for file_path, timestamp in changes_to_process.items():
            try:
                await self.monitor._handle_file_change_async(file_path, 'modified')
            except Exception as e:
                self.logger.error(f"Error processing batched change {file_path}: {e}")


class OptimizedLogFileMonitor(LogFileMonitor):
    """
    Optimized log file monitor with performance enhancements.
    
    Includes caching, batching, resource optimization, and
    intelligent file reading strategies.
    """
    
    def __init__(self, name: str = "OptimizedLogFileMonitor"):
        super().__init__(name)
        
        # Replace event handler with optimized version
        self.event_handler = OptimizedFileChangeHandler(self)
        
        # Performance optimizer integration
        self.performance_optimizer = get_performance_optimizer()
        
        # Optimized settings
        self.chunk_size = 16384  # Larger chunks for better I/O performance
        self.max_line_length = 50000  # Increased for better handling
        self.read_ahead_size = 65536  # Read-ahead buffer size
        
        # File metadata cache
        self._file_metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 60  # seconds
        
        # Batch processing for file reads
        self._read_batch_size = 10
        self._pending_reads: List[tuple] = []
        self._read_batch_task: Optional[asyncio.Task] = None
        
        # Resource optimization
        self._file_handles: Dict[str, Any] = {}  # Keep file handles open for frequently accessed files
        self._handle_access_times: Dict[str, float] = {}
        self._max_open_handles = 50
        self._handle_cleanup_interval = 300  # seconds
    
    async def _start_impl(self) -> None:
        """Start the optimized file monitor."""
        await super()._start_impl()
        
        # Start handle cleanup task
        self._handle_cleanup_task = asyncio.create_task(self._cleanup_file_handles_continuously())
        
        logger.info(f"Optimized file monitor {self.name} started with enhanced performance features")
    
    async def _stop_impl(self) -> None:
        """Stop the optimized file monitor."""
        # Cancel handle cleanup task
        if hasattr(self, '_handle_cleanup_task') and self._handle_cleanup_task:
            self._handle_cleanup_task.cancel()
            try:
                await self._handle_cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all file handles
        await self._close_all_file_handles()
        
        await super()._stop_impl()
    
    @performance_cache(ttl=60)
    async def _get_file_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get cached file metadata."""
        try:
            path = Path(file_path)
            if not path.exists():
                return None
            
            stat = path.stat()
            return {
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'inode': stat.st_ino,
                'exists': True
            }
        except Exception as e:
            logger.warning(f"Failed to get metadata for {file_path}: {e}")
            return None
    
    async def _handle_file_change_async(self, file_path: str, event_type: str) -> None:
        """Async version of file change handling with optimizations."""
        try:
            # Check if we should process this file change
            if not await self._should_process_file_change(file_path):
                return
            
            # Find matching source configurations
            matching_sources = self._find_matching_sources(file_path)
            
            if not matching_sources:
                return
            
            # Batch process multiple sources for the same file
            await self._process_file_change_batch(matching_sources, file_path, event_type)
            
        except Exception as e:
            logger.error(f"Error in async file change handling {file_path}: {e}")
    
    async def _should_process_file_change(self, file_path: str) -> bool:
        """Check if file change should be processed based on metadata."""
        try:
            current_metadata = await self._get_file_metadata(file_path)
            if not current_metadata:
                return False
            
            # Check cache for previous metadata
            cache_key = f"metadata:{file_path}"
            cached_metadata = self.performance_optimizer.cache_get(cache_key)
            
            if cached_metadata:
                # Only process if file actually changed
                if (current_metadata['size'] == cached_metadata['size'] and 
                    current_metadata['mtime'] == cached_metadata['mtime']):
                    return False
            
            # Update cache
            self.performance_optimizer.cache_set(cache_key, current_metadata)
            return True
            
        except Exception as e:
            logger.warning(f"Error checking file change necessity for {file_path}: {e}")
            return True  # Process on error to be safe
    
    async def _process_file_change_batch(
        self, 
        sources: List[LogSourceConfig], 
        file_path: str, 
        event_type: str
    ) -> None:
        """Process file change for multiple sources in batch."""
        try:
            # Read file content once for all sources
            new_entries_by_source = await self._read_new_content_optimized(sources, file_path)
            
            # Process entries for each source
            for source_config, entries in new_entries_by_source.items():
                if entries:
                    await self._process_entries_for_source(source_config, entries)
            
        except Exception as e:
            logger.error(f"Error in batch file change processing {file_path}: {e}")
    
    async def _read_new_content_optimized(
        self, 
        sources: List[LogSourceConfig], 
        file_path: str
    ) -> Dict[LogSourceConfig, List[LogEntry]]:
        """Optimized file reading for multiple sources."""
        entries_by_source = {source: [] for source in sources}
        
        try:
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                return entries_by_source
            
            current_size = path.stat().st_size
            
            # Get the minimum offset across all sources
            min_offset = min(
                self.file_offsets.get(source.path, 0) 
                for source in sources
            )
            
            # Check if file was truncated
            if current_size < min_offset:
                logger.info(f"File {file_path} appears to have been rotated, resetting offsets")
                min_offset = 0
                for source in sources:
                    self.file_offsets[source.path] = 0
            
            # If no new content, return empty results
            if current_size <= min_offset:
                return entries_by_source
            
            # Use optimized file handle management
            file_handle = await self._get_file_handle(file_path)
            
            try:
                # Read new content efficiently
                file_handle.seek(min_offset)
                
                # Read in larger chunks for better performance
                buffer = ""
                bytes_to_read = current_size - min_offset
                
                while bytes_to_read > 0:
                    chunk_size = min(self.read_ahead_size, bytes_to_read)
                    chunk = file_handle.read(chunk_size)
                    if not chunk:
                        break
                    
                    buffer += chunk
                    bytes_to_read -= len(chunk.encode('utf-8'))
                
                # Process lines for each source
                lines = buffer.split('\n')
                current_offset = min_offset
                
                for i, line in enumerate(lines):
                    if not line.strip() and i == len(lines) - 1:
                        # Skip empty last line
                        continue
                    
                    line_size = len(line.encode('utf-8')) + 1  # +1 for newline
                    
                    # Create entries for each source that needs this line
                    for source in sources:
                        source_offset = self.file_offsets.get(source.path, 0)
                        
                        if current_offset >= source_offset:
                            # Limit line length
                            if len(line) > self.max_line_length:
                                line = line[:self.max_line_length] + "... [truncated]"
                            
                            entry = LogEntry(
                                content=line.strip(),
                                source_path=file_path,
                                source_name=source.source_name,
                                priority=source.priority,
                                file_offset=current_offset + line_size
                            )
                            entries_by_source[source].append(entry)
                    
                    current_offset += line_size
                
                # Update offsets for all sources
                for source in sources:
                    self.file_offsets[source.path] = current_size
                    self.file_sizes[source.path] = current_size
                    source.file_size = current_size
                    source.last_offset = current_size
            
            finally:
                # Don't close handle immediately - keep it for reuse
                self._handle_access_times[file_path] = time.time()
            
        except Exception as e:
            logger.error(f"Error in optimized content reading from {file_path}: {e}")
            raise
        
        return entries_by_source
    
    async def _get_file_handle(self, file_path: str):
        """Get or create a cached file handle."""
        if file_path in self._file_handles:
            self._handle_access_times[file_path] = time.time()
            return self._file_handles[file_path]
        
        # Clean up old handles if at limit
        if len(self._file_handles) >= self._max_open_handles:
            await self._cleanup_oldest_handles(self._max_open_handles // 2)
        
        try:
            handle = open(file_path, 'r', encoding='utf-8', errors='ignore')
            self._file_handles[file_path] = handle
            self._handle_access_times[file_path] = time.time()
            return handle
        except Exception as e:
            logger.error(f"Failed to open file handle for {file_path}: {e}")
            raise
    
    async def _cleanup_oldest_handles(self, count: int) -> None:
        """Clean up the oldest file handles."""
        if not self._handle_access_times:
            return
        
        # Sort by access time and close oldest
        sorted_handles = sorted(
            self._handle_access_times.items(),
            key=lambda x: x[1]
        )
        
        for file_path, _ in sorted_handles[:count]:
            await self._close_file_handle(file_path)
    
    async def _close_file_handle(self, file_path: str) -> None:
        """Close a specific file handle."""
        if file_path in self._file_handles:
            try:
                self._file_handles[file_path].close()
                del self._file_handles[file_path]
                del self._handle_access_times[file_path]
            except Exception as e:
                logger.warning(f"Error closing file handle for {file_path}: {e}")
    
    async def _close_all_file_handles(self) -> None:
        """Close all file handles."""
        for file_path in list(self._file_handles.keys()):
            await self._close_file_handle(file_path)
    
    async def _cleanup_file_handles_continuously(self) -> None:
        """Continuously clean up old file handles."""
        while not self._shutdown_event.is_set():
            try:
                current_time = time.time()
                handles_to_close = []
                
                for file_path, access_time in self._handle_access_times.items():
                    if current_time - access_time > self._handle_cleanup_interval:
                        handles_to_close.append(file_path)
                
                for file_path in handles_to_close:
                    await self._close_file_handle(file_path)
                
                if handles_to_close:
                    logger.debug(f"Cleaned up {len(handles_to_close)} idle file handles")
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in file handle cleanup: {e}")
                await asyncio.sleep(60)
    
    async def _process_entries_for_source(
        self, 
        source_config: LogSourceConfig, 
        entries: List[LogEntry]
    ) -> None:
        """Process entries for a specific source with optimizations."""
        try:
            start_time = time.time()
            
            # Process entries in batches for better performance
            batch_size = self.performance_optimizer.get_optimal_batch_size()
            
            for i in range(0, len(entries), batch_size):
                batch = entries[i:i + batch_size]
                
                # Call all registered callbacks for this batch
                for callback in self.log_entry_callbacks:
                    try:
                        # Process batch if callback supports it
                        if hasattr(callback, 'process_batch'):
                            await callback.process_batch(batch)
                        else:
                            # Process individually
                            for entry in batch:
                                callback(entry)
                    except Exception as e:
                        logger.error(f"Error in log entry callback: {e}")
            
            # Update metrics
            processing_time = time.time() - start_time
            self.entries_processed += len(entries)
            self.last_processing_time = processing_time
            
            # Record batch processing metrics
            self.performance_optimizer.record_batch_processing(len(entries), processing_time)
            
            # Update source status
            source_config.last_monitored = datetime.now(timezone.utc)
            source_config.status = MonitoringStatus.ACTIVE
            source_config.error_message = None
            
            # Update health metrics
            self.update_health_metric("entries_processed", self.entries_processed)
            self.update_health_metric("last_processing_time", self.last_processing_time)
            self.update_health_metric("avg_batch_size", len(entries))
            
            if entries:
                logger.debug(f"Processed {len(entries)} entries for {source_config.source_name} in {processing_time:.2f}s")
            
        except Exception as e:
            # Update source error status
            source_config.status = MonitoringStatus.ERROR
            source_config.error_message = str(e)
            
            self._handle_error(e, f"processing entries for source {source_config.source_name}")
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization-specific statistics."""
        return {
            'file_handles': {
                'open_handles': len(self._file_handles),
                'max_handles': self._max_open_handles,
                'handle_utilization': len(self._file_handles) / self._max_open_handles
            },
            'cache_stats': {
                'metadata_cache_size': len(self._file_metadata_cache),
                'cache_ttl': self._cache_ttl
            },
            'performance_settings': {
                'chunk_size': self.chunk_size,
                'read_ahead_size': self.read_ahead_size,
                'max_line_length': self.max_line_length,
                'read_batch_size': self._read_batch_size
            },
            'resource_usage': {
                'entries_processed': self.entries_processed,
                'last_processing_time': self.last_processing_time,
                'avg_processing_rate': self.entries_processed / max(self.last_processing_time, 0.001)
            }
        }