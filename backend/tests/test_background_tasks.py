"""
Integration tests for the automated processing pipeline.

Tests the complete workflow from log ingestion to AI analysis,
including error handling and retry logic.
"""
import pytest
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from app.background_tasks import (
    BackgroundTaskManager,
    process_raw_log,
    trigger_log_parsing,
    trigger_ai_analysis,
    get_processing_stats,
    reset_processing_stats,
    ProcessingError
)
from app.models import RawLog, Event, AIAnalysis as AIAnalysisModel
from app.schemas import ParsedEvent, EventCategory, AIAnalysis
from app.database import get_database_session
from app.parser import ParsingError
from app.analyzer import AnalysisError


class TestBackgroundTaskManager:
    """Test the BackgroundTaskManager class."""
    
    def test_init(self):
        """Test manager initialization."""
        manager = BackgroundTaskManager(max_retries=5, retry_delay=2.0)
        assert manager.max_retries == 5
        assert manager.retry_delay == 2.0
        assert manager.stats['total_tasks'] == 0
    
    @pytest.mark.asyncio
    async def test_process_raw_log_success(self, test_db, sample_raw_log):
        """Test successful raw log processing."""
        manager = BackgroundTaskManager(max_retries=1, retry_delay=0.1)
        
        # Mock the processing attempt to succeed
        with patch.object(manager, '_process_raw_log_attempt') as mock_attempt:
            mock_attempt.return_value = {
                'events_parsed': 3,
                'events_analyzed': 3,
                'errors': []
            }
            
            result = await manager.process_raw_log_with_retry(sample_raw_log.id)
            
            assert result['success'] is True
            assert result['raw_log_id'] == sample_raw_log.id
            assert result['attempt'] == 1
            assert result['events_parsed'] == 3
            assert result['events_analyzed'] == 3
            assert 'processing_time' in result
            
            # Check stats
            stats = manager.get_stats()
            assert stats['total_tasks'] == 1
            assert stats['successful_tasks'] == 1
            assert stats['failed_tasks'] == 0
    
    @pytest.mark.asyncio
    async def test_process_raw_log_retry_then_success(self, test_db, sample_raw_log):
        """Test raw log processing with retry logic."""
        manager = BackgroundTaskManager(max_retries=2, retry_delay=0.01)
        
        # Mock the processing attempt to fail once, then succeed
        with patch.object(manager, '_process_raw_log_attempt') as mock_attempt:
            mock_attempt.side_effect = [
                ProcessingError("First attempt failed"),
                {
                    'events_parsed': 2,
                    'events_analyzed': 2,
                    'errors': []
                }
            ]
            
            result = await manager.process_raw_log_with_retry(sample_raw_log.id)
            
            assert result['success'] is True
            assert result['attempt'] == 2
            assert mock_attempt.call_count == 2
            
            # Check stats
            stats = manager.get_stats()
            assert stats['retried_tasks'] == 1
    
    @pytest.mark.asyncio
    async def test_process_raw_log_all_attempts_fail(self, test_db, sample_raw_log):
        """Test raw log processing when all attempts fail."""
        manager = BackgroundTaskManager(max_retries=1, retry_delay=0.01)
        
        # Mock all attempts to fail
        with patch.object(manager, '_process_raw_log_attempt') as mock_attempt:
            mock_attempt.side_effect = ProcessingError("All attempts failed")
            
            result = await manager.process_raw_log_with_retry(sample_raw_log.id)
            
            assert result['success'] is False
            assert result['attempts'] == 2  # max_retries + 1
            assert 'All attempts failed' in result['error']
            
            # Check stats
            stats = manager.get_stats()
            assert stats['failed_tasks'] == 1
    
    @pytest.mark.asyncio
    async def test_process_raw_log_attempt_success(self, db_session, sample_raw_log):
        """Test successful processing attempt."""
        manager = BackgroundTaskManager()
        
        # Mock parsing and analysis
        with patch('app.background_tasks.parse_log_entries') as mock_parse, \
             patch('app.background_tasks.analyze_event') as mock_analyze:
            
            # Setup mock parsed events
            mock_events = [
                ParsedEvent(
                    id=str(uuid.uuid4()),
                    raw_log_id=sample_raw_log.id,
                    timestamp=datetime.now(timezone.utc),
                    source="test_source",
                    message="test message",
                    category=EventCategory.SYSTEM,
                    parsed_at=datetime.now(timezone.utc)
                )
            ]
            mock_parse.return_value = mock_events
            
            # Setup mock analysis
            mock_analysis = AIAnalysis(
                id=str(uuid.uuid4()),
                event_id=mock_events[0].id,
                severity_score=5,
                explanation="Test analysis",
                recommendations=["Test recommendation"],
                analyzed_at=datetime.now(timezone.utc)
            )
            mock_analyze.return_value = mock_analysis
            
            result = await manager._process_raw_log_attempt(sample_raw_log.id, 0)
            
            assert result['events_parsed'] == 1
            assert result['events_analyzed'] == 1
            assert len(result['errors']) == 0
            
            # Verify database entries were created
            with get_database_session() as db:
                events = db.query(Event).filter(Event.raw_log_id == sample_raw_log.id).all()
                assert len(events) == 1
                
                analyses = db.query(AIAnalysisModel).filter(
                    AIAnalysisModel.event_id == mock_events[0].id
                ).all()
                assert len(analyses) == 1
    
    @pytest.mark.asyncio
    async def test_process_raw_log_attempt_parsing_error(self, db_session, sample_raw_log):
        """Test processing attempt with parsing error."""
        manager = BackgroundTaskManager()
        
        with patch('app.background_tasks.parse_log_entries') as mock_parse:
            mock_parse.side_effect = ParsingError("Parsing failed")
            
            with pytest.raises(ProcessingError, match="Failed to parse raw log"):
                await manager._process_raw_log_attempt(sample_raw_log.id, 0)
    
    @pytest.mark.asyncio
    async def test_process_raw_log_attempt_analysis_error(self, db_session, sample_raw_log):
        """Test processing attempt with analysis error (should continue)."""
        manager = BackgroundTaskManager()
        
        with patch('app.background_tasks.parse_log_entries') as mock_parse, \
             patch('app.background_tasks.analyze_event') as mock_analyze:
            
            # Setup mock parsed events
            mock_events = [
                ParsedEvent(
                    id=str(uuid.uuid4()),
                    raw_log_id=sample_raw_log.id,
                    timestamp=datetime.now(timezone.utc),
                    source="test_source",
                    message="test message",
                    category=EventCategory.SYSTEM,
                    parsed_at=datetime.now(timezone.utc)
                )
            ]
            mock_parse.return_value = mock_events
            mock_analyze.side_effect = AnalysisError("Analysis failed")
            
            result = await manager._process_raw_log_attempt(sample_raw_log.id, 0)
            
            assert result['events_parsed'] == 1
            assert result['events_analyzed'] == 0  # Analysis failed
            assert len(result['errors']) == 1
            assert "Failed to analyze event" in result['errors'][0]
    
    @pytest.mark.asyncio
    async def test_process_raw_log_attempt_raw_log_not_found(self, db_session):
        """Test processing attempt when raw log doesn't exist."""
        manager = BackgroundTaskManager()
        
        with pytest.raises(ProcessingError, match="Raw log .* not found"):
            await manager._process_raw_log_attempt("nonexistent_id", 0)
    
    def test_get_stats(self):
        """Test statistics calculation."""
        manager = BackgroundTaskManager()
        
        # Simulate some processing times
        manager.stats['processing_times'] = [1.0, 2.0, 3.0]
        manager.stats['total_tasks'] = 5
        manager.stats['successful_tasks'] = 4
        
        stats = manager.get_stats()
        
        assert stats['avg_processing_time'] == 2.0
        assert stats['min_processing_time'] == 1.0
        assert stats['max_processing_time'] == 3.0
        assert stats['success_rate'] == 0.8
    
    def test_reset_stats(self):
        """Test statistics reset."""
        manager = BackgroundTaskManager()
        
        # Set some stats
        manager.stats['total_tasks'] = 10
        manager.stats['processing_times'] = [1.0, 2.0]
        
        manager.reset_stats()
        
        assert manager.stats['total_tasks'] == 0
        assert manager.stats['processing_times'] == []


class TestProcessingFunctions:
    """Test the processing pipeline functions."""
    
    @pytest.mark.asyncio
    async def test_process_raw_log_function(self, db_session, sample_raw_log):
        """Test the main process_raw_log function."""
        with patch('app.background_tasks.task_manager') as mock_manager:
            mock_manager.process_raw_log_with_retry = AsyncMock(return_value={
                'success': True,
                'events_parsed': 2
            })
            
            result = await process_raw_log(sample_raw_log.id)
            
            assert result['success'] is True
            mock_manager.process_raw_log_with_retry.assert_called_once_with(sample_raw_log.id)
    
    def test_trigger_log_parsing_success(self, db_session, sample_raw_log):
        """Test successful log parsing trigger."""
        with patch('app.background_tasks.parse_log_entries') as mock_parse:
            mock_events = [
                ParsedEvent(
                    id=str(uuid.uuid4()),
                    raw_log_id=sample_raw_log.id,
                    timestamp=datetime.now(timezone.utc),
                    source="test_source",
                    message="test message",
                    category=EventCategory.SYSTEM,
                    parsed_at=datetime.now(timezone.utc)
                )
            ]
            mock_parse.return_value = mock_events
            
            result = trigger_log_parsing(sample_raw_log.id)
            
            assert result is True
            
            # Verify event was stored
            with get_database_session() as db:
                events = db.query(Event).filter(Event.raw_log_id == sample_raw_log.id).all()
                assert len(events) == 1
    
    def test_trigger_log_parsing_not_found(self, db_session):
        """Test log parsing trigger when raw log doesn't exist."""
        result = trigger_log_parsing("nonexistent_id")
        assert result is False
    
    def test_trigger_log_parsing_error(self, db_session, sample_raw_log):
        """Test log parsing trigger with parsing error."""
        with patch('app.background_tasks.parse_log_entries') as mock_parse:
            mock_parse.side_effect = ParsingError("Parsing failed")
            
            result = trigger_log_parsing(sample_raw_log.id)
            assert result is False
    
    def test_trigger_ai_analysis_success(self, db_session, sample_event):
        """Test successful AI analysis trigger."""
        with patch('app.background_tasks.analyze_event') as mock_analyze:
            mock_analysis = AIAnalysis(
                id=str(uuid.uuid4()),
                event_id=sample_event.id,
                severity_score=7,
                explanation="Test analysis",
                recommendations=["Test recommendation"],
                analyzed_at=datetime.now(timezone.utc)
            )
            mock_analyze.return_value = mock_analysis
            
            results = trigger_ai_analysis([sample_event.id])
            
            assert results[sample_event.id] is True
            
            # Verify analysis was stored
            with get_database_session() as db:
                analysis = db.query(AIAnalysisModel).filter(
                    AIAnalysisModel.event_id == sample_event.id
                ).first()
                assert analysis is not None
                assert analysis.severity_score == 7
    
    def test_trigger_ai_analysis_event_not_found(self, db_session):
        """Test AI analysis trigger when event doesn't exist."""
        results = trigger_ai_analysis(["nonexistent_id"])
        assert results["nonexistent_id"] is False
    
    def test_trigger_ai_analysis_error(self, db_session, sample_event):
        """Test AI analysis trigger with analysis error."""
        with patch('app.background_tasks.analyze_event') as mock_analyze:
            mock_analyze.side_effect = AnalysisError("Analysis failed")
            
            results = trigger_ai_analysis([sample_event.id])
            assert results[sample_event.id] is False
    
    def test_trigger_ai_analysis_update_existing(self, db_session, sample_event, sample_ai_analysis):
        """Test AI analysis trigger updating existing analysis."""
        with patch('app.background_tasks.analyze_event') as mock_analyze:
            mock_analysis = AIAnalysis(
                id=str(uuid.uuid4()),
                event_id=sample_event.id,
                severity_score=9,
                explanation="Updated analysis",
                recommendations=["Updated recommendation"],
                analyzed_at=datetime.now(timezone.utc)
            )
            mock_analyze.return_value = mock_analysis
            
            results = trigger_ai_analysis([sample_event.id])
            
            assert results[sample_event.id] is True
            
            # Verify analysis was updated
            with get_database_session() as db:
                analysis = db.query(AIAnalysisModel).filter(
                    AIAnalysisModel.event_id == sample_event.id
                ).first()
                assert analysis.severity_score == 9
                assert analysis.explanation == "Updated analysis"
    
    def test_get_processing_stats(self):
        """Test getting processing statistics."""
        with patch('app.background_tasks.task_manager') as mock_manager:
            mock_manager.get_stats.return_value = {
                'total_tasks': 10,
                'successful_tasks': 8
            }
            
            stats = get_processing_stats()
            
            assert stats['total_tasks'] == 10
            assert stats['successful_tasks'] == 8
    
    def test_reset_processing_stats(self):
        """Test resetting processing statistics."""
        with patch('app.background_tasks.task_manager') as mock_manager:
            reset_processing_stats()
            mock_manager.reset_stats.assert_called_once()


class TestIntegrationWorkflow:
    """Integration tests for the complete processing workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_processing_workflow(self, db_session):
        """Test the complete workflow from raw log to analyzed events."""
        # Create a raw log with realistic content
        raw_log_content = """Jan 15 10:30:45 MacBook-Pro loginwindow[123]: User authentication failed for user 'admin'
Jan 15 10:31:00 MacBook-Pro kernel[0]: System boot completed successfully
Jan 15 10:31:15 MacBook-Pro sshd[456]: Failed login attempt from 192.168.1.100"""
        
        raw_log = RawLog(
            id=str(uuid.uuid4()),
            content=raw_log_content,
            source="test_integration",
            ingested_at=datetime.now(timezone.utc)
        )
        
        with get_database_session() as db:
            db.add(raw_log)
            db.commit()
            db.refresh(raw_log)
        
        # Process the raw log
        manager = BackgroundTaskManager(max_retries=1, retry_delay=0.1)
        result = await manager.process_raw_log_with_retry(raw_log.id)
        
        assert result['success'] is True
        assert result['events_parsed'] > 0
        assert result['events_analyzed'] > 0
        
        # Verify events were created
        with get_database_session() as db:
            events = db.query(Event).filter(Event.raw_log_id == raw_log.id).all()
            assert len(events) == result['events_parsed']
            
            # Verify AI analyses were created
            for event in events:
                analysis = db.query(AIAnalysisModel).filter(
                    AIAnalysisModel.event_id == event.id
                ).first()
                assert analysis is not None
                assert 1 <= analysis.severity_score <= 10
                assert len(analysis.explanation) > 0
    
    @pytest.mark.asyncio
    async def test_processing_with_malformed_logs(self, db_session):
        """Test processing with malformed log entries."""
        # Create a raw log with mixed valid and invalid entries
        raw_log_content = """Jan 15 10:30:45 MacBook-Pro loginwindow[123]: Valid log entry
This is not a valid log entry
Another invalid entry without timestamp
Jan 15 10:31:00 MacBook-Pro kernel[0]: Another valid entry"""
        
        raw_log = RawLog(
            id=str(uuid.uuid4()),
            content=raw_log_content,
            source="test_malformed",
            ingested_at=datetime.now(timezone.utc)
        )
        
        with get_database_session() as db:
            db.add(raw_log)
            db.commit()
            db.refresh(raw_log)
        
        # Process the raw log
        manager = BackgroundTaskManager(max_retries=1, retry_delay=0.1)
        result = await manager.process_raw_log_with_retry(raw_log.id)
        
        # Should succeed even with some malformed entries
        assert result['success'] is True
        assert result['events_parsed'] >= 2  # At least the valid entries
        
        # Verify valid events were processed
        with get_database_session() as db:
            events = db.query(Event).filter(Event.raw_log_id == raw_log.id).all()
            assert len(events) >= 2
    
    @pytest.mark.asyncio
    async def test_processing_performance_with_large_log(self, db_session):
        """Test processing performance with a large log file."""
        # Create a large log with many entries
        log_entries = []
        for i in range(100):
            log_entries.append(
                f"Jan 15 10:{30 + i % 30}:{i % 60:02d} MacBook-Pro test[{i}]: Test message {i}"
            )
        
        raw_log_content = "\n".join(log_entries)
        
        raw_log = RawLog(
            id=str(uuid.uuid4()),
            content=raw_log_content,
            source="test_large",
            ingested_at=datetime.now(timezone.utc)
        )
        
        with get_database_session() as db:
            db.add(raw_log)
            db.commit()
            db.refresh(raw_log)
        
        # Process the raw log and measure time
        import time
        start_time = time.time()
        
        manager = BackgroundTaskManager(max_retries=1, retry_delay=0.1)
        result = await manager.process_raw_log_with_retry(raw_log.id)
        
        processing_time = time.time() - start_time
        
        assert result['success'] is True
        assert result['events_parsed'] == 100
        assert processing_time < 30  # Should complete within 30 seconds
        
        # Verify all events were processed
        with get_database_session() as db:
            events = db.query(Event).filter(Event.raw_log_id == raw_log.id).all()
            assert len(events) == 100
            
            # Verify all have AI analysis
            analyses = db.query(AIAnalysisModel).join(Event).filter(
                Event.raw_log_id == raw_log.id
            ).all()
            assert len(analyses) == 100


# Test database setup (copied from test_api.py)
@pytest.fixture(scope="function")
def test_db():
    """Create a test database for each test."""
    import tempfile
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    # Create test engine
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    yield TestingSessionLocal
    
    # Cleanup
    os.unlink(db_path)


# Fixtures for testing
@pytest.fixture
def sample_raw_log(test_db):
    """Create a sample raw log for testing."""
    raw_log = RawLog(
        id=str(uuid.uuid4()),
        content="Jan 15 10:30:45 MacBook-Pro test[123]: Test log message",
        source="test_source",
        ingested_at=datetime.now(timezone.utc)
    )
    
    db = test_db()
    db.add(raw_log)
    db.commit()
    db.refresh(raw_log)
    db.close()
    
    return raw_log


@pytest.fixture
def sample_event(test_db, sample_raw_log):
    """Create a sample event for testing."""
    event = Event(
        id=str(uuid.uuid4()),
        raw_log_id=sample_raw_log.id,
        timestamp=datetime.now(timezone.utc),
        source="test_source",
        message="Test event message",
        category=EventCategory.SYSTEM.value,
        parsed_at=datetime.now(timezone.utc)
    )
    
    db = test_db()
    db.add(event)
    db.commit()
    db.refresh(event)
    db.close()
    
    return event


@pytest.fixture
def sample_ai_analysis(test_db, sample_event):
    """Create a sample AI analysis for testing."""
    analysis = AIAnalysisModel(
        id=str(uuid.uuid4()),
        event_id=sample_event.id,
        severity_score=5,
        explanation="Test analysis",
        recommendations='["Test recommendation"]',
        analyzed_at=datetime.now(timezone.utc)
    )
    
    db = test_db()
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    db.close()
    
    return analysis