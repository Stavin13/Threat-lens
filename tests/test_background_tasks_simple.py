"""
Simplified integration tests for the automated processing pipeline.

Tests the core functionality of the background task system.
"""
import pytest
import asyncio
import uuid
import tempfile
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.background_tasks import (
    BackgroundTaskManager,
    process_raw_log,
    get_processing_stats,
    reset_processing_stats,
    ProcessingError
)
from app.models import Base, RawLog, Event, AIAnalysis as AIAnalysisModel
from app.schemas import ParsedEvent, EventCategory, AIAnalysis


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
    
    yield TestingSessionLocal
    
    # Cleanup
    os.unlink(db_path)


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
    async def test_process_raw_log_function(self, test_db, sample_raw_log):
        """Test the main process_raw_log function."""
        with patch('app.background_tasks.task_manager') as mock_manager:
            mock_manager.process_raw_log_with_retry = AsyncMock(return_value={
                'success': True,
                'events_parsed': 2
            })
            
            result = await process_raw_log(sample_raw_log.id)
            
            assert result['success'] is True
            mock_manager.process_raw_log_with_retry.assert_called_once_with(sample_raw_log.id)
    
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
    async def test_complete_processing_workflow(self, test_db):
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
        
        db = test_db()
        db.add(raw_log)
        db.commit()
        db.refresh(raw_log)
        db.close()
        
        # Mock the database session to use our test database
        with patch('app.background_tasks.get_database_session') as mock_get_db:
            mock_get_db.return_value.__enter__ = lambda x: test_db()
            mock_get_db.return_value.__exit__ = lambda x, y, z, w: None
            
            # Process the raw log
            manager = BackgroundTaskManager(max_retries=1, retry_delay=0.1)
            result = await manager.process_raw_log_with_retry(raw_log.id)
            
            assert result['success'] is True
            assert result['events_parsed'] > 0
            assert result['events_analyzed'] > 0
            
            # Verify events were created
            db = test_db()
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
            
            db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])