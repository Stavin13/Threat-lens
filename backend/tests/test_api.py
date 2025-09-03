"""
Integration tests for ThreatLens FastAPI endpoints.

Tests all API endpoints using FastAPI TestClient with comprehensive
scenarios including success cases, error handling, and edge cases.
"""
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

# Import the FastAPI app and dependencies
from main import app
from app.database import get_database_session, init_database
from app.models import Base, RawLog, Event, AIAnalysis as AIAnalysisModel
from app.schemas import EventCategory


# Test database setup
@pytest.fixture(scope="function")
def test_db():
    """Create a test database for each test."""
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    # Create test engine
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    # Override the dependency
    app.dependency_overrides[get_database_session] = override_get_db
    
    yield TestingSessionLocal
    
    # Cleanup
    app.dependency_overrides.clear()
    os.unlink(db_path)


@pytest.fixture
def client(test_db):
    """Create test client with test database."""
    return TestClient(app)


@pytest.fixture
def sample_log_content():
    """Sample log content for testing."""
    return """Jan 15 10:30:45 MacBook-Pro loginwindow[123]: User john logged in successfully
Jan 15 10:31:02 MacBook-Pro sshd[456]: Failed password for admin from 192.168.1.100 port 22 ssh2
Jan 15 10:31:15 MacBook-Pro kernel[0]: Memory pressure warning
Jan 15 10:32:00 MacBook-Pro SecurityAgent[789]: Authentication failed for user admin"""


@pytest.fixture
def sample_events_data(test_db):
    """Create sample events in the test database."""
    db = test_db()
    
    # Create raw log
    raw_log = RawLog(
        id="test-raw-log-1",
        content="Test log content",
        source="test_source",
        ingested_at=datetime.now(timezone.utc)
    )
    db.add(raw_log)
    
    # Create events with different categories and severities
    events_data = [
        {
            "id": "event-1",
            "category": EventCategory.AUTH.value,
            "message": "Failed login attempt",
            "severity": 7
        },
        {
            "id": "event-2", 
            "category": EventCategory.SYSTEM.value,
            "message": "System startup completed",
            "severity": 2
        },
        {
            "id": "event-3",
            "category": EventCategory.SECURITY.value,
            "message": "Suspicious network activity detected",
            "severity": 9
        }
    ]
    
    for i, event_data in enumerate(events_data):
        # Create event
        event = Event(
            id=event_data["id"],
            raw_log_id="test-raw-log-1",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=i),
            source=f"test-source-{i+1}",
            message=event_data["message"],
            category=event_data["category"],
            parsed_at=datetime.now(timezone.utc)
        )
        db.add(event)
        
        # Create AI analysis
        analysis = AIAnalysisModel(
            id=f"analysis-{i+1}",
            event_id=event_data["id"],
            severity_score=event_data["severity"],
            explanation=f"Test explanation for event {i+1}",
            recommendations=json.dumps([f"Recommendation 1 for event {i+1}", f"Recommendation 2 for event {i+1}"]),
            analyzed_at=datetime.now(timezone.utc)
        )
        db.add(analysis)
    
    db.commit()
    db.close()
    
    return events_data


class TestRootEndpoint:
    """Test the root endpoint."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns API information."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "ThreatLens API"
        assert data["version"] == "1.0.0"
        assert "description" in data
        assert "docs" in data


class TestHealthEndpoint:
    """Test the health check endpoint."""
    
    def test_health_check_success(self, client):
        """Test health check with healthy database."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "timestamp" in data
        assert data["database"]["connection"] is True


class TestLogIngestionEndpoint:
    """Test the log ingestion endpoint."""
    
    @patch('main.process_raw_log')
    def test_ingest_text_content_success(self, mock_process, client, sample_log_content):
        """Test successful text content ingestion."""
        response = client.post(
            "/ingest-log",
            params={"content": sample_log_content, "source": "test_source"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "raw_log_id" in data
        assert data["message"].startswith("Text content from 'test_source' ingested successfully")
        assert data["events_parsed"] == 0  # Will be updated after background processing
        assert "ingested_at" in data
        
        # Verify background task was scheduled
        mock_process.assert_called_once()
    
    @patch('main.process_raw_log')
    def test_ingest_file_upload_success(self, mock_process, client, sample_log_content):
        """Test successful file upload ingestion."""
        # Create a temporary file-like object
        file_content = sample_log_content.encode('utf-8')
        
        response = client.post(
            "/ingest-log",
            files={"file": ("test.log", file_content, "text/plain")}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "raw_log_id" in data
        assert data["message"].startswith("File 'test.log' ingested successfully")
        assert "ingested_at" in data
        
        # Verify background task was scheduled
        mock_process.assert_called_once()
    
    def test_ingest_both_file_and_content_error(self, client):
        """Test error when both file and content are provided."""
        response = client.post(
            "/ingest-log",
            files={"file": ("test.log", b"test content", "text/plain")},
            params={"content": "test content"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Cannot provide both file and content" in data["detail"]
    
    def test_ingest_no_input_error(self, client):
        """Test error when neither file nor content is provided."""
        response = client.post("/ingest-log")
        
        assert response.status_code == 400
        data = response.json()
        assert "Must provide either file or content" in data["detail"]
    
    def test_ingest_empty_content_error(self, client):
        """Test error with empty content."""
        response = client.post(
            "/ingest-log",
            params={"content": "", "source": "test"}
        )
        
        assert response.status_code == 400
        # Empty content should be caught by the validation logic
        response_data = response.json()
        # Could be either a validation error or IngestionError
        assert "Must provide either file or content" in response_data.get("detail", "") or \
               "IngestionError" in response_data.get("error", "")
    
    def test_ingest_invalid_file_extension(self, client):
        """Test error with invalid file extension."""
        response = client.post(
            "/ingest-log",
            files={"file": ("test.exe", b"test content", "application/octet-stream")}
        )
        
        assert response.status_code == 400
        assert "IngestionError" in response.json()["error"]
    
    def test_ingest_large_file_error(self, client):
        """Test error with file too large."""
        # Create content larger than the limit (50MB)
        large_content = "x" * (51 * 1024 * 1024)  # 51MB
        
        response = client.post(
            "/ingest-log",
            files={"file": ("large.log", large_content.encode(), "text/plain")}
        )
        
        assert response.status_code == 400
        assert "IngestionError" in response.json()["error"]


class TestEventsEndpoint:
    """Test the events listing endpoint."""
    
    def test_get_events_success(self, client, sample_events_data):
        """Test successful events retrieval."""
        response = client.get("/events")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["per_page"] == 20
        assert len(data["events"]) == 3
        
        # Check event structure
        event = data["events"][0]
        assert "id" in event
        assert "timestamp" in event
        assert "source" in event
        assert "message" in event
        assert "category" in event
        assert "ai_analysis" in event
        
        # Check AI analysis structure
        if event["ai_analysis"]:
            analysis = event["ai_analysis"]
            assert "severity_score" in analysis
            assert "explanation" in analysis
            assert "recommendations" in analysis
    
    def test_get_events_pagination(self, client, sample_events_data):
        """Test events pagination."""
        # Get first page with 2 events per page
        response = client.get("/events?page=1&per_page=2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["per_page"] == 2
        assert data["total_pages"] == 2
        assert len(data["events"]) == 2
        
        # Get second page
        response = client.get("/events?page=2&per_page=2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["page"] == 2
        assert len(data["events"]) == 1
    
    def test_get_events_category_filter(self, client, sample_events_data):
        """Test events filtering by category."""
        response = client.get("/events?category=auth")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["events"]) == 1
        assert data["events"][0]["category"] == "auth"
    
    def test_get_events_severity_filter(self, client, sample_events_data):
        """Test events filtering by severity."""
        response = client.get("/events?min_severity=7")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return events with severity >= 7 (events 1 and 3)
        assert len(data["events"]) == 2
        for event in data["events"]:
            if event["ai_analysis"]:
                assert event["ai_analysis"]["severity_score"] >= 7
    
    def test_get_events_source_filter(self, client, sample_events_data):
        """Test events filtering by source."""
        response = client.get("/events?source=test-source-1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["events"]) == 1
        assert "test-source-1" in data["events"][0]["source"]
    
    def test_get_events_sorting(self, client, sample_events_data):
        """Test events sorting."""
        # Sort by severity ascending
        response = client.get("/events?sort_by=severity&sort_order=asc")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that events are sorted by severity (ascending)
        severities = []
        for event in data["events"]:
            if event["ai_analysis"]:
                severities.append(event["ai_analysis"]["severity_score"])
        
        assert severities == sorted(severities)
    
    def test_get_events_invalid_sort_field(self, client, sample_events_data):
        """Test error with invalid sort field."""
        response = client.get("/events?sort_by=invalid_field")
        
        assert response.status_code == 400
        assert "Invalid sort field" in response.json()["detail"]
    
    def test_get_events_invalid_sort_order(self, client, sample_events_data):
        """Test error with invalid sort order."""
        response = client.get("/events?sort_order=invalid")
        
        assert response.status_code == 400
        assert "Sort order must be" in response.json()["detail"]
    
    def test_get_events_invalid_severity_range(self, client, sample_events_data):
        """Test error with invalid severity range."""
        response = client.get("/events?min_severity=8&max_severity=5")
        
        assert response.status_code == 400
        assert "min_severity cannot be greater than max_severity" in response.json()["detail"]
    
    def test_get_events_invalid_page(self, client, sample_events_data):
        """Test error with invalid page number."""
        response = client.get("/events?page=0")
        
        assert response.status_code == 422  # Validation error
    
    def test_get_events_invalid_per_page(self, client, sample_events_data):
        """Test error with invalid per_page value."""
        response = client.get("/events?per_page=101")  # Exceeds maximum
        
        assert response.status_code == 422  # Validation error


class TestEventDetailEndpoint:
    """Test the event detail endpoint."""
    
    def test_get_event_detail_success(self, client, sample_events_data):
        """Test successful event detail retrieval."""
        event_id = "event-1"
        response = client.get(f"/event/{event_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == event_id
        assert "timestamp" in data
        assert "source" in data
        assert "message" in data
        assert "category" in data
        assert "ai_analysis" in data
        
        # Check AI analysis
        analysis = data["ai_analysis"]
        assert analysis is not None
        assert analysis["severity_score"] == 7
        assert "explanation" in analysis
        assert "recommendations" in analysis
        assert isinstance(analysis["recommendations"], list)
    
    def test_get_event_detail_not_found(self, client, sample_events_data):
        """Test event detail with non-existent event ID."""
        response = client.get("/event/non-existent-id")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_get_event_detail_invalid_id_format(self, client, sample_events_data):
        """Test event detail with invalid ID format."""
        # Test with empty ID
        response = client.get("/event/")
        
        # Should return 404 or 405 depending on routing
        assert response.status_code in [404, 405]


class TestStatsEndpoint:
    """Test the system statistics endpoint."""
    
    def test_get_stats_success(self, client, sample_events_data):
        """Test successful stats retrieval."""
        response = client.get("/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "database" in data
        assert "api_version" in data
        assert "timestamp" in data
        
        # Check database stats
        db_stats = data["database"]
        assert "raw_logs_count" in db_stats
        assert "events_count" in db_stats
        assert "ai_analysis_count" in db_stats
        assert "reports_count" in db_stats


class TestErrorHandling:
    """Test error handling across endpoints."""
    
    def test_cors_headers(self, client):
        """Test CORS headers are present."""
        response = client.options("/")
        
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers
    
    def test_404_for_unknown_endpoint(self, client):
        """Test 404 response for unknown endpoints."""
        response = client.get("/unknown-endpoint")
        
        assert response.status_code == 404
    
    def test_method_not_allowed(self, client):
        """Test 405 response for unsupported methods."""
        response = client.delete("/events")  # DELETE not supported on /events
        
        assert response.status_code == 405


class TestBackgroundProcessing:
    """Test background processing functionality."""
    
    @patch('app.parser.parse_log_entries')
    @patch('app.analyzer.analyze_event')
    def test_background_processing_success(self, mock_analyze, mock_parse, client, test_db, sample_log_content):
        """Test successful background processing of ingested logs."""
        from main import process_raw_log
        from app.schemas import ParsedEvent, AIAnalysis
        
        # Mock parser response
        mock_event = ParsedEvent(
            id="test-event-1",
            raw_log_id="test-raw-1",
            timestamp=datetime.now(timezone.utc),
            source="test-source",
            message="Test message",
            category=EventCategory.SYSTEM,
            parsed_at=datetime.now(timezone.utc)
        )
        mock_parse.return_value = [mock_event]
        
        # Mock analyzer response
        mock_analysis = AIAnalysis(
            id="test-analysis-1",
            event_id="test-event-1",
            severity_score=5,
            explanation="Test explanation",
            recommendations=["Test recommendation"],
            analyzed_at=datetime.now(timezone.utc)
        )
        mock_analyze.return_value = mock_analysis
        
        # Create raw log in database
        db = test_db()
        raw_log = RawLog(
            id="test-raw-1",
            content=sample_log_content,
            source="test_source",
            ingested_at=datetime.now(timezone.utc)
        )
        db.add(raw_log)
        db.commit()
        db.close()
        
        # Run background processing
        import asyncio
        asyncio.run(process_raw_log("test-raw-1"))
        
        # Verify mocks were called
        mock_parse.assert_called_once_with(sample_log_content, "test-raw-1")
        mock_analyze.assert_called_once()
        
        # Verify data was stored in database
        db = test_db()
        stored_event = db.query(Event).filter(Event.id == "test-event-1").first()
        assert stored_event is not None
        assert stored_event.message == "Test message"
        
        stored_analysis = db.query(AIAnalysisModel).filter(AIAnalysisModel.event_id == "test-event-1").first()
        assert stored_analysis is not None
        assert stored_analysis.severity_score == 5
        db.close()


# Integration test for complete workflow
class TestCompleteWorkflow:
    """Test complete workflow from ingestion to retrieval."""
    
    @patch('app.analyzer.analyze_event')
    def test_complete_ingestion_to_retrieval_workflow(self, mock_analyze, client, sample_log_content):
        """Test complete workflow from log ingestion to event retrieval."""
        # Mock AI analysis
        mock_analysis = AIAnalysis(
            id="workflow-analysis-1",
            event_id="workflow-event-1",
            severity_score=6,
            explanation="Workflow test explanation",
            recommendations=["Workflow recommendation 1", "Workflow recommendation 2"],
            analyzed_at=datetime.now(timezone.utc)
        )
        mock_analyze.return_value = mock_analysis
        
        # Step 1: Ingest log
        response = client.post(
            "/ingest-log",
            params={"content": sample_log_content, "source": "workflow_test"}
        )
        
        assert response.status_code == 200
        ingestion_data = response.json()
        raw_log_id = ingestion_data["raw_log_id"]
        
        # Step 2: Manually trigger background processing (since we can't wait for async)
        from main import process_raw_log
        import asyncio
        asyncio.run(process_raw_log(raw_log_id))
        
        # Step 3: Retrieve events
        response = client.get("/events")
        
        assert response.status_code == 200
        events_data = response.json()
        
        # Should have parsed events from the ingested log
        assert events_data["total"] > 0
        assert len(events_data["events"]) > 0
        
        # Step 4: Get detailed view of first event
        first_event_id = events_data["events"][0]["id"]
        response = client.get(f"/event/{first_event_id}")
        
        assert response.status_code == 200
        event_detail = response.json()
        
        assert event_detail["id"] == first_event_id
        assert event_detail["ai_analysis"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])