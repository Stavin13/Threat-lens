"""
Database connection utilities and configuration for ThreatLens.
"""
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from typing import Generator, Optional
from .models import Base

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/threatlens.db")
SQLITE_WAL_MODE = True  # Enable WAL mode for better concurrency

# Global engine and session factory
engine = None
SessionLocal = None


def create_database_engine():
    """Create and configure the SQLAlchemy engine."""
    global engine
    
    if engine is None:
        # Create engine with SQLite-specific configurations
        engine = create_engine(
            DATABASE_URL,
            echo=False,  # Set to True for SQL query logging in development
            pool_pre_ping=True,  # Verify connections before use
            connect_args={
                "check_same_thread": False,  # Allow multiple threads for SQLite
                "timeout": 30  # Connection timeout in seconds
            }
        )
        
        # Enable WAL mode for SQLite if configured
        if SQLITE_WAL_MODE and DATABASE_URL.startswith("sqlite"):
            with engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.execute(text("PRAGMA synchronous=NORMAL"))
                conn.execute(text("PRAGMA cache_size=1000"))
                conn.execute(text("PRAGMA temp_store=memory"))
                conn.commit()
                logger.info("SQLite WAL mode enabled with performance optimizations")
    
    return engine


def create_session_factory():
    """Create the session factory."""
    global SessionLocal
    
    if SessionLocal is None:
        engine = create_database_engine()
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    return SessionLocal


def get_database_session() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    Used with FastAPI dependency injection.
    """
    session_factory = create_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Use this for manual session management outside of FastAPI.
    """
    session_factory = create_session_factory()
    db = session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_database():
    """
    Initialize the database by creating all tables and indexes.
    This should be called during application startup.
    """
    try:
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Create engine and tables
        engine = create_database_engine()
        Base.metadata.create_all(bind=engine)
        
        # Run database migrations
        from app.migrations.runner import MigrationRunner
        migration_runner = MigrationRunner(DATABASE_URL)
        migration_success = migration_runner.run_migrations()
        
        if not migration_success:
            logger.warning("Some database migrations failed, but continuing with initialization")
        else:
            logger.info("Database migrations completed successfully")
        
        # Create indexes for better query performance
        with engine.connect() as conn:
            # Existing indexes
            # Index on events timestamp for time-based queries
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_events_timestamp 
                ON events(timestamp)
            """))
            
            # Index on events category for filtering
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_events_category 
                ON events(category)
            """))
            
            # Index on ai_analysis severity_score for filtering
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_ai_analysis_severity 
                ON ai_analysis(severity_score)
            """))
            
            # Index on reports report_date for date-based queries
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_reports_date 
                ON reports(report_date)
            """))
            
            # Composite index for event queries with timestamp and category
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_events_timestamp_category 
                ON events(timestamp, category)
            """))
            
            # New indexes for real-time monitoring
            # Index on log_sources for efficient lookups
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_log_sources_name 
                ON log_sources(source_name)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_log_sources_path 
                ON log_sources(path)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_log_sources_enabled 
                ON log_sources(enabled)
            """))
            
            # Index on processing_metrics for time-based queries
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_processing_metrics_timestamp 
                ON processing_metrics(timestamp)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_processing_metrics_source 
                ON processing_metrics(source_name)
            """))
            
            # Index on notification_history for efficient queries
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_notification_history_event 
                ON notification_history(event_id)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_notification_history_status 
                ON notification_history(status)
            """))
            
            # Index on events for real-time processing fields
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_events_realtime_processed 
                ON events(realtime_processed)
            """))
            
            conn.commit()
        
        logger.info("Database initialized successfully with all tables and indexes")
        return True
        
    except SQLAlchemyError as e:
        logger.error(f"Database initialization failed: {e}")
        return False


def check_database_health() -> dict:
    """
    Perform database health check.
    Returns status information about database connectivity and basic operations.
    """
    health_status = {
        "status": "unhealthy",
        "database_url": DATABASE_URL.split("://")[0] + "://***",  # Hide sensitive info
        "connection": False,
        "tables_exist": False,
        "error": None
    }
    
    try:
        engine = create_database_engine()
        
        # Test basic connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            health_status["connection"] = True
        
        # Check if tables exist
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('raw_logs', 'events', 'ai_analysis', 'reports', 
                'monitoring_config', 'log_sources', 'processing_metrics', 'notification_history')
            """))
            tables = [row[0] for row in result]
            
            expected_tables = {'raw_logs', 'events', 'ai_analysis', 'reports', 
                             'monitoring_config', 'log_sources', 'processing_metrics', 'notification_history'}
            health_status["tables_exist"] = expected_tables.issubset(set(tables))
            health_status["existing_tables"] = tables
        
        # If we get here, database is healthy
        health_status["status"] = "healthy"
        
    except Exception as e:
        health_status["error"] = str(e)
        logger.error(f"Database health check failed: {e}")
    
    return health_status


def get_database_stats() -> dict:
    """
    Get basic database statistics for monitoring.
    """
    stats = {
        "raw_logs_count": 0,
        "events_count": 0,
        "ai_analysis_count": 0,
        "reports_count": 0,
        "log_sources_count": 0,
        "monitoring_configs_count": 0,
        "processing_metrics_count": 0,
        "notification_history_count": 0,
        "error": None
    }
    
    try:
        with get_db_session() as db:
            # Count records in each table
            stats["raw_logs_count"] = db.execute(text("SELECT COUNT(*) FROM raw_logs")).scalar()
            stats["events_count"] = db.execute(text("SELECT COUNT(*) FROM events")).scalar()
            stats["ai_analysis_count"] = db.execute(text("SELECT COUNT(*) FROM ai_analysis")).scalar()
            stats["reports_count"] = db.execute(text("SELECT COUNT(*) FROM reports")).scalar()
            
            # New real-time monitoring tables
            try:
                stats["log_sources_count"] = db.execute(text("SELECT COUNT(*) FROM log_sources")).scalar()
            except:
                stats["log_sources_count"] = 0  # Table might not exist yet
            
            try:
                stats["monitoring_configs_count"] = db.execute(text("SELECT COUNT(*) FROM monitoring_config")).scalar()
            except:
                stats["monitoring_configs_count"] = 0
            
            try:
                stats["processing_metrics_count"] = db.execute(text("SELECT COUNT(*) FROM processing_metrics")).scalar()
            except:
                stats["processing_metrics_count"] = 0
            
            try:
                stats["notification_history_count"] = db.execute(text("SELECT COUNT(*) FROM notification_history")).scalar()
            except:
                stats["notification_history_count"] = 0
            
    except Exception as e:
        stats["error"] = str(e)
        logger.error(f"Failed to get database stats: {e}")
    
    return stats


def close_database_connections():
    """
    Close all database connections.
    Should be called during application shutdown.
    """
    global engine
    if engine:
        engine.dispose()
        logger.info("Database connections closed")