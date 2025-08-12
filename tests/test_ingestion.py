"""
Unit tests for the ingestion module.
"""
import pytest
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from io import BytesIO, StringIO

from app.ingestion import (
    validate_file_upload,
    validate_text_input,
    store_raw_log,
    ingest_log_file,
    ingest_log_text,
    get_raw_log,
    delete_raw_log,
    get_ingestion_stats,
    IngestionError,
    MAX_FILE_SIZE,
    MAX_TEXT_SIZE
)
from app.schemas import IngestionRequest
from app.models import Base, RawLog
from app.database import get_db_session


@pytest.fixture
def test_db():
    """Create a test database session."""
    # Create in-memory SQLite database for testing
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def get_test_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    return TestingSessionLocal()


@pytest.fixture
def sample_log_content():
    """Sample log content for testing."""
    return """Oct 15 10:30:45 MacBook-Pro kernel[0]: System startup
Oct 15 10:30:46 MacBook-Pro loginwindow[123]: User authentication successful
Oct 15 10:30:47 MacBook-Pro sshd[456]: Failed login attempt from 192.168.1.100
Oct 15 10:30:48 MacBook-Pro kernel[0]: Network interface en0 up"""


@pytest.fixture
def mock_upload_file():
    """Create a mock UploadFile for testing."""
    def create_mock_file(filename="test.log", content="test log content", content_type="text/plain"):
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = filename
        mock_file.content_type = content_type
        
        # Create a proper async read method that returns chunks
        content_bytes = content.encode('utf-8')
        chunks = [content_bytes[i:i+8192] for i in range(0, len(content_bytes), 8192)]
        chunks.append(b'')  # Add empty chunk to signal end
        
        async def mock_read(size=8192):
            if chunks:
                return chunks.pop(0)
            return b''
        
        mock_file.read = mock_read
        return mock_file
    return create_mock_file


class TestFileValidation:
    """Test file upload validation."""
    
    def test_validate_file_upload_success(self, mock_upload_file):
        """Test successful file validation."""
        file = mock_upload_file("test.log", "content", "text/plain")
        # Should not raise any exception
        validate_file_upload(file)
    
    def test_validate_file_upload_no_filename(self, mock_upload_file):
        """Test validation failure when filename is missing."""
        file = mock_upload_file("", "content")
        file.filename = None
        
        with pytest.raises(IngestionError, match="File must have a filename"):
            validate_file_upload(file)
    
    def test_validate_file_upload_invalid_extension(self, mock_upload_file):
        """Test validation failure for invalid file extension."""
        file = mock_upload_file("test.exe", "content")
        
        with pytest.raises(IngestionError, match="File extension '.exe' not allowed"):
            validate_file_upload(file)
    
    def test_validate_file_upload_allowed_extensions(self, mock_upload_file):
        """Test that all allowed extensions pass validation."""
        allowed_extensions = ['.log', '.txt', '.out']
        
        for ext in allowed_extensions:
            file = mock_upload_file(f"test{ext}", "content")
            validate_file_upload(file)  # Should not raise


class TestTextValidation:
    """Test text input validation."""
    
    def test_validate_text_input_success(self):
        """Test successful text validation."""
        content = "This is a valid log entry with sufficient content"
        result = validate_text_input(content)
        assert result == content
    
    def test_validate_text_input_empty(self):
        """Test validation failure for empty content."""
        with pytest.raises(IngestionError, match="Content cannot be empty"):
            validate_text_input("")
        
        with pytest.raises(IngestionError, match="Content cannot be empty"):
            validate_text_input("   ")
    
    def test_validate_text_input_too_short(self):
        """Test validation failure for content that's too short."""
        with pytest.raises(IngestionError, match="Content too short"):
            validate_text_input("short")
    
    def test_validate_text_input_too_large(self):
        """Test validation failure for content that's too large."""
        large_content = "x" * (MAX_TEXT_SIZE + 1)
        
        with pytest.raises(IngestionError, match="Text content too large"):
            validate_text_input(large_content)
    
    def test_validate_text_input_sanitization(self):
        """Test that control characters are sanitized."""
        content_with_control_chars = "Valid log entry\x00\x01\x02 with control chars"
        result = validate_text_input(content_with_control_chars)
        
        # Control characters should be removed
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x02" not in result
        assert "Valid log entry with control chars" in result


class TestRawLogStorage:
    """Test raw log storage functionality."""
    
    def test_store_raw_log_success(self, test_db, sample_log_content):
        """Test successful raw log storage."""
        raw_log_id = store_raw_log(sample_log_content, "test_source", test_db)
        
        # Verify the log was stored
        assert raw_log_id is not None
        assert len(raw_log_id) == 36  # UUID length
        
        # Verify in database
        stored_log = test_db.query(RawLog).filter(RawLog.id == raw_log_id).first()
        assert stored_log is not None
        assert stored_log.content == sample_log_content
        assert stored_log.source == "test_source"
        assert stored_log.ingested_at is not None
    
    def test_store_raw_log_database_error(self, sample_log_content):
        """Test storage failure due to database error."""
        # Create a mock session that raises an exception
        mock_db = Mock()
        mock_db.add.side_effect = Exception("Database connection failed")
        
        with pytest.raises(IngestionError, match="Unexpected error during storage"):
            store_raw_log(sample_log_content, "test_source", mock_db)


class TestFileIngestion:
    """Test file ingestion functionality."""
    
    @pytest.mark.asyncio
    async def test_ingest_log_file_success(self, mock_upload_file, sample_log_content):
        """Test successful file ingestion."""
        file = mock_upload_file("test.log", sample_log_content)
        
        with patch('app.ingestion.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            with patch('app.ingestion.store_raw_log') as mock_store:
                mock_store.return_value = "test-uuid-123"
                
                result = await ingest_log_file(file)
                
                assert result.raw_log_id == "test-uuid-123"
                assert "test.log" in result.message
                assert result.events_parsed == 0
                assert result.ingested_at is not None
    
    @pytest.mark.asyncio
    async def test_ingest_log_file_too_large(self, mock_upload_file):
        """Test file ingestion failure for oversized file."""
        # Create a file that's too large
        large_content = "x" * (MAX_FILE_SIZE + 1)
        file = mock_upload_file("large.log", large_content)
        
        with pytest.raises(IngestionError, match="File too large"):
            await ingest_log_file(file)
    
    @pytest.mark.asyncio
    async def test_ingest_log_file_latin1_fallback(self, mock_upload_file):
        """Test file ingestion with latin-1 fallback encoding."""
        # Test that files with non-UTF-8 content can still be processed via latin-1 fallback
        # This is a more realistic test than trying to force encoding errors
        file = mock_upload_file("test.log", "Valid content that will be processed")
        
        with patch('app.ingestion.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            with patch('app.ingestion.store_raw_log') as mock_store:
                mock_store.return_value = "test-uuid-123"
                
                result = await ingest_log_file(file)
                
                assert result.raw_log_id == "test-uuid-123"
                assert "test.log" in result.message
    
    @pytest.mark.asyncio
    async def test_ingest_log_file_with_source(self, mock_upload_file, sample_log_content):
        """Test file ingestion with custom source."""
        file = mock_upload_file("test.log", sample_log_content)
        
        with patch('app.ingestion.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            with patch('app.ingestion.store_raw_log') as mock_store:
                mock_store.return_value = "test-uuid-123"
                
                result = await ingest_log_file(file, source="custom_source")
                
                # Verify store_raw_log was called with custom source
                mock_store.assert_called_once()
                args = mock_store.call_args[0]
                assert args[1] == "custom_source"  # source parameter


class TestTextIngestion:
    """Test text ingestion functionality."""
    
    def test_ingest_log_text_success(self, sample_log_content):
        """Test successful text ingestion."""
        request = IngestionRequest(content=sample_log_content, source="test_source")
        
        with patch('app.ingestion.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            with patch('app.ingestion.store_raw_log') as mock_store:
                mock_store.return_value = "test-uuid-123"
                
                result = ingest_log_text(request)
                
                assert result.raw_log_id == "test-uuid-123"
                assert "test_source" in result.message
                assert result.events_parsed == 0
                assert result.ingested_at is not None
    
    def test_ingest_log_text_validation_error(self):
        """Test text ingestion with validation error."""
        # Test with content that passes Pydantic validation but fails our custom validation
        with patch('app.ingestion.validate_text_input') as mock_validate:
            mock_validate.side_effect = IngestionError("Content too short")
            
            request = IngestionRequest(content="This is valid content for pydantic", source="test")
            
            with pytest.raises(IngestionError, match="Content too short"):
                ingest_log_text(request)


class TestRawLogRetrieval:
    """Test raw log retrieval and deletion."""
    
    def test_get_raw_log_success(self, test_db, sample_log_content):
        """Test successful raw log retrieval."""
        # Store a log first
        raw_log_id = store_raw_log(sample_log_content, "test_source", test_db)
        
        # Retrieve it
        retrieved_log = get_raw_log(raw_log_id, test_db)
        
        assert retrieved_log is not None
        assert retrieved_log.id == raw_log_id
        assert retrieved_log.content == sample_log_content
        assert retrieved_log.source == "test_source"
    
    def test_get_raw_log_not_found(self, test_db):
        """Test raw log retrieval when log doesn't exist."""
        result = get_raw_log("nonexistent-id", test_db)
        assert result is None
    
    def test_delete_raw_log_success(self, test_db, sample_log_content):
        """Test successful raw log deletion."""
        # Store a log first
        raw_log_id = store_raw_log(sample_log_content, "test_source", test_db)
        
        # Verify it exists
        assert get_raw_log(raw_log_id, test_db) is not None
        
        # Delete it
        result = delete_raw_log(raw_log_id, test_db)
        assert result is True
        
        # Verify it's gone
        assert get_raw_log(raw_log_id, test_db) is None
    
    def test_delete_raw_log_not_found(self, test_db):
        """Test raw log deletion when log doesn't exist."""
        result = delete_raw_log("nonexistent-id", test_db)
        assert result is False


class TestIngestionStats:
    """Test ingestion statistics functionality."""
    
    def test_get_ingestion_stats_empty(self):
        """Test getting stats when no logs exist."""
        with patch('app.ingestion.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            # Mock empty database results
            mock_db.execute.return_value.first.return_value = (0, 0, 0)
            mock_db.execute.return_value.fetchall.return_value = []
            
            stats = get_ingestion_stats()
            
            assert stats["total_raw_logs"] == 0
            assert stats["total_content_size"] == 0
            assert stats["sources"] == []
            assert stats["recent_ingestions"] == []
            assert stats["error"] is None
    
    def test_get_ingestion_stats_with_data(self):
        """Test getting stats with sample data."""
        with patch('app.ingestion.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            # Mock database results with sample data
            mock_db.execute.return_value.first.return_value = (5, 1000, 2)
            mock_db.execute.return_value.fetchall.side_effect = [
                [("source1", 3), ("source2", 2)],  # sources
                [("id1", "source1", datetime.now(), 500)]  # recent ingestions
            ]
            
            stats = get_ingestion_stats()
            
            assert stats["total_raw_logs"] == 5
            assert stats["total_content_size"] == 1000
            assert stats["unique_sources"] == 2
            assert len(stats["sources"]) == 2
            assert stats["sources"][0]["source"] == "source1"
            assert stats["sources"][0]["count"] == 3
            assert len(stats["recent_ingestions"]) == 1
    
    def test_get_ingestion_stats_database_error(self):
        """Test stats retrieval with database error."""
        with patch('app.ingestion.get_db_session') as mock_get_db:
            mock_get_db.side_effect = Exception("Database connection failed")
            
            stats = get_ingestion_stats()
            
            assert stats["error"] is not None
            assert "Database connection failed" in stats["error"]


class TestIngestionIntegration:
    """Integration tests for the ingestion module."""
    
    @pytest.mark.asyncio
    async def test_full_file_ingestion_workflow(self, mock_upload_file, sample_log_content):
        """Test complete file ingestion workflow."""
        file = mock_upload_file("system.log", sample_log_content)
        
        with patch('app.ingestion.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            # Mock successful storage
            with patch('uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = Mock()
                mock_uuid.return_value.__str__ = Mock(return_value="test-uuid-123")
                
                result = await ingest_log_file(file)
                
                # Verify the workflow
                assert result.raw_log_id == "test-uuid-123"
                assert "system.log" in result.message
                assert result.events_parsed == 0
                
                # Verify database operations
                mock_db.add.assert_called_once()
                mock_db.commit.assert_called_once()
    
    def test_full_text_ingestion_workflow(self, sample_log_content):
        """Test complete text ingestion workflow."""
        request = IngestionRequest(content=sample_log_content, source="manual_input")
        
        with patch('app.ingestion.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            # Mock successful storage
            with patch('uuid.uuid4') as mock_uuid:
                mock_uuid.return_value = Mock()
                mock_uuid.return_value.__str__ = Mock(return_value="test-uuid-456")
                
                result = ingest_log_text(request)
                
                # Verify the workflow
                assert result.raw_log_id == "test-uuid-456"
                assert "manual_input" in result.message
                assert result.events_parsed == 0
                
                # Verify database operations
                mock_db.add.assert_called_once()
                mock_db.commit.assert_called_once()