"""
File system monitoring for real-time log detection.

This module implements file system monitoring using the watchdog library
to detect changes in log files and directories in real-time.
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable, Any
from datetime import datetime, timezone
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
import fnmatch

from .base import RealtimeComponent, HealthMonitorMixin
from .models import LogSourceConfig, LogSourceType, MonitoringStatus
from .exceptions import MonitoringError
from .ingestion_queue import LogEntry, LogEntryPriority, ProcessingStatus

logger = logging.getLogger(__name__)



class FileChangeHandler(FileSystemEventHandler):
    """
    Handles file system events for log file monitoring.
    """
    
    def __init__(self, monitor: 'LogFileMonitor'):
        super().__init__()
        self.monitor = monitor
        self.logger = logging.getLogger(f"{__name__}.FileChangeHandler")
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        try:
            self.monitor._handle_file_change(event.src_path, 'modified')
        except Exception as e:
            self.logger.error(f"Error handling file modification {event.src_path}: {e}")
    
    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
        
        try:
            self.monitor._handle_file_change(event.src_path, 'created')
        except Exception as e:
            self.logger.error(f"Error handling file creation {event.src_path}: {e}")


class LogFileMonitor(HealthMonitorMixin, RealtimeComponent):
    """
    Monitors log files and directories for changes using watchdog.
    
    Provides real-time detection of new log entries and manages
    file offsets to avoid processing duplicate content.
    """
    
    def __init__(self, name: str = "LogFileMonitor"):
        super().__init__(name)
        self.observer = Observer()
        self.event_handler = FileChangeHandler(self)
        
        # Configuration and state
        self.log_sources: Dict[str, LogSourceConfig] = {}
        self.file_offsets: Dict[str, int] = {}  # Track file read positions
        self.file_sizes: Dict[str, int] = {}    # Track file sizes
        self.watched_paths: Set[str] = set()    # Track watched directories
        
        # Callbacks for log entries
        self.log_entry_callbacks: List[Callable[[LogEntry], None]] = []
        
        # Performance tracking
        self.entries_processed = 0
        self.last_processing_time = 0.0
        
        # File reading settings
        self.chunk_size = 8192  # Read files in 8KB chunks
        
        # Event loop for async callbacks
        self._main_loop = None
        self.max_line_length = 10000  # Maximum line length to prevent memory issues
    
    async def _start_impl(self) -> None:
        """Start the file monitoring system."""
        try:
            # Store the main event loop for async callbacks
            self._main_loop = asyncio.get_event_loop()
            
            # Start the watchdog observer
            self.observer.start()
            logger.info(f"File monitor {self.name} started successfully")
            
            # Initialize file offsets for existing sources
            await self._initialize_file_offsets()
            
        except Exception as e:
            raise MonitoringError(f"Failed to start file monitor: {e}")
    
    async def _stop_impl(self) -> None:
        """Stop the file monitoring system."""
        try:
            # Stop the observer
            self.observer.stop()
            self.observer.join(timeout=5.0)
            
            # Clear state
            self.watched_paths.clear()
            self.file_offsets.clear()
            self.file_sizes.clear()
            
            logger.info(f"File monitor {self.name} stopped successfully")
            
        except Exception as e:
            raise MonitoringError(f"Failed to stop file monitor: {e}")
    
    def _convert_priority(self, priority: int) -> LogEntryPriority:
        """Convert integer priority to LogEntryPriority enum."""
        # Map integer priority (1-10) to LogEntryPriority
        # Higher numbers = higher priority in config, but lower numbers = higher priority in enum
        if priority >= 8:
            return LogEntryPriority.CRITICAL
        elif priority >= 6:
            return LogEntryPriority.HIGH
        elif priority >= 4:
            return LogEntryPriority.MEDIUM
        elif priority >= 2:
            return LogEntryPriority.LOW
        else:
            return LogEntryPriority.BULK
    
    def add_log_source(self, source_config: LogSourceConfig) -> bool:
        """
        Add a log source for monitoring.
        
        Args:
            source_config: Configuration for the log source
            
        Returns:
            True if source was added successfully
            
        Raises:
            MonitoringError: If source cannot be added
        """
        try:
            source_name = source_config.source_name
            
            # Check if source already exists
            if source_name in self.log_sources:
                logger.warning(f"Log source {source_name} already exists")
                return False
            
            # Validate the source path
            if not self._validate_source_path(source_config):
                raise MonitoringError(f"Invalid source path: {source_config.path}")
            
            # Add to sources
            self.log_sources[source_name] = source_config
            
            # Set up monitoring if enabled
            if source_config.enabled:
                self._setup_source_monitoring(source_config)
            
            logger.info(f"Added log source: {source_name} -> {source_config.path}")
            return True
            
        except Exception as e:
            self._handle_error(e, f"adding log source {source_config.source_name}")
            raise MonitoringError(f"Failed to add log source: {e}")
    
    def remove_log_source(self, source_name: str) -> bool:
        """
        Remove a log source from monitoring.
        
        Args:
            source_name: Name of the source to remove
            
        Returns:
            True if source was removed successfully
        """
        try:
            if source_name not in self.log_sources:
                logger.warning(f"Log source {source_name} not found")
                return False
            
            source_config = self.log_sources[source_name]
            
            # Remove monitoring
            self._remove_source_monitoring(source_config)
            
            # Clean up state
            del self.log_sources[source_name]
            self.file_offsets.pop(source_config.path, None)
            self.file_sizes.pop(source_config.path, None)
            
            logger.info(f"Removed log source: {source_name}")
            return True
            
        except Exception as e:
            self._handle_error(e, f"removing log source {source_name}")
            return False
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get detailed monitoring status for all sources."""
        status = {
            "total_sources": len(self.log_sources),
            "active_sources": 0,
            "inactive_sources": 0,
            "error_sources": 0,
            "watched_paths": len(self.watched_paths),
            "entries_processed": self.entries_processed,
            "last_processing_time": self.last_processing_time,
            "sources": {}
        }
        
        for name, config in self.log_sources.items():
            source_status = {
                "enabled": config.enabled,
                "status": config.status.value,
                "path": config.path,
                "last_monitored": config.last_monitored.isoformat() if config.last_monitored else None,
                "file_size": config.file_size,
                "last_offset": config.last_offset,
                "error_message": config.error_message
            }
            
            status["sources"][name] = source_status
            
            # Count by status
            if config.status == MonitoringStatus.ACTIVE:
                status["active_sources"] += 1
            elif config.status == MonitoringStatus.ERROR:
                status["error_sources"] += 1
            else:
                status["inactive_sources"] += 1
        
        return status
    
    def add_log_entry_callback(self, callback: Callable[[LogEntry], None]) -> None:
        """Add a callback to be called when new log entries are detected."""
        self.log_entry_callbacks.append(callback)
    
    def remove_log_entry_callback(self, callback: Callable[[LogEntry], None]) -> None:
        """Remove a log entry callback."""
        if callback in self.log_entry_callbacks:
            self.log_entry_callbacks.remove(callback)
    
    def _validate_source_path(self, source_config: LogSourceConfig) -> bool:
        """Validate that a source path is accessible and appropriate."""
        try:
            path = Path(source_config.path)
            
            if source_config.source_type == LogSourceType.FILE:
                # For files, check if it exists and is readable
                if not path.exists():
                    logger.warning(f"File does not exist: {source_config.path}")
                    return True  # Allow monitoring non-existent files (they might be created)
                
                if not path.is_file():
                    logger.error(f"Path is not a file: {source_config.path}")
                    return False
                
                # Check read permissions
                if not os.access(path, os.R_OK):
                    logger.error(f"No read permission for file: {source_config.path}")
                    return False
            
            elif source_config.source_type == LogSourceType.DIRECTORY:
                # For directories, check if it exists and is readable
                if not path.exists():
                    logger.error(f"Directory does not exist: {source_config.path}")
                    return False
                
                if not path.is_dir():
                    logger.error(f"Path is not a directory: {source_config.path}")
                    return False
                
                # Check read permissions
                if not os.access(path, os.R_OK):
                    logger.error(f"No read permission for directory: {source_config.path}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating source path {source_config.path}: {e}")
            return False
    
    def _setup_source_monitoring(self, source_config: LogSourceConfig) -> None:
        """Set up monitoring for a specific source."""
        try:
            if source_config.source_type == LogSourceType.FILE:
                # For files, monitor the parent directory
                parent_dir = str(Path(source_config.path).parent)
                if parent_dir not in self.watched_paths:
                    self.observer.schedule(self.event_handler, parent_dir, recursive=False)
                    self.watched_paths.add(parent_dir)
                    logger.debug(f"Started watching directory: {parent_dir}")
            
            elif source_config.source_type == LogSourceType.DIRECTORY:
                # For directories, monitor the directory itself
                if source_config.path not in self.watched_paths:
                    self.observer.schedule(
                        self.event_handler, 
                        source_config.path, 
                        recursive=source_config.recursive
                    )
                    self.watched_paths.add(source_config.path)
                    logger.debug(f"Started watching directory: {source_config.path} (recursive={source_config.recursive})")
            
            # Initialize file offset
            self._initialize_file_offset(source_config)
            
            # Update status
            source_config.status = MonitoringStatus.ACTIVE
            source_config.last_monitored = datetime.now(timezone.utc)
            
        except Exception as e:
            source_config.status = MonitoringStatus.ERROR
            source_config.error_message = str(e)
            logger.error(f"Failed to setup monitoring for {source_config.source_name}: {e}")
    
    def _remove_source_monitoring(self, source_config: LogSourceConfig) -> None:
        """Remove monitoring for a specific source."""
        try:
            # Note: We don't remove the observer watch here because other sources
            # might be using the same directory. This is a simplification.
            # In a production system, you'd want to track which sources use which paths.
            
            source_config.status = MonitoringStatus.INACTIVE
            logger.debug(f"Removed monitoring for {source_config.source_name}")
            
        except Exception as e:
            logger.error(f"Error removing monitoring for {source_config.source_name}: {e}")
    
    async def _initialize_file_offsets(self) -> None:
        """Initialize file offsets for all configured sources."""
        for source_config in self.log_sources.values():
            if source_config.enabled:
                self._initialize_file_offset(source_config)
    
    def _initialize_file_offset(self, source_config: LogSourceConfig) -> None:
        """Initialize file offset for a single source."""
        try:
            if source_config.source_type == LogSourceType.FILE:
                path = Path(source_config.path)
                if path.exists() and path.is_file():
                    # Start from the end of the file to avoid processing old logs
                    file_size = path.stat().st_size
                    self.file_offsets[source_config.path] = file_size
                    self.file_sizes[source_config.path] = file_size
                    
                    # Update source config
                    source_config.file_size = file_size
                    source_config.last_offset = file_size
                    
                    logger.debug(f"Initialized offset for {source_config.path}: {file_size}")
                else:
                    # File doesn't exist yet, start from beginning
                    self.file_offsets[source_config.path] = 0
                    self.file_sizes[source_config.path] = 0
                    source_config.file_size = 0
                    source_config.last_offset = 0
            
        except Exception as e:
            logger.error(f"Error initializing file offset for {source_config.path}: {e}")
    
    def _handle_file_change(self, file_path: str, event_type: str) -> None:
        """Handle a file system change event."""
        try:
            # Find matching source configurations
            matching_sources = self._find_matching_sources(file_path)
            
            if not matching_sources:
                return  # No sources match this file
            
            # Process the file change for each matching source
            for source_config in matching_sources:
                if source_config.enabled and source_config.status == MonitoringStatus.ACTIVE:
                    # Schedule the async processing in a thread-safe way
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Use call_soon_threadsafe to schedule from watchdog thread
                            loop.call_soon_threadsafe(
                                lambda: asyncio.create_task(
                                    self._process_file_change(source_config, file_path, event_type)
                                )
                            )
                        else:
                            # If no loop is running, process synchronously
                            self._process_file_change_sync(source_config, file_path, event_type)
                    except RuntimeError:
                        # No event loop available, process synchronously
                        self._process_file_change_sync(source_config, file_path, event_type)
            
        except Exception as e:
            logger.error(f"Error handling file change {file_path}: {e}")
    
    def _find_matching_sources(self, file_path: str) -> List[LogSourceConfig]:
        """Find source configurations that match the given file path."""
        matching_sources = []
        
        for source_config in self.log_sources.values():
            if self._source_matches_file(source_config, file_path):
                matching_sources.append(source_config)
        
        return matching_sources
    
    def _source_matches_file(self, source_config: LogSourceConfig, file_path: str) -> bool:
        """Check if a source configuration matches a file path."""
        try:
            if source_config.source_type == LogSourceType.FILE:
                # Direct file match
                return os.path.abspath(source_config.path) == os.path.abspath(file_path)
            
            elif source_config.source_type == LogSourceType.DIRECTORY:
                # Check if file is in the monitored directory
                source_path = Path(source_config.path)
                file_path_obj = Path(file_path)
                
                # Check if file is within the directory
                try:
                    file_path_obj.relative_to(source_path)
                except ValueError:
                    return False  # File is not within the directory
                
                # Check file pattern if specified
                if source_config.file_pattern:
                    filename = file_path_obj.name
                    if not fnmatch.fnmatch(filename, source_config.file_pattern):
                        return False
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error matching source {source_config.source_name} to file {file_path}: {e}")
            return False
    
    async def _process_file_change(self, source_config: LogSourceConfig, file_path: str, event_type: str) -> None:
        """Process a file change event for a specific source."""
        try:
            start_time = time.time()
            
            # Read new content from the file
            new_entries = await self._read_new_content(source_config, file_path)
            
            # Process each new entry
            for entry in new_entries:
                # Call all registered callbacks
                for callback in self.log_entry_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            # Await async callback
                            await callback(entry)
                        else:
                            callback(entry)
                    except Exception as e:
                        logger.error(f"Error in log entry callback: {e}")
            
            # Update metrics
            self.entries_processed += len(new_entries)
            self.last_processing_time = time.time() - start_time
            
            # Update source status
            source_config.last_monitored = datetime.now(timezone.utc)
            source_config.status = MonitoringStatus.ACTIVE
            source_config.error_message = None
            
            # Update health metrics
            self.update_health_metric("entries_processed", self.entries_processed)
            self.update_health_metric("last_processing_time", self.last_processing_time)
            
            if new_entries:
                logger.debug(f"Processed {len(new_entries)} new entries from {file_path}")
            
        except Exception as e:
            # Update source error status
            source_config.status = MonitoringStatus.ERROR
            source_config.error_message = str(e)
            
            self._handle_error(e, f"processing file change {file_path}")
    
    async def _read_new_content(self, source_config: LogSourceConfig, file_path: str) -> List[LogEntry]:
        """Read new content from a file since the last offset."""
        entries = []
        
        try:
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                return entries
            
            current_size = path.stat().st_size
            last_offset = self.file_offsets.get(file_path, 0)
            
            # Check if file was truncated (log rotation)
            if current_size < last_offset:
                logger.info(f"File {file_path} appears to have been rotated, resetting offset")
                last_offset = 0
            
            # If no new content, return empty list
            if current_size <= last_offset:
                return entries
            
            # Read new content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(last_offset)
                
                # Read in chunks to handle large files
                buffer = ""
                bytes_read = 0
                
                while bytes_read < (current_size - last_offset):
                    chunk = f.read(min(self.chunk_size, current_size - last_offset - bytes_read))
                    if not chunk:
                        break
                    
                    buffer += chunk
                    bytes_read += len(chunk.encode('utf-8'))
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        
                        # Skip empty lines
                        if not line.strip():
                            continue
                        
                        # Limit line length to prevent memory issues
                        if len(line) > self.max_line_length:
                            line = line[:self.max_line_length] + "... [truncated]"
                        
                        # Create log entry
                        entry = LogEntry(
                            content=line.strip(),
                            source_path=file_path,
                            source_name=source_config.source_name,
                            timestamp=datetime.now(timezone.utc),
                            priority=self._convert_priority(source_config.priority),
                            file_offset=last_offset + len(line) + 1  # +1 for newline
                        )
                        entries.append(entry)
                
                # Handle remaining buffer (incomplete line)
                if buffer.strip():
                    entry = LogEntry(
                        content=buffer.strip(),
                        source_path=file_path,
                        source_name=source_config.source_name,
                        timestamp=datetime.now(timezone.utc),
                        priority=self._convert_priority(source_config.priority),
                        file_offset=current_size
                    )
                    entries.append(entry)
            
            # Update offsets
            self.file_offsets[file_path] = current_size
            self.file_sizes[file_path] = current_size
            source_config.file_size = current_size
            source_config.last_offset = current_size
            
        except Exception as e:
            logger.error(f"Error reading new content from {file_path}: {e}")
            raise
        
        return entries
    
    def _process_file_change_sync(self, source_config: LogSourceConfig, file_path: str, event_type: str) -> None:
        """Synchronous version of file change processing for thread safety."""
        try:
            start_time = time.time()
            
            # Read new content from the file (synchronous version)
            new_entries = self._read_new_content_sync(source_config, file_path)
            
            # Process each new entry
            for entry in new_entries:
                # Call all registered callbacks
                for callback in self.log_entry_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            # For sync context, we need to handle async callbacks differently
                            try:
                                # Try to get the main thread's event loop
                                import threading
                                if hasattr(self, '_main_loop') and self._main_loop:
                                    # Schedule callback in the main loop
                                    self._main_loop.call_soon_threadsafe(
                                        lambda: asyncio.create_task(callback(entry))
                                    )
                                else:
                                    # Skip async callback if no main loop available
                                    logger.warning(f"No main event loop available for async callback")
                            except Exception as e:
                                logger.warning(f"Error scheduling async callback: {e}")
                        else:
                            callback(entry)
                    except Exception as e:
                        logger.error(f"Error in log entry callback: {e}")
            
            # Update metrics
            self.entries_processed += len(new_entries)
            self.last_processing_time = time.time() - start_time
            
            # Update source status
            source_config.last_monitored = datetime.now(timezone.utc)
            source_config.status = MonitoringStatus.ACTIVE
            source_config.error_message = None
            
            # Update health metrics
            self.update_health_metric("entries_processed", self.entries_processed)
            self.update_health_metric("last_processing_time", self.last_processing_time)
            
            if new_entries:
                logger.debug(f"Processed {len(new_entries)} new entries from {file_path}")
            
        except Exception as e:
            # Update source error status
            source_config.status = MonitoringStatus.ERROR
            source_config.error_message = str(e)
            
            self._handle_error(e, f"processing file change {file_path}")
    
    def _read_new_content_sync(self, source_config: LogSourceConfig, file_path: str) -> List[LogEntry]:
        """Synchronous version of reading new content from a file."""
        entries = []
        
        try:
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                return entries
            
            current_size = path.stat().st_size
            last_offset = self.file_offsets.get(file_path, 0)
            
            # Check if file was truncated (log rotation)
            if current_size < last_offset:
                logger.info(f"File {file_path} appears to have been rotated, resetting offset")
                last_offset = 0
            
            # If no new content, return empty list
            if current_size <= last_offset:
                return entries
            
            # Read new content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(last_offset)
                
                # Read in chunks to handle large files
                buffer = ""
                bytes_read = 0
                
                while bytes_read < (current_size - last_offset):
                    chunk = f.read(min(self.chunk_size, current_size - last_offset - bytes_read))
                    if not chunk:
                        break
                    
                    buffer += chunk
                    bytes_read += len(chunk.encode('utf-8'))
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        
                        # Skip empty lines
                        if not line.strip():
                            continue
                        
                        # Limit line length to prevent memory issues
                        if len(line) > self.max_line_length:
                            line = line[:self.max_line_length] + "... [truncated]"
                        
                        # Create log entry
                        entry = LogEntry(
                            content=line.strip(),
                            source_path=file_path,
                            source_name=source_config.source_name,
                            timestamp=datetime.now(timezone.utc),
                            priority=self._convert_priority(source_config.priority),
                            file_offset=last_offset + len(line) + 1  # +1 for newline
                        )
                        entries.append(entry)
                
                # Handle remaining buffer (incomplete line)
                if buffer.strip():
                    entry = LogEntry(
                        content=buffer.strip(),
                        source_path=file_path,
                        source_name=source_config.source_name,
                        timestamp=datetime.now(timezone.utc),
                        priority=self._convert_priority(source_config.priority),
                        file_offset=current_size
                    )
                    entries.append(entry)
            
            # Update offsets
            self.file_offsets[file_path] = current_size
            self.file_sizes[file_path] = current_size
            source_config.file_size = current_size
            source_config.last_offset = current_size
            
        except Exception as e:
            logger.error(f"Error reading new content from {file_path}: {e}")
            raise
        
        return entries