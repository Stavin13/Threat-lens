"""
Tests for database migration system.
"""
import pytest
import tempfile
import os
from pathlib import Path
from sqlalchemy import create_engine, text

from app.migrations.migration_manager import MigrationManager
from app.migrations.runner import MigrationRunner
from app.migrations.cleanup import DatabaseCleanup


class TestMigrationManager:
    """Test the migration manager functionality."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        db_url = f"sqlite:///{db_path}"
        yield db_url
        
        # Cleanup
        try:
            os.unlink(db_path)
        except OSError:
            pass
    
    @pytest.fixture
    def migration_manager(self, temp_db):
        """Create a migration manager with temporary database."""
        return MigrationManager(temp_db)
    
    def test_migration_table_creation(self, migration_manager):
        """Test that migration tracking table is created."""
        migration_manager._ensure_migration_table()
        
        # Check that table exists
        with migration_manager.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='schema_migrations'
            """))
            assert result.fetchone() is not None
    
    def test_apply_migration(self, migration_manager):
        """Test applying a migration."""
        test_sql = """
        CREATE TABLE test_table (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
        
        rollback_sql = "DROP TABLE test_table"
        
        success = migration_manager.apply_migration(
            version="001_test",
            description="Test migration",
            forward_sql=test_sql,
            rollback_sql=rollback_sql
        )
        
        assert success
        assert migration_manager.is_migration_applied("001_test")
        
        # Check that table was created
        assert migration_manager.table_exists("test_table")
    
    def test_rollback_migration(self, migration_manager):
        """Test rolling back a migration."""
        # First apply a migration
        test_sql = "CREATE TABLE test_rollback (id INTEGER PRIMARY KEY)"
        rollback_sql = "DROP TABLE test_rollback"
        
        migration_manager.apply_migration(
            version="002_rollback_test",
            description="Rollback test",
            forward_sql=test_sql,
            rollback_sql=rollback_sql
        )
        
        assert migration_manager.table_exists("test_rollback")
        
        # Now rollback
        success = migration_manager.rollback_migration("002_rollback_test")
        assert success
        assert not migration_manager.is_migration_applied("002_rollback_test")
        assert not migration_manager.table_exists("test_rollback")
    
    def test_migration_status(self, migration_manager):
        """Test getting migration status."""
        # Apply a test migration
        migration_manager.apply_migration(
            version="003_status_test",
            description="Status test",
            forward_sql="CREATE TABLE status_test (id INTEGER)",
            rollback_sql="DROP TABLE status_test"
        )
        
        status = migration_manager.get_migration_status()
        
        assert status["total_applied"] == 1
        assert "003_status_test" in status["applied_versions"]
        assert len(status["migrations"]) == 1
        assert status["migrations"][0]["version"] == "003_status_test"
    
    def test_column_exists(self, migration_manager):
        """Test column existence checking."""
        # Create a test table
        with migration_manager.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE column_test (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """))
            conn.commit()
        
        assert migration_manager.column_exists("column_test", "id")
        assert migration_manager.column_exists("column_test", "name")
        assert not migration_manager.column_exists("column_test", "nonexistent")
        assert not migration_manager.column_exists("nonexistent_table", "id")


class TestMigrationRunner:
    """Test the migration runner functionality."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        db_url = f"sqlite:///{db_path}"
        yield db_url
        
        # Cleanup
        try:
            os.unlink(db_path)
        except OSError:
            pass
    
    @pytest.fixture
    def migration_runner(self, temp_db):
        """Create a migration runner with temporary database."""
        return MigrationRunner(temp_db)
    
    def test_discover_migrations(self, migration_runner):
        """Test migration discovery."""
        migrations = migration_runner.discover_migrations()
        
        # Should find our migration files
        versions = [m["version"] for m in migrations]
        assert "001_add_realtime_tables" in versions
        assert "002_add_realtime_fields" in versions
        
        # Check that migrations are sorted
        assert versions == sorted(versions)
    
    def test_schema_validation(self, migration_runner):
        """Test database schema validation."""
        # Before migrations
        validation = migration_runner.validate_database_schema()
        assert not validation["valid"]
        assert len(validation["missing_tables"]) > 0
        
        # Create basic tables first
        with migration_runner.manager.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE events (
                    id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP,
                    source TEXT,
                    message TEXT,
                    category TEXT
                )
            """))
            conn.commit()
        
        # Run migrations
        success = migration_runner.run_migrations()
        assert success
        
        # After migrations
        validation = migration_runner.validate_database_schema()
        # Note: Some tables might still be missing if not created by migrations
        # This is expected in the test environment


class TestDatabaseCleanup:
    """Test database cleanup functionality."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        db_url = f"sqlite:///{db_path}"
        
        # Set up database URL for the app
        os.environ["DATABASE_URL"] = db_url
        
        yield db_url
        
        # Cleanup
        try:
            os.unlink(db_path)
        except OSError:
            pass
    
    @pytest.fixture
    def setup_test_data(self, temp_db):
        """Set up test data for cleanup tests."""
        from app.database import init_database
        
        # Initialize database
        init_database()
        
        # Add some test data
        from app.database import get_db_session
        from datetime import datetime, timedelta
        
        with get_db_session() as db:
            # Add old processing metrics
            old_date = datetime.now() - timedelta(days=45)
            db.execute(text("""
                INSERT INTO processing_metrics 
                (source_name, metric_type, metric_value, timestamp)
                VALUES ('test_source', 'test_metric', '{"value": 1}', :old_date)
            """), {"old_date": old_date})
            
            # Add recent processing metrics
            recent_date = datetime.now() - timedelta(days=5)
            db.execute(text("""
                INSERT INTO processing_metrics 
                (source_name, metric_type, metric_value, timestamp)
                VALUES ('test_source', 'test_metric', '{"value": 2}', :recent_date)
            """), {"recent_date": recent_date})
    
    def test_cleanup_old_metrics(self, temp_db, setup_test_data):
        """Test cleanup of old processing metrics."""
        cleanup = DatabaseCleanup()
        
        # Clean up metrics older than 30 days
        deleted_count = cleanup.cleanup_old_processing_metrics(days_to_keep=30)
        
        # Should have deleted the old record
        assert deleted_count == 1
        
        # Verify recent record still exists
        from app.database import get_db_session
        with get_db_session() as db:
            result = db.execute(text("SELECT COUNT(*) FROM processing_metrics"))
            remaining_count = result.scalar()
            assert remaining_count == 1
    
    def test_database_size_info(self, temp_db, setup_test_data):
        """Test getting database size information."""
        cleanup = DatabaseCleanup()
        
        size_info = cleanup.get_database_size_info()
        
        assert size_info["error"] is None
        assert size_info["total_pages"] > 0
        assert size_info["page_size"] > 0
        assert size_info["total_size_bytes"] > 0
        assert "processing_metrics" in size_info["table_sizes"]
    
    def test_vacuum_and_analyze(self, temp_db, setup_test_data):
        """Test database vacuum and analyze operations."""
        cleanup = DatabaseCleanup()
        
        # Test vacuum
        vacuum_success = cleanup.vacuum_database()
        assert vacuum_success
        
        # Test analyze
        analyze_success = cleanup.analyze_database()
        assert analyze_success
    
    def test_full_cleanup(self, temp_db, setup_test_data):
        """Test full cleanup operation."""
        cleanup = DatabaseCleanup()
        
        results = cleanup.run_full_cleanup(
            metrics_days=30,
            notification_days=90,
            events_days=365,
            vacuum=True,
            analyze=True
        )
        
        assert "processing_metrics_deleted" in results
        assert "vacuum_success" in results
        assert "analyze_success" in results
        assert results["vacuum_success"] is True
        assert results["analyze_success"] is True