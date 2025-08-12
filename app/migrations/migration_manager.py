"""
Database migration manager for ThreatLens.
Handles schema migrations with version tracking and rollback capabilities.
"""
import os
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, DateTime
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import func
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database schema migrations with version tracking."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.metadata = MetaData()
        
    def _ensure_migration_table(self):
        """Ensure the migration tracking table exists."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version VARCHAR(50) UNIQUE NOT NULL,
                        description TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        rollback_sql TEXT,
                        checksum VARCHAR(64)
                    )
                """))
                conn.commit()
                logger.info("Migration tracking table ensured")
        except SQLAlchemyError as e:
            logger.error(f"Failed to create migration table: {e}")
            raise
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions."""
        self._ensure_migration_table()
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT version FROM schema_migrations 
                    ORDER BY applied_at
                """))
                return [row[0] for row in result]
        except SQLAlchemyError as e:
            logger.error(f"Failed to get applied migrations: {e}")
            return []
    
    def is_migration_applied(self, version: str) -> bool:
        """Check if a specific migration version has been applied."""
        applied = self.get_applied_migrations()
        return version in applied
    
    def apply_migration(self, version: str, description: str, 
                       forward_sql: str, rollback_sql: str = None) -> bool:
        """Apply a migration with the given SQL."""
        if self.is_migration_applied(version):
            logger.info(f"Migration {version} already applied, skipping")
            return True
        
        try:
            with self.engine.connect() as conn:
                # Start transaction
                trans = conn.begin()
                
                try:
                    # Execute migration SQL
                    for statement in forward_sql.split(';'):
                        statement = statement.strip()
                        if statement:
                            conn.execute(text(statement))
                    
                    # Record migration
                    conn.execute(text("""
                        INSERT INTO schema_migrations (version, description, rollback_sql)
                        VALUES (:version, :description, :rollback_sql)
                    """), {
                        "version": version,
                        "description": description,
                        "rollback_sql": rollback_sql
                    })
                    
                    trans.commit()
                    logger.info(f"Migration {version} applied successfully: {description}")
                    return True
                    
                except Exception as e:
                    trans.rollback()
                    logger.error(f"Migration {version} failed: {e}")
                    raise
                    
        except SQLAlchemyError as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            return False
    
    def rollback_migration(self, version: str) -> bool:
        """Rollback a specific migration."""
        if not self.is_migration_applied(version):
            logger.info(f"Migration {version} not applied, nothing to rollback")
            return True
        
        try:
            # Get rollback SQL first
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT rollback_sql FROM schema_migrations 
                    WHERE version = :version
                """), {"version": version})
                
                row = result.fetchone()
                if not row or not row[0]:
                    logger.error(f"No rollback SQL found for migration {version}")
                    return False
                
                rollback_sql = row[0]
            
            # Execute rollback in a new connection with transaction
            with self.engine.connect() as conn:
                trans = conn.begin()
                
                try:
                    # Execute rollback SQL
                    for statement in rollback_sql.split(';'):
                        statement = statement.strip()
                        if statement:
                            conn.execute(text(statement))
                    
                    # Remove migration record
                    conn.execute(text("""
                        DELETE FROM schema_migrations WHERE version = :version
                    """), {"version": version})
                    
                    trans.commit()
                    logger.info(f"Migration {version} rolled back successfully")
                    return True
                    
                except Exception as e:
                    trans.rollback()
                    logger.error(f"Rollback of migration {version} failed: {e}")
                    raise
                    
        except SQLAlchemyError as e:
            logger.error(f"Failed to rollback migration {version}: {e}")
            return False
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status."""
        try:
            applied = self.get_applied_migrations()
            
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT version, description, applied_at 
                    FROM schema_migrations 
                    ORDER BY applied_at DESC
                """))
                
                migrations = []
                for row in result:
                    migrations.append({
                        "version": row[0],
                        "description": row[1],
                        "applied_at": row[2]
                    })
            
            return {
                "total_applied": len(applied),
                "applied_versions": applied,
                "migrations": migrations
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to get migration status: {e}")
            return {"error": str(e)}
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name = :table_name
                """), {"table_name": table_name})
                return result.fetchone() is not None
        except SQLAlchemyError:
            return False
    
    def column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"PRAGMA table_info({table_name})"))
                columns = [row[1] for row in result]  # Column name is at index 1
                return column_name in columns
        except SQLAlchemyError:
            return False