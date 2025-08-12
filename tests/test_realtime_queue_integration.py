"""
Tests for real-time queue integration with background processing.

This module tests the integration between the real-time ingestion queue
and the existing background processing system.
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock

from app.realtime.ingestion_queue import (
    RealtimeIngestionQueue, LogEntry, LogEntryPriority, ProcessingStatus
)
from app.realtime.enhanced_processor import EnhancedBackgroundProcessor
from app.realtime.queue_integration import (
    QueueIntegrationManager, get_integration_manager, enqueue_realtime_log
)
from app.realtime.processing_pipeline import process_log_entry, ValidationResult


class TestRealtimeIngestionQueue:
    """Test the real-time ingestion queue."""
    
    @pytest_asyncio.fixture
    async def queue(self):
        """Create a test queue."""
        queue = RealtimeIngestionQueue(max_queue_size=100, batch_size=10)
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
    async def test_queue_initialization(self, queue):
        """Test queue initialization."""
        assert queue.is_running
        assert queue.max_queue_size == 100
        assert queue.batch_size == 10
    
    @pytest.mark.asyncio
    async def test_enqueue_entry(self, queue, sample_entry):
        """Test enqueuing a log entry."""
        result = await queue.enqueue_log_entry(sample_entry)
        assert result is True
        
        stats = await queue.get_queue_stats()
        assert stats.total_entries == 1
        assert stats.pending_entries == 1
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, queue):
        """Test batch processing functionality."""
        processed_batches = []
        
        async def mock_processor(batch):
            processed_batches.append(batch)
        
        queue.set_batch_processor(mock_processor)
        
        # Add multiple entries
        for i in range(5):
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
        
        # Check that batch was processed
        assert len(processed_batches) > 0
        assert len(processed_batches[0]) <= queue.batch_size
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self, queue):
        """Test priority-based ordering."""
        processed_entries = []
        
        async def mock_processor(batch):
            processed_entries.extend(batch)
        
        queue.set_batch_processor(mock_processor)
        
        # Add entries with different priorities
        low_priority = LogEntry(
            content="Low priority",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.LOW
        )
        
        high_priority = LogEntry(
            content="High priority",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.HIGH
        )
        
        # Add low priority first, then high priority
        await queue.enqueue_log_entry(low_priority)
        await queue.enqueue_log_entry(high_priority)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # High priority should be processed first
        if processed_entries:
            assert processed_entries[0].priority == LogEntryPriority.HIGH
    
    @pytest.mark.asyncio
    async def test_backpressure_handling(self, queue):
        """Test backpressure handling."""
        # Fill queue to trigger backpressure
        entries_added = 0
        for i in range(queue.max_queue_size + 10):
            entry = LogEntry(
                content=f"Test message {i}",
                source_path="/var/log/test.log",
                source_name="test_source",
                timestamp=datetime.now(timezone.utc),
                priority=LogEntryPriority.LOW  # Use low priority to trigger backpressure
            )
            result = await queue.enqueue_log_entry(entry)
            if result:
                entries_added += 1
        
        # Should not have added all entries due to backpressure
        assert entries_added <= queue.max_queue_size


class TestEnhancedBackgroundProcessor:
    """Test the enhanced background processor."""
    
    @pytest_asyncio.fixture
    async def queue_and_processor(self):
        """Create queue and processor for testing."""
        queue = RealtimeIngestionQueue(max_queue_size=100, batch_size=5)
        await queue.start()
        
        processor = EnhancedBackgroundProcessor(queue)
        await processor.start()
        
        yield queue, processor
        
        await processor.stop()
        await queue.stop()
    
    @pytest.mark.asyncio
    async def test_processor_initialization(self, queue_and_processor):
        """Test processor initialization."""
        queue, processor = queue_and_processor
        
        assert processor.is_running
        assert processor.ingestion_queue == queue
    
    @pytest.mark.asyncio
    @patch('app.realtime.enhanced_processor.parse_log_entries')
    @patch('app.realtime.enhanced_processor.analyze_event')
    @patch('app.realtime.enhanced_processor.get_database_session')
    async def test_entry_processing(self, mock_db, mock_analyze, mock_parse, queue_and_processor):
        """Test processing of a single entry."""
        queue, processor = queue_and_processor
        
        # Mock dependencies
        mock_parse.return_value = []  # No parsed events for simplicity
        mock_db.return_value.__enter__.return_value = Mock()
        
        # Create test entry
        entry = LogEntry(
            content="Test log message",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.MEDIUM
        )
        
        # Process entry directly
        result = await processor.process_realtime_entry(entry)
        
        assert result['success'] is True
        assert result['entry_id'] == entry.entry_id
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, queue_and_processor):
        """Test metrics collection."""
        queue, processor = queue_and_processor
        
        metrics = processor.get_processing_metrics()
        
        assert 'entries_processed' in metrics
        assert 'processing_rate' in metrics
        assert 'success_rate' in metrics
        assert isinstance(metrics['entries_processed'], int)


class TestQueueIntegrationManager:
    """Test the queue integration manager."""
    
    @pytest_asyncio.fixture
    async def integration_manager(self):
        """Create integration manager for testing."""
        manager = QueueIntegrationManager(max_queue_size=50, batch_size=5)
        await manager.start()
        yield manager
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_initialization(self, integration_manager):
        """Test integration manager initialization."""
        assert integration_manager.is_running
        assert integration_manager.ingestion_queue.is_running
        assert integration_manager.enhanced_processor.is_running
    
    @pytest.mark.asyncio
    async def test_enqueue_log_entry(self, integration_manager):
        """Test enqueuing through integration manager."""
        result = await integration_manager.enqueue_log_entry(
            content="Test log message",
            source_path="/var/log/test.log",
            source_name="test_source",
            priority=LogEntryPriority.MEDIUM
        )
        
        assert result is True
        
        # Check queue status
        status = await integration_manager.get_queue_status()
        assert 'queue_stats' in status
        assert status['queue_stats']['total_entries'] == 1
    
    @pytest.mark.asyncio
    @patch('app.realtime.queue_integration.process_raw_log')
    async def test_traditional_log_processing(self, mock_process, integration_manager):
        """Test traditional log processing through integration manager."""
        mock_process.return_value = {
            'success': True,
            'raw_log_id': 'test_id',
            'events_parsed': 1
        }
        
        result = await integration_manager.process_traditional_log('test_id')
        
        assert result['success'] is True
        assert result['raw_log_id'] == 'test_id'
        mock_process.assert_called_once_with('test_id')
    
    @pytest.mark.asyncio
    async def test_get_queue_status(self, integration_manager):
        """Test getting comprehensive queue status."""
        status = await integration_manager.get_queue_status()
        
        assert 'integration_status' in status
        assert 'queue_stats' in status
        assert 'realtime_processing' in status
        assert 'traditional_processing' in status
        assert status['integration_status']['is_running'] is True


class TestProcessingPipeline:
    """Test the processing pipeline components."""
    
    def test_log_entry_validation(self):
        """Test log entry validation."""
        # Valid entry
        valid_entry = LogEntry(
            content="Normal log message",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc)
        )
        
        result = process_log_entry(valid_entry)
        assert result.success is True
        assert result.validation_result == ValidationResult.VALID
    
    def test_suspicious_content_detection(self):
        """Test detection of suspicious content."""
        # Entry with suspicious content
        suspicious_entry = LogEntry(
            content="SELECT * FROM users WHERE 1=1",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc)
        )
        
        result = process_log_entry(suspicious_entry)
        assert result.validation_result == ValidationResult.SUSPICIOUS
    
    def test_invalid_entry_handling(self):
        """Test handling of invalid entries."""
        # Entry with no content
        invalid_entry = LogEntry(
            content="",
            source_path="/var/log/test.log",
            source_name="test_source",
            timestamp=datetime.now(timezone.utc)
        )
        
        result = process_log_entry(invalid_entry)
        assert result.success is False
        assert result.validation_result == ValidationResult.INVALID


class TestIntegrationFunctions:
    """Test integration convenience functions."""
    
    @pytest.mark.asyncio
    @patch('app.realtime.queue_integration.get_integration_manager')
    async def test_enqueue_realtime_log(self, mock_get_manager):
        """Test convenience function for enqueuing real-time logs."""
        mock_manager = AsyncMock()
        mock_manager.enqueue_log_entry.return_value = True
        mock_get_manager.return_value = mock_manager
        
        result = await enqueue_realtime_log(
            content="Test message",
            source_path="/var/log/test.log",
            source_name="test_source"
        )
        
        assert result is True
        mock_manager.enqueue_log_entry.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('app.realtime.queue_integration.get_integration_manager')
    async def test_get_realtime_processing_status(self, mock_get_manager):
        """Test getting real-time processing status."""
        from app.realtime.queue_integration import get_realtime_processing_status
        
        mock_manager = AsyncMock()
        mock_manager.get_queue_status.return_value = {'status': 'running'}
        mock_get_manager.return_value = mock_manager
        
        status = await get_realtime_processing_status()
        
        assert status == {'status': 'running'}
        mock_manager.get_queue_status.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])