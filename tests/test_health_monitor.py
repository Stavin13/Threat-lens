"""
Tests for the health monitoring system.
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from app.realtime.health_monitor import (
    HealthMonitor, HealthStatus, HealthCheck, SystemMetrics, ComponentMetrics
)
from app.realtime.health_checks import (
    FileMonitorHealthCheck, QueueProcessingHealthCheck, 
    WebSocketHealthCheck, ProcessingPipelineHealthCheck,
    register_all_health_checks
)


class TestHealthMonitor:
    """Test cases for HealthMonitor class."""
    
    @pytest.fixture
    def health_monitor(self):
        """Create a health monitor instance for testing."""
        return HealthMonitor()
        
    @pytest.fixture
    def mock_components(self):
        """Create mock components for testing."""
        file_monitor = Mock()
        file_monitor.monitoring_active = True
        file_monitor.get_monitoring_status.return_value = {
            'monitored_paths': ['/var/log/test1.log', '/var/log/test2.log'],
            'failed_paths': [],
            'last_activity': datetime.now()
        }
        
        ingestion_queue = Mock()
        ingestion_queue.get_queue_stats.return_value = {
            'queue_size': 10,
            'processing_active': True,
            'processed_count': 100,
            'error_count': 2
        }
        ingestion_queue.max_queue_size = 1000
        
        websocket_manager = Mock()
        websocket_manager.get_connected_clients.return_value = ['client1', 'client2']
        websocket_manager.server_active = True
        websocket_manager.connection_stats = {
            'total_connections': 50,
            'failed_connections': 2,
            'messages_sent': 1000,
            'messages_failed': 10
        }
        
        enhanced_processor = Mock()
        enhanced_processor.get_processing_metrics.return_value = {
            'processing_active': True,
            'avg_processing_time_ms': 150.0,
            'success_rate_percent': 98.0,
            'pending_tasks': 5,
            'total_processed': 500,
            'total_errors': 10
        }
        
        return {
            'file_monitor': file_monitor,
            'ingestion_queue': ingestion_queue,
            'websocket_manager': websocket_manager,
            'enhanced_processor': enhanced_processor
        }
    
    def test_health_monitor_initialization(self, health_monitor):
        """Test health monitor initialization."""
        assert not health_monitor.monitoring_active
        assert health_monitor.check_interval == 30
        assert len(health_monitor.health_checks) == 0
        assert len(health_monitor.component_metrics) == 0
        
    def test_register_health_check(self, health_monitor):
        """Test registering health check callbacks."""
        def dummy_check():
            return True
            
        health_monitor.register_health_check('test_component', dummy_check)
        assert 'test_component' in health_monitor.health_check_callbacks
        
    def test_record_processing_event(self, health_monitor):
        """Test recording processing events for metrics."""
        component = 'test_component'
        latency = 100.0
        
        health_monitor.record_processing_event(component, latency)
        
        assert component in health_monitor.processing_rates
        assert component in health_monitor.latency_samples
        assert len(health_monitor.processing_rates[component]) == 1
        assert len(health_monitor.latency_samples[component]) == 1
        assert health_monitor.latency_samples[component][0] == latency
        
    def test_record_error(self, health_monitor):
        """Test recording errors for components."""
        component = 'test_component'
        
        health_monitor.record_error(component)
        health_monitor.record_error(component)
        
        assert health_monitor.error_counts[component] == 2
        
    def test_get_overall_health_no_checks(self, health_monitor):
        """Test overall health when no checks are registered."""
        assert health_monitor.get_overall_health() == HealthStatus.UNKNOWN
        
    def test_get_overall_health_with_checks(self, health_monitor):
        """Test overall health calculation with various check results."""
        # Add healthy check
        health_monitor.health_checks['component1'] = HealthCheck(
            component='component1',
            status=HealthStatus.HEALTHY,
            message='OK',
            timestamp=datetime.now(),
            metrics={}
        )
        assert health_monitor.get_overall_health() == HealthStatus.HEALTHY
        
        # Add warning check
        health_monitor.health_checks['component2'] = HealthCheck(
            component='component2',
            status=HealthStatus.WARNING,
            message='Warning',
            timestamp=datetime.now(),
            metrics={}
        )
        assert health_monitor.get_overall_health() == HealthStatus.WARNING
        
        # Add critical check
        health_monitor.health_checks['component3'] = HealthCheck(
            component='component3',
            status=HealthStatus.CRITICAL,
            message='Critical',
            timestamp=datetime.now(),
            metrics={}
        )
        assert health_monitor.get_overall_health() == HealthStatus.CRITICAL
        
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.getloadavg')
    @pytest.mark.asyncio
    async def test_collect_system_metrics(self, mock_loadavg, mock_disk, mock_memory, mock_cpu, health_monitor):
        """Test system metrics collection."""
        # Mock system metrics
        mock_cpu.return_value = 25.5
        mock_memory.return_value = Mock(percent=60.0, used=4000000000, total=8000000000)
        mock_disk.return_value = Mock(used=50000000000, total=100000000000)
        mock_loadavg.return_value = [0.5, 0.7, 0.9]
        
        await health_monitor._collect_system_metrics()
        
        assert len(health_monitor.system_metrics_history) == 1
        metrics = health_monitor.system_metrics_history[0]
        assert metrics.cpu_percent == 25.5
        assert metrics.memory_percent == 60.0
        assert metrics.load_average == [0.5, 0.7, 0.9]
        
    @pytest.mark.asyncio
    async def test_perform_health_checks(self, health_monitor):
        """Test performing health checks."""
        # Register a mock health check
        async def mock_health_check():
            return {
                'status': 'healthy',
                'message': 'All good',
                'metrics': {'test_metric': 42}
            }
            
        health_monitor.register_health_check('test_component', mock_health_check)
        
        await health_monitor._perform_health_checks()
        
        assert 'test_component' in health_monitor.health_checks
        check = health_monitor.health_checks['test_component']
        assert check.status == HealthStatus.HEALTHY
        assert check.message == 'All good'
        assert check.metrics['test_metric'] == 42
        
    def test_get_health_summary(self, health_monitor):
        """Test getting comprehensive health summary."""
        # Add some test data
        health_monitor.health_checks['test'] = HealthCheck(
            component='test',
            status=HealthStatus.HEALTHY,
            message='OK',
            timestamp=datetime.now(),
            metrics={},
            latency_ms=50.0
        )
        
        summary = health_monitor.get_health_summary()
        
        assert 'overall_status' in summary
        assert 'timestamp' in summary
        assert 'uptime_seconds' in summary
        assert 'component_health' in summary
        assert 'test' in summary['component_health']
        assert summary['component_health']['test']['status'] == 'healthy'


class TestFileMonitorHealthCheck:
    """Test cases for FileMonitorHealthCheck."""
    
    def test_file_monitor_not_initialized(self):
        """Test health check when file monitor is not initialized."""
        health_check = FileMonitorHealthCheck(None)
        result = asyncio.run(health_check.check_health())
        
        assert result['status'] == HealthStatus.CRITICAL.value
        assert 'not initialized' in result['message']
        
    def test_file_monitor_not_active(self):
        """Test health check when file monitoring is not active."""
        mock_monitor = Mock()
        mock_monitor.monitoring_active = False
        
        health_check = FileMonitorHealthCheck(mock_monitor)
        result = asyncio.run(health_check.check_health())
        
        assert result['status'] == HealthStatus.CRITICAL.value
        assert 'not active' in result['message']
        
    def test_file_monitor_healthy(self):
        """Test health check when file monitor is healthy."""
        mock_monitor = Mock()
        mock_monitor.monitoring_active = True
        mock_monitor.get_monitoring_status.return_value = {
            'monitored_paths': ['/var/log/test1.log', '/var/log/test2.log'],
            'failed_paths': [],
            'last_activity': datetime.now()
        }
        
        health_check = FileMonitorHealthCheck(mock_monitor)
        result = asyncio.run(health_check.check_health())
        
        assert result['status'] == HealthStatus.HEALTHY.value
        assert 'successfully' in result['message']
        assert result['metrics']['monitored_sources'] == 2
        assert result['metrics']['failed_sources'] == 0
        
    def test_file_monitor_with_failures(self):
        """Test health check when some sources fail."""
        mock_monitor = Mock()
        mock_monitor.monitoring_active = True
        mock_monitor.get_monitoring_status.return_value = {
            'monitored_paths': ['/var/log/test1.log', '/var/log/test2.log'],
            'failed_paths': ['/var/log/test2.log'],
            'last_activity': datetime.now()
        }
        
        health_check = FileMonitorHealthCheck(mock_monitor)
        result = asyncio.run(health_check.check_health())
        
        assert result['status'] == HealthStatus.WARNING.value
        assert 'failed' in result['message']
        assert result['metrics']['monitored_sources'] == 2
        assert result['metrics']['failed_sources'] == 1


class TestQueueProcessingHealthCheck:
    """Test cases for QueueProcessingHealthCheck."""
    
    def test_queue_not_initialized(self):
        """Test health check when queue is not initialized."""
        health_check = QueueProcessingHealthCheck(None)
        result = asyncio.run(health_check.check_health())
        
        assert result['status'] == HealthStatus.CRITICAL.value
        assert 'not initialized' in result['message']
        
    def test_queue_processing_not_active(self):
        """Test health check when queue processing is not active."""
        mock_queue = Mock()
        mock_queue.get_queue_stats.return_value = {
            'queue_size': 0,
            'processing_active': False,
            'processed_count': 0,
            'error_count': 0
        }
        mock_queue.max_queue_size = 1000
        
        health_check = QueueProcessingHealthCheck(mock_queue)
        result = asyncio.run(health_check.check_health())
        
        assert result['status'] == HealthStatus.CRITICAL.value
        assert 'not active' in result['message']
        
    def test_queue_healthy(self):
        """Test health check when queue is healthy."""
        mock_queue = Mock()
        mock_queue.get_queue_stats.return_value = {
            'queue_size': 10,
            'processing_active': True,
            'processed_count': 100,
            'error_count': 2
        }
        mock_queue.max_queue_size = 1000
        
        health_check = QueueProcessingHealthCheck(mock_queue)
        result = asyncio.run(health_check.check_health())
        
        assert result['status'] == HealthStatus.HEALTHY.value
        assert 'normally' in result['message']
        assert result['metrics']['queue_size'] == 10
        assert result['metrics']['error_rate_percent'] == 2.0
        
    def test_queue_high_utilization(self):
        """Test health check when queue utilization is high."""
        mock_queue = Mock()
        mock_queue.get_queue_stats.return_value = {
            'queue_size': 950,
            'processing_active': True,
            'processed_count': 100,
            'error_count': 2
        }
        mock_queue.max_queue_size = 1000
        
        health_check = QueueProcessingHealthCheck(mock_queue)
        result = asyncio.run(health_check.check_health())
        
        assert result['status'] == HealthStatus.CRITICAL.value
        assert 'critical' in result['message']
        assert result['metrics']['queue_utilization_percent'] == 95.0


class TestWebSocketHealthCheck:
    """Test cases for WebSocketHealthCheck."""
    
    def test_websocket_not_initialized(self):
        """Test health check when WebSocket manager is not initialized."""
        health_check = WebSocketHealthCheck(None)
        result = asyncio.run(health_check.check_health())
        
        assert result['status'] == HealthStatus.CRITICAL.value
        assert 'not initialized' in result['message']
        
    def test_websocket_server_not_active(self):
        """Test health check when WebSocket server is not active."""
        mock_manager = Mock()
        mock_manager.get_connected_clients.return_value = []
        mock_manager.server_active = False
        mock_manager.connection_stats = {}
        
        health_check = WebSocketHealthCheck(mock_manager)
        result = asyncio.run(health_check.check_health())
        
        assert result['status'] == HealthStatus.CRITICAL.value
        assert 'not active' in result['message']
        
    def test_websocket_healthy(self):
        """Test health check when WebSocket server is healthy."""
        mock_manager = Mock()
        mock_manager.get_connected_clients.return_value = ['client1', 'client2']
        mock_manager.server_active = True
        mock_manager.connection_stats = {
            'total_connections': 50,
            'failed_connections': 2,
            'messages_sent': 1000,
            'messages_failed': 10
        }
        
        health_check = WebSocketHealthCheck(mock_manager)
        result = asyncio.run(health_check.check_health())
        
        assert result['status'] == HealthStatus.HEALTHY.value
        assert 'healthy' in result['message']
        assert result['metrics']['active_connections'] == 2
        assert result['metrics']['message_success_rate_percent'] == 99.0


def test_register_all_health_checks():
    """Test registering all health checks."""
    health_monitor = HealthMonitor()
    
    # Create mock components
    mock_components = {
        'file_monitor': Mock(),
        'ingestion_queue': Mock(),
        'websocket_manager': Mock(),
        'enhanced_processor': Mock()
    }
    
    register_all_health_checks(health_monitor, mock_components)
    
    expected_components = ['file_monitor', 'ingestion_queue', 'websocket_server', 'processing_pipeline']
    for component in expected_components:
        assert component in health_monitor.health_check_callbacks