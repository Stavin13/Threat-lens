"""
Log ingestion module for ThreatLens.
Handles file uploads, text input, and raw log storage.
"""
import os
import uuid
import logging
from datetime import datetime
from typing import Optional, Union, BinaryIO
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .models import RawLog
from .schemas import IngestionRequest, IngestionResponse
from .database import get_db_session
from .validation import (
    validate_file_upload, 
    sanitize_log_content, 
    sanitize_filename, 
    sanitize_source_identifier,
    validate_request_size
)

logger = logging.getLogger(__name__)

# Configuration constants
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB max file size
MAX_TEXT_SIZE = 10 * 1024 * 1024  # 10MB max text size
ALLOWED_FILE_EXTENSIONS = {'.log', '.txt', '.out'}
ALLOWED_MIME_TYPES = {
    'text/plain',
    'text/x-log',
    'application/octet-stream',  # Some log files may have this MIME type
    'text/x-generic'
}


class IngestionError(Exception):
    """Custom exception for ingestion-related errors."""
    pass


def validate_file_upload_basic(file: UploadFile) -> None:
    """
    Basic validation of uploaded file before reading content.
    
    Args:
        file: FastAPI UploadFile object
        
    Raises:
        IngestionError: If file validation fails
    """
    if not file.filename:
        raise IngestionError("File must have a filename")
    
    # Sanitize filename
    sanitized_filename = sanitize_filename(file.filename)
    
    # Check file extension
    file_ext = os.path.splitext(sanitized_filename.lower())[1]
    if file_ext not in ALLOWED_FILE_EXTENSIONS:
        raise IngestionError(
            f"File extension '{file_ext}' not allowed. "
            f"Allowed extensions: {', '.join(ALLOWED_FILE_EXTENSIONS)}"
        )
    
    # Check MIME type if available
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        logger.warning(f"Unexpected MIME type: {file.content_type} for file: {sanitized_filename}")
    
    logger.info(f"Basic file validation passed for: {sanitized_filename}")


def validate_text_input(content: str) -> str:
    """
    Validate and sanitize text input.
    
    Args:
        content: Raw text content
        
    Returns:
        Sanitized content
        
    Raises:
        IngestionError: If text validation fails
    """
    if not content or not content.strip():
        raise IngestionError("Content cannot be empty")
    
    # Check size limit
    content_size = len(content.encode('utf-8'))
    if content_size > MAX_TEXT_SIZE:
        raise IngestionError(
            f"Text content too large: {content_size} bytes. "
            f"Maximum allowed: {MAX_TEXT_SIZE} bytes"
        )
    
    # Use comprehensive sanitization from validation module
    sanitized = sanitize_log_content(content)
    
    if len(sanitized.strip()) < 10:
        raise IngestionError("Content too short to be meaningful (minimum 10 characters)")
    
    return sanitized


def store_raw_log(content: str, source: str, db: Session) -> str:
    """
    Store raw log data in the database.
    
    Args:
        content: Raw log content
        source: Source identifier for the logs
        db: Database session
        
    Returns:
        ID of the stored raw log entry
        
    Raises:
        IngestionError: If storage fails
    """
    try:
        # Generate unique ID for the raw log entry
        raw_log_id = str(uuid.uuid4())
        
        # Create raw log entry
        raw_log = RawLog(
            id=raw_log_id,
            content=content,
            source=source,
            ingested_at=datetime.utcnow()
        )
        
        # Store in database
        db.add(raw_log)
        db.commit()
        db.refresh(raw_log)
        
        logger.info(f"Raw log stored successfully with ID: {raw_log_id}")
        return raw_log_id
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error storing raw log: {e}")
        raise IngestionError(f"Failed to store log data: {str(e)}")
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error storing raw log: {e}")
        raise IngestionError(f"Unexpected error during storage: {str(e)}")


async def ingest_log_file(file: UploadFile, source: Optional[str] = None) -> IngestionResponse:
    """
    Ingest log data from an uploaded file.
    
    Args:
        file: FastAPI UploadFile object
        source: Optional source identifier (defaults to filename)
        
    Returns:
        IngestionResponse with ingestion details
        
    Raises:
        IngestionError: If ingestion fails
    """
    try:
        # Basic validation first
        validate_file_upload_basic(file)
        
        # Read file content with size checking
        content_chunks = []
        total_size = 0
        
        while True:
            chunk = await file.read(8192)  # Read in 8KB chunks
            if not chunk:
                break
                
            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE:
                raise IngestionError(
                    f"File too large: {total_size} bytes. "
                    f"Maximum allowed: {MAX_FILE_SIZE} bytes"
                )
            
            content_chunks.append(chunk)
        
        # Combine chunks and validate using comprehensive validation
        content_bytes = b''.join(content_chunks)
        
        # Use comprehensive file validation from validation module
        is_valid, error_msg = validate_file_upload(content_bytes, file.filename)
        if not is_valid:
            raise IngestionError(f"File validation failed: {error_msg}")
        
        # Try to decode as UTF-8, fallback to latin-1 for binary log files
        try:
            content = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                content = content_bytes.decode('latin-1')
                logger.warning(f"File {file.filename} decoded using latin-1 fallback")
            except UnicodeDecodeError:
                raise IngestionError("File encoding not supported. Please use UTF-8 or latin-1 encoded files.")
        
        # Additional sanitization (already done in validate_file_upload, but ensure consistency)
        content = sanitize_log_content(content)
        
        # Use filename as source if not provided, with sanitization
        if not source:
            source = sanitize_filename(file.filename) if file.filename else "uploaded_file"
        else:
            source = sanitize_source_identifier(source)
        
        # Store in database
        with get_db_session() as db:
            raw_log_id = store_raw_log(content, source, db)
        
        # Create response
        response = IngestionResponse(
            raw_log_id=raw_log_id,
            message=f"File '{file.filename}' ingested successfully",
            events_parsed=0,  # Will be updated after parsing
            ingested_at=datetime.utcnow()
        )
        
        logger.info(f"File ingestion completed: {file.filename} -> {raw_log_id}")
        return response
        
    except IngestionError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during file ingestion: {e}")
        raise IngestionError(f"File ingestion failed: {str(e)}")


def ingest_log_text(request: IngestionRequest) -> IngestionResponse:
    """
    Ingest log data from text input.
    
    Args:
        request: IngestionRequest with content and source
        
    Returns:
        IngestionResponse with ingestion details
        
    Raises:
        IngestionError: If ingestion fails
    """
    try:
        # Validate and sanitize content (already done by Pydantic, but double-check)
        content = validate_text_input(request.content)
        
        # Sanitize source identifier
        source = sanitize_source_identifier(request.source)
        
        # Store in database
        with get_db_session() as db:
            raw_log_id = store_raw_log(content, source, db)
        
        # Create response
        response = IngestionResponse(
            raw_log_id=raw_log_id,
            message=f"Text content from '{source}' ingested successfully",
            events_parsed=0,  # Will be updated after parsing
            ingested_at=datetime.utcnow()
        )
        
        logger.info(f"Text ingestion completed: {source} -> {raw_log_id}")
        return response
        
    except IngestionError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during text ingestion: {e}")
        raise IngestionError(f"Text ingestion failed: {str(e)}")


def get_raw_log(raw_log_id: str, db: Session) -> Optional[RawLog]:
    """
    Retrieve a raw log entry by ID.
    
    Args:
        raw_log_id: ID of the raw log entry
        db: Database session
        
    Returns:
        RawLog object if found, None otherwise
    """
    try:
        return db.query(RawLog).filter(RawLog.id == raw_log_id).first()
    except SQLAlchemyError as e:
        logger.error(f"Database error retrieving raw log {raw_log_id}: {e}")
        return None


def delete_raw_log(raw_log_id: str, db: Session) -> bool:
    """
    Delete a raw log entry and all associated events.
    
    Args:
        raw_log_id: ID of the raw log entry to delete
        db: Database session
        
    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        raw_log = db.query(RawLog).filter(RawLog.id == raw_log_id).first()
        if raw_log:
            db.delete(raw_log)
            db.commit()
            logger.info(f"Raw log {raw_log_id} deleted successfully")
            return True
        else:
            logger.warning(f"Raw log {raw_log_id} not found for deletion")
            return False
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error deleting raw log {raw_log_id}: {e}")
        return False


def get_ingestion_stats() -> dict:
    """
    Get statistics about ingested logs.
    
    Returns:
        Dictionary with ingestion statistics
    """
    stats = {
        "total_raw_logs": 0,
        "total_content_size": 0,
        "sources": [],
        "recent_ingestions": [],
        "error": None
    }
    
    try:
        with get_db_session() as db:
            # Get total count
            from sqlalchemy import func, text
            
            result = db.execute(text("""
                SELECT 
                    COUNT(*) as total_logs,
                    SUM(LENGTH(content)) as total_size,
                    COUNT(DISTINCT source) as unique_sources
                FROM raw_logs
            """)).first()
            
            if result:
                stats["total_raw_logs"] = result[0] or 0
                stats["total_content_size"] = result[1] or 0
                stats["unique_sources"] = result[2] or 0
            
            # Get source breakdown
            source_result = db.execute(text("""
                SELECT source, COUNT(*) as count
                FROM raw_logs
                GROUP BY source
                ORDER BY count DESC
                LIMIT 10
            """)).fetchall()
            
            stats["sources"] = [{"source": row[0], "count": row[1]} for row in source_result]
            
            # Get recent ingestions
            recent_result = db.execute(text("""
                SELECT id, source, ingested_at, LENGTH(content) as size
                FROM raw_logs
                ORDER BY ingested_at DESC
                LIMIT 5
            """)).fetchall()
            
            stats["recent_ingestions"] = [
                {
                    "id": row[0],
                    "source": row[1],
                    "ingested_at": row[2],
                    "size": row[3]
                }
                for row in recent_result
            ]
            
    except Exception as e:
        stats["error"] = str(e)
        logger.error(f"Failed to get ingestion stats: {e}")
    
    return stats