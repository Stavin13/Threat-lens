"""
Tests for the health monitoring API endpoints.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.realtime.health_api import health_router
from app.realtime.health_monitor import HealthMonitor, HealthStatus, HealthCheck, SystemMetrics, ComponentMetrics


@pytest.fixture
def app():
    """Create a test FastAPI app with health router."""
    test_app = FastAPI()
    test_app.include_router(health_router)
    return test_app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_health_monitor():
    """Create a mock health monitor with test data."""
    monitor = Mock(spec=HealthMonitor)
    
    # Mock health checks
    monitor.health_checks = {
        'file_monitor': HealthCheck(
            component='file_monitor',
            status=HealthStatus.HEALTHY,
            message='All good',
            timestamp=datetime.now(),
            metrics={'monitored_sources': 2},
            latency_ms=50.0
        ),
        'ingestion_queue': HealthCheck(
            component='ingestion_queue',
            status=HealthStatus.WARNING,
            message='Queue utilization high',
            timestamp=datetime.now(),
            metrics={'queue_size': 100},
            latency_ms=25.0
        )
    }
    
    # Mock component metrics
    monitor.component_metrics = {
        'file_monitor': ComponentMetrics(
            component='file_monitor',
            processing_rate=10.5,
            average_latency_ms=45.0,
            error_rate=0.1,
            queue_size=5,
            active_connections=2,
            uptime_seconds=3600.0,
            timestamp=datetime.now()
        )
    }
    
    # Mock system metrics
    monitor.system_metrics_history = [
        SystemMetrics(
            cpu_percent=25.5,
            memory_percent=60.0,
            memory_used_mb=4000.0,
            memory_total_mb=8000.0,
            disk_percent=45.0,
            disk_used_gb=50.0,
            disk_total_gb=100.0,
            load_average=[0.5, 0.7, 0.9],
            timestamp=datetime.now()
        )
    ]
    
    monitor.start_time = datetime.now() - timedelta(hours=1)
    monitor.monitoring_active = True
    
    # Mock methods
    monitor.get_overall_health.return_value = HealthStatus.WARNING
    monitor.get_health_summary.return_value = {
        'overall_status': 'warning',
        'timestamp': datetime.now().isoformat(),
        'uptime_seconds': 3600.0,
        'monitoring_active': True,
        'component_health': {
            'file_monitor': {
                'status': 'healthy',
                'message': 'All good',
                'latency_ms': 50.0,
                'last_check': datetime.now().isoformat()
            }
        },
        'system_metrics': {
            'cpu_percent': 25.5,
            'memory_percent': 60.0,
            'timestamp': datetime.now().isoformat()
        },
        'component_metrics': {
            'file_monitor': {
                'component': 'file_monitor',
                'processing_rate': 10.5,
                'average_latency_ms': 45.0,
                'timestamp': datetime.now().isoformat()
            }
        }
    }
    
    monitor.get_component_health.return_value = monitor.health_checks['file_monitor']
    monitor.get_system_metrics.return_value = monitor.system_metrics_history
    monitor.get_component_metrics.return_value = monitor.component_metrics['file_monitor']
    
    return monitor


class TestHealthAPI:
    """Test cases for health API endpoints."""
    
    @patch('app.realtime.health_api.health_monitor')
    def test_get_health_summary(self, mock_monitor, client, mock_health_monitor):
        """Test getting comprehensive health summary."""
        mock_monitor.get_health_summary.return_value = mock_health_monitor.get_health_summary()
        
        response = client.get("/api/health/")
        
        assert response.status_code == 200
        data = response.json()
        assert data['overall_status'] == 'warning'
        assert data['monitoring_active'] is True
        assert 'component_health' in data
        assert 'system_metrics' in data
        assert 'component_metrics' in data
        
    @patch('app.realtime.health_api.health_monitor')
    def test_get_overall_status(self, mock_monitor, client, mock_health_monitor):
        """Test getting overall system status."""
        mock_monitor.get_overall_health.return_value = HealthStatus.HEALTHY
        
        response = client.get("/api/health/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
        
    @patch('app.realtime.health_api.health_monitor')
    def test_get_all_component_health(self, mock_monitor, client, mock_health_monitor):
        """Test getting health status for all components."""
        mock_monitor.health_checks = mock_health_monitor.health_checks
        
        response = client.get("/api/health/components")
        
        assert response.status_code == 200
        data = response.json()
        assert 'file_monitor' in data
        assert 'ingestion_queue' in data
        assert data['file_monitor']['status'] == 'healthy'
        assert data['ingestion_queue']['status'] == 'warning'
        
    @patch('app.realtime.health_api.health_monitor')
    def test_get_component_health(self, mock_monitor, client, mock_health_monitor):
        """Test getting health status for a specific component."""
        mock_monitor.get_component_health.return_value = mock_health_monitor.health_checks['file_monitor']
        
        response = client.get("/api/health/components/file_monitor")
        
        assert response.status_code == 200
        data = response.json()
        assert data['component'] == 'file_monitor'
        assert data['status'] == 'healthy'
        assert data['message'] == 'All good'
        assert data['latency_ms'] == 50.0
        
    @patch('app.realtime.health_api.health_monitor')
    def test_get_component_health_not_found(self, mock_monitor, client):
        """Test getting health status for non-existent component."""
        mock_monitor.get_component_health.return_value = None
        
        response = client.get("/api/health/components/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data['detail']
        
    @patch('app.realtime.health_api.health_monitor')
    def test_get_system_metrics(self, mock_monitor, client, mock_health_monitor):
        """Test getting system metrics."""
        mock_monitor.get_system_metrics.return_value = mock_health_monitor.system_metrics_history
        
        response = client.get("/api/health/metrics/system?hours=2")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]['cpu_percent'] == 25.5
        assert data[0]['memory_percent'] == 60.0
        assert data[0]['load_average'] == [0.5, 0.7, 0.9]
        
    @patch('app.realtime.health_api.health_monitor')
    def test_get_all_component_metrics(self, mock_monitor, client, mock_health_monitor):
        """Test getting performance metrics for all components."""
        mock_monitor.component_metrics = mock_health_monitor.component_metrics
        
        response = client.get("/api/health/metrics/components")
        
        assert response.status_code == 200
        data = response.json()
        assert 'file_monitor' in data
        assert data['file_monitor']['processing_rate'] == 10.5
        assert data['file_monitor']['average_latency_ms'] == 45.0
        
    @patch('app.realtime.health_api.health_monitor')
    def test_get_component_metrics(self, mock_monitor, client, mock_health_monitor):
        """Test getting performance metrics for a specific component."""
        mock_monitor.get_component_metrics.return_value = mock_health_monitor.component_metrics['file_monitor']
        
        response = client.get("/api/health/metrics/components/file_monitor")
        
        assert response.status_code == 200
        data = response.json()
        assert data['component'] == 'file_monitor'
        assert data['processing_rate'] == 10.5
        assert data['error_rate'] == 0.1
        
    @patch('app.realtime.health_api.health_monitor')
    def test_get_component_metrics_not_found(self, mock_monitor, client):
        """Test getting metrics for non-existent component."""
        mock_monitor.get_component_metrics.return_value = None
        
        response = client.get("/api/health/metrics/components/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data['detail']
        
    @patch('app.realtime.health_api.health_monitor')
    def test_get_prometheus_metrics(self, mock_monitor, client, mock_health_monitor):
        """Test getting metrics in Prometheus format."""
        mock_monitor.get_overall_health.return_value = HealthStatus.HEALTHY
        mock_monitor.health_checks = mock_health_monitor.health_checks
        mock_monitor.system_metrics_history = mock_health_monitor.system_metrics_history
        mock_monitor.component_metrics = mock_health_monitor.component_metrics
        
        response = client.get("/api/health/metrics/prometheus")
        
        assert response.status_code == 200
        assert response.headers['content-type'] == 'text/plain; charset=utf-8'
        
        content = response.text
        assert 'threatlens_health_status' in content
        assert 'threatlens_component_health' in content
        assert 'threatlens_cpu_percent' in content
        assert 'threatlens_processing_rate' in content
        
    @patch('app.realtime.health_api.health_monitor')
    def test_get_uptime(self, mock_monitor, client, mock_health_monitor):
        """Test getting system uptime information."""
        mock_monitor.start_time = mock_health_monitor.start_time
        mock_monitor.monitoring_active = True
        
        response = client.get("/api/health/uptime")
        
        assert response.status_code == 200
        data = response.json()
        assert 'uptime_seconds' in data
        assert 'uptime_human' in data
        assert 'start_time' in data
        assert data['monitoring_active'] is True
        
    def test_ping(self, client):
        """Test simple ping endpoint."""
        response = client.get("/api/health/ping")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert 'timestamp' in data
        
    @patch('app.realtime.health_api.health_monitor')
    def test_api_error_handling(self, mock_monitor, client):
        """Test API error handling."""
        mock_monitor.get_health_summary.side_effect = Exception("Test error")
        
        response = client.get("/api/health/")
        
        assert response.status_code == 500
        data = response.json()
        assert 'Failed to retrieve health summary' in data['detail']
        
    def test_system_metrics_query_params(self, client):
        """Test system metrics endpoint with query parameters."""
        # Test invalid hours parameter
        response = client.get("/api/health/metrics/system?hours=0")
        assert response.status_code == 422
        
        response = client.get("/api/health/metrics/system?hours=25")
        assert response.status_code == 422
        
        # Test valid hours parameter
        with patch('app.realtime.health_api.health_monitor') as mock_monitor:
            mock_monitor.get_system_metrics.return_value = []
            response = client.get("/api/health/metrics/system?hours=12")
            assert response.status_code == 200
            mock_monitor.get_system_metrics.assert_called_once_with(hours=12)