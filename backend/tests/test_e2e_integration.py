"""
End-to-End Integration Tests for ThreatLens

Comprehensive integration tests covering the complete workflow from log ingestion
to dashboard display, including various log formats, edge cases, AI analysis
integration, and performance testing.
"""
import pytest
import asyncio
import time
import json
import uuid
import tempfile
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from unittest.mock import patch, Mock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from app.database import get_database_session
from app.models import Base, RawLog, Event, AIAnalysis as AIAnalysisModel
from app.schemas import EventCategory, AIAnalysis, ParsedEvent
from tests.fixtures.test_data import TestDataFixtures


class TestE2EIntegration:
    """End-to-end integration tests for complete workflow."""
    
    @pytest.fixture(scope="function")
    def test_db(self):
        """Create isolated test database for each test."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)
        
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        Base.metadata.create_all(bind=engine)
        
        def override_get_db():
            try:
                db = TestingSessionLocal()
                yield db
            finally:
                db.close()
        
        app.dependency_overrides[get_database_session] = override_get_db
        
        yield TestingSessionLocal
        
        app.dependency_overrides.clear()
        os.unlink(db_path)
    
    @pytest.fixture
    def client(self, test_db):
        """Create test client with isolated database."""
        return TestClient(app)
    
    @pytest.fixture
    def test_fixtures(self):
        """Provide test data fixtures."""
        return TestDataFixtures()
    
    def test_complete_macos_system_log_workflow(self, client, test_fixtures):
        """Test complete workflow with macOS system.log format."""
        # Use realistic macOS system log content
        log_content = test_fixtures.get_macos_system_log()
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            # Mock AI analysis responses with realistic data
            mock_analyze.side_effect = self._create_mock_ai_analysis
            
            # Step 1: Ingest log via API
            response = client.post(
                "/ingest-log",
                data={"content": log_content, "source": "macos_system_test"}
            )
            
            assert response.status_code == 200
            ingestion_data = response.json()
            raw_log_id = ingestion_data["raw_log_id"]
            assert "ingested_at" in ingestion_data
            
            # Step 2: Wait for background processing
            self._wait_for_processing(client, raw_log_id, expected_events=5)
            
            # Step 3: Verify events were parsed correctly
            response = client.get("/events")
            assert response.status_code == 200
            
            events_data = response.json()
            assert events_data["total"] >= 5
            
            # Verify event categories are correctly identified
            categories = {event["category"] for event in events_data["events"]}
            expected_categories = {"system", "auth", "network"}
            assert len(categories.intersection(expected_categories)) >= 2
            
            # Step 4: Test event filtering by category
            response = client.get("/events?category=auth")
            assert response.status_code == 200
            auth_events = response.json()
            
            for event in auth_events["events"]:
                assert event["category"] == "auth"
                assert event["ai_analysis"] is not None
            
            # Step 5: Test severity filtering
            response = client.get("/events?min_severity=7")
            assert response.status_code == 200
            high_severity_events = response.json()
            
            for event in high_severity_events["events"]:
                if event["ai_analysis"]:
                    assert event["ai_analysis"]["severity_score"] >= 7
            
            # Step 6: Test event detail retrieval
            if events_data["events"]:
                event_id = events_data["events"][0]["id"]
                response = client.get(f"/event/{event_id}")
                assert response.status_code == 200
                
                event_detail = response.json()
                assert event_detail["id"] == event_id
                assert event_detail["ai_analysis"] is not None
                assert "recommendations" in event_detail["ai_analysis"]
    
    def test_complete_macos_auth_log_workflow(self, client, test_fixtures):
        """Test complete workflow with macOS auth.log format."""
        log_content = test_fixtures.get_macos_auth_log()
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = self._create_mock_ai_analysis
            
            # Ingest auth log
            response = client.post(
                "/ingest-log",
                data={"content": log_content, "source": "macos_auth_test"}
            )
            
            assert response.status_code == 200
            raw_log_id = response.json()["raw_log_id"]
            
            # Wait for processing
            self._wait_for_processing(client, raw_log_id, expected_events=4)
            
            # Verify auth events have appropriate severity scores
            response = client.get("/events?category=auth")
            assert response.status_code == 200
            
            auth_events = response.json()
            assert auth_events["total"] >= 3
            
            # Failed auth events should have higher severity
            for event in auth_events["events"]:
                if "failed" in event["message"].lower() or "denied" in event["message"].lower():
                    if event["ai_analysis"]:
                        assert event["ai_analysis"]["severity_score"] >= 6
    
    def test_mixed_log_formats_workflow(self, client, test_fixtures):
        """Test workflow with mixed log formats in single ingestion."""
        mixed_content = test_fixtures.get_mixed_log_formats()
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = self._create_mock_ai_analysis
            
            response = client.post(
                "/ingest-log",
                data={"content": mixed_content, "source": "mixed_formats_test"}
            )
            
            assert response.status_code == 200
            raw_log_id = response.json()["raw_log_id"]
            
            # Wait for processing
            self._wait_for_processing(client, raw_log_id, expected_events=6)
            
            # Verify different categories were detected
            response = client.get("/events")
            assert response.status_code == 200
            
            events_data = response.json()
            categories = {event["category"] for event in events_data["events"]}
            assert len(categories) >= 3  # Should detect multiple categories
    
    def test_file_upload_workflow(self, client, test_fixtures):
        """Test complete workflow with file upload."""
        log_content = test_fixtures.get_macos_system_log()
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = self._create_mock_ai_analysis
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
                f.write(log_content)
                temp_file_path = f.name
            
            try:
                # Upload file
                with open(temp_file_path, 'rb') as f:
                    files = {"file": ("test_system.log", f, "text/plain")}
                    response = client.post("/ingest-log", files=files)
                
                assert response.status_code == 200
                raw_log_id = response.json()["raw_log_id"]
                
                # Wait for processing
                self._wait_for_processing(client, raw_log_id, expected_events=5)
                
                # Verify processing completed
                response = client.get("/events")
                assert response.status_code == 200
                assert response.json()["total"] >= 5
                
            finally:
                os.unlink(temp_file_path)
    
    def test_large_log_file_performance(self, client, test_fixtures):
        """Test performance with large log files."""
        # Generate large log content (1000 entries)
        large_log_content = test_fixtures.generate_large_log_dataset(1000)
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = self._create_mock_ai_analysis
            
            # Measure ingestion time
            start_time = time.time()
            
            response = client.post(
                "/ingest-log",
                data={"content": large_log_content, "source": "performance_test"}
            )
            
            ingestion_time = time.time() - start_time
            
            assert response.status_code == 200
            assert ingestion_time < 10.0  # Should ingest quickly
            
            raw_log_id = response.json()["raw_log_id"]
            
            # Wait for processing with longer timeout
            processing_start = time.time()
            self._wait_for_processing(client, raw_log_id, expected_events=1000, timeout=60)
            processing_time = time.time() - processing_start
            
            # Verify all events were processed
            response = client.get("/events")
            assert response.status_code == 200
            
            events_data = response.json()
            assert events_data["total"] == 1000
            
            # Performance assertions
            assert processing_time < 60.0  # Should complete within 1 minute
            
            # Test pagination performance
            start_time = time.time()
            response = client.get("/events?page=1&per_page=50")
            pagination_time = time.time() - start_time
            
            assert response.status_code == 200
            assert pagination_time < 2.0  # Pagination should be fast
            assert len(response.json()["events"]) == 50
    
    def test_concurrent_ingestion_workflow(self, client, test_fixtures):
        """Test concurrent log ingestion and processing."""
        import threading
        import queue
        
        results = queue.Queue()
        
        def ingest_log(index):
            log_content = test_fixtures.get_sample_log_entry(index)
            
            with patch('app.analyzer.analyze_event') as mock_analyze:
                mock_analyze.side_effect = self._create_mock_ai_analysis
                
                response = client.post(
                    "/ingest-log",
                    data={"content": log_content, "source": f"concurrent_test_{index}"}
                )
                results.put((index, response.status_code, response.json()))
        
        # Start 10 concurrent ingestions
        threads = []
        for i in range(10):
            thread = threading.Thread(target=ingest_log, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all to complete
        for thread in threads:
            thread.join()
        
        # Verify all succeeded
        success_count = 0
        raw_log_ids = []
        
        while not results.empty():
            index, status_code, response_data = results.get()
            assert status_code == 200
            raw_log_ids.append(response_data["raw_log_id"])
            success_count += 1
        
        assert success_count == 10
        
        # Wait for all processing to complete
        time.sleep(5.0)
        
        # Verify all logs were processed
        response = client.get("/events")
        assert response.status_code == 200
        assert response.json()["total"] >= 10
    
    def test_error_recovery_workflow(self, client, test_fixtures):
        """Test system recovery from various error conditions."""
        # Test with problematic log content
        problematic_content = test_fixtures.get_problematic_log_content()
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            # Simulate intermittent AI failures
            def mock_analyze_with_failures(event):
                if "cause_failure" in event.message:
                    raise Exception("Simulated AI failure")
                return self._create_mock_ai_analysis(event)
            
            mock_analyze.side_effect = mock_analyze_with_failures
            
            response = client.post(
                "/ingest-log",
                data={"content": problematic_content, "source": "error_recovery_test"}
            )
            
            assert response.status_code == 200
            raw_log_id = response.json()["raw_log_id"]
            
            # Wait for processing
            time.sleep(3.0)
            
            # Verify that valid entries were still processed
            response = client.get("/events")
            assert response.status_code == 200
            
            events_data = response.json()
            assert events_data["total"] >= 3  # Should process valid entries
            
            # Verify some events have analysis (non-failing ones)
            analyzed_count = sum(1 for event in events_data["events"] 
                               if event["ai_analysis"] is not None)
            assert analyzed_count >= 2
    
    def test_dashboard_real_time_updates(self, client, test_fixtures):
        """Test real-time dashboard updates via WebSocket."""
        # This test would ideally use WebSocket testing
        # For now, we'll test the REST API that feeds the dashboard
        
        log_content = test_fixtures.get_macos_system_log()
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = self._create_mock_ai_analysis
            
            # Get initial event count
            response = client.get("/events")
            initial_count = response.json()["total"]
            
            # Ingest new log
            response = client.post(
                "/ingest-log",
                data={"content": log_content, "source": "realtime_test"}
            )
            
            assert response.status_code == 200
            raw_log_id = response.json()["raw_log_id"]
            
            # Wait for processing
            self._wait_for_processing(client, raw_log_id, expected_events=5)
            
            # Verify event count increased
            response = client.get("/events")
            new_count = response.json()["total"]
            assert new_count > initial_count
            
            # Test real-time status endpoint
            response = client.get("/realtime/status")
            assert response.status_code == 200
            
            status = response.json()
            assert "components" in status or "status" in status
    
    def test_report_generation_workflow(self, client, test_fixtures):
        """Test PDF report generation after event processing."""
        log_content = test_fixtures.get_comprehensive_log_sample()
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = self._create_mock_ai_analysis
            
            # Ingest logs
            response = client.post(
                "/ingest-log",
                data={"content": log_content, "source": "report_test"}
            )
            
            assert response.status_code == 200
            raw_log_id = response.json()["raw_log_id"]
            
            # Wait for processing
            self._wait_for_processing(client, raw_log_id, expected_events=8)
            
            # Generate daily report
            response = client.get("/report/daily")
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
            
            # Verify PDF content is not empty
            pdf_content = response.content
            assert len(pdf_content) > 1000  # PDF should have substantial content
            assert pdf_content.startswith(b"%PDF")  # Valid PDF header
    
    def test_api_error_handling_workflow(self, client, test_fixtures):
        """Test API error handling in various scenarios."""
        # Test invalid log content
        response = client.post(
            "/ingest-log",
            data={"content": "", "source": "empty_test"}
        )
        assert response.status_code == 400
        
        # Test both file and content provided
        response = client.post(
            "/ingest-log",
            files={"file": ("test.log", b"content", "text/plain")},
            data={"content": "text content"}
        )
        assert response.status_code == 400
        
        # Test invalid event ID
        response = client.get("/event/non-existent-id")
        assert response.status_code == 404
        
        # Test invalid filter parameters
        response = client.get("/events?min_severity=10&max_severity=5")
        assert response.status_code == 400
        
        # Test invalid sort parameters
        response = client.get("/events?sort_by=invalid_field")
        assert response.status_code == 400
    
    def test_system_health_monitoring(self, client, test_fixtures):
        """Test system health monitoring during processing."""
        # Test health check endpoint
        response = client.get("/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert "status" in health_data
        assert "database" in health_data
        assert "timestamp" in health_data
        
        # Test system stats
        response = client.get("/stats")
        assert response.status_code == 200
        
        stats = response.json()
        assert "database" in stats
        assert "processing" in stats
        assert "api_version" in stats
        
        # Ingest some data and verify stats update
        log_content = test_fixtures.get_macos_system_log()
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = self._create_mock_ai_analysis
            
            response = client.post(
                "/ingest-log",
                data={"content": log_content, "source": "health_test"}
            )
            
            assert response.status_code == 200
            raw_log_id = response.json()["raw_log_id"]
            
            # Wait for processing
            self._wait_for_processing(client, raw_log_id, expected_events=5)
            
            # Check updated stats
            response = client.get("/stats")
            assert response.status_code == 200
            
            updated_stats = response.json()
            assert updated_stats["database"]["events_count"] >= 5
    
    def test_edge_case_log_formats(self, client, test_fixtures):
        """Test handling of edge case log formats."""
        edge_cases = test_fixtures.get_edge_case_logs()
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = self._create_mock_ai_analysis
            
            for case_name, log_content in edge_cases.items():
                response = client.post(
                    "/ingest-log",
                    data={"content": log_content, "source": f"edge_case_{case_name}"}
                )
                
                # Should handle gracefully (either succeed or fail predictably)
                assert response.status_code in [200, 400]
                
                if response.status_code == 200:
                    raw_log_id = response.json()["raw_log_id"]
                    # Wait briefly for processing
                    time.sleep(1.0)
                    
                    # Verify system remains stable
                    health_response = client.get("/health")
                    assert health_response.status_code == 200
    
    def test_data_consistency_workflow(self, client, test_fixtures):
        """Test data consistency across the complete workflow."""
        log_content = test_fixtures.get_macos_system_log()
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = self._create_mock_ai_analysis
            
            # Ingest log
            response = client.post(
                "/ingest-log",
                data={"content": log_content, "source": "consistency_test"}
            )
            
            assert response.status_code == 200
            raw_log_id = response.json()["raw_log_id"]
            
            # Wait for processing
            self._wait_for_processing(client, raw_log_id, expected_events=5)
            
            # Get all events
            response = client.get("/events?per_page=100")
            assert response.status_code == 200
            
            events = response.json()["events"]
            
            # Verify data consistency
            for event in events:
                # Each event should have required fields
                assert event["id"]
                assert event["timestamp"]
                assert event["source"]
                assert event["message"]
                assert event["category"]
                
                # If AI analysis exists, it should be complete
                if event["ai_analysis"]:
                    analysis = event["ai_analysis"]
                    assert 1 <= analysis["severity_score"] <= 10
                    assert analysis["explanation"]
                    assert isinstance(analysis["recommendations"], list)
                
                # Verify event detail consistency
                detail_response = client.get(f"/event/{event['id']}")
                assert detail_response.status_code == 200
                
                detail = detail_response.json()
                assert detail["id"] == event["id"]
                assert detail["message"] == event["message"]
                
                # AI analysis should match
                if event["ai_analysis"] and detail["ai_analysis"]:
                    assert (event["ai_analysis"]["severity_score"] == 
                           detail["ai_analysis"]["severity_score"])
    
    # Helper methods
    
    def _create_mock_ai_analysis(self, event):
        """Create realistic mock AI analysis based on event content."""
        message_lower = event.message.lower()
        
        # Determine severity based on content
        if any(word in message_lower for word in ["failed", "error", "denied", "attack", "breach"]):
            severity = 7 + (hash(event.id) % 3)  # 7-9
        elif any(word in message_lower for word in ["warning", "suspicious", "unusual"]):
            severity = 4 + (hash(event.id) % 3)  # 4-6
        else:
            severity = 1 + (hash(event.id) % 3)  # 1-3
        
        # Generate explanation based on category and content
        explanations = {
            "auth": f"Authentication event detected: {event.message[:50]}...",
            "system": f"System event: {event.message[:50]}...",
            "network": f"Network activity: {event.message[:50]}...",
            "security": f"Security event requiring attention: {event.message[:50]}..."
        }
        
        explanation = explanations.get(event.category, f"Event analysis: {event.message[:50]}...")
        
        # Generate recommendations
        recommendations = [
            f"Monitor {event.source} for similar events",
            f"Review {event.category} logs for patterns"
        ]
        
        if severity >= 7:
            recommendations.append("Immediate investigation recommended")
        
        return AIAnalysis(
            id=str(uuid.uuid4()),
            event_id=event.id,
            severity_score=severity,
            explanation=explanation,
            recommendations=recommendations,
            analyzed_at=datetime.now(timezone.utc)
        )
    
    def _wait_for_processing(self, client, raw_log_id: str, expected_events: int, timeout: int = 30):
        """Wait for background processing to complete."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = client.get("/events")
            if response.status_code == 200:
                events_data = response.json()
                if events_data["total"] >= expected_events:
                    # Verify AI analysis is complete
                    analyzed_count = sum(1 for event in events_data["events"] 
                                       if event["ai_analysis"] is not None)
                    if analyzed_count >= expected_events * 0.8:  # 80% analyzed
                        return
            
            time.sleep(0.5)
        
        # If we get here, processing didn't complete in time
        response = client.get("/events")
        if response.status_code == 200:
            actual_count = response.json()["total"]
            pytest.fail(f"Processing timeout: expected {expected_events} events, got {actual_count}")
        else:
            pytest.fail(f"Processing timeout: unable to retrieve events")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])