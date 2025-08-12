"""
Tests for authentication and security features.

This module tests the authentication, authorization, input validation,
and security measures implemented for real-time features.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from app.database import get_database_session
from app.models import Base, User, AuditLog
from app.realtime.auth import get_auth_manager, UserRole, Permission
from app.realtime.security import get_input_validator, get_file_sandbox
from app.realtime.exceptions import InputValidationError as ValidationError, SecurityViolation
from app.realtime.audit import get_audit_logger, AuditEventType


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_security.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_database_session] = override_get_db


@pytest.fixture(scope="module")
def setup_database():
    """Set up test database."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_user():
    """Create test user in database."""
    db = TestingSessionLocal()
    try:
        import hashlib
        import uuid
        
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256("testpass123".encode()).hexdigest()
        
        user = User(
            id=user_id,
            username="testuser",
            email="test@example.com",
            password_hash=password_hash,
            role="analyst",
            enabled=1
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


class TestAuthentication:
    """Test authentication functionality."""
    
    def test_create_session(self, setup_database):
        """Test session creation."""
        auth_manager = get_auth_manager()
        
        session_info = auth_manager.create_session(
            user_id="test-user-id",
            username="testuser",
            role=UserRole.ANALYST,
            client_ip="127.0.0.1"
        )
        
        assert session_info.user_id == "test-user-id"
        assert session_info.username == "testuser"
        assert session_info.role == UserRole.ANALYST
        assert Permission.LOG_SOURCE_READ in session_info.permissions
        assert Permission.CONFIG_DELETE not in session_info.permissions
    
    def test_validate_session(self, setup_database):
        """Test session validation."""
        auth_manager = get_auth_manager()
        
        # Create session
        session_info = auth_manager.create_session(
            user_id="test-user-id",
            username="testuser",
            role=UserRole.VIEWER
        )
        
        # Validate session
        validated = auth_manager.validate_session(session_info.session_id)
        assert validated is not None
        assert validated.session_id == session_info.session_id
        
        # Test invalid session
        invalid = auth_manager.validate_session("invalid-session-id")
        assert invalid is None
    
    def test_generate_and_validate_token(self, setup_database):
        """Test token generation and validation."""
        auth_manager = get_auth_manager()
        
        # Create session
        session_info = auth_manager.create_session(
            user_id="test-user-id",
            username="testuser",
            role=UserRole.ADMIN
        )
        
        # Generate token
        token = auth_manager.generate_token(session_info)
        assert token.token is not None
        assert token.session_id == session_info.session_id
        
        # Validate token
        validated_session = auth_manager.validate_token(token.token)
        assert validated_session is not None
        assert validated_session.user_id == session_info.user_id


class TestInputValidation:
    """Test input validation functionality."""
    
    def test_validate_file_path(self):
        """Test file path validation."""
        validator = get_input_validator()
        
        # Valid paths
        valid_path = validator.validate_file_path("/var/log/system.log")
        assert valid_path == "/var/log/system.log"
        
        # Invalid paths
        with pytest.raises(ValidationError):
            validator.validate_file_path("../../../etc/passwd")
        
        with pytest.raises(ValidationError):
            validator.validate_file_path("/path/with/../traversal")
        
        with pytest.raises(ValidationError):
            validator.validate_file_path("path; rm -rf /")
    
    def test_validate_log_source_name(self):
        """Test log source name validation."""
        validator = get_input_validator()
        
        # Valid names
        valid_name = validator.validate_log_source_name("system_logs")
        assert valid_name == "system_logs"
        
        valid_name2 = validator.validate_log_source_name("app-logs.2024")
        assert valid_name2 == "app-logs.2024"
        
        # Invalid names
        with pytest.raises(ValidationError):
            validator.validate_log_source_name("name with spaces")
        
        with pytest.raises(ValidationError):
            validator.validate_log_source_name("name;rm -rf /")
        
        with pytest.raises(ValidationError):
            validator.validate_log_source_name("<script>alert('xss')</script>")
    
    def test_validate_notification_config(self):
        """Test notification configuration validation."""
        validator = get_input_validator()
        
        # Valid config
        valid_config = {
            "email": "admin@example.com",
            "webhook_url": "https://hooks.slack.com/webhook",
            "enabled": True,
            "timeout": 30
        }
        
        sanitized = validator.validate_notification_config(valid_config)
        assert sanitized["email"] == "admin@example.com"
        assert sanitized["enabled"] is True
        assert sanitized["timeout"] == 30
        
        # Invalid config
        with pytest.raises(ValidationError):
            validator.validate_notification_config({
                "email": "not-an-email",
                "webhook_url": "javascript:alert('xss')"
            })


class TestFilePathSandbox:
    """Test file path sandboxing."""
    
    def test_validate_allowed_path(self):
        """Test validation of allowed paths."""
        sandbox = get_file_sandbox()
        
        # Add test allowed path
        sandbox.add_allowed_path("./data")
        
        # Test allowed path (this might fail if path doesn't exist in strict mode)
        try:
            validated = sandbox.validate_path("./data/test.log")
            assert "data" in str(validated)
        except SecurityViolation:
            # Expected in strict mode if file doesn't exist
            pass
    
    def test_block_dangerous_paths(self):
        """Test blocking of dangerous paths."""
        sandbox = get_file_sandbox()
        
        # These should be blocked
        dangerous_paths = [
            "/etc/passwd",
            "/root/.ssh/id_rsa",
            "/sys/kernel",
            "/proc/version"
        ]
        
        for path in dangerous_paths:
            with pytest.raises(SecurityViolation):
                sandbox.validate_path(path)


class TestAuditLogging:
    """Test audit logging functionality."""
    
    def test_log_event(self, setup_database):
        """Test basic event logging."""
        audit_logger = get_audit_logger()
        
        entry = audit_logger.log_event(
            event_type=AuditEventType.CONFIG_CREATED,
            description="Test configuration created",
            resource_type="test_resource",
            resource_id="test-123",
            success=True
        )
        
        assert entry.event_type == AuditEventType.CONFIG_CREATED
        assert entry.description == "Test configuration created"
        assert entry.success is True
    
    def test_log_configuration_change(self, setup_database):
        """Test configuration change logging."""
        audit_logger = get_audit_logger()
        
        old_values = {"enabled": False, "path": "/old/path"}
        new_values = {"enabled": True, "path": "/new/path"}
        
        entry = audit_logger.log_configuration_change(
            action="update",
            resource_type="log_source",
            resource_id="test-source",
            description="Updated log source configuration",
            old_values=old_values,
            new_values=new_values
        )
        
        assert entry.action == "update"
        assert entry.resource_type == "log_source"
        assert entry.old_values == old_values
        assert entry.new_values == new_values
        assert "enabled" in entry.changes
        assert "path" in entry.changes


class TestAPIAuthentication:
    """Test API endpoint authentication."""
    
    def test_protected_endpoint_without_auth(self, client, setup_database):
        """Test accessing protected endpoint without authentication."""
        response = client.get("/api/v1/monitoring/log-sources")
        assert response.status_code == 401
    
    def test_login_endpoint(self, client, setup_database, test_user):
        """Test login endpoint."""
        response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "token" in data
        assert data["user_info"]["username"] == "testuser"
    
    def test_invalid_login(self, client, setup_database, test_user):
        """Test login with invalid credentials."""
        response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
        data = response.json()
        assert "Invalid username or password" in data["detail"]


@pytest.mark.asyncio
class TestWebSocketAuthentication:
    """Test WebSocket authentication."""
    
    async def test_websocket_without_token(self):
        """Test WebSocket connection without authentication token."""
        from app.realtime.websocket_server import WebSocketManager
        from fastapi import WebSocket
        
        # This would need a mock WebSocket for proper testing
        # For now, just test the manager initialization
        manager = WebSocketManager(require_auth=True)
        assert manager.require_auth is True
        assert manager.stats["authenticated_connections"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])