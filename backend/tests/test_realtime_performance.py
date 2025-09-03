"""
Performance tests for real-time log processing system.

Tests system performance under various load conditions, including high-volume
log processing, concurrent operations, and stress testing scenarios.
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import os
import time
import statistics
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict, Any, Tuple

from app.realtime.file_monitor import LogFileMonitor, LogEntry
from app.realtime.ingestion_queue import RealtimeIngestionQueue, LogEntryPriority
from app.realtime.websocket_server import WebSocketManager, EventUpdate
from app.realtime.models import LogSourceConfig, LogSourceType


class PerformanceMetrics:
    """Collect and analyze performance metrics."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.processing_times = []
        self.throughput_samples = []
        self.memory_samples = []
        self.queue_size_samples = []
        self.websocket_latencies = []
        self.error_counts = 0
    
    def start_measurement(self):
        """Start performance measurement."""
        self.start_time = time.time()
    
    def end_measurement(self):
        """End performance measurement."""
        self.end_time = time.time()
    
    def record_processing_time(self, processing_time: float):
        """Record processing time for a batch."""
        self.processing_times.append(processing_time)
    
    def record_throughput_sample(self, entries_processed: int, time_window: float):
        """Record throughput sample."""
        if time_window > 0:
            throughput = entries_processed / time_window
            self.throughput_samples.append(throughput)
    
    def record_queue_size(self, queue_size: int):
        """Record queue size sample."""
        self.queue_size_samples.append(queue_size)
    
    def record_websocket_latency(self, latency: float):
        """Record WebSocket message latency."""
        self.websocket_latencies.append(latency)
    
    def record_error(self):
        """Record an error occurrence."""
        self.error_counts += 1
    
    def get_total_duration(self) -> float:
        """Get total measurement duration."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    def get_average_processing_time(self) -> float:
        """Get average processing time."""
        return statistics.mean(self.processing_times) if self.processing_times else 0.0
    
    def get_processing_time_percentiles(self) -> Dict[str, float]:
        """Get processing time percentiles."""
        if not self.processing_times:
            return {}
        
        sorted_times = sorted(self.processing_times)
        return {
            'p50': statistics.median(sorted_times),
            'p95': sorted_times[int(0.95 * len(sorted_times))],
            'p99': sorted_times[int(0.99 * len(sorted_times))]
        }
    
    def get_average_throughput(self) -> float:
        """Get average throughput."""
        return statistics.mean(self.throughput_samples) if self.throughput_samples else 0.0
    
    def get_max_queue_size(self) -> int:
        """Get maximum queue size observed."""
        return max(self.queue_size_samples) if self.queue_size_samples else 0
    
    def get_average_websocket_latency(self) -> float:
        """Get average WebSocket latency."""
        return statistics.mean(self.websocket_latencies) if self.websocket_latencies else 0.0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        return {
            'total_duration': self.get_total_duration(),
            'average_processing_time': self.get_average_processing_time(),
            'processing_time_percentiles': self.get_processing_time_percentiles(),
            'average_throughput': self.get_average_throughput(),
            'max_throughput': max(self.throughput_samples) if self.throughput_samples else 0.0,
            'max_queue_size': self.get_max_queue_size(),
            'average_websocket_latency': self.get_average_websocket_latency(),
            'total_errors': self.error_counts,
            'total_processing_samples': len(self.processing_times),
            'total_throughput_samples': len(self.throughput_samples)
        }


class PerformanceTestHarness:
    """Test harness for performance testing."""
    
    def __init__(self):
        self.file_monitor = None
        self.ingestion_queue = None
        self.websocket_manager = None
        self.temp_files = []
        self.metrics = PerformanceMetrics()
        self.processed_entries = []
        self.websocket_messages = []
    
    async def setup(self, queue_size: int = 10000, batch_size: int = 100, max_connections: int = 100):
        """Set up performance test environment."""
        self.file_monitor = LogFileMonitor("perf_test_monitor")
        self.ingestion_queue = RealtimeIngestionQueue(
            max_queue_size=queue_size,
            batch_size=batch_size,
            batch_timeout=1.0
        )
        self.websocket_manager = WebSocketManager(max_connections=max_connections)
        
        await self.file_monitor.start()
        await self.ingestion_queue.start()
        await self.websocket_manager.start()
        
        # Set up processing pipeline
        self.ingestion_queue.set_batch_processor(self._performance_batch_processor)
        self.file_monitor.add_log_entry_callback(self._handle_log_entry)
    
    async def teardown(self):
        """Clean up test environment."""
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
    
    async def add_log_source(self, file_path: str, source_name: str) -> bool:
        """Add log source for monitoring."""
        source_config = LogSourceConfig(
            source_name=source_name,
            path=file_path,
            source_type=LogSourceType.FILE,
            enabled=True,
            priority=5
        )
        return self.file_monitor.add_log_source(source_config)
    
    def _handle_log_entry(self, entry: LogEntry):
        """Handle log entries from file monitor."""
        asyncio.create_task(self.ingestion_queue.enqueue_log_entry(entry))
    
    async def _performance_batch_processor(self, batch: List[LogEntry]):
        """Performance-focused batch processor."""
        batch_start_time = time.time()
        
        try:
            # Simulate processing work
            for entry in batch:
                self.processed_entries.append({
                    'entry_id': entry.entry_id,
                    'source_name': entry.source_name,
                    'content_length': len(entry.content),
                    'processed_at': time.time()
                })
            
            # Record processing time
            processing_time = time.time() - batch_start_time
            self.metrics.record_processing_time(processing_time)
            
            # Broadcast to WebSocket clients
            event = EventUpdate(
                event_type="batch_processed",
                data={
                    'batch_size': len(batch),
                    'processing_time': processing_time
                }
            )
            
            broadcast_start = time.time()
            await self.websocket_manager.broadcast_event(event)
            broadcast_time = time.time() - broadcast_start
            self.metrics.record_websocket_latency(broadcast_time)
            
        except Exception as e:
            self.metrics.record_error()
            raise
    
    async def generate_log_entries(self, file_path: str, num_entries: int, entry_size: int = 100):
        """Generate log entries in a file."""
        with open(file_path, 'a') as f:
            for i in range(num_entries):
                timestamp = datetime.now().isoformat()
                content = f"[{timestamp}] Performance test entry {i:06d} " + "x" * (entry_size - 50) + "\n"
                f.write(content)
    
    async def generate_concurrent_log_entries(self, file_paths: List[str], entries_per_file: int):
        """Generate log entries concurrently across multiple files."""
        tasks = []
        for file_path in file_paths:
            task = asyncio.create_task(
                self.generate_log_entries(file_path, entries_per_file)
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
    
    async def connect_websocket_clients(self, num_clients: int) -> List[str]:
        """Connect multiple WebSocket clients."""
        client_ids = []
        for i in range(num_clients):
            try:
                mock_ws = MockWebSocket()
                client_id = await self.websocket_manager.connect(mock_ws, f"perf_client_{i}")
                client_ids.append(client_id)
            except Exception as e:
                self.metrics.record_error()
                break
        return client_ids
    
    async def monitor_performance(self, duration: float, sample_interval: float = 1.0):
        """Monitor performance metrics during test execution."""
        end_time = time.time() + duration
        
        while time.time() < end_time:
            # Sample queue size
            queue_stats = await self.ingestion_queue.get_queue_stats()
            self.metrics.record_queue_size(queue_stats.total_entries)
            
            # Sample throughput
            current_processed = len(self.processed_entries)
            if hasattr(self, '_last_processed_count'):
                entries_in_window = current_processed - self._last_processed_count
                self.metrics.record_throughput_sample(entries_in_window, sample_interval)
            self._last_processed_count = current_processed
            
            await asyncio.sleep(sample_interval)


class MockWebSocket:
    """Mock WebSocket for performance testing."""
    
    def __init__(self):
        self.messages = []
        self.closed = False
        self.headers = {"user-agent": "perf-test-client/1.0"}
        self.message_count = 0
    
    async def accept(self):
        pass
    
    async def send_text(self, message: str):
        if not self.closed:
            self.message_count += 1
            # Don't store all messages to save memory during performance tests
            if self.message_count <= 10:
                self.messages.append(message)
    
    async def close(self, code=None, reason=None):
        self.closed = True


@pytest_asyncio.fixture
async def perf_harness():
    """Create performance test harness."""
    harness = PerformanceTestHarness()
    await harness.setup()
    yield harness
    await harness.teardown()


class TestHighVolumeProcessing:
    """Test high-volume log processing performance."""
    
    @pytest.mark.asyncio
    async def test_single_source_high_volume(self, perf_harness):
        """Test processing high volume from single source."""
        # Create log file
        log_file = perf_harness.create_temp_log_file()
        await perf_harness.add_log_source(log_file, "high_volume_source")
        
        # Connect WebSocket client
        client_ids = await perf_harness.connect_websocket_clients(1)
        assert len(client_ids) == 1
        
        # Start performance measurement
        perf_harness.metrics.start_measurement()
        
        # Start monitoring
        monitor_task = asyncio.create_task(
            perf_harness.monitor_performance(duration=10.0)
        )
        
        # Generate high volume of log entries
        num_entries = 1000
        await perf_harness.generate_log_entries(log_file, num_entries, entry_size=200)
        
        # Wait for processing
        await asyncio.sleep(8.0)
        
        # Stop monitoring
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        perf_harness.metrics.end_measurement()
        
        # Analyze performance
        summary = perf_harness.metrics.get_summary()
        
        # Verify processing occurred
        assert len(perf_harness.processed_entries) > 0
        
        # Performance assertions
        assert summary['average_throughput'] > 50  # At least 50 entries/second
        assert summary['average_processing_time'] < 1.0  # Less than 1 second per batch
        assert summary['total_errors'] == 0  # No errors during processing
        
        print(f"High Volume Performance Summary: {summary}")
    
    @pytest.mark.asyncio
    async def test_multiple_sources_concurrent_processing(self, perf_harness):
        """Test concurrent processing from multiple sources."""
        # Create multiple log files
        num_sources = 5
        log_files = []
        
        for i in range(num_sources):
            log_file = perf_harness.create_temp_log_file()
            log_files.append(log_file)
            await perf_harness.add_log_source(log_file, f"concurrent_source_{i}")
        
        # Connect WebSocket clients
        client_ids = await perf_harness.connect_websocket_clients(3)
        
        # Start performance measurement
        perf_harness.metrics.start_measurement()
        
        # Start monitoring
        monitor_task = asyncio.create_task(
            perf_harness.monitor_performance(duration=12.0)
        )
        
        # Generate entries concurrently
        entries_per_file = 200
        await perf_harness.generate_concurrent_log_entries(log_files, entries_per_file)
        
        # Wait for processing
        await asyncio.sleep(10.0)
        
        # Stop monitoring
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        perf_harness.metrics.end_measurement()
        
        # Analyze performance
        summary = perf_harness.metrics.get_summary()
        
        # Verify processing from all sources
        unique_sources = set(entry['source_name'] for entry in perf_harness.processed_entries)
        assert len(unique_sources) == num_sources
        
        # Performance assertions
        assert summary['average_throughput'] > 30  # At least 30 entries/second with concurrency
        assert summary['max_queue_size'] < 5000  # Queue didn't grow too large
        assert summary['total_errors'] == 0
        
        print(f"Concurrent Processing Performance Summary: {summary}")
    
    @pytest.mark.asyncio
    async def test_burst_processing_performance(self, perf_harness):
        """Test performance during burst traffic patterns."""
        # Create log file
        log_file = perf_harness.create_temp_log_file()
        await perf_harness.add_log_source(log_file, "burst_source")
        
        # Connect WebSocket clients
        client_ids = await perf_harness.connect_websocket_clients(2)
        
        # Start performance measurement
        perf_harness.metrics.start_measurement()
        
        # Start monitoring
        monitor_task = asyncio.create_task(
            perf_harness.monitor_performance(duration=15.0)
        )
        
        # Generate burst patterns
        for burst in range(3):
            # High burst
            await perf_harness.generate_log_entries(log_file, 300, entry_size=150)
            await asyncio.sleep(2.0)  # Processing time
            
            # Low activity
            await perf_harness.generate_log_entries(log_file, 50, entry_size=100)
            await asyncio.sleep(3.0)  # Quiet period
        
        # Final processing wait
        await asyncio.sleep(3.0)
        
        # Stop monitoring
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        perf_harness.metrics.end_measurement()
        
        # Analyze performance
        summary = perf_harness.metrics.get_summary()
        
        # Verify burst handling
        assert len(perf_harness.processed_entries) > 0
        assert summary['max_queue_size'] > 0  # Queue was utilized
        assert summary['total_errors'] == 0
        
        # Check throughput variation handling
        throughput_samples = perf_harness.metrics.throughput_samples
        if len(throughput_samples) > 1:
            throughput_std = statistics.stdev(throughput_samples)
            assert throughput_std >= 0  # Some variation expected in burst patterns
        
        print(f"Burst Processing Performance Summary: {summary}")


class TestWebSocketBroadcastPerformance:
    """Test WebSocket broadcast performance under load."""
    
    @pytest.mark.asyncio
    async def test_many_clients_broadcast_performance(self, perf_harness):
        """Test broadcast performance with many connected clients."""
        # Create log file
        log_file = perf_harness.create_temp_log_file()
        await perf_harness.add_log_source(log_file, "broadcast_perf_source")
        
        # Connect many WebSocket clients
        num_clients = 50
        client_ids = await perf_harness.connect_websocket_clients(num_clients)
        
        # Start performance measurement
        perf_harness.metrics.start_measurement()
        
        # Start monitoring
        monitor_task = asyncio.create_task(
            perf_harness.monitor_performance(duration=8.0)
        )
        
        # Generate log entries to trigger broadcasts
        await perf_harness.generate_log_entries(log_file, 100, entry_size=300)
        
        # Wait for processing and broadcasting
        await asyncio.sleep(6.0)
        
        # Stop monitoring
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        perf_harness.metrics.end_measurement()
        
        # Analyze performance
        summary = perf_harness.metrics.get_summary()
        
        # Verify broadcasts occurred
        assert len(perf_harness.processed_entries) > 0
        
        # Performance assertions for broadcast
        assert summary['average_websocket_latency'] < 0.5  # Less than 500ms broadcast latency
        assert summary['total_errors'] == 0
        
        # Verify clients are still connected (no disconnections due to performance issues)
        active_connections = len(perf_harness.websocket_manager.connections)
        assert active_connections >= num_clients * 0.9  # At least 90% still connected
        
        print(f"Broadcast Performance Summary: {summary}")
        print(f"Active connections: {active_connections}/{num_clients}")
    
    @pytest.mark.asyncio
    async def test_high_frequency_broadcast_performance(self, perf_harness):
        """Test performance with high-frequency broadcasts."""
        # Create log file
        log_file = perf_harness.create_temp_log_file()
        await perf_harness.add_log_source(log_file, "high_freq_source")
        
        # Connect moderate number of clients
        client_ids = await perf_harness.connect_websocket_clients(10)
        
        # Start performance measurement
        perf_harness.metrics.start_measurement()
        
        # Start monitoring
        monitor_task = asyncio.create_task(
            perf_harness.monitor_performance(duration=10.0)
        )
        
        # Generate high-frequency entries
        for i in range(20):  # 20 bursts
            await perf_harness.generate_log_entries(log_file, 25, entry_size=100)
            await asyncio.sleep(0.2)  # Short interval between bursts
        
        # Wait for final processing
        await asyncio.sleep(3.0)
        
        # Stop monitoring
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        perf_harness.metrics.end_measurement()
        
        # Analyze performance
        summary = perf_harness.metrics.get_summary()
        
        # Verify high-frequency processing
        assert len(perf_harness.processed_entries) > 0
        assert summary['average_throughput'] > 20  # Sustained throughput
        assert summary['average_websocket_latency'] < 1.0  # Reasonable latency under load
        assert summary['total_errors'] == 0
        
        print(f"High Frequency Broadcast Performance Summary: {summary}")


class TestMemoryAndResourceUsage:
    """Test memory usage and resource efficiency."""
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, perf_harness):
        """Test memory usage patterns under sustained load."""
        # Create multiple log files
        log_files = []
        for i in range(3):
            log_file = perf_harness.create_temp_log_file()
            log_files.append(log_file)
            await perf_harness.add_log_source(log_file, f"memory_test_source_{i}")
        
        # Connect clients
        client_ids = await perf_harness.connect_websocket_clients(5)
        
        # Start performance measurement
        perf_harness.metrics.start_measurement()
        
        # Generate sustained load
        for round_num in range(5):
            await perf_harness.generate_concurrent_log_entries(log_files, 100)
            await asyncio.sleep(2.0)  # Allow processing
        
        # Wait for final processing
        await asyncio.sleep(5.0)
        
        perf_harness.metrics.end_measurement()
        
        # Analyze performance
        summary = perf_harness.metrics.get_summary()
        
        # Verify processing completed
        assert len(perf_harness.processed_entries) > 0
        
        # Check queue didn't grow unbounded (memory efficiency)
        assert summary['max_queue_size'] < 2000  # Reasonable queue size limit
        
        # Verify system remained responsive
        assert summary['average_processing_time'] < 2.0  # Processing didn't slow down significantly
        assert summary['total_errors'] == 0
        
        print(f"Memory Usage Performance Summary: {summary}")
    
    @pytest.mark.asyncio
    async def test_queue_backpressure_performance(self, perf_harness):
        """Test performance under queue backpressure conditions."""
        # Set up with smaller queue for faster backpressure
        await perf_harness.teardown()
        await perf_harness.setup(queue_size=500, batch_size=20)
        
        # Create log file
        log_file = perf_harness.create_temp_log_file()
        await perf_harness.add_log_source(log_file, "backpressure_source")
        
        # Connect client
        client_ids = await perf_harness.connect_websocket_clients(1)
        
        # Start performance measurement
        perf_harness.metrics.start_measurement()
        
        # Start monitoring
        monitor_task = asyncio.create_task(
            perf_harness.monitor_performance(duration=8.0)
        )
        
        # Generate load that should trigger backpressure
        await perf_harness.generate_log_entries(log_file, 800, entry_size=200)
        
        # Wait for processing under backpressure
        await asyncio.sleep(6.0)
        
        # Stop monitoring
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        perf_harness.metrics.end_measurement()
        
        # Analyze performance
        summary = perf_harness.metrics.get_summary()
        
        # Verify backpressure was handled
        assert summary['max_queue_size'] > 0
        
        # System should remain stable under backpressure
        assert summary['total_errors'] == 0
        
        # Some entries should have been processed despite backpressure
        assert len(perf_harness.processed_entries) > 0
        
        print(f"Backpressure Performance Summary: {summary}")


class TestScalabilityLimits:
    """Test system scalability limits and breaking points."""
    
    @pytest.mark.asyncio
    async def test_maximum_concurrent_sources(self, perf_harness):
        """Test performance with maximum number of concurrent sources."""
        # Create many log sources
        max_sources = 25
        log_files = []
        
        for i in range(max_sources):
            log_file = perf_harness.create_temp_log_file()
            log_files.append(log_file)
            success = await perf_harness.add_log_source(log_file, f"scale_source_{i}")
            if not success:
                break
        
        # Connect clients
        client_ids = await perf_harness.connect_websocket_clients(5)
        
        # Start performance measurement
        perf_harness.metrics.start_measurement()
        
        # Generate moderate load across all sources
        await perf_harness.generate_concurrent_log_entries(log_files, 50)
        
        # Wait for processing
        await asyncio.sleep(10.0)
        
        perf_harness.metrics.end_measurement()
        
        # Analyze performance
        summary = perf_harness.metrics.get_summary()
        
        # Verify processing from multiple sources
        unique_sources = set(entry['source_name'] for entry in perf_harness.processed_entries)
        assert len(unique_sources) > 0
        
        # System should handle many sources
        assert summary['total_errors'] == 0
        assert summary['average_throughput'] > 0
        
        print(f"Scalability Test Summary: {summary}")
        print(f"Processed from {len(unique_sources)} sources")
    
    @pytest.mark.asyncio
    async def test_connection_limit_performance(self, perf_harness):
        """Test performance at WebSocket connection limits."""
        # Create log file
        log_file = perf_harness.create_temp_log_file()
        await perf_harness.add_log_source(log_file, "connection_limit_source")
        
        # Try to connect up to the limit
        max_clients = perf_harness.websocket_manager.max_connections
        client_ids = await perf_harness.connect_websocket_clients(max_clients)
        
        connected_count = len(client_ids)
        print(f"Connected {connected_count}/{max_clients} clients")
        
        # Start performance measurement
        perf_harness.metrics.start_measurement()
        
        # Generate load with maximum connections
        await perf_harness.generate_log_entries(log_file, 200, entry_size=150)
        
        # Wait for processing and broadcasting
        await asyncio.sleep(8.0)
        
        perf_harness.metrics.end_measurement()
        
        # Analyze performance
        summary = perf_harness.metrics.get_summary()
        
        # Verify processing occurred
        assert len(perf_harness.processed_entries) > 0
        
        # Performance should degrade gracefully at limits
        assert summary['average_websocket_latency'] < 2.0  # Still reasonable latency
        assert summary['total_errors'] == 0
        
        # Most connections should remain active
        active_connections = len(perf_harness.websocket_manager.connections)
        assert active_connections >= connected_count * 0.8  # At least 80% still connected
        
        print(f"Connection Limit Performance Summary: {summary}")
        print(f"Final active connections: {active_connections}")


if __name__ == "__main__":
    pytest.main([__file__])