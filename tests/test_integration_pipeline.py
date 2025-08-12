"""
Integration tests for the complete ingestion-to-analysis pipeline.

Tests the end-to-end workflow from API ingestion through automated
processing to final event retrieval.
"""
import pytest
import asyncio
import time
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from main import app
from app.database import get_database_session
from app.models import RawLog, Event, AIAnalysis as AIAnalysisModel


class TestIngestionToAnalysisPipeline:
    """Test the complete pipeline from ingestion to analysis."""
    
    def test_text_ingestion_to_analysis_pipeline(self, client: TestClient, db_session):
        """Test complete pipeline with text ingestion."""
        # Sample log content
        log_content = """Jan 15 10:30:45 MacBook-Pro loginwindow[123]: User authentication failed for user 'admin'
Jan 15 10:31:00 MacBook-Pro kernel[0]: System boot completed successfully
Jan 15 10:31:15 MacBook-Pro sshd[456]: Failed login attempt from 192.168.1.100"""
        
        # Step 1: Ingest log via API
        response = client.post(
            "/ingest-log",
            data={"content": log_content, "source": "test_pipeline"}
        )
        
        assert response.status_code == 200
        ingestion_data = response.json()
        raw_log_id = ingestion_data["raw_log_id"]
        
        # Step 2: Wait for background processing to complete
        # In a real scenario, this would be handled by FastAPI BackgroundTasks
        # For testing, we'll simulate the processing
        time.sleep(0.5)  # Allow background task to start
        
        # Step 3: Verify raw log was stored
        with get_database_session() as db:
            raw_log = db.query(RawLog).filter(RawLog.id == raw_log_id).first()
            assert raw_log is not None
            assert raw_log.content == log_content
            assert raw_log.source == "test_pipeline"
        
        # Step 4: Wait a bit more for processing to complete
        time.sleep(2.0)
        
        # Step 5: Verify events were parsed and analyzed
        with get_database_session() as db:
            events = db.query(Event).filter(Event.raw_log_id == raw_log_id).all()
            assert len(events) >= 3  # Should have parsed at least 3 events
            
            # Verify each event has AI analysis
            for event in events:
                analysis = db.query(AIAnalysisModel).filter(
                    AIAnalysisModel.event_id == event.id
                ).first()
                assert analysis is not None
                assert 1 <= analysis.severity_score <= 10
                assert len(analysis.explanation) > 0
        
        # Step 6: Retrieve events via API
        response = client.get("/events")
        assert response.status_code == 200
        
        events_data = response.json()
        assert events_data["total"] >= 3
        assert len(events_data["events"]) >= 3
        
        # Verify each event has AI analysis in the response
        for event in events_data["events"]:
            assert event["ai_analysis"] is not None
            assert "severity_score" in event["ai_analysis"]
            assert "explanation" in event["ai_analysis"]
            assert "recommendations" in event["ai_analysis"]
    
    def test_file_ingestion_to_analysis_pipeline(self, client: TestClient, db_session):
        """Test complete pipeline with file ingestion."""
        # Create a temporary log file content
        log_content = """Jan 15 10:30:45 MacBook-Pro authd[789]: Authentication successful for user 'john'
Jan 15 10:31:00 MacBook-Pro networkd[101]: Network interface en0 connected
Jan 15 10:31:15 MacBook-Pro securityd[202]: Certificate validation failed"""
        
        # Step 1: Ingest log file via API
        files = {"file": ("test.log", log_content, "text/plain")}
        response = client.post("/ingest-log", files=files)
        
        assert response.status_code == 200
        ingestion_data = response.json()
        raw_log_id = ingestion_data["raw_log_id"]
        
        # Step 2: Wait for background processing
        time.sleep(2.5)
        
        # Step 3: Verify processing completed successfully
        with get_database_session() as db:
            events = db.query(Event).filter(Event.raw_log_id == raw_log_id).all()
            assert len(events) >= 3
            
            # Check that different event categories were detected
            categories = {event.category for event in events}
            assert len(categories) >= 2  # Should have multiple categories
            
            # Verify AI analyses exist and have reasonable severity scores
            for event in events:
                analysis = db.query(AIAnalysisModel).filter(
                    AIAnalysisModel.event_id == event.id
                ).first()
                assert analysis is not None
                
                # Authentication events should have higher severity
                if "authentication" in event.message.lower() and "failed" in event.message.lower():
                    assert analysis.severity_score >= 5
    
    def test_pipeline_with_processing_errors(self, client: TestClient, db_session):
        """Test pipeline behavior when processing encounters errors."""
        # Log content with some problematic entries
        log_content = """Jan 15 10:30:45 MacBook-Pro test[123]: Normal log entry
This is not a valid log entry at all
Jan 15 10:31:00 MacBook-Pro kernel[0]: Another normal entry
Invalid entry without proper format
Jan 15 10:31:15 MacBook-Pro sshd[456]: Final normal entry"""
        
        # Ingest the log
        response = client.post(
            "/ingest-log",
            data={"content": log_content, "source": "test_errors"}
        )
        
        assert response.status_code == 200
        raw_log_id = response.json()["raw_log_id"]
        
        # Wait for processing
        time.sleep(2.0)
        
        # Verify that valid entries were still processed despite errors
        with get_database_session() as db:
            events = db.query(Event).filter(Event.raw_log_id == raw_log_id).all()
            assert len(events) >= 3  # Should have processed the valid entries
            
            # All processed events should have analysis
            for event in events:
                analysis = db.query(AIAnalysisModel).filter(
                    AIAnalysisModel.event_id == event.id
                ).first()
                assert analysis is not None
    
    def test_pipeline_performance_with_large_dataset(self, client: TestClient, db_session):
        """Test pipeline performance with a larger dataset."""
        # Generate a larger log file
        log_entries = []
        for i in range(50):  # 50 entries for reasonable test time
            timestamp = f"Jan 15 10:{30 + i // 60}:{i % 60:02d}"
            if i % 5 == 0:
                # Authentication events
                log_entries.append(f"{timestamp} MacBook-Pro authd[{100+i}]: User login attempt for user{i}")
            elif i % 5 == 1:
                # System events
                log_entries.append(f"{timestamp} MacBook-Pro kernel[0]: System event {i}")
            elif i % 5 == 2:
                # Network events
                log_entries.append(f"{timestamp} MacBook-Pro networkd[{200+i}]: Network activity detected")
            elif i % 5 == 3:
                # Security events
                log_entries.append(f"{timestamp} MacBook-Pro securityd[{300+i}]: Security check completed")
            else:
                # Application events
                log_entries.append(f"{timestamp} MacBook-Pro app[{400+i}]: Application event {i}")
        
        log_content = "\n".join(log_entries)
        
        # Measure ingestion time
        start_time = time.time()
        
        response = client.post(
            "/ingest-log",
            data={"content": log_content, "source": "test_performance"}
        )
        
        ingestion_time = time.time() - start_time
        assert response.status_code == 200
        assert ingestion_time < 5.0  # Ingestion should be fast
        
        raw_log_id = response.json()["raw_log_id"]
        
        # Wait for processing to complete
        processing_start = time.time()
        time.sleep(5.0)  # Allow more time for larger dataset
        
        # Verify all events were processed
        with get_database_session() as db:
            events = db.query(Event).filter(Event.raw_log_id == raw_log_id).all()
            assert len(events) == 50
            
            # Verify all have analysis
            analyses = db.query(AIAnalysisModel).join(Event).filter(
                Event.raw_log_id == raw_log_id
            ).all()
            assert len(analyses) == 50
            
            # Check category distribution
            categories = {}
            for event in events:
                categories[event.category] = categories.get(event.category, 0) + 1
            
            assert len(categories) >= 3  # Should have multiple categories
        
        total_processing_time = time.time() - processing_start
        assert total_processing_time < 30.0  # Should complete within reasonable time
    
    def test_pipeline_event_retrieval_and_filtering(self, client: TestClient, db_session):
        """Test event retrieval and filtering after pipeline processing."""
        # Create log with events of different severities
        log_content = """Jan 15 10:30:45 MacBook-Pro loginwindow[123]: User authentication failed for user 'admin'
Jan 15 10:31:00 MacBook-Pro kernel[0]: System boot completed successfully
Jan 15 10:31:15 MacBook-Pro sshd[456]: Failed login attempt from 192.168.1.100
Jan 15 10:31:30 MacBook-Pro securityd[789]: Security violation detected
Jan 15 10:31:45 MacBook-Pro app[101]: Application started normally"""
        
        # Ingest and process
        response = client.post(
            "/ingest-log",
            data={"content": log_content, "source": "test_filtering"}
        )
        assert response.status_code == 200
        
        # Wait for processing
        time.sleep(3.0)
        
        # Test basic event retrieval
        response = client.get("/events")
        assert response.status_code == 200
        events_data = response.json()
        assert events_data["total"] >= 5
        
        # Test filtering by severity (high severity events)
        response = client.get("/events?min_severity=7")
        assert response.status_code == 200
        high_severity_events = response.json()
        
        # Should have fewer high-severity events
        assert high_severity_events["total"] <= events_data["total"]
        
        # Verify all returned events have severity >= 7
        for event in high_severity_events["events"]:
            if event["ai_analysis"]:
                assert event["ai_analysis"]["severity_score"] >= 7
        
        # Test filtering by category
        response = client.get("/events?category=auth")
        assert response.status_code == 200
        auth_events = response.json()
        
        # Verify all returned events are auth category
        for event in auth_events["events"]:
            assert event["category"] == "auth"
        
        # Test event detail retrieval
        if events_data["events"]:
            event_id = events_data["events"][0]["id"]
            response = client.get(f"/event/{event_id}")
            assert response.status_code == 200
            
            event_detail = response.json()
            assert event_detail["id"] == event_id
            assert event_detail["ai_analysis"] is not None
    
    def test_manual_processing_trigger(self, client: TestClient, db_session):
        """Test manual processing trigger endpoint."""
        # Create a raw log directly in database (simulating failed processing)
        raw_log_content = "Jan 15 10:30:45 MacBook-Pro test[123]: Manual processing test"
        
        raw_log = RawLog(
            id=str(uuid.uuid4()),
            content=raw_log_content,
            source="manual_test",
            ingested_at=datetime.now(timezone.utc)
        )
        
        with get_database_session() as db:
            db.add(raw_log)
            db.commit()
            db.refresh(raw_log)
        
        # Trigger manual processing
        response = client.post(f"/trigger-processing/{raw_log.id}")
        assert response.status_code == 200
        
        trigger_data = response.json()
        assert trigger_data["raw_log_id"] == raw_log.id
        assert "triggered_at" in trigger_data
        
        # Wait for processing
        time.sleep(1.5)
        
        # Verify processing completed
        with get_database_session() as db:
            events = db.query(Event).filter(Event.raw_log_id == raw_log.id).all()
            assert len(events) >= 1
    
    def test_processing_statistics_endpoint(self, client: TestClient, db_session):
        """Test processing statistics endpoint."""
        # Ingest some logs to generate statistics
        for i in range(3):
            log_content = f"Jan 15 10:30:{i:02d} MacBook-Pro test[{i}]: Test message {i}"
            response = client.post(
                "/ingest-log",
                data={"content": log_content, "source": f"stats_test_{i}"}
            )
            assert response.status_code == 200
        
        # Wait for processing
        time.sleep(2.0)
        
        # Get system statistics
        response = client.get("/stats")
        assert response.status_code == 200
        
        stats = response.json()
        assert "processing" in stats
        assert "database" in stats
        
        processing_stats = stats["processing"]
        assert "total_tasks" in processing_stats
        assert "successful_tasks" in processing_stats
        assert processing_stats["total_tasks"] >= 3
    
    def test_pipeline_error_recovery(self, client: TestClient, db_session):
        """Test pipeline error recovery and retry logic."""
        # This test would ideally simulate various failure scenarios
        # For now, we'll test with content that might cause issues
        
        problematic_content = """Jan 15 10:30:45 MacBook-Pro test[123]: Normal entry
Jan 15 10:30:46 MacBook-Pro test[124]: Entry with unicode: café résumé naïve
Jan 15 10:30:47 MacBook-Pro test[125]: Entry with special chars: !@#$%^&*()
Jan 15 10:30:48 MacBook-Pro test[126]: Very long entry: """ + "x" * 1000
        
        response = client.post(
            "/ingest-log",
            data={"content": problematic_content, "source": "error_recovery_test"}
        )
        
        assert response.status_code == 200
        raw_log_id = response.json()["raw_log_id"]
        
        # Wait for processing
        time.sleep(2.0)
        
        # Verify that processing handled the problematic content gracefully
        with get_database_session() as db:
            events = db.query(Event).filter(Event.raw_log_id == raw_log_id).all()
            assert len(events) >= 3  # Should process most entries
            
            # Verify analyses were created despite potential issues
            for event in events:
                analysis = db.query(AIAnalysisModel).filter(
                    AIAnalysisModel.event_id == event.id
                ).first()
                assert analysis is not None


class TestPipelineEdgeCases:
    """Test edge cases and error conditions in the pipeline."""
    
    def test_empty_log_ingestion(self, client: TestClient, db_session):
        """Test ingestion of empty log content."""
        response = client.post(
            "/ingest-log",
            data={"content": "", "source": "empty_test"}
        )
        
        # Should fail validation
        assert response.status_code == 400
    
    def test_very_large_log_ingestion(self, client: TestClient, db_session):
        """Test ingestion of very large log content."""
        # Create content that exceeds reasonable limits
        large_content = "Jan 15 10:30:45 MacBook-Pro test[123]: " + "x" * (5 * 1024 * 1024)  # 5MB+
        
        response = client.post(
            "/ingest-log",
            data={"content": large_content, "source": "large_test"}
        )
        
        # Should fail due to size limits
        assert response.status_code == 400
    
    def test_invalid_file_upload(self, client: TestClient, db_session):
        """Test upload of invalid file types."""
        # Try to upload a non-log file
        files = {"file": ("test.exe", b"binary content", "application/octet-stream")}
        response = client.post("/ingest-log", files=files)
        
        # Should fail validation
        assert response.status_code == 400
    
    def test_concurrent_ingestion(self, client: TestClient, db_session):
        """Test concurrent log ingestion."""
        import threading
        import queue
        
        results = queue.Queue()
        
        def ingest_log(index):
            log_content = f"Jan 15 10:30:{index:02d} MacBook-Pro test[{index}]: Concurrent test {index}"
            response = client.post(
                "/ingest-log",
                data={"content": log_content, "source": f"concurrent_test_{index}"}
            )
            results.put((index, response.status_code))
        
        # Start multiple concurrent ingestions
        threads = []
        for i in range(5):
            thread = threading.Thread(target=ingest_log, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all to complete
        for thread in threads:
            thread.join()
        
        # Check results
        success_count = 0
        while not results.empty():
            index, status_code = results.get()
            if status_code == 200:
                success_count += 1
        
        assert success_count == 5  # All should succeed
        
        # Wait for processing
        time.sleep(3.0)
        
        # Verify all logs were processed
        with get_database_session() as db:
            total_events = db.query(Event).count()
            assert total_events >= 5


# Test fixtures and utilities
@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment before each test."""
    # Reset processing statistics before each test
    from app.background_tasks import reset_processing_stats
    reset_processing_stats()
    
    yield
    
    # Cleanup after test if needed
    pass