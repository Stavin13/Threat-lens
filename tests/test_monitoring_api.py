"""
Tests for real-time monitoring API endpoints.
"""

import pytest
import json
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock

from main import app
from app.realtime.models import LogSourceConfig, LogSourceType, MonitoringStatus
from app.realtime.config_manager import ConfigManager


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_config_manager():
    """Mock configuration manager."""
    mock_manager = Mock(spec=ConfigManager)
    
    # Mock log source
    mock_source = LogSourceConfig(
        source_name="test_source",
        path="/var/log/test.log",
        source_type=LogSourceType.FILE,
        enabled=True,
        status=MonitoringStatus.ACTIVE
    )
    
    mock_manager.get_log_sources.return_value = [mock_source]
    mock_manager.get_log_source.return_value = mock_source
    mock_manager.add_log_source.return_value = True
    mock_manager.update_log_source.return_value = True
    mock_manager.remove_log_source.return_value = True
    
    return mock_manager


class TestLogSourceEndpoints:
    """Test log source management endpoints."""
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_create_log_source(self, mock_get_manager, client, mock_config_manager):
        """Test creating a new log source."""
        mock_get_manager.return_value = mock_config_manager
        
        request_data = {
            "source_name": "test_source",
            "path": "/var/log/test.log",
            "source_type": "file",
            "enabled": True,
            "recursive": False,
            "polling_interval": 1.0,
            "batch_size": 100,
            "priority": 5,
            "description": "Test log source",
            "tags": ["test"]
        }
        
        response = client.post("/api/v1/monitoring/log-sources", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["source_name"] == "test_source"
        assert data["path"] == "/var/log/test.log"
        assert data["source_type"] == "file"
        assert data["enabled"] is True
        
        mock_config_manager.add_log_source.assert_called_once()
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_list_log_sources(self, mock_get_manager, client, mock_config_manager):
        """Test listing log sources."""
        mock_get_manager.return_value = mock_config_manager
        
        response = client.get("/api/v1/monitoring/log-sources")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["source_name"] == "test_source"
        
        mock_config_manager.get_log_sources.assert_called_once()
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_get_log_source(self, mock_get_manager, client, mock_config_manager):
        """Test getting a specific log source."""
        mock_get_manager.return_value = mock_config_manager
        
        response = client.get("/api/v1/monitoring/log-sources/test_source")
        
        assert response.status_code == 200
        data = response.json()
        assert data["source_name"] == "test_source"
        assert data["path"] == "/var/log/test.log"
        
        mock_config_manager.get_log_source.assert_called_once_with("test_source")
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_get_log_source_not_found(self, mock_get_manager, client, mock_config_manager):
        """Test getting a non-existent log source."""
        mock_get_manager.return_value = mock_config_manager
        mock_config_manager.get_log_source.return_value = None
        
        response = client.get("/api/v1/monitoring/log-sources/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_update_log_source(self, mock_get_manager, client, mock_config_manager):
        """Test updating a log source."""
        mock_get_manager.return_value = mock_config_manager
        
        request_data = {
            "source_name": "test_source_updated",
            "path": "/var/log/test_updated.log",
            "source_type": "file",
            "enabled": False,
            "recursive": False,
            "polling_interval": 2.0,
            "batch_size": 200,
            "priority": 7,
            "description": "Updated test log source",
            "tags": ["test", "updated"]
        }
        
        response = client.put("/api/v1/monitoring/log-sources/test_source", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["source_name"] == "test_source_updated"
        assert data["enabled"] is False
        
        mock_config_manager.update_log_source.assert_called_once()
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_delete_log_source(self, mock_get_manager, client, mock_config_manager):
        """Test deleting a log source."""
        mock_get_manager.return_value = mock_config_manager
        
        response = client.delete("/api/v1/monitoring/log-sources/test_source")
        
        assert response.status_code == 200
        data = response.json()
        assert "deleted successfully" in data["message"]
        
        mock_config_manager.remove_log_source.assert_called_once_with("test_source")
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_test_log_source(self, mock_get_manager, client, mock_config_manager):
        """Test testing a log source configuration."""
        mock_get_manager.return_value = mock_config_manager
        
        with patch('pathlib.Path') as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.is_file.return_value = True
            mock_path.return_value = mock_path_instance
            
            with patch('os.access', return_value=True):
                response = client.post("/api/v1/monitoring/log-sources/test_source/test")
                
                assert response.status_code == 200
                data = response.json()
                assert data["source_name"] == "test_source"
                assert "tests" in data
                assert data["overall_status"] in ["passed", "failed"]
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_get_log_source_status(self, mock_get_manager, client, mock_config_manager):
        """Test getting log source status."""
        mock_get_manager.return_value = mock_config_manager
        
        response = client.get("/api/v1/monitoring/log-sources/test_source/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["source_name"] == "test_source"
        assert data["status"] == "active"
        assert data["enabled"] is True


class TestNotificationEndpoints:
    """Test notification management endpoints."""
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_create_notification_rule(self, mock_get_manager, client, mock_config_manager):
        """Test creating a notification rule."""
        mock_get_manager.return_value = mock_config_manager
        
        # Mock the config load and save
        mock_config = Mock()
        mock_config.add_notification_rule.return_value = True
        mock_config_manager.load_config.return_value = mock_config
        mock_config_manager.save_config.return_value = True
        
        request_data = {
            "rule_name": "test_rule",
            "enabled": True,
            "min_severity": 5,
            "max_severity": 10,
            "categories": ["security"],
            "sources": ["test_source"],
            "channels": ["email"],
            "throttle_minutes": 60,
            "email_recipients": ["admin@example.com"]
        }
        
        response = client.post("/api/v1/monitoring/notification-rules", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["rule_name"] == "test_rule"
        assert data["enabled"] is True
        assert data["min_severity"] == 5
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_list_notification_rules(self, mock_get_manager, client, mock_config_manager):
        """Test listing notification rules."""
        mock_get_manager.return_value = mock_config_manager
        
        # Mock notification rule
        from app.realtime.models import NotificationRule, NotificationChannel
        mock_rule = NotificationRule(
            rule_name="test_rule",
            enabled=True,
            min_severity=5,
            max_severity=10,
            channels=[NotificationChannel.EMAIL],
            email_recipients=["admin@example.com"]
        )
        
        mock_config = Mock()
        mock_config.notification_rules = [mock_rule]
        mock_config_manager.load_config.return_value = mock_config
        
        response = client.get("/api/v1/monitoring/notification-rules")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["rule_name"] == "test_rule"


class TestSystemEndpoints:
    """Test system monitoring endpoints."""
    
    def test_get_monitoring_health(self, client):
        """Test getting monitoring health status."""
        with patch('app.realtime.monitoring_api.health_monitor') as mock_monitor:
            mock_monitor.get_overall_health.return_value = {
                "overall_status": "healthy",
                "components": {}
            }
            
            response = client.get("/api/v1/monitoring/health")
            
            assert response.status_code == 200
            data = response.json()
            assert "overall_status" in data
            assert "timestamp" in data
    
    @patch('app.realtime.monitoring_api.get_database_session')
    def test_get_processing_metrics(self, mock_get_db, client):
        """Test getting processing metrics."""
        mock_db = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_get_db.return_value.__exit__.return_value = None
        
        # Mock query results
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        response = client.get("/api/v1/monitoring/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "summary" in data
        assert "timestamp" in data
    
    def test_get_system_diagnostics(self, client):
        """Test getting system diagnostics."""
        with patch('app.realtime.monitoring_api.get_system_diagnostics') as mock_get_diag:
            mock_get_diag.return_value = {
                "system_info": {},
                "component_status": {},
                "performance_metrics": {}
            }
            
            response = client.get("/api/v1/monitoring/diagnostics")
            
            assert response.status_code == 200
            data = response.json()
            assert "timestamp" in data
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_get_monitoring_config(self, mock_get_manager, client, mock_config_manager):
        """Test getting monitoring configuration."""
        mock_get_manager.return_value = mock_config_manager
        
        # Mock configuration
        from app.realtime.models import MonitoringConfig
        mock_config = MonitoringConfig()
        mock_config_manager.load_config.return_value = mock_config
        
        response = client.get("/api/v1/monitoring/config")
        
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "log_sources" in data
        assert "notification_rules" in data
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_get_monitoring_stats(self, mock_get_manager, client, mock_config_manager):
        """Test getting monitoring statistics."""
        mock_get_manager.return_value = mock_config_manager
        mock_config_manager.get_configuration_summary.return_value = {
            "total_sources": 1,
            "enabled_sources": 1,
            "notification_rules": 0
        }
        
        response = client.get("/api/v1/monitoring/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "configuration" in data
        assert "runtime" in data
        assert "timestamp" in data


class TestErrorHandling:
    """Test error handling in monitoring API."""
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_create_log_source_validation_error(self, mock_get_manager, client):
        """Test validation error when creating log source."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        # Invalid request data (missing required fields)
        request_data = {
            "source_name": "",  # Empty name should fail validation
            "path": "/var/log/test.log"
        }
        
        response = client.post("/api/v1/monitoring/log-sources", json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    @patch('app.realtime.monitoring_api.get_config_manager')
    def test_configuration_error_handling(self, mock_get_manager, client):
        """Test configuration error handling."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        from app.realtime.exceptions import ConfigurationError
        mock_manager.add_log_source.side_effect = ConfigurationError("Duplicate source name")
        
        request_data = {
            "source_name": "duplicate_source",
            "path": "/var/log/test.log",
            "source_type": "file",
            "enabled": True
        }
        
        response = client.post("/api/v1/monitoring/log-sources", json=request_data)
        
        assert response.status_code == 400  # Configuration error
        data = response.json()
        assert "Duplicate source name" in data["detail"]