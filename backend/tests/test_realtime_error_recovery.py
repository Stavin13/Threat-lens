"""
Tests for real-time system error handling and recovery scenarios.

Tests various failure modes, error recovery mechanisms, and system resilience
under adverse conditions.
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import List, Dict, Any

from app.realtime.file_monitor import LogFileMonitor, LogEntry
from app.realtime.ingestion_queue import RealtimeIngestionQueue, LogEntryPriority, ProcessingStatus
from app.realtime.websocket_server import WebSocketManager, EventUpdate
from app.realtime.models import LogSourceConfig, LogSourceType, MonitoringStatus
from app.realtime.exceptions import RealtimeError, ProcessingError, MonitoringError, WebSocketError


class ErrorInjectionHarness:
    """Test harness for injecting various types of errors."""
    
    def __init__(self):
        self.file_monitor = None
        self.ingestion_queue = None
        self.websocket_manager = None
        self.temp_files = []
        self.error_counts = {
            'processing_errors': 0,
            'websocket_errors': 0,
            'file_errors': 0,
            'queue_errors': 0
        }
        self.recovery_events = []
    
    async def setup(self):
        """Set up components for error testing."""
        self.file_monitor = LogFileMonitor("error_test_monitor")
        self.ingestion_queue = RealtimeIngestionQueue(
            max_queue_size=100,
            batch_size=5,
            batch_timeout=0.5
        )
        self.websocket_manager = WebSocketManager(max_connections=10)
        
        await self.file_monitor.start()
        await self.ingestion_queue.start()
        await self.websocket_manager.start()
    
    async def teardown(self):
        """Clean up test harness."""
        if self.websocket_manager:
            await self.websocket_manager.stop()
        if self.ingestion_queue:
            await self.ingestion_queue.stop()
        if self.file_monitor:
            await self.file_monitor.stop()
        
        for temp_file in self.temp_files:
            try:
                os.unlink(temp_file)
            except FileNotFoundError:
                pass
    
    def create_temp_log_file(self, content: str = "") -> str:
        """Create temporary log file."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log')
        temp_file.write(content)
        temp_file.close()
        self.temp_files.append(temp_file.name)
        return temp_file.name
    
    async def inject_processing_error(self, error_type: str = "generic"):
        """Inject processing errors into the pipeline."""
        async def failing_processor(batch: List[LogEntry]):
            self.error_counts['processing_errors'] += 1
            
            if error_type == "timeout":
                await asyncio.sleep(10)  # Simulate timeout
            elif error_type == "exception":
                raise ProcessingError("Injected processing error")
            elif error_type == "memory":
                raise MemoryError("Simulated memory error")
            else:
                raise Exception("Generic injected error")
        
        self.ingestion_queue.set_batch_processor(failing_processor)
    
    async def inject_websocket_error(self, client_id: str, error_type: str = "disconnect"):
        """Inject WebSocket errors."""
        if error_type == "disconnect":
            await self.websocket_manager.disconnect(client_id, "Injected disconnect")
        elif error_type == "send_failure":
            # Mock the send method to fail
            if client_id in self.websocket_manager.connections:
                connection = self.websocket_manager.connections[client_id]
                original_send = connection.websocket.send_text
                
                async def failing_send(message):
                    self.error_counts['websocket_errors'] += 1
                    raise Exception("Injected send error")
                
                connection.websocket.send_text = failing_send
    
    def inject_file_error(self, file_path: str, error_type: str = "permission"):
        """Inject file system errors."""
        if error_type == "permission":
            os.chmod(file_path, 0o000)  # Remove all permissions
        elif error_type == "delete":
            os.unlink(file_path)  # Delete the file
        elif error_type == "corrupt":
            # Write binary data to corrupt the file
            with open(file_path, 'wb') as f:
                f.write(b'\x00\x01\x02\x03\x04\x05')
    
    def record_recovery_event(self, component: str, event_type: str, details: Dict[str, Any]):
        """Record a recovery event."""
        self.recovery_events.append({
            'timestamp': datetime.now(timezone.utc),
            'component': component,
            'event_type': event_type,
            'details': details
        })


@pytest_asyncio.fixture
async def error_harness():
    """Create error injection test harness."""
    harness = ErrorInjectionHarness()
    await harness.setup()
    yield harness
    await harness.teardown()


class TestProcessingErrorRecovery:
    """Test processing error recovery mechanisms."""
    
    @pytest.mark.asyncio
    async def test_processing_exception_recovery(self, error_harness):
        """Test recovery from processing exceptions."""
        # Create log file and source
        log_file = error_harness.create_temp_log_file("initial content\n")
        source_config = LogSourceConfig(
            source_name="exception_test",
            path=log_file,
            source_type=LogSourceType.FILE,
            enabled=True
        )
        error_harness.file_monitor.add_log_source(source_config)
        
        # Inject processing error
        await error_harness.inject_processing_error("exception")
        
        # Create log entry manually
        entry = LogEntry(
            content="test entry for exception",
            source_path=log_file,
            source_name="exception_test",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.MEDIUM,
            max_retries=3
        )
        
        # Enqueue entry
        await error_harness.ingestion_queue.enqueue_log_entry(entry)
        
        # Wait for retry attempts
        await asyncio.sleep(2.0)
        
        # Verify error was recorded
        assert error_harness.error_counts['processing_errors'] > 0
        
        # Verify entry was marked for retry or failed
        retrieved_entry = await error_harness.ingestion_queue.get_entry_by_id(entry.entry_id)
        assert retrieved_entry is not None
        assert retrieved_entry.status in [ProcessingStatus.RETRYING, ProcessingStatus.FAILED]
        assert retrieved_entry.error_count > 0
    
    @pytest.mark.asyncio
    async def test_processing_timeout_handling(self, error_harness):
        """Test handling of processing timeouts."""
        # Create log entry
        entry = LogEntry(
            content="timeout test entry",
            source_path="/test/path",
            source_name="timeout_test",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.MEDIUM
        )
        
        # Inject timeout error
        await error_harness.inject_processing_error("timeout")
        
        # Enqueue entry
        await error_harness.ingestion_queue.enqueue_log_entry(entry)
        
        # Wait briefly (should timeout before this)
        await asyncio.sleep(1.0)
        
        # Verify processing was attempted
        assert error_harness.error_counts['processing_errors'] > 0
        
        # Verify queue is still functional
        queue_stats = await error_harness.ingestion_queue.get_queue_stats()
        assert queue_stats is not None
    
    @pytest.mark.asyncio
    async def test_memory_error_recovery(self, error_harness):
        """Test recovery from memory errors."""
        # Create multiple entries to test memory pressure
        entries = []
        for i in range(10):
            entry = LogEntry(
                content=f"memory test entry {i}",
                source_path="/test/path",
                source_name="memory_test",
                timestamp=datetime.now(timezone.utc),
                priority=LogEntryPriority.MEDIUM
            )
            entries.append(entry)
        
        # Inject memory error
        await error_harness.inject_processing_error("memory")
        
        # Enqueue entries
        for entry in entries:
            await error_harness.ingestion_queue.enqueue_log_entry(entry)
        
        # Wait for processing attempts
        await asyncio.sleep(1.0)
        
        # Verify memory error was encountered
        assert error_harness.error_counts['processing_errors'] > 0
        
        # Verify system didn't crash
        assert error_harness.ingestion_queue.is_running
    
    @pytest.mark.asyncio
    async def test_successful_retry_after_failure(self, error_harness):
        """Test successful processing after initial failures."""
        failure_count = 0
        processed_entries = []
        
        async def intermittent_failing_processor(batch: List[LogEntry]):
            nonlocal failure_count
            failure_count += 1
            
            if failure_count <= 2:  # Fail first 2 attempts
                error_harness.error_counts['processing_errors'] += 1
                raise ProcessingError("Intermittent failure")
            
            # Succeed on subsequent attempts
            for entry in batch:
                processed_entries.append(entry)
                error_harness.record_recovery_event(
                    "processor", "success_after_retry",
                    {"entry_id": entry.entry_id, "retry_count": failure_count}
                )
        
        error_harness.ingestion_queue.set_batch_processor(intermittent_failing_processor)
        
        # Create and enqueue entry
        entry = LogEntry(
            content="retry test entry",
            source_path="/test/path",
            source_name="retry_test",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.MEDIUM,
            max_retries=5
        )
        
        await error_harness.ingestion_queue.enqueue_log_entry(entry)
        
        # Wait for retries and eventual success
        await asyncio.sleep(3.0)
        
        # Verify initial failures occurred
        assert error_harness.error_counts['processing_errors'] >= 2
        
        # Verify eventual success
        assert len(processed_entries) > 0
        assert len(error_harness.recovery_events) > 0
        
        # Verify recovery event was recorded
        success_events = [e for e in error_harness.recovery_events 
                         if e['event_type'] == 'success_after_retry']
        assert len(success_events) > 0


class TestWebSocketErrorRecovery:
    """Test WebSocket error recovery mechanisms."""
    
    @pytest.mark.asyncio
    async def test_client_disconnect_recovery(self, error_harness):
        """Test handling of client disconnections."""
        # Connect multiple clients
        client1_id = await error_harness.websocket_manager.connect(MockWebSocket(), "client1")
        client2_id = await error_harness.websocket_manager.connect(MockWebSocket(), "client2")
        
        initial_client_count = len(error_harness.websocket_manager.connections)
        assert initial_client_count == 2
        
        # Inject disconnect error for one client
        await error_harness.inject_websocket_error(client1_id, "disconnect")
        
        # Verify client was removed
        assert len(error_harness.websocket_manager.connections) == 1
        assert client1_id not in error_harness.websocket_manager.connections
        assert client2_id in error_harness.websocket_manager.connections
        
        # Verify remaining client still functional
        test_event = EventUpdate(
            event_type="test_after_disconnect",
            data={"message": "test"}
        )
        
        result = await error_harness.websocket_manager.broadcast_event(test_event)
        assert result == 1  # Should broadcast to remaining client
    
    @pytest.mark.asyncio
    async def test_send_failure_recovery(self, error_harness):
        """Test recovery from WebSocket send failures."""
        # Connect client
        mock_ws = MockWebSocket()
        client_id = await error_harness.websocket_manager.connect(mock_ws, "send_fail_client")
        
        # Inject send failure
        await error_harness.inject_websocket_error(client_id, "send_failure")
        
        # Try to send message
        test_message = {"type": "test", "data": {"content": "test message"}}
        result = await error_harness.websocket_manager.send_to_client(client_id, test_message)
        
        # Verify send failed
        assert result is False
        assert error_harness.error_counts['websocket_errors'] > 0
        
        # Verify client was disconnected due to send failure
        assert client_id not in error_harness.websocket_manager.connections
    
    @pytest.mark.asyncio
    async def test_broadcast_partial_failure_recovery(self, error_harness):
        """Test recovery when broadcast fails to some clients."""
        # Connect multiple clients
        good_client_id = await error_harness.websocket_manager.connect(MockWebSocket(), "good_client")
        bad_client_id = await error_harness.websocket_manager.connect(MockWebSocket(), "bad_client")
        
        # Inject error for one client
        await error_harness.inject_websocket_error(bad_client_id, "send_failure")
        
        # Broadcast event
        test_event = EventUpdate(
            event_type="partial_failure_test",
            data={"message": "broadcast test"}
        )
        
        result = await error_harness.websocket_manager.broadcast_event(test_event)
        await asyncio.sleep(0.2)  # Wait for broadcast processing
        
        # Verify broadcast continued despite partial failure
        assert len(error_harness.websocket_manager.connections) >= 1
        
        # Verify good client still connected
        assert good_client_id in error_harness.websocket_manager.connections
    
    @pytest.mark.asyncio
    async def test_connection_limit_recovery(self, error_harness):
        """Test recovery when connection limit is reached."""
        # Fill up to connection limit
        client_ids = []
        for i in range(error_harness.websocket_manager.max_connections):
            try:
                client_id = await error_harness.websocket_manager.connect(
                    MockWebSocket(), f"client_{i}"
                )
                client_ids.append(client_id)
            except WebSocketError:
                break
        
        # Try to exceed limit
        with pytest.raises(WebSocketError):
            await error_harness.websocket_manager.connect(MockWebSocket(), "overflow_client")
        
        # Disconnect some clients
        for i in range(3):
            if i < len(client_ids):
                await error_harness.websocket_manager.disconnect(client_ids[i])
        
        # Verify new connections can be made after disconnections
        new_client_id = await error_harness.websocket_manager.connect(
            MockWebSocket(), "recovery_client"
        )
        assert new_client_id is not None
        assert new_client_id in error_harness.websocket_manager.connections


class TestFileSystemErrorRecovery:
    """Test file system error recovery mechanisms."""
    
    @pytest.mark.asyncio
    async def test_permission_error_recovery(self, error_harness):
        """Test recovery from file permission errors."""
        # Create log file
        log_file = error_harness.create_temp_log_file("initial content\n")
        source_config = LogSourceConfig(
            source_name="permission_test",
            path=log_file,
            source_type=LogSourceType.FILE,
            enabled=True
        )
        
        error_harness.file_monitor.add_log_source(source_config)
        
        # Inject permission error
        error_harness.inject_file_error(log_file, "permission")
        
        # Try to trigger file reading
        with open(log_file, 'a') as f:
            f.write("new content\n")
        
        # Wait for error detection
        await asyncio.sleep(1.0)
        
        # Check monitoring status
        status = error_harness.file_monitor.get_monitoring_status()
        source_status = status["sources"].get("permission_test")
        
        # Restore permissions
        os.chmod(log_file, 0o644)
        
        # Verify system can recover
        with open(log_file, 'a') as f:
            f.write("recovery content\n")
        
        await asyncio.sleep(1.0)
        
        # System should handle the error gracefully
        assert error_harness.file_monitor.is_running
    
    @pytest.mark.asyncio
    async def test_file_deletion_recovery(self, error_harness):
        """Test recovery when monitored file is deleted."""
        # Create log file
        log_file = error_harness.create_temp_log_file("initial content\n")
        source_config = LogSourceConfig(
            source_name="deletion_test",
            path=log_file,
            source_type=LogSourceType.FILE,
            enabled=True
        )
        
        error_harness.file_monitor.add_log_source(source_config)
        
        # Delete the file
        error_harness.inject_file_error(log_file, "delete")
        
        # Wait for error detection
        await asyncio.sleep(1.0)
        
        # Recreate the file
        with open(log_file, 'w') as f:
            f.write("recreated content\n")
        
        # Wait for recovery
        await asyncio.sleep(1.0)
        
        # Verify system is still running
        assert error_harness.file_monitor.is_running
        
        # Check monitoring status
        status = error_harness.file_monitor.get_monitoring_status()
        assert "deletion_test" in status["sources"]
    
    @pytest.mark.asyncio
    async def test_corrupted_file_recovery(self, error_harness):
        """Test recovery from corrupted file content."""
        # Create log file
        log_file = error_harness.create_temp_log_file("initial content\n")
        source_config = LogSourceConfig(
            source_name="corruption_test",
            path=log_file,
            source_type=LogSourceType.FILE,
            enabled=True
        )
        
        error_harness.file_monitor.add_log_source(source_config)
        
        # Corrupt the file
        error_harness.inject_file_error(log_file, "corrupt")
        
        # Wait for error detection
        await asyncio.sleep(1.0)
        
        # Restore file with valid content
        with open(log_file, 'w') as f:
            f.write("restored content\n")
        
        # Wait for recovery
        await asyncio.sleep(1.0)
        
        # Verify system recovered
        assert error_harness.file_monitor.is_running
        
        # Verify file can be monitored again
        with open(log_file, 'a') as f:
            f.write("new valid content\n")
        
        await asyncio.sleep(1.0)
        
        # System should handle recovery gracefully
        status = error_harness.file_monitor.get_monitoring_status()
        assert status["total_sources"] > 0


class TestSystemResilienceUnderLoad:
    """Test system resilience under various load and error conditions."""
    
    @pytest.mark.asyncio
    async def test_cascading_failure_recovery(self, error_harness):
        """Test recovery from cascading failures across components."""
        # Set up multiple components with potential failures
        log_file = error_harness.create_temp_log_file("initial\n")
        source_config = LogSourceConfig(
            source_name="cascade_test",
            path=log_file,
            source_type=LogSourceType.FILE,
            enabled=True
        )
        error_harness.file_monitor.add_log_source(source_config)
        
        # Connect WebSocket client
        client_id = await error_harness.websocket_manager.connect(MockWebSocket(), "cascade_client")
        
        # Inject multiple errors simultaneously
        await error_harness.inject_processing_error("exception")
        await error_harness.inject_websocket_error(client_id, "send_failure")
        error_harness.inject_file_error(log_file, "permission")
        
        # Try to process data despite errors
        entry = LogEntry(
            content="cascade test entry",
            source_path=log_file,
            source_name="cascade_test",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.MEDIUM
        )
        
        await error_harness.ingestion_queue.enqueue_log_entry(entry)
        
        # Wait for error propagation
        await asyncio.sleep(2.0)
        
        # Verify errors were encountered
        assert error_harness.error_counts['processing_errors'] > 0
        assert error_harness.error_counts['websocket_errors'] > 0
        
        # Verify core components are still running
        assert error_harness.file_monitor.is_running
        assert error_harness.ingestion_queue.is_running
        assert error_harness.websocket_manager.is_running
        
        # Restore system gradually
        os.chmod(log_file, 0o644)  # Fix file permissions
        
        # Set up working processor
        processed_entries = []
        
        async def recovery_processor(batch: List[LogEntry]):
            processed_entries.extend(batch)
        
        error_harness.ingestion_queue.set_batch_processor(recovery_processor)
        
        # Connect new WebSocket client
        recovery_client_id = await error_harness.websocket_manager.connect(
            MockWebSocket(), "recovery_client"
        )
        
        # Test recovery
        recovery_entry = LogEntry(
            content="recovery test entry",
            source_path=log_file,
            source_name="cascade_test",
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.MEDIUM
        )
        
        await error_harness.ingestion_queue.enqueue_log_entry(recovery_entry)
        
        # Wait for recovery processing
        await asyncio.sleep(1.0)
        
        # Verify system recovered
        assert len(processed_entries) > 0
        assert recovery_client_id in error_harness.websocket_manager.connections
    
    @pytest.mark.asyncio
    async def test_resource_exhaustion_recovery(self, error_harness):
        """Test recovery from resource exhaustion scenarios."""
        # Create many log sources to stress the system
        log_files = []
        for i in range(20):
            log_file = error_harness.create_temp_log_file(f"stress test {i}\n")
            log_files.append(log_file)
            
            source_config = LogSourceConfig(
                source_name=f"stress_source_{i}",
                path=log_file,
                source_type=LogSourceType.FILE,
                enabled=True
            )
            error_harness.file_monitor.add_log_source(source_config)
        
        # Connect many WebSocket clients
        client_ids = []
        for i in range(15):
            try:
                client_id = await error_harness.websocket_manager.connect(
                    MockWebSocket(), f"stress_client_{i}"
                )
                client_ids.append(client_id)
            except WebSocketError:
                break  # Hit connection limit
        
        # Generate high load
        for i, log_file in enumerate(log_files[:10]):  # Use subset to avoid overwhelming
            with open(log_file, 'a') as f:
                for j in range(5):
                    f.write(f"stress entry {j} from source {i}\n")
        
        # Wait for processing under stress
        await asyncio.sleep(3.0)
        
        # Verify system is still responsive
        assert error_harness.file_monitor.is_running
        assert error_harness.ingestion_queue.is_running
        assert error_harness.websocket_manager.is_running
        
        # Verify queue stats are available (system not deadlocked)
        queue_stats = await error_harness.ingestion_queue.get_queue_stats()
        assert queue_stats is not None
        
        # Verify WebSocket manager is responsive
        ws_stats = error_harness.websocket_manager.get_statistics()
        assert ws_stats is not None


class MockWebSocket:
    """Mock WebSocket for error testing."""
    
    def __init__(self, should_fail=False):
        self.messages = []
        self.closed = False
        self.should_fail = should_fail
        self.headers = {"user-agent": "test-client/1.0"}
    
    async def accept(self):
        if self.should_fail:
            raise Exception("Mock accept failure")
    
    async def send_text(self, message: str):
        if self.should_fail:
            raise Exception("Mock send failure")
        if not self.closed:
            self.messages.append(message)
    
    async def close(self, code=None, reason=None):
        self.closed = True


if __name__ == "__main__":
    pytest.main([__file__])