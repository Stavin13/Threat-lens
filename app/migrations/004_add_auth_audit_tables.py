"""
Migration 004: Add authentication and audit tables.

This migration adds tables for user authentication, session management,
and comprehensive audit logging for security and configuration changes.
"""

import logging
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def upgrade(connection):
    """Apply migration - add authentication and audit tables."""
    try:
        logger.info("Starting migration 004: Adding authentication and audit tables")
        
        # Create users table
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                failed_login_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP
            )
        """))
        
        # Create user_sessions table
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                client_ip TEXT,
                user_agent TEXT,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """))
        
        # Create audit_logs table
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                username TEXT,
                user_role TEXT,
                session_id TEXT,
                client_ip TEXT,
                user_agent TEXT,
                correlation_id TEXT,
                resource_type TEXT,
                resource_id TEXT,
                action TEXT,
                description TEXT NOT NULL,
                old_values TEXT,
                new_values TEXT,
                changes TEXT,
                event_metadata TEXT,
                tags TEXT,
                success INTEGER DEFAULT 1,
                error_message TEXT
            )
        """))
        
        # Create indexes for better query performance
        
        # Users table indexes
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_username ON users (username)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_role ON users (role)
        """))
        
        # User sessions table indexes
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions (user_id)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions (session_token)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions (expires_at)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_sessions_active ON user_sessions (is_active, expires_at)
        """))
        
        # Audit logs table indexes
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs (timestamp)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs (event_type)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs (user_id)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_username ON audit_logs (username)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs (resource_type, resource_id)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_severity ON audit_logs (severity)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_success ON audit_logs (success)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_session_id ON audit_logs (session_id)
        """))
        
        # Create default admin user (password: admin123 - should be changed in production)
        import hashlib
        import secrets
        import uuid
        
        admin_id = str(uuid.uuid4())
        # Simple password hashing for demo - use proper bcrypt in production
        password_hash = hashlib.sha256("admin123".encode()).hexdigest()
        
        connection.execute(text("""
            INSERT OR IGNORE INTO users (id, username, email, password_hash, role, enabled)
            VALUES (:id, 'admin', 'admin@threatlens.local', :password_hash, 'admin', 1)
        """), {
            "id": admin_id,
            "password_hash": password_hash
        })
        
        # Create default analyst user (password: analyst123)
        analyst_id = str(uuid.uuid4())
        analyst_password_hash = hashlib.sha256("analyst123".encode()).hexdigest()
        
        connection.execute(text("""
            INSERT OR IGNORE INTO users (id, username, email, password_hash, role, enabled)
            VALUES (:id, 'analyst', 'analyst@threatlens.local', :password_hash, 'analyst', 1)
        """), {
            "id": analyst_id,
            "password_hash": analyst_password_hash
        })
        
        # Create default viewer user (password: viewer123)
        viewer_id = str(uuid.uuid4())
        viewer_password_hash = hashlib.sha256("viewer123".encode()).hexdigest()
        
        connection.execute(text("""
            INSERT OR IGNORE INTO users (id, username, email, password_hash, role, enabled)
            VALUES (:id, 'viewer', 'viewer@threatlens.local', :password_hash, 'viewer', 1)
        """), {
            "id": viewer_id,
            "password_hash": viewer_password_hash
        })
        
        # Log initial audit entry
        audit_id = str(uuid.uuid4())
        connection.execute(text("""
            INSERT INTO audit_logs (
                id, event_type, severity, description, resource_type, action, success
            ) VALUES (
                :id, 'system_started', 'medium', 'Authentication and audit system initialized', 
                'system', 'migration', 1
            )
        """), {"id": audit_id})
        
        connection.commit()
        logger.info("Migration 004 completed successfully")
        
    except SQLAlchemyError as e:
        logger.error(f"Migration 004 failed: {e}")
        connection.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error in migration 004: {e}")
        connection.rollback()
        raise


def downgrade(connection):
    """Rollback migration - remove authentication and audit tables."""
    try:
        logger.info("Rolling back migration 004: Removing authentication and audit tables")
        
        # Drop indexes first
        indexes_to_drop = [
            "idx_users_username",
            "idx_users_email", 
            "idx_users_role",
            "idx_user_sessions_user_id",
            "idx_user_sessions_token",
            "idx_user_sessions_expires_at",
            "idx_user_sessions_active",
            "idx_audit_logs_timestamp",
            "idx_audit_logs_event_type",
            "idx_audit_logs_user_id",
            "idx_audit_logs_username",
            "idx_audit_logs_resource",
            "idx_audit_logs_severity",
            "idx_audit_logs_success",
            "idx_audit_logs_session_id"
        ]
        
        for index_name in indexes_to_drop:
            try:
                connection.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
            except Exception as e:
                logger.warning(f"Could not drop index {index_name}: {e}")
        
        # Drop tables
        connection.execute(text("DROP TABLE IF EXISTS audit_logs"))
        connection.execute(text("DROP TABLE IF EXISTS user_sessions"))
        connection.execute(text("DROP TABLE IF EXISTS users"))
        
        connection.commit()
        logger.info("Migration 004 rollback completed successfully")
        
    except SQLAlchemyError as e:
        logger.error(f"Migration 004 rollback failed: {e}")
        connection.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error in migration 004 rollback: {e}")
        connection.rollback()
        raise


# Migration metadata
MIGRATION_ID = "004"
MIGRATION_NAME = "add_auth_audit_tables"
MIGRATION_DESCRIPTION = "Add authentication and audit tables for security"
DEPENDS_ON = ["003"]  # Depends on previous migration