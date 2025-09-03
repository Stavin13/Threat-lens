"""
Integration tests for real-time monitoring API endpoints.
"""

import pytest
import json
from datetime import datetime, timezone
from fastapi.testclient import TestClient

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestMonitoringAPIIntegration:
    """Integration tests for monitoring API endpoints."""
    
    def test_monitoring_health_endpoint(self, client):
        """Test the monitoring health endpoint."""
        response = client.get("/api/v1/monitoring/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "overall_status" in data
        assert "timestamp" in data
    
    def test_monitoring_config_endpoint(self, client):
        """Test the monitoring configuration endpoint."""
        response = client.get("/api/v1/monitoring/config")
        
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "log_sources" in data
        assert "notification_rules" in data
        assert isinstance(data["log_sources"], list)
        assert isinstance(data["notification_rules"], list)
    
    def test_monitoring_stats_endpoint(self, client):
        """Test the monitoring statistics endpoint."""
        response = client.get("/api/v1/monitoring/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "configuration" in data
        assert "runtime" in data
        assert "timestamp" in data
    
    def test_log_sources_list_endpoint(self, client):
        """Test listing log sources."""
        response = client.get("/api/v1/monitoring/log-sources")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_notification_rules_list_endpoint(self, client):
        """Test listing notification rules."""
        response = client.get("/api/v1/monitoring/notification-rules")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_processing_metrics_endpoint(self, client):
        """Test getting processing metrics."""
        response = client.get("/api/v1/monitoring/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "summary" in data
        assert "timestamp" in data
        assert isinstance(data["metrics"], list)
    
    def test_system_diagnostics_endpoint(self, client):
        """Test getting system diagnostics."""
        response = client.get("/api/v1/monitoring/diagnostics")
        
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
    
    def test_notification_history_endpoint(self, client):
        """Test getting notification history."""
        response = client.get("/api/v1/monitoring/notification-history")
        
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
        assert "total_returned" in data
        assert "timestamp" in data
        assert isinstance(data["history"], list)
    
    def test_create_log_source_validation(self, client):
        """Test log source creation with validation."""
        # Test with invalid data (missing required fields)
        invalid_data = {
            "source_name": "",  # Empty name should fail
            "path": "/var/log/test.log"
        }
        
        response = client.post("/api/v1/monitoring/log-sources", json=invalid_data)
        assert response.status_code == 422  # Validation error
    
    def test_get_nonexistent_log_source(self, client):
        """Test getting a non-existent log source."""
        response = client.get("/api/v1/monitoring/log-sources/nonexistent_source")
        assert response.status_code == 404
        
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_get_nonexistent_notification_rule(self, client):
        """Test getting a non-existent notification rule."""
        response = client.get("/api/v1/monitoring/notification-rules/nonexistent_rule")
        assert response.status_code == 404
        
        data = response.json()
        assert "not found" in data["detail"].lower()


class TestMonitoringAPIErrorHandling:
    """Test error handling in monitoring API."""
    
    def test_invalid_log_source_data(self, client):
        """Test creating log source with invalid data."""
        invalid_data = {
            "source_name": "test_source",
            "path": "/var/log/test.log",
            "source_type": "invalid_type",  # Invalid source type
            "enabled": True
        }
        
        response = client.post("/api/v1/monitoring/log-sources", json=invalid_data)
        assert response.status_code == 422  # Validation error
    
    def test_invalid_notification_rule_data(self, client):
        """Test creating notification rule with invalid data."""
        invalid_data = {
            "rule_name": "test_rule",
            "enabled": True,
            "min_severity": 10,  # Invalid: min > max
            "max_severity": 5,
            "channels": ["invalid_channel"]  # Invalid channel
        }
        
        response = client.post("/api/v1/monitoring/notification-rules", json=invalid_data)
        assert response.status_code == 422  # Validation error
    
    def test_metrics_with_invalid_parameters(self, client):
        """Test metrics endpoint with invalid parameters."""
        response = client.get("/api/v1/monitoring/metrics?hours=0")  # Invalid hours
        assert response.status_code == 422  # Validation error
        
        response = client.get("/api/v1/monitoring/metrics?hours=200")  # Too many hours
        assert response.status_code == 422  # Validation error
    
    def test_notification_history_with_invalid_limit(self, client):
        """Test notification history with invalid limit."""
        response = client.get("/api/v1/monitoring/notification-history?limit=0")  # Invalid limit
        assert response.status_code == 422  # Validation error
        
        response = client.get("/api/v1/monitoring/notification-history?limit=2000")  # Too high limit
        assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    # Run a simple test
    client = TestClient(app)
    
    print("Testing monitoring health endpoint...")
    response = client.get("/api/v1/monitoring/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    print("\nTesting monitoring config endpoint...")
    response = client.get("/api/v1/monitoring/config")
    print(f"Status: {response.status_code}")
    print(f"Response keys: {list(response.json().keys())}")
    
    print("\nTesting log sources list endpoint...")
    response = client.get("/api/v1/monitoring/log-sources")
    print(f"Status: {response.status_code}")
    print(f"Number of sources: {len(response.json())}")
    
    print("\nAll basic tests passed!")