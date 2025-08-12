"""
Unit tests for RealtimeIngestionQueue priority handling and batch processing.

Tests the priority-based queuing, batch processing, backpressure handling,
and performance monitoring functionality.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

from app.realtime.ingestion_queue import (
    RealtimeIngestionQueue, LogEntry, LogEntryPriority, ProcessingStatus, QueueStats
)
from app.realtime.exceptions import QueueError


class TestLogEntry:
    """Test LogEntry data model and functionality."""
    
    def test_log_entry_creation(self):
        """Test basic log entry creation."""
        timestamp = datetime.now(timezone.utc)
        entry = LogEntry(
            content="Test log message",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=timestamp,
            priority=LogEntryPriority.HIGH,
            file_offset=100
        )
        
        assert entry.content == "Test log message"
        assert entry.source_path == "/var/log/test.log"
        assert entry.source_name == "test_source"
        assert entry.timestamp == timestamp
        assert entry.priority == LogEntryPriority.HIGH
        assert entry.file_offset == 100
        assert entry.status == ProcessingStatus.PENDING
        assert entry.entry_id is not None
        assert "test_source" in entry.entry_id
    
    def test_log_entry_defaults(self):
        """Test log entry with default values."""
        entry = LogEntry(
            content="Test message",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc)
        )
        
        assert entry.priority == LogEntryPriority.MEDIUM
        assert entry.file_offset == 0
        assert entry.status == ProcessingStatus.PENDING
        assert entry.retry_count == 0
        assert entry.max_retries == 3
        assert entry.error_count == 0
    
    def test_log_entry_comparison(self):
        """Test log entry priority comparison for queue ordering."""
        timestamp = datetime.now(timezone.utc)
        
        high_priority = LogEntry(
            content="High priority",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=timestamp,
            priority=LogEntryPriority.HIGH
        )
        
        low_priority = LogEntry(
            content="Low priority",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=timestamp,
            priority=LogEntryPriority.LOW
        )
        
        # High priority should be "less than" low priority for min-heap
        assert high_priority < low_priority
        assert not (low_priority < high_priority)
    
    def test_log_entry_timestamp_comparison(self):
        """Test log entry timestamp comparison for same priority."""
        base_time = datetime.now(timezone.utc)
        older_time = base_time - timedelta(seconds=10)
        
        older_entry = LogEntry(
            content="Older entry",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=older_time,
            priority=LogEntryPriority.MEDIUM
        )
        
        newer_entry = LogEntry(
            content="Newer entry",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=base_time,
            priority=LogEntryPriority.MEDIUM
        )
        
        # Older entries should be processed first for same priority
        assert older_entry < newer_entry
    
    def test_processing_status_methods(self):
        """Test processing status management methods."""
        entry = LogEntry(
            content="Test message",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc)
        )
        
        # Test mark processing started
        entry.mark_processing_started()
        assert entry.status == ProcessingStatus.PROCESSING
        assert entry.processing_started_at is not None
        
        # Test mark processing completed
        entry.mark_processing_completed()
        assert entry.status == ProcessingStatus.COMPLETED
        assert entry.processing_completed_at is not None
        
        # Test processing time calculation
        processing_time = entry.get_processing_time()
        assert processing_time is not None
        assert processing_time >= 0
    
    def test_processing_failure_and_retry(self):
        """Test processing failure and retry logic."""
        entry = LogEntry(
            content="Test message",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc)
        )
        
        # Test mark processing failed
        error_msg = "Processing failed"
        entry.mark_processing_failed(error_msg)
        assert entry.status == ProcessingStatus.FAILED
        assert entry.last_error == error_msg
        assert entry.error_count == 1
        
        # Test retry capability
        assert entry.can_retry() is True
        
        # Test mark for retry
        entry.mark_for_retry()
        assert entry.status == ProcessingStatus.RETRYING
        assert entry.retry_count == 1
        
        # Test retry limit
        entry.retry_count = entry.max_retries
        assert entry.can_retry() is False
    
    def test_log_entry_serialization(self):
        """Test log entry to_dict method."""
        timestamp = datetime.now(timezone.utc)
        entry = LogEntry(
            content="Test message",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=timestamp,
            priority=LogEntryPriority.HIGH,
            metadata={"key": "value"}
        )
        
        entry_dict = entry.to_dict()
        
        assert entry_dict["content"] == "Test message"
        assert entry_dict["source_path"] == "/var/log/test.log"
        assert entry_dict["source_name"] == "test_source"
        assert entry_dict["priority"] == LogEntryPriority.HIGH.value
        assert entry_dict["metadata"] == {"key": "value"}
        assert "timestamp" in entry_dict
        assert "entry_id" in entry_dict


class TestQueueStats:
    """Test QueueStats data model."""
    
    def test_queue_stats_creation(self):
        """Test queue stats creation and defaults."""
        stats = QueueStats()
        
        assert stats.total_entries == 0
        assert stats.pending_entries == 0
        assert stats.processing_entries == 0
        assert stats.completed_entries == 0
        assert stats.failed_entries == 0
        assert stats.avg_processing_time == 0.0
        assert stats.throughput_per_second == 0.0
        assert stats.error_rate == 0.0
        assert isinstance(stats.priority_distribution, dict)
        assert stats.last_updated is not None
    
    def test_queue_stats_serialization(self):
        """Test queue stats to_dict method."""
        stats = QueueStats(
            total_entries=100,
            pending_entries=10,
            avg_processing_time=1.5,
            priority_distribution={"HIGH": 20, "MEDIUM": 60, "LOW": 20}
        )
        
        stats_dict = stats.to_dict()
        
        assert stats_dict["total_entries"] == 100
        assert stats_dict["pending_entries"] == 10
        assert stats_dict["avg_processing_time"] == 1.5
        assert stats_dict["priority_distribution"]["HIGH"] == 20
        assert "last_updated" in stats_dict


class TestRealtimeIngestionQueue:
    """Test RealtimeIngestionQueue functionality."""
    
    @pytest.fixture
    async def queue(self):
        """Create a test queue."""
        queue = RealtimeIngestionQueue(
            max_queue_size=100,
            batch_size=10,
            batch_timeout=1.0,
            max_concurrent_batches=2
        )
        await queue.start()
        yield queue
        await queue.stop()
    
    @pytest.fixture
    def sample_entry(self):
        """Create a sample log entry."""
        return LogEntry(
            content="Test log message",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.MEDIUM
        )
    
    @pytest.mark.asyncio
    async def test_queue_initialization(self):
        """Test queue initialization and configuration."""
        queue = RealtimeIngestionQueue(
            max_queue_size=50,
            batch_size=5,
            batch_timeout=2.0,
            max_concurrent_batches=3,
            backpressure_threshold=0.7
        )
        
        assert queue.max_queue_size == 50
        assert queue.batch_size == 5
        assert queue.batch_timeout == 2.0
        assert queue.max_concurrent_batches == 3
        assert queue.backpressure_threshold == 0.7
        assert not queue.is_running
        assert len(queue._queue) == 0
    
    @pytest.mark.asyncio
    async def test_queue_lifecycle(self, queue):
        """Test queue start and stop lifecycle."""
        assert queue.is_running
        assert queue._processor_task is not None
        assert queue._stats_task is not None
        
        # Stop queue
        await queue.stop()
        assert not queue.is_running
    
    @pytest.mark.asyncio
    async def test_enqueue_entry(self, queue, sample_entry):
        """Test enqueuing a log entry."""
        result = await queue.enqueue_log_entry(sample_entry)
        assert result is True
        
        # Check queue state
        assert len(queue._queue) == 1
        assert sample_entry.entry_id in queue._entries_by_id
        assert sample_entry in queue._entries_by_status[ProcessingStatus.PENDING]
    
    @pytest.mark.asyncio
    async def test_enqueue_invalid_entry(self, queue):
        """Test enqueuing invalid log entry."""
        # Entry with no content
        invalid_entry = LogEntry(
            content="",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc)
        )
        
        with pytest.raises(QueueError):
            await queue.enqueue_log_entry(invalid_entry)
        
        # Entry with no source name
        invalid_entry2 = LogEntry(
            content="Test message",
            source_path="/var/log/test.log",
            source_name="",
            timestamp=datetime.now(timezone.utc)
        )
        
        with pytest.raises(QueueError):
            await queue.enqueue_log_entry(invalid_entry2)
    
    @pytest.mark.asyncio
    async def test_enqueue_when_stopped(self, sample_entry):
        """Test enqueuing when queue is stopped."""
        queue = RealtimeIngestionQueue(max_queue_size=10)
        
        with pytest.raises(QueueError):
            await queue.enqueue_log_entry(sample_entry)
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self, queue):
        """Test priority-based ordering in queue."""
        # Create entries with different priorities
        high_entry = LogEntry(
            content="High priority",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.HIGH
        )
        
        low_entry = LogEntry(
            content="Low priority",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.LOW
        )
        
        medium_entry = LogEntry(
            content="Medium priority",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.MEDIUM
        )
        
        # Add in reverse priority order
        await queue.enqueue_log_entry(low_entry)
        await queue.enqueue_log_entry(medium_entry)
        await queue.enqueue_log_entry(high_entry)
        
        # Collect batch should return highest priority first
        batch = await queue._collect_batch()
        
        assert len(batch) == 3
        assert batch[0].priority == LogEntryPriority.HIGH
        assert batch[1].priority == LogEntryPriority.MEDIUM
        assert batch[2].priority == LogEntryPriority.LOW
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, queue):
        """Test batch processing functionality."""
        processed_batches = []
        
        async def mock_processor(batch):
            processed_batches.append(batch)
        
        queue.set_batch_processor(mock_processor)
        
        # Add entries
        for i in range(15):  # More than batch size
            entry = LogEntry(
                content=f"Test message {i}",
                source_path="/var/log/test.log",
                source_name="test_source",
                timestamp=datetime.now(timezone.utc),
                priority=LogEntryPriority.MEDIUM
            )
            await queue.enqueue_log_entry(entry)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Should have processed at least one batch
        assert len(processed_batches) > 0
        
        # Each batch should not exceed batch size
        for batch in processed_batches:
            assert len(batch) <= queue.batch_size
    
    @pytest.mark.asyncio
    async def test_batch_timeout(self, queue):
        """Test batch timeout functionality."""
        processed_batches = []
        
        async def mock_processor(batch):
            processed_batches.append(batch)
        
        queue.set_batch_processor(mock_processor)
        
        # Add just one entry (less than batch size)
        entry = LogEntry(
            content="Single entry",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.MEDIUM
        )
        await queue.enqueue_log_entry(entry)
        
        # Wait for batch timeout
        await asyncio.sleep(queue.batch_timeout + 0.5)
        
        # Should have processed the single entry due to timeout
        assert len(processed_batches) > 0
        assert len(processed_batches[0]) == 1
    
    @pytest.mark.asyncio
    async def test_backpressure_handling(self, queue):
        """Test backpressure handling."""
        # Fill queue to trigger backpressure
        backpressure_limit = int(queue.max_queue_size * queue.backpressure_threshold)
        
        # Add entries up to backpressure threshold
        for i in range(backpressure_limit + 5):
            entry = LogEntry(
                content=f"Test message {i}",
                source_path="/var/log/test.log",
                source_name="test_source",
                timestamp=datetime.now(timezone.utc),
                priority=LogEntryPriority.LOW  # Use low priority to trigger backpressure
            )
            result = await queue.enqueue_log_entry(entry)
            
            # Some entries should be rejected due to backpressure
            if i >= backpressure_limit:
                # Low priority entries should be rejected
                assert result is False
        
        # High priority entries should still be accepted during backpressure
        high_priority_entry = LogEntry(
            content="High priority during backpressure",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.HIGH
        )
        result = await queue.enqueue_log_entry(high_priority_entry)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_queue_full_rejection(self, queue):
        """Test queue full rejection."""
        # Fill queue to maximum capacity
        for i in range(queue.max_queue_size):
            entry = LogEntry(
                content=f"Test message {i}",
                source_path="/var/log/test.log",
                source_name="test_source",
                timestamp=datetime.now(timezone.utc),
                priority=LogEntryPriority.MEDIUM
            )
            result = await queue.enqueue_log_entry(entry)
            assert result is True
        
        # Next entry should be rejected
        overflow_entry = LogEntry(
            content="Overflow entry",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.HIGH  # Even high priority should be rejected when full
        )
        result = await queue.enqueue_log_entry(overflow_entry)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_error_handling_in_processing(self, queue):
        """Test error handling during batch processing."""
        processed_batches = []
        failed_entries = []
        
        async def failing_processor(batch):
            processed_batches.append(batch)
            raise Exception("Processing failed")
        
        def error_handler(entry, error):
            failed_entries.append((entry, error))
        
        queue.set_batch_processor(failing_processor)
        queue.set_error_handler(error_handler)
        
        # Add entry
        entry = LogEntry(
            content="Test message",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.MEDIUM
        )
        await queue.enqueue_log_entry(entry)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Should have attempted processing
        assert len(processed_batches) > 0
        
        # Entry should be marked for retry or failed
        async with queue._queue_lock:
            entry_status = queue._entries_by_id[entry.entry_id].status
            assert entry_status in [ProcessingStatus.RETRYING, ProcessingStatus.FAILED]
    
    @pytest.mark.asyncio
    async def test_retry_logic(self, queue):
        """Test retry logic for failed entries."""
        retry_attempts = []
        
        async def failing_processor(batch):
            retry_attempts.append(len(batch))
            raise Exception("Processing failed")
        
        queue.set_batch_processor(failing_processor)
        
        # Add entry with low max_retries for faster testing
        entry = LogEntry(
            content="Test message",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.MEDIUM,
            max_retries=2
        )
        await queue.enqueue_log_entry(entry)
        
        # Wait for processing and retries
        await asyncio.sleep(2.0)
        
        # Should have attempted processing multiple times
        assert len(retry_attempts) > 1
        
        # Entry should eventually be marked as failed
        async with queue._queue_lock:
            final_entry = queue._entries_by_id[entry.entry_id]
            assert final_entry.status == ProcessingStatus.FAILED
            assert final_entry.retry_count >= 1
    
    @pytest.mark.asyncio
    async def test_get_queue_stats(self, queue):
        """Test queue statistics calculation."""
        # Add some entries
        for i in range(5):
            entry = LogEntry(
                content=f"Test message {i}",
                source_path="/var/log/test.log",
                source_name="test_source",
                timestamp=datetime.now(timezone.utc),
                priority=LogEntryPriority.MEDIUM
            )
            await queue.enqueue_log_entry(entry)
        
        stats = await queue.get_queue_stats()
        
        assert stats.total_entries == 5
        assert stats.pending_entries == 5
        assert "MEDIUM" in stats.priority_distribution
        assert stats.priority_distribution["MEDIUM"] == 5
        assert isinstance(stats.last_updated, datetime)
    
    @pytest.mark.asyncio
    async def test_get_entry_by_id(self, queue, sample_entry):
        """Test retrieving entry by ID."""
        await queue.enqueue_log_entry(sample_entry)
        
        retrieved_entry = await queue.get_entry_by_id(sample_entry.entry_id)
        assert retrieved_entry == sample_entry
        
        # Test non-existent ID
        non_existent = await queue.get_entry_by_id("non_existent_id")
        assert non_existent is None
    
    @pytest.mark.asyncio
    async def test_get_entries_by_status(self, queue, sample_entry):
        """Test retrieving entries by status."""
        await queue.enqueue_log_entry(sample_entry)
        
        pending_entries = await queue.get_entries_by_status(ProcessingStatus.PENDING)
        assert len(pending_entries) == 1
        assert sample_entry in pending_entries
        
        completed_entries = await queue.get_entries_by_status(ProcessingStatus.COMPLETED)
        assert len(completed_entries) == 0
    
    @pytest.mark.asyncio
    async def test_clear_completed_entries(self, queue):
        """Test clearing old completed entries."""
        # Create and process some entries
        processed_batches = []
        
        async def mock_processor(batch):
            processed_batches.append(batch)
        
        queue.set_batch_processor(mock_processor)
        
        # Add entries
        for i in range(3):
            entry = LogEntry(
                content=f"Test message {i}",
                source_path="/var/log/test.log",
                source_name="test_source",
                timestamp=datetime.now(timezone.utc),
                priority=LogEntryPriority.MEDIUM
            )
            await queue.enqueue_log_entry(entry)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Manually mark entries as completed with old timestamp
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        async with queue._queue_lock:
            for entry in queue._entries_by_status[ProcessingStatus.COMPLETED]:
                entry.processing_completed_at = old_time
        
        # Clear old entries
        cleared_count = await queue.clear_completed_entries(max_age_hours=24)
        
        # Should have cleared the old entries
        assert cleared_count > 0
    
    def test_get_queue_info(self, queue):
        """Test getting comprehensive queue information."""
        info = queue.get_queue_info()
        
        assert "name" in info
        assert "is_running" in info
        assert "configuration" in info
        assert "current_state" in info
        assert "health_status" in info
        assert "health_metrics" in info
        
        assert info["name"] == queue.name
        assert info["is_running"] == queue.is_running
        assert info["configuration"]["max_queue_size"] == queue.max_queue_size
        assert info["configuration"]["batch_size"] == queue.batch_size


if __name__ == "__main__":
    pytest.main([__file__])