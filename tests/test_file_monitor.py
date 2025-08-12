"""
Unit tests for LogFileMonitor file change detection.

Tests the file system monitoring functionality including file change detection,
log source configuration, and file content processing.
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import os
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from watchdog.events import FileModifiedEvent, FileCreatedEvent

from app.realtime.file_monitor import (
    LogFileMonitor, LogEntry, FileChangeHandler, LogSourceConfig, 
    LogSourceType, MonitoringStatus
)
from app.realtime.exceptions import MonitoringError


class TestLogEntry:
    """Test LogEntry data model."""
    
    def test_log_entry_creation(self):
        """Test basic log entry creation."""
        entry = LogEntry(
            content="Test log message",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc),
            priority=5,
            file_offset=100
        )
        
        assert entry.content == "Test log message"
        assert entry.source_path == "/var/log/test.log"
        assert entry.source_name == "test_source"
        assert entry.priority == 5
        assert entry.file_offset == 100
        assert entry.id is not None
        assert "test_source" in entry.id
    
    def test_log_entry_defaults(self):
        """Test log entry with default values."""
        entry = LogEntry(
            content="Test message",
            source_path="/var/log/test.log",
            source_name="test_source"
        )
        
        assert entry.priority == 5  # Default priority
        assert entry.file_offset == 0  # Default offset
        assert entry.timestamp is not None
        assert entry.id is not None
    
    def test_log_entry_repr(self):
        """Test log entry string representation."""
        entry = LogEntry(
            content="Test message",
            source_path="/var/log/test.log",
            source_name="test_source"
        )
        
        repr_str = repr(entry)
        assert "LogEntry" in repr_str
        assert "test_source" in repr_str
        assert str(len("Test message")) in repr_str


class TestFileChangeHandler:
    """Test FileChangeHandler event handling."""
    
    @pytest.fixture
    def mock_monitor(self):
        """Create a mock LogFileMonitor."""
        monitor = Mock(spec=LogFileMonitor)
        monitor._handle_file_change = Mock()
        return monitor
    
    def test_handler_creation(self, mock_monitor):
        """Test handler creation."""
        handler = FileChangeHandler(mock_monitor)
        assert handler.monitor == mock_monitor
    
    def test_on_modified_file(self, mock_monitor):
        """Test handling file modification events."""
        handler = FileChangeHandler(mock_monitor)
        
        # Create mock event
        event = Mock(spec=FileModifiedEvent)
        event.is_directory = False
        event.src_path = "/var/log/test.log"
        
        handler.on_modified(event)
        
        mock_monitor._handle_file_change.assert_called_once_with(
            "/var/log/test.log", "modified"
        )
    
    def test_on_created_file(self, mock_monitor):
        """Test handling file creation events."""
        handler = FileChangeHandler(mock_monitor)
        
        # Create mock event
        event = Mock(spec=FileCreatedEvent)
        event.is_directory = False
        event.src_path = "/var/log/new.log"
        
        handler.on_created(event)
        
        mock_monitor._handle_file_change.assert_called_once_with(
            "/var/log/new.log", "created"
        )
    
    def test_ignore_directory_events(self, mock_monitor):
        """Test that directory events are ignored."""
        handler = FileChangeHandler(mock_monitor)
        
        # Create mock directory event
        event = Mock()
        event.is_directory = True
        event.src_path = "/var/log"
        
        handler.on_modified(event)
        handler.on_created(event)
        
        # Should not call monitor
        mock_monitor._handle_file_change.assert_not_called()
    
    def test_error_handling(self, mock_monitor):
        """Test error handling in event processing."""
        handler = FileChangeHandler(mock_monitor)
        
        # Make monitor raise exception
        mock_monitor._handle_file_change.side_effect = Exception("Test error")
        
        # Create mock event
        event = Mock()
        event.is_directory = False
        event.src_path = "/var/log/test.log"
        
        # Should not raise exception
        handler.on_modified(event)
        
        mock_monitor._handle_file_change.assert_called_once()


class TestLogFileMonitor:
    """Test LogFileMonitor functionality."""
    
    @pytest_asyncio.fixture
    async def monitor(self):
        """Create a LogFileMonitor for testing."""
        monitor = LogFileMonitor("test_monitor")
        await monitor.start()
        yield monitor
        await monitor.stop()
    
    @pytest.fixture
    def sample_log_source(self):
        """Create a sample log source configuration."""
        return LogSourceConfig(
            source_name="test_source",
            path="/var/log/test.log",
            source_type=LogSourceType.FILE,
            enabled=True,
            priority=5
        )
    
    @pytest.mark.asyncio
    async def test_monitor_lifecycle(self):
        """Test monitor start and stop lifecycle."""
        monitor = LogFileMonitor("test_monitor")
        
        # Initial state
        assert not monitor.is_running
        assert len(monitor.log_sources) == 0
        
        # Start monitor
        await monitor.start()
        assert monitor.is_running
        assert monitor.observer.is_alive()
        
        # Stop monitor
        await monitor.stop()
        assert not monitor.is_running
    
    @pytest.mark.asyncio
    async def test_add_log_source_file(self, monitor, sample_log_source):
        """Test adding a file log source."""
        with patch.object(monitor, '_validate_source_path', return_value=True):
            with patch.object(monitor, '_setup_source_monitoring'):
                result = monitor.add_log_source(sample_log_source)
                
                assert result is True
                assert "test_source" in monitor.log_sources
                assert monitor.log_sources["test_source"] == sample_log_source
    
    @pytest.mark.asyncio
    async def test_add_duplicate_source(self, monitor, sample_log_source):
        """Test adding duplicate log source."""
        with patch.object(monitor, '_validate_source_path', return_value=True):
            with patch.object(monitor, '_setup_source_monitoring'):
                # Add source first time
                result1 = monitor.add_log_source(sample_log_source)
                assert result1 is True
                
                # Try to add same source again
                result2 = monitor.add_log_source(sample_log_source)
                assert result2 is False
    
    @pytest.mark.asyncio
    async def test_add_invalid_source(self, monitor, sample_log_source):
        """Test adding invalid log source."""
        with patch.object(monitor, '_validate_source_path', return_value=False):
            with pytest.raises(MonitoringError):
                monitor.add_log_source(sample_log_source)
    
    def test_remove_log_source(self, monitor, sample_log_source):
        """Test removing a log source."""
        # Add source first
        with patch.object(monitor, '_validate_source_path', return_value=True):
            with patch.object(monitor, '_setup_source_monitoring'):
                monitor.add_log_source(sample_log_source)
        
        # Remove source
        with patch.object(monitor, '_remove_source_monitoring'):
            result = monitor.remove_log_source("test_source")
            
            assert result is True
            assert "test_source" not in monitor.log_sources
    
    def test_remove_nonexistent_source(self, monitor):
        """Test removing non-existent log source."""
        result = monitor.remove_log_source("nonexistent")
        assert result is False
    
    def test_get_monitoring_status(self, monitor, sample_log_source):
        """Test getting monitoring status."""
        # Add a source
        with patch.object(monitor, '_validate_source_path', return_value=True):
            with patch.object(monitor, '_setup_source_monitoring'):
                monitor.add_log_source(sample_log_source)
        
        status = monitor.get_monitoring_status()
        
        assert "total_sources" in status
        assert "active_sources" in status
        assert "sources" in status
        assert status["total_sources"] == 1
        assert "test_source" in status["sources"]
    
    def test_log_entry_callbacks(self, monitor):
        """Test log entry callback management."""
        callback1 = Mock()
        callback2 = Mock()
        
        # Add callbacks
        monitor.add_log_entry_callback(callback1)
        monitor.add_log_entry_callback(callback2)
        
        assert len(monitor.log_entry_callbacks) == 2
        assert callback1 in monitor.log_entry_callbacks
        assert callback2 in monitor.log_entry_callbacks
        
        # Remove callback
        monitor.remove_log_entry_callback(callback1)
        
        assert len(monitor.log_entry_callbacks) == 1
        assert callback1 not in monitor.log_entry_callbacks
        assert callback2 in monitor.log_entry_callbacks
    
    def test_validate_source_path_file(self, monitor):
        """Test source path validation for files."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(b"test content")
        
        try:
            source_config = LogSourceConfig(
                source_name="temp_source",
                path=temp_path,
                source_type=LogSourceType.FILE,
                enabled=True
            )
            
            result = monitor._validate_source_path(source_config)
            assert result is True
        finally:
            os.unlink(temp_path)
    
    def test_validate_source_path_directory(self, monitor):
        """Test source path validation for directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_config = LogSourceConfig(
                source_name="temp_source",
                path=temp_dir,
                source_type=LogSourceType.DIRECTORY,
                enabled=True
            )
            
            result = monitor._validate_source_path(source_config)
            assert result is True
    
    def test_validate_nonexistent_file(self, monitor):
        """Test validation of non-existent file (should allow)."""
        source_config = LogSourceConfig(
            source_name="nonexistent_source",
            path="/nonexistent/file.log",
            source_type=LogSourceType.FILE,
            enabled=True
        )
        
        # Should return True to allow monitoring files that don't exist yet
        result = monitor._validate_source_path(source_config)
        assert result is True
    
    def test_validate_nonexistent_directory(self, monitor):
        """Test validation of non-existent directory (should fail)."""
        source_config = LogSourceConfig(
            source_name="nonexistent_source",
            path="/nonexistent/directory",
            source_type=LogSourceType.DIRECTORY,
            enabled=True
        )
        
        result = monitor._validate_source_path(source_config)
        assert result is False
    
    def test_find_matching_sources_file(self, monitor):
        """Test finding matching sources for file events."""
        source_config = LogSourceConfig(
            source_name="test_source",
            path="/var/log/test.log",
            source_type=LogSourceType.FILE,
            enabled=True
        )
        
        monitor.log_sources["test_source"] = source_config
        
        # Test exact match
        matches = monitor._find_matching_sources("/var/log/test.log")
        assert len(matches) == 1
        assert matches[0] == source_config
        
        # Test non-match
        matches = monitor._find_matching_sources("/var/log/other.log")
        assert len(matches) == 0
    
    def test_find_matching_sources_directory(self, monitor):
        """Test finding matching sources for directory events."""
        source_config = LogSourceConfig(
            source_name="test_source",
            path="/var/log",
            source_type=LogSourceType.DIRECTORY,
            enabled=True,
            file_pattern="*.log"
        )
        
        monitor.log_sources["test_source"] = source_config
        
        # Test matching file in directory
        matches = monitor._find_matching_sources("/var/log/test.log")
        assert len(matches) == 1
        assert matches[0] == source_config
        
        # Test non-matching file pattern
        matches = monitor._find_matching_sources("/var/log/test.txt")
        assert len(matches) == 0
        
        # Test file outside directory
        matches = monitor._find_matching_sources("/other/test.log")
        assert len(matches) == 0
    
    @pytest.mark.asyncio
    async def test_read_new_content(self, monitor):
        """Test reading new content from a file."""
        # Create temporary file with initial content
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("line 1\nline 2\n")
            temp_path = temp_file.name
        
        try:
            source_config = LogSourceConfig(
                source_name="temp_source",
                path=temp_path,
                source_type=LogSourceType.FILE,
                enabled=True
            )
            
            # Initialize file offset to beginning
            monitor.file_offsets[temp_path] = 0
            monitor.file_sizes[temp_path] = 0
            
            # Read new content
            entries = await monitor._read_new_content(source_config, temp_path)
            
            assert len(entries) == 2
            assert entries[0].content == "line 1"
            assert entries[1].content == "line 2"
            assert entries[0].source_name == "temp_source"
            
            # Check that offset was updated
            assert monitor.file_offsets[temp_path] > 0
            
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_read_new_content_incremental(self, monitor):
        """Test reading incremental content from a file."""
        # Create temporary file with initial content
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("line 1\n")
            temp_path = temp_file.name
        
        try:
            source_config = LogSourceConfig(
                source_name="temp_source",
                path=temp_path,
                source_type=LogSourceType.FILE,
                enabled=True
            )
            
            # Read initial content
            monitor.file_offsets[temp_path] = 0
            entries1 = await monitor._read_new_content(source_config, temp_path)
            assert len(entries1) == 1
            assert entries1[0].content == "line 1"
            
            # Append more content
            with open(temp_path, 'a') as f:
                f.write("line 2\n")
            
            # Read new content only
            entries2 = await monitor._read_new_content(source_config, temp_path)
            assert len(entries2) == 1
            assert entries2[0].content == "line 2"
            
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_read_content_file_rotation(self, monitor):
        """Test handling file rotation (truncation)."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("old content\n")
            temp_path = temp_file.name
        
        try:
            source_config = LogSourceConfig(
                source_name="temp_source",
                path=temp_path,
                source_type=LogSourceType.FILE,
                enabled=True
            )
            
            # Set offset to end of file
            file_size = os.path.getsize(temp_path)
            monitor.file_offsets[temp_path] = file_size
            monitor.file_sizes[temp_path] = file_size
            
            # Truncate and write new content (simulate log rotation)
            with open(temp_path, 'w') as f:
                f.write("new content\n")
            
            # Read content - should detect rotation and read from beginning
            entries = await monitor._read_new_content(source_config, temp_path)
            
            assert len(entries) == 1
            assert entries[0].content == "new content"
            
        finally:
            os.unlink(temp_path)
    
    def test_handle_file_change_sync(self, monitor):
        """Test synchronous file change handling."""
        # Create mock source
        source_config = LogSourceConfig(
            source_name="test_source",
            path="/var/log/test.log",
            source_type=LogSourceType.FILE,
            enabled=True,
            status=MonitoringStatus.ACTIVE
        )
        monitor.log_sources["test_source"] = source_config
        
        # Mock the file reading
        with patch.object(monitor, '_read_new_content_sync') as mock_read:
            mock_entry = LogEntry(
                content="test message",
                source_path="/var/log/test.log",
                source_name="test_source"
            )
            mock_read.return_value = [mock_entry]
            
            # Add callback to capture entries
            captured_entries = []
            monitor.add_log_entry_callback(lambda entry: captured_entries.append(entry))
            
            # Handle file change
            monitor._handle_file_change("/var/log/test.log", "modified")
            
            # Check that callback was called
            assert len(captured_entries) == 1
            assert captured_entries[0].content == "test message"
    
    def test_initialize_file_offset(self, monitor):
        """Test file offset initialization."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("existing content\n")
            temp_path = temp_file.name
        
        try:
            source_config = LogSourceConfig(
                source_name="temp_source",
                path=temp_path,
                source_type=LogSourceType.FILE,
                enabled=True
            )
            
            # Initialize offset
            monitor._initialize_file_offset(source_config)
            
            # Should start from end of file to avoid processing old logs
            file_size = os.path.getsize(temp_path)
            assert monitor.file_offsets[temp_path] == file_size
            assert monitor.file_sizes[temp_path] == file_size
            assert source_config.file_size == file_size
            assert source_config.last_offset == file_size
            
        finally:
            os.unlink(temp_path)
    
    def test_initialize_file_offset_nonexistent(self, monitor):
        """Test file offset initialization for non-existent file."""
        source_config = LogSourceConfig(
            source_name="nonexistent_source",
            path="/nonexistent/file.log",
            source_type=LogSourceType.FILE,
            enabled=True
        )
        
        # Initialize offset for non-existent file
        monitor._initialize_file_offset(source_config)
        
        # Should start from beginning
        assert monitor.file_offsets["/nonexistent/file.log"] == 0
        assert monitor.file_sizes["/nonexistent/file.log"] == 0
        assert source_config.file_size == 0
        assert source_config.last_offset == 0


if __name__ == "__main__":
    pytest.main([__file__])