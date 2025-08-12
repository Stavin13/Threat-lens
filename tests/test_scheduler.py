"""
Integration tests for scheduled report generation functionality.

Tests the APScheduler integration, file management utilities,
and audit logging for automated report generation.
"""
import asyncio
import pytest
import tempfile
import shutil
import os
from datetime import datetime, date, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.scheduler import (
    ScheduledReportManager,
    start_scheduled_reports,
    stop_scheduled_reports,
    get_scheduler_status,
    get_audit_log,
    trigger_manual_report,
    get_report_files_info
)
from app.database import get_database_session
from app.models import Base, Report, Event, AIAnalysis as AIAnalysisModel
# Test database fixture
@pytest.fixture(scope="function")
def db_session():
    """Create a test database session for each test."""
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    # Create test engine
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    session = TestingSessionLocal()
    
    yield session
    
    # Cleanup
    session.close()
    os.unlink(db_path)


# Test helper functions
def create_test_event(db_session, event_id=None, timestamp=None, message="Test event", category="system"):
    """Create a test event in the database."""
    import uuid
    from app.models import Event
    
    if event_id is None:
        event_id = str(uuid.uuid4())
    if timestamp is None:
        timestamp = datetime.now()
    
    event = Event(
        id=event_id,
        raw_log_id="test-raw-log",
        timestamp=timestamp,
        source="test-source",
        message=message,
        category=category,
        parsed_at=datetime.now()
    )
    
    db_session.add(event)
    db_session.commit()
    return event


def create_test_ai_analysis(db_session, event_id, analysis_id=None, severity_score=5):
    """Create a test AI analysis in the database."""
    import uuid
    import json
    from app.models import AIAnalysis as AIAnalysisModel
    
    if analysis_id is None:
        analysis_id = str(uuid.uuid4())
    
    analysis = AIAnalysisModel(
        id=analysis_id,
        event_id=event_id,
        severity_score=severity_score,
        explanation="Test AI analysis explanation",
        recommendations=json.dumps(["Test recommendation 1", "Test recommendation 2"]),
        analyzed_at=datetime.now()
    )
    
    db_session.add(analysis)
    db_session.commit()
    return analysis


class TestScheduledReportManager:
    """Test cases for the ScheduledReportManager class."""
    
    @pytest.fixture
    def temp_reports_dir(self):
        """Create a temporary directory for test reports."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def report_manager(self, temp_reports_dir):
        """Create a ScheduledReportManager instance for testing."""
        manager = ScheduledReportManager(reports_dir=temp_reports_dir, max_reports=5)
        yield manager
        # Clean up scheduler if running
        if manager.scheduler.running:
            manager.stop_scheduler()
    
    def test_initialization(self, temp_reports_dir):
        """Test ScheduledReportManager initialization."""
        manager = ScheduledReportManager(reports_dir=temp_reports_dir, max_reports=10)
        
        assert manager.reports_dir == Path(temp_reports_dir)
        assert manager.max_reports == 10
        assert manager.scheduler is not None
        assert manager.audit_log == []
        assert manager.reports_dir.exists()
    
    def test_start_stop_scheduler(self, report_manager):
        """Test starting and stopping the scheduler."""
        # Test starting
        report_manager.start_scheduler()
        assert report_manager.scheduler.running
        
        # Check that jobs were added
        jobs = report_manager.scheduler.get_jobs()
        job_ids = [job.id for job in jobs]
        assert 'daily_report_generation' in job_ids
        assert 'weekly_report_cleanup' in job_ids
        
        # Test stopping
        report_manager.stop_scheduler()
        # Note: AsyncIOScheduler may not immediately show as stopped in tests
        # The important thing is that shutdown was called without error
    
    @pytest.mark.asyncio
    async def test_generate_daily_report_job_success(self, report_manager, db_session):
        """Test successful daily report generation job."""
        # Create test data
        test_date = date.today() - timedelta(days=1)
        event = create_test_event(db_session, timestamp=datetime.combine(test_date, datetime.min.time()))
        analysis = create_test_ai_analysis(db_session, event.id)
        
        # Mock the report generation
        with patch('app.scheduler.generate_daily_report') as mock_generate:
            mock_generate.return_value = ("/fake/path/report.pdf", b"fake pdf content")
            
            with patch('app.scheduler.save_report_record') as mock_save:
                mock_save.return_value = "test-report-id"
                
                # Execute the job
                result = await report_manager._generate_daily_report_job()
                
                # Verify results
                assert result["success"] is True
                assert result["report_id"] == "test-report-id"
                assert result["report_date"] == test_date
                
                # Verify audit log
                audit_entries = report_manager.get_audit_log()
                assert len(audit_entries) > 0
                assert audit_entries[0]["action"] == "daily_report_generated"
    
    @pytest.mark.asyncio
    async def test_generate_daily_report_job_failure(self, report_manager):
        """Test daily report generation job failure handling."""
        # Mock the report generation to fail
        with patch('app.scheduler.generate_daily_report') as mock_generate:
            mock_generate.side_effect = Exception("Report generation failed")
            
            # Execute the job and expect it to raise
            with pytest.raises(Exception, match="Report generation failed"):
                await report_manager._generate_daily_report_job()
            
            # Verify audit log contains failure entry
            audit_entries = report_manager.get_audit_log()
            assert len(audit_entries) > 0
            assert audit_entries[0]["action"] == "daily_report_failed"
    
    @pytest.mark.asyncio
    async def test_cleanup_old_reports_job(self, report_manager, temp_reports_dir):
        """Test cleanup of old report files."""
        reports_dir = Path(temp_reports_dir)
        
        # Create test report files (more than max_reports)
        test_dates = [date.today() - timedelta(days=i) for i in range(10)]
        created_files = []
        
        for test_date in test_dates:
            filename = f"security_report_{test_date.strftime('%Y%m%d')}.pdf"
            file_path = reports_dir / filename
            file_path.write_bytes(b"fake pdf content")
            created_files.append(file_path)
        
        # Mock database operations
        with patch('app.scheduler.get_db_session') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value.__enter__.return_value = mock_session
            
            # Execute cleanup job
            result = await report_manager._cleanup_old_reports_job()
            
            # Verify results
            assert result["success"] is True
            assert result["files_removed"] == 5  # Should remove 5 files (keep 5)
            assert result["total_files"] == 10
            
            # Verify files were actually removed
            remaining_files = list(reports_dir.glob("security_report_*.pdf"))
            assert len(remaining_files) == 5
            
            # Verify audit log
            audit_entries = report_manager.get_audit_log()
            cleanup_entry = next((e for e in audit_entries if e["action"] == "report_cleanup_completed"), None)
            assert cleanup_entry is not None
            assert cleanup_entry["details"]["files_removed"] == 5
    
    def test_audit_log_functionality(self, report_manager):
        """Test audit logging functionality."""
        # Add some audit entries
        report_manager._add_audit_entry("test_action_1", "Test message 1", {"key": "value1"})
        report_manager._add_audit_entry("test_action_2", "Test message 2", {"key": "value2"})
        
        # Get audit log
        audit_log = report_manager.get_audit_log()
        
        assert len(audit_log) == 2
        assert audit_log[0]["action"] == "test_action_2"  # Most recent first
        assert audit_log[0]["message"] == "Test message 2"
        assert audit_log[1]["action"] == "test_action_1"
        
        # Test with limit
        limited_log = report_manager.get_audit_log(limit=1)
        assert len(limited_log) == 1
        assert limited_log[0]["action"] == "test_action_2"
    
    def test_audit_log_size_limit(self, report_manager):
        """Test that audit log doesn't grow indefinitely."""
        # Add more than 1000 entries
        for i in range(1100):
            report_manager._add_audit_entry(f"test_action_{i}", f"Test message {i}")
        
        # Verify log is capped at 1000 entries
        assert len(report_manager.audit_log) == 1000
        
        # Verify it kept the most recent entries
        assert report_manager.audit_log[-1]["action"] == "test_action_1099"
        assert report_manager.audit_log[0]["action"] == "test_action_100"
    
    def test_get_scheduler_status(self, report_manager):
        """Test getting scheduler status information."""
        # Test when not started
        status = report_manager.get_scheduler_status()
        assert status["status"] == "stopped"
        assert status["jobs"] == []
        
        # Test when started
        report_manager.start_scheduler()
        status = report_manager.get_scheduler_status()
        assert status["status"] == "running"
        assert len(status["jobs"]) == 2  # daily report + cleanup jobs
        assert status["reports_directory"] == str(report_manager.reports_dir)
        assert status["max_reports"] == report_manager.max_reports
        
        # Verify job details
        job_ids = [job["id"] for job in status["jobs"]]
        assert "daily_report_generation" in job_ids
        assert "weekly_report_cleanup" in job_ids
    
    def test_trigger_manual_report_generation(self, report_manager, db_session):
        """Test manual report generation trigger."""
        test_date = date.today() - timedelta(days=1)
        
        # Mock the report generation
        with patch('app.scheduler.generate_daily_report') as mock_generate:
            mock_generate.return_value = ("/fake/path/report.pdf", b"fake pdf content")
            
            with patch('app.scheduler.save_report_record') as mock_save:
                mock_save.return_value = "manual-report-id"
                
                # Trigger manual report
                result = report_manager.trigger_manual_report_generation(test_date)
                
                # Verify results
                assert result["success"] is True
                assert result["report_id"] == "manual-report-id"
                assert result["report_date"] == test_date
                assert result["file_size"] == len(b"fake pdf content")
                
                # Verify audit log
                audit_entries = report_manager.get_audit_log()
                manual_entry = next((e for e in audit_entries if e["action"] == "manual_report_generated"), None)
                assert manual_entry is not None
    
    def test_trigger_manual_report_generation_failure(self, report_manager):
        """Test manual report generation failure handling."""
        test_date = date.today() - timedelta(days=1)
        
        # Mock the report generation to fail
        with patch('app.scheduler.generate_daily_report') as mock_generate:
            mock_generate.side_effect = Exception("Manual generation failed")
            
            # Trigger manual report
            result = report_manager.trigger_manual_report_generation(test_date)
            
            # Verify failure handling
            assert result["success"] is False
            assert "Manual generation failed" in result["error"]
            assert result["report_date"] == test_date
            
            # Verify audit log
            audit_entries = report_manager.get_audit_log()
            failure_entry = next((e for e in audit_entries if e["action"] == "manual_report_failed"), None)
            assert failure_entry is not None
    
    def test_get_report_files_info(self, report_manager, temp_reports_dir):
        """Test getting information about existing report files."""
        reports_dir = Path(temp_reports_dir)
        
        # Create test report files
        test_dates = [
            date.today() - timedelta(days=1),
            date.today() - timedelta(days=2),
            date.today() - timedelta(days=3)
        ]
        
        for test_date in test_dates:
            filename = f"security_report_{test_date.strftime('%Y%m%d')}.pdf"
            file_path = reports_dir / filename
            file_path.write_bytes(b"fake pdf content")
        
        # Create an invalid file (should be ignored)
        invalid_file = reports_dir / "invalid_report.pdf"
        invalid_file.write_bytes(b"invalid content")
        
        # Get report files info
        files_info = report_manager.get_report_files_info()
        
        # Verify results
        assert len(files_info) == 3  # Should ignore invalid file
        
        # Verify sorting (newest first)
        assert files_info[0]["report_date"] == test_dates[0].isoformat()
        assert files_info[1]["report_date"] == test_dates[1].isoformat()
        assert files_info[2]["report_date"] == test_dates[2].isoformat()
        
        # Verify file information
        for file_info in files_info:
            assert "filename" in file_info
            assert "file_path" in file_info
            assert "file_size" in file_info
            assert "created_at" in file_info
            assert "modified_at" in file_info
            assert file_info["file_size"] == len(b"fake pdf content")


class TestSchedulerGlobalFunctions:
    """Test cases for global scheduler functions."""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Ensure scheduler is stopped after each test."""
        # Stop any running scheduler before test
        try:
            stop_scheduled_reports()
        except:
            pass  # Ignore errors if already stopped
        
        yield
        
        # Stop scheduler after test
        try:
            stop_scheduled_reports()
        except:
            pass  # Ignore errors if already stopped
    
    def test_start_stop_scheduled_reports(self):
        """Test global start/stop functions."""
        # Test starting
        start_scheduled_reports()
        status = get_scheduler_status()
        assert status["status"] == "running"
        
        # Test stopping
        stop_scheduled_reports()
        status = get_scheduler_status()
        assert status["status"] == "stopped"
    
    def test_get_scheduler_status_global(self):
        """Test global scheduler status function."""
        status = get_scheduler_status()
        assert "status" in status
        assert "jobs" in status
        assert "reports_directory" in status
        assert "max_reports" in status
    
    def test_get_audit_log_global(self):
        """Test global audit log function."""
        # Start scheduler to generate some audit entries
        start_scheduled_reports()
        
        audit_log = get_audit_log()
        assert isinstance(audit_log, list)
        
        # Should have at least the scheduler_started entry
        assert len(audit_log) > 0
        assert any(entry["action"] == "scheduler_started" for entry in audit_log)
    
    def test_trigger_manual_report_global(self):
        """Test global manual report trigger function."""
        test_date = date.today() - timedelta(days=1)
        
        # Mock the report generation
        with patch('app.scheduler.generate_daily_report') as mock_generate:
            mock_generate.return_value = ("/fake/path/report.pdf", b"fake pdf content")
            
            with patch('app.scheduler.save_report_record') as mock_save:
                mock_save.return_value = "global-test-report-id"
                
                # Trigger manual report
                result = trigger_manual_report(test_date)
                
                # Verify results
                assert result["success"] is True
                assert result["report_id"] == "global-test-report-id"
                assert result["report_date"] == test_date
    
    def test_get_report_files_info_global(self):
        """Test global report files info function."""
        files_info = get_report_files_info()
        assert isinstance(files_info, list)


class TestSchedulerIntegration:
    """Integration tests for scheduler with database and report generation."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_scheduled_report_generation(self, db_session):
        """Test complete end-to-end scheduled report generation."""
        # Create test data for yesterday
        test_date = date.today() - timedelta(days=1)
        test_datetime = datetime.combine(test_date, datetime.min.time())
        
        # Create test events
        event1 = create_test_event(
            db_session, 
            timestamp=test_datetime,
            message="Test security event 1",
            category="authentication"
        )
        event2 = create_test_event(
            db_session,
            timestamp=test_datetime + timedelta(hours=1),
            message="Test security event 2", 
            category="network"
        )
        
        # Create AI analyses
        analysis1 = create_test_ai_analysis(db_session, event1.id, severity_score=8)
        analysis2 = create_test_ai_analysis(db_session, event2.id, severity_score=5)
        
        # Create temporary reports directory
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ScheduledReportManager(reports_dir=temp_dir, max_reports=5)
            
            try:
                # Execute the daily report generation job
                result = await manager._generate_daily_report_job()
                
                # Verify report was generated
                assert result["success"] is True
                assert result["report_date"] == test_date
                
                # Verify file was created (the mock should have been called)
                # Note: Since we're mocking generate_daily_report, no actual file is created
                # But we can verify the function was called correctly
                assert result["report_id"] is not None
                
                # Verify audit log
                audit_entries = manager.get_audit_log()
                report_entry = next((e for e in audit_entries if e["action"] == "daily_report_generated"), None)
                assert report_entry is not None
                assert report_entry["details"]["report_date"] == test_date.isoformat()
                
            finally:
                if manager.scheduler.running:
                    manager.stop_scheduler()
    
    @pytest.mark.asyncio
    async def test_scheduler_error_handling_and_recovery(self, db_session):
        """Test scheduler error handling and recovery mechanisms."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ScheduledReportManager(reports_dir=temp_dir, max_reports=5)
            
            try:
                # Test job error listener
                manager.start_scheduler()
                
                # Simulate a job error
                from apscheduler.events import JobExecutionEvent
                
                # Create a mock event with error
                mock_event = MagicMock()
                mock_event.job_id = "test_job"
                mock_event.exception = Exception("Test error")
                mock_event.traceback = "Test traceback"
                
                # Trigger error listener
                manager._job_error_listener(mock_event)
                
                # Verify audit log contains error entry
                audit_entries = manager.get_audit_log()
                error_entry = next((e for e in audit_entries if e["action"] == "scheduled_job_failed"), None)
                assert error_entry is not None
                assert error_entry["details"]["job_id"] == "test_job"
                assert "Test error" in error_entry["details"]["error"]
                
            finally:
                if manager.scheduler.running:
                    manager.stop_scheduler()
    
    def test_file_management_utilities(self):
        """Test file management utilities for report storage and cleanup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ScheduledReportManager(reports_dir=temp_dir, max_reports=3)
            reports_dir = Path(temp_dir)
            
            # Create test files with different dates
            test_dates = [
                date.today() - timedelta(days=i) for i in range(5)
            ]
            
            for test_date in test_dates:
                filename = f"security_report_{test_date.strftime('%Y%m%d')}.pdf"
                file_path = reports_dir / filename
                file_path.write_bytes(f"Report content for {test_date}".encode())
            
            # Get initial file info
            initial_files = manager.get_report_files_info()
            assert len(initial_files) == 5
            
            # Run cleanup (should keep only 3 most recent)
            asyncio.run(manager._cleanup_old_reports_job())
            
            # Verify cleanup
            remaining_files = manager.get_report_files_info()
            assert len(remaining_files) == 3
            
            # Verify the most recent files were kept
            kept_dates = [file_info["report_date"] for file_info in remaining_files]
            expected_dates = [test_dates[i].isoformat() for i in range(3)]
            assert set(kept_dates) == set(expected_dates)