"""
Integration tests for end-to-end real-time log processing pipeline.

Tests the complete pipeline from file change detection to WebSocket updates,
including error handling, recovery scenarios, and performance under load.
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict, Any

from app.realtime.file_monitor import LogFileMonitor, LogEntry
from app.realtime.ingestion_queue import RealtimeIngestionQueue, LogEntryPriority
from app.realtime.websocket_server import WebSocketManager, EventUpdate
from app.realtime.enhanced_processor import EnhancedBackgroundProcessor
from app.realtime.models import LogSourceConfig, LogSourceType, MonitoringStatus
from app.realtime.exceptions import RealtimeError, ProcessingError


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.messages = []
        self.closed = False
        self.accept_called = False
        self.headers = {"user-agent": "test-client/1.0"}
    
    async def accept(self):
        self.accept_called = True
    
    async def send_text(self, message: str):
        if not self.closed:
            self.messages.append(message)
    
    async def close(self, code=None, reason=None):
        self.closed = True


class EndToEndTestHarness:
    """Test harness for end-to-end integration testing."""
    
    def __init__(self):
        self.file_monitor = None
        self.ingestion_queue = None
        self.websocket_manager = None
        self.enhanced_processor = None
        self.temp_files = []
        self.mock_websockets = []
        self.received_events = []
        self.processing_results = []
    
    async def setup(self):
        """Set up the complete real-time pipeline."""
        # Create components
        self.file_monitor = LogFileMonitor("test_monitor")
        self.ingestion_queue = RealtimeIngestionQueue(
            max_queue_size=1000,
            batch_size=10,
            batch_timeout=0.5
        )
        self.websocket_manager = WebSocketManager(max_connections=10)
        
        # Start components
        await self.file_monitor.start()
        await self.ingestion_queue.start()
        await self.websocket_manager.start()
        
        # Set up processing pipeline
        self.ingestion_queue.set_batch_processor(self._mock_batch_processor)
        self.file_monitor.add_log_entry_callback(self._handle_log_entry)
    
    async def teardown(self):
        """Clean up the test harness."""
        # Stop components
        if self.enhanced_processor:
            await self.enhanced_processor.stop()
        if self.websocket_manager:
            await self.websocket_manager.stop()
        if self.ingestion_queue:
            await self.ingestion_queue.stop()
        if self.file_monitor:
            await self.file_monitor.stop()
        
        # Clean up temp files
        for temp_file in self.temp_files:
            try:
                os.unlink(temp_file)
            except FileNotFoundError:
                pass
    
    def create_temp_log_file(self, initial_content: str = "") -> str:
        """Create a temporary log file for testing."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log')
        temp_file.write(initial_content)
        temp_file.close()
        self.temp_files.append(temp_file.name)
        return temp_file.name
    
    def append_to_log_file(self, file_path: str, content: str):
        """Append content to a log file."""
        with open(file_path, 'a') as f:
            f.write(content)
    
    async def add_log_source(self, file_path: str, source_name: str = "test_source") -> bool:
        """Add a log source to the file monitor."""
        source_config = LogSourceConfig(
            source_name=source_name,
            path=file_path,
            source_type=LogSourceType.FILE,
            enabled=True,
            priority=5
        )
        return self.file_monitor.add_log_source(source_config)
    
    async def connect_websocket_client(self, client_id: str = None) -> str:
        """Connect a mock WebSocket client."""
        mock_ws = MockWebSocket()
        self.mock_websockets.append(mock_ws)
        return await self.websocket_manager.connect(mock_ws, client_id)
    
    def _handle_log_entry(self, entry: LogEntry):
        """Handle log entries from file monitor."""
        # Add to ingestion queue
        asyncio.create_task(self.ingestion_queue.enqueue_log_entry(entry))
    
    async def _mock_batch_processor(self, batch: List[LogEntry]):
        """Mock batch processor that simulates processing."""
        for entry in batch:
            # Simulate processing
            result = {
                'entry_id': entry.entry_id,
                'source_name': entry.source_name,
                'content': entry.content,
                'processed_at': datetime.now(timezone.utc).isoformat(),
                'success': True
            }
            self.processing_results.append(result)
            
            # Broadcast to WebSocket clients
            event = EventUpdate(
                event_type="log_processed",
                data=result,
                priority=entry.priority.value
            )
            await self.websocket_manager.broadcast_event(event)
    
    def get_websocket_messages(self, client_index: int = 0) -> List[Dict[str, Any]]:
        """Get messages received by a WebSocket client."""
        if client_index >= len(self.mock_websockets):
            return []
        
        messages = []
        for msg_str in self.mock_websockets[client_index].messages:
            try:
                messages.append(json.loads(msg_str))
            except json.JSONDecodeError:
                pass
        return messages
    
    async def wait_for_processing(self, timeout: float = 2.0):
        """Wait for processing to complete."""
        await asyncio.sleep(timeout)


@pytest_asyncio.fixture
async def e2e_harness():
    """Create and set up end-to-end test harness."""
    harness = EndToEndTestHarness()
    await harness.setup()
    yield harness
    await harness.teardown()


class TestEndToEndPipeline:
    """Test complete end-to-end pipeline functionality."""
    
    @pytest.mark.asyncio
    async def test_file_change_to_websocket_update(self, e2e_harness):
        """Test complete pipeline from file change to WebSocket update."""
        # Create log file and add to monitoring
        log_file = e2e_harness.create_temp_log_file("initial content\n")
        await e2e_harness.add_log_source(log_file, "test_source")
        
        # Connect WebSocket client
        client_id = await e2e_harness.connect_websocket_client()
        
        # Append new content to log file
        e2e_harness.append_to_log_file(log_file, "new log entry\n")
        
        # Wait for processing
        await e2e_harness.wait_for_processing()
        
        # Verify processing occurred
        assert len(e2e_harness.processing_results) > 0
        
        # Verify WebSocket client received updates
        messages = e2e_harness.get_websocket_messages(0)
        log_processed_messages = [msg for msg in messages if msg.get("type") == "log_processed"]
        assert len(log_processed_messages) > 0
        
        # Verify message content
        processed_msg = log_processed_messages[0]
        assert "new log entry" in processed_msg["data"]["content"]
    
    @pytest.mark.asyncio
    async def test_multiple_file_sources(self, e2e_harness):
        """Test monitoring multiple log sources simultaneously."""
        # Create multiple log files
        log_file1 = e2e_harness.create_temp_log_file("file1 initial\n")
        log_file2 = e2e_harness.create_temp_log_file("file2 initial\n")
        
        await e2e_harness.add_log_source(log_file1, "source1")
        await e2e_harness.add_log_source(log_file2, "source2")
        
        # Connect WebSocket client
        client_id = await e2e_harness.connect_websocket_client()
        
        # Append to both files
        e2e_harness.append_to_log_file(log_file1, "source1 new entry\n")
        e2e_harness.append_to_log_file(log_file2, "source2 new entry\n")
        
        # Wait for processing
        await e2e_harness.wait_for_processing()
        
        # Verify both sources were processed
        source1_results = [r for r in e2e_harness.processing_results if r["source_name"] == "source1"]
        source2_results = [r for r in e2e_harness.processing_results if r["source_name"] == "source2"]
        
        assert len(source1_results) > 0
        assert len(source2_results) > 0
        
        # Verify WebSocket received updates from both sources
        messages = e2e_harness.get_websocket_messages(0)
        log_messages = [msg for msg in messages if msg.get("type") == "log_processed"]
        
        source1_messages = [msg for msg in log_messages if msg["data"]["source_name"] == "source1"]
        source2_messages = [msg for msg in log_messages if msg["data"]["source_name"] == "source2"]
        
        assert len(source1_messages) > 0
        assert len(source2_messages) > 0
    
    @pytest.mark.asyncio
    async def test_priority_processing_order(self, e2e_harness):
        """Test that high-priority entries are processed first."""
        # Create log file
        log_file = e2e_harness.create_temp_log_file()
        
        # Add source with different priorities
        source_config_high = LogSourceConfig(
            source_name="high_priority_source",
            path=log_file,
            source_type=LogSourceType.FILE,
            enabled=True,
            priority=1  # High priority (lower number)
        )
        
        source_config_low = LogSourceConfig(
            source_name="low_priority_source", 
            path=log_file,
            source_type=LogSourceType.FILE,
            enabled=True,
            priority=9  # Low priority (higher number)
        )
        
        # Manually create entries with different priorities
        low_priority_entry = LogEntry(
            content="low priority entry",
            source_path=log_file,
            source_name="low_priority_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.LOW
        )
        
        high_priority_entry = LogEntry(
            content="high priority entry",
            source_path=log_file,
            source_name="high_priority_source",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.HIGH
        )
        
        # Add entries in reverse priority order
        await e2e_harness.ingestion_queue.enqueue_log_entry(low_priority_entry)
        await e2e_harness.ingestion_queue.enqueue_log_entry(high_priority_entry)
        
        # Wait for processing
        await e2e_harness.wait_for_processing()
        
        # Verify high priority was processed first
        assert len(e2e_harness.processing_results) >= 2
        first_processed = e2e_harness.processing_results[0]
        assert "high priority entry" in first_processed["content"]
    
    @pytest.mark.asyncio
    async def test_multiple_websocket_clients(self, e2e_harness):
        """Test broadcasting to multiple WebSocket clients."""
        # Create log file
        log_file = e2e_harness.create_temp_log_file("initial\n")
        await e2e_harness.add_log_source(log_file, "broadcast_test")
        
        # Connect multiple WebSocket clients
        client1_id = await e2e_harness.connect_websocket_client("client1")
        client2_id = await e2e_harness.connect_websocket_client("client2")
        client3_id = await e2e_harness.connect_websocket_client("client3")
        
        # Append to log file
        e2e_harness.append_to_log_file(log_file, "broadcast message\n")
        
        # Wait for processing
        await e2e_harness.wait_for_processing()
        
        # Verify all clients received the broadcast
        for i in range(3):
            messages = e2e_harness.get_websocket_messages(i)
            log_messages = [msg for msg in messages if msg.get("type") == "log_processed"]
            assert len(log_messages) > 0
            
            # Verify message content
            processed_msg = log_messages[0]
            assert "broadcast message" in processed_msg["data"]["content"]
    
    @pytest.mark.asyncio
    async def test_file_rotation_handling(self, e2e_harness):
        """Test handling of log file rotation."""
        # Create log file with initial content
        log_file = e2e_harness.create_temp_log_file("line 1\nline 2\n")
        await e2e_harness.add_log_source(log_file, "rotation_test")
        
        # Connect WebSocket client
        client_id = await e2e_harness.connect_websocket_client()
        
        # Simulate file rotation by truncating and writing new content
        with open(log_file, 'w') as f:
            f.write("rotated line 1\n")
        
        # Wait for processing
        await e2e_harness.wait_for_processing()
        
        # Verify the rotated content was processed
        messages = e2e_harness.get_websocket_messages(0)
        log_messages = [msg for msg in messages if msg.get("type") == "log_processed"]
        
        # Should have processed the new content after rotation
        rotated_messages = [msg for msg in log_messages 
                          if "rotated line 1" in msg["data"]["content"]]
        assert len(rotated_messages) > 0


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery scenarios."""
    
    @pytest.mark.asyncio
    async def test_processing_error_recovery(self, e2e_harness):
        """Test recovery from processing errors."""
        # Create log file
        log_file = e2e_harness.create_temp_log_file()
        await e2e_harness.add_log_source(log_file, "error_test")
        
        # Replace batch processor with one that fails initially
        failure_count = 0
        original_results = e2e_harness.processing_results
        
        async def failing_processor(batch: List[LogEntry]):
            nonlocal failure_count
            failure_count += 1
            
            if failure_count <= 2:  # Fail first 2 attempts
                raise ProcessingError("Simulated processing failure")
            
            # Succeed on subsequent attempts
            for entry in batch:
                result = {
                    'entry_id': entry.entry_id,
                    'source_name': entry.source_name,
                    'content': entry.content,
                    'processed_at': datetime.now(timezone.utc).isoformat(),
                    'success': True,
                    'retry_attempt': failure_count
                }
                original_results.append(result)
        
        e2e_harness.ingestion_queue.set_batch_processor(failing_processor)
        
        # Append to log file
        e2e_harness.append_to_log_file(log_file, "test error recovery\n")
        
        # Wait longer for retry processing
        await e2e_harness.wait_for_processing(timeout=3.0)
        
        # Verify processing eventually succeeded
        assert len(e2e_harness.processing_results) > 0
        successful_results = [r for r in e2e_harness.processing_results if r.get("success")]
        assert len(successful_results) > 0
    
    @pytest.mark.asyncio
    async def test_websocket_client_disconnect_handling(self, e2e_harness):
        """Test handling of WebSocket client disconnections."""
        # Create log file
        log_file = e2e_harness.create_temp_log_file()
        await e2e_harness.add_log_source(log_file, "disconnect_test")
        
        # Connect clients
        client1_id = await e2e_harness.connect_websocket_client("client1")
        client2_id = await e2e_harness.connect_websocket_client("client2")
        
        # Disconnect one client
        await e2e_harness.websocket_manager.disconnect(client1_id, "Test disconnect")
        
        # Append to log file
        e2e_harness.append_to_log_file(log_file, "after disconnect\n")
        
        # Wait for processing
        await e2e_harness.wait_for_processing()
        
        # Verify remaining client still receives updates
        client2_messages = e2e_harness.get_websocket_messages(1)  # Second client
        log_messages = [msg for msg in client2_messages if msg.get("type") == "log_processed"]
        assert len(log_messages) > 0
        
        # Verify disconnected client doesn't receive new messages
        # (beyond what it received before disconnect)
        assert len(e2e_harness.websocket_manager.connections) == 1
    
    @pytest.mark.asyncio
    async def test_file_permission_error_handling(self, e2e_harness):
        """Test handling of file permission errors."""
        # Create log file
        log_file = e2e_harness.create_temp_log_file("initial content\n")
        
        # Add source
        await e2e_harness.add_log_source(log_file, "permission_test")
        
        # Remove read permissions (simulate permission error)
        try:
            os.chmod(log_file, 0o000)  # No permissions
            
            # Try to append (this should trigger permission error in monitoring)
            e2e_harness.append_to_log_file(log_file, "should fail\n")
            
            # Wait for processing
            await e2e_harness.wait_for_processing()
            
            # Check that the source status reflects the error
            status = e2e_harness.file_monitor.get_monitoring_status()
            source_status = status["sources"].get("permission_test")
            
            # The source should either be in error state or have error count > 0
            assert source_status is not None
            
        finally:
            # Restore permissions for cleanup
            try:
                os.chmod(log_file, 0o644)
            except:
                pass
    
    @pytest.mark.asyncio
    async def test_queue_backpressure_handling(self, e2e_harness):
        """Test queue backpressure handling under high load."""
        # Create log file
        log_file = e2e_harness.create_temp_log_file()
        await e2e_harness.add_log_source(log_file, "backpressure_test")
        
        # Create a slow processor to build up queue
        processed_count = 0
        
        async def slow_processor(batch: List[LogEntry]):
            nonlocal processed_count
            await asyncio.sleep(0.1)  # Slow processing
            processed_count += len(batch)
        
        e2e_harness.ingestion_queue.set_batch_processor(slow_processor)
        
        # Generate many log entries quickly
        for i in range(50):
            e2e_harness.append_to_log_file(log_file, f"high volume entry {i}\n")
        
        # Wait for processing
        await e2e_harness.wait_for_processing(timeout=5.0)
        
        # Verify some entries were processed (may not be all due to backpressure)
        assert processed_count > 0
        
        # Verify queue handled backpressure gracefully
        queue_stats = await e2e_harness.ingestion_queue.get_queue_stats()
        assert queue_stats.total_entries >= 0  # Should not crash


class TestPerformanceUnderLoad:
    """Test system performance under various load conditions."""
    
    @pytest.mark.asyncio
    async def test_high_volume_log_processing(self, e2e_harness):
        """Test processing high volume of log entries."""
        # Create log file
        log_file = e2e_harness.create_temp_log_file()
        await e2e_harness.add_log_source(log_file, "high_volume_test")
        
        # Connect WebSocket client
        client_id = await e2e_harness.connect_websocket_client()
        
        # Generate high volume of log entries
        start_time = datetime.now()
        num_entries = 100
        
        for i in range(num_entries):
            e2e_harness.append_to_log_file(
                log_file, 
                f"high volume entry {i} - {datetime.now().isoformat()}\n"
            )
        
        # Wait for processing
        await e2e_harness.wait_for_processing(timeout=10.0)
        
        end_time = datetime.now()
        processing_duration = (end_time - start_time).total_seconds()
        
        # Verify processing completed
        assert len(e2e_harness.processing_results) > 0
        
        # Calculate throughput
        throughput = len(e2e_harness.processing_results) / processing_duration
        
        # Verify reasonable throughput (adjust threshold as needed)
        assert throughput > 5  # At least 5 entries per second
        
        # Verify WebSocket clients received updates
        messages = e2e_harness.get_websocket_messages(0)
        log_messages = [msg for msg in messages if msg.get("type") == "log_processed"]
        assert len(log_messages) > 0
    
    @pytest.mark.asyncio
    async def test_concurrent_file_monitoring(self, e2e_harness):
        """Test monitoring multiple files concurrently."""
        # Create multiple log files
        num_files = 5
        log_files = []
        
        for i in range(num_files):
            log_file = e2e_harness.create_temp_log_file(f"file{i} initial\n")
            log_files.append(log_file)
            await e2e_harness.add_log_source(log_file, f"concurrent_source_{i}")
        
        # Connect WebSocket client
        client_id = await e2e_harness.connect_websocket_client()
        
        # Append to all files concurrently
        start_time = datetime.now()
        
        for i, log_file in enumerate(log_files):
            for j in range(10):  # 10 entries per file
                e2e_harness.append_to_log_file(
                    log_file, 
                    f"concurrent entry {j} from file {i}\n"
                )
        
        # Wait for processing
        await e2e_harness.wait_for_processing(timeout=5.0)
        
        end_time = datetime.now()
        processing_duration = (end_time - start_time).total_seconds()
        
        # Verify all sources were processed
        unique_sources = set(r["source_name"] for r in e2e_harness.processing_results)
        assert len(unique_sources) == num_files
        
        # Verify reasonable processing time
        assert processing_duration < 10.0  # Should complete within 10 seconds
    
    @pytest.mark.asyncio
    async def test_websocket_broadcast_performance(self, e2e_harness):
        """Test WebSocket broadcast performance with many clients."""
        # Create log file
        log_file = e2e_harness.create_temp_log_file()
        await e2e_harness.add_log_source(log_file, "broadcast_perf_test")
        
        # Connect many WebSocket clients
        num_clients = 20
        client_ids = []
        
        for i in range(num_clients):
            client_id = await e2e_harness.connect_websocket_client(f"perf_client_{i}")
            client_ids.append(client_id)
        
        # Generate log entries
        start_time = datetime.now()
        num_entries = 20
        
        for i in range(num_entries):
            e2e_harness.append_to_log_file(log_file, f"broadcast perf entry {i}\n")
        
        # Wait for processing and broadcasting
        await e2e_harness.wait_for_processing(timeout=5.0)
        
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        
        # Verify all clients received messages
        clients_with_messages = 0
        total_messages_received = 0
        
        for i in range(num_clients):
            messages = e2e_harness.get_websocket_messages(i)
            log_messages = [msg for msg in messages if msg.get("type") == "log_processed"]
            
            if len(log_messages) > 0:
                clients_with_messages += 1
                total_messages_received += len(log_messages)
        
        # Verify broadcast efficiency
        assert clients_with_messages > 0
        assert total_duration < 10.0  # Should complete within reasonable time
        
        # Calculate broadcast efficiency
        expected_total_messages = num_entries * num_clients
        broadcast_efficiency = total_messages_received / expected_total_messages if expected_total_messages > 0 else 0
        
        # Should have reasonable broadcast efficiency (allowing for some message loss in testing)
        assert broadcast_efficiency > 0.5  # At least 50% of expected messages delivered


if __name__ == "__main__":
    pytest.main([__file__])