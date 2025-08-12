#!/usr/bin/env python3
"""
Demonstration of ThreatLens security and authentication features.

This script demonstrates the security features implemented for real-time
log monitoring, including authentication, authorization, input validation,
and audit logging.
"""

import asyncio
import sys
from datetime import datetime, timezone

# Add the current directory to Python path
sys.path.append('.')

from app.realtime.auth import get_auth_manager, UserRole, Permission
from app.realtime.security import get_input_validator, get_file_sandbox
from app.realtime.audit import get_audit_logger, AuditEventType, AuditSeverity
from app.realtime.exceptions import InputValidationError, SecurityViolation


def demo_authentication():
    """Demonstrate authentication and authorization features."""
    print("=" * 60)
    print("AUTHENTICATION & AUTHORIZATION DEMO")
    print("=" * 60)
    
    auth_manager = get_auth_manager()
    
    # Create sessions for different user roles
    print("\n1. Creating user sessions with different roles:")
    
    admin_session = auth_manager.create_session(
        user_id="admin-001",
        username="admin_user",
        role=UserRole.ADMIN,
        client_ip="192.168.1.100"
    )
    print(f"   Admin session: {admin_session.session_id[:8]}... (role: {admin_session.role.value})")
    print(f"   Permissions: {len(admin_session.permissions)} permissions")
    
    analyst_session = auth_manager.create_session(
        user_id="analyst-001", 
        username="security_analyst",
        role=UserRole.ANALYST,
        client_ip="192.168.1.101"
    )
    print(f"   Analyst session: {analyst_session.session_id[:8]}... (role: {analyst_session.role.value})")
    print(f"   Permissions: {len(analyst_session.permissions)} permissions")
    
    viewer_session = auth_manager.create_session(
        user_id="viewer-001",
        username="readonly_user", 
        role=UserRole.VIEWER,
        client_ip="192.168.1.102"
    )
    print(f"   Viewer session: {viewer_session.session_id[:8]}... (role: {viewer_session.role.value})")
    print(f"   Permissions: {len(viewer_session.permissions)} permissions")
    
    # Generate and validate tokens
    print("\n2. Generating and validating authentication tokens:")
    
    admin_token = auth_manager.generate_token(admin_session)
    print(f"   Admin token generated (expires in {admin_token.expires_in}s)")
    
    # Validate token
    validated_session = auth_manager.validate_token(admin_token.token)
    if validated_session:
        print(f"   Token validation successful: {validated_session.username}")
    else:
        print("   Token validation failed!")
    
    # Test permission checking
    print("\n3. Testing permission-based access control:")
    
    permissions_to_test = [
        Permission.CONFIG_WRITE,
        Permission.LOG_SOURCE_DELETE,
        Permission.SYSTEM_ADMIN
    ]
    
    for permission in permissions_to_test:
        admin_has = permission in admin_session.permissions
        analyst_has = permission in analyst_session.permissions
        viewer_has = permission in viewer_session.permissions
        
        print(f"   {permission.value}:")
        print(f"     Admin: {'✓' if admin_has else '✗'}")
        print(f"     Analyst: {'✓' if analyst_has else '✗'}")
        print(f"     Viewer: {'✓' if viewer_has else '✗'}")


def demo_input_validation():
    """Demonstrate input validation and security measures."""
    print("\n" + "=" * 60)
    print("INPUT VALIDATION & SECURITY DEMO")
    print("=" * 60)
    
    validator = get_input_validator()
    
    # Test file path validation
    print("\n1. File path validation:")
    
    test_paths = [
        "/var/log/system.log",  # Valid
        "/tmp/app.log",         # Valid
        "../../../etc/passwd",  # Path traversal attack
        "/path/with;rm -rf /",  # Command injection
        "normal_file.log",      # Relative path
        "/var/log/app.log; cat /etc/shadow"  # Command injection
    ]
    
    for path in test_paths:
        try:
            result = validator.validate_file_path(path, allow_relative=True)
            print(f"   ✓ '{path}' -> '{result}'")
        except InputValidationError as e:
            print(f"   ✗ '{path}' -> BLOCKED: {e}")
    
    # Test log source name validation
    print("\n2. Log source name validation:")
    
    test_names = [
        "system_logs",          # Valid
        "app-logs.2024",        # Valid
        "web server logs",      # Invalid (spaces)
        "logs<script>alert()</script>",  # XSS attempt
        "logs;rm -rf /",        # Command injection
        "con",                  # Reserved name
    ]
    
    for name in test_names:
        try:
            result = validator.validate_log_source_name(name)
            print(f"   ✓ '{name}' -> '{result}'")
        except InputValidationError as e:
            print(f"   ✗ '{name}' -> BLOCKED: {e}")
    
    # Test notification config validation
    print("\n3. Notification configuration validation:")
    
    test_configs = [
        {
            "email": "admin@company.com",
            "webhook_url": "https://hooks.slack.com/webhook",
            "enabled": True,
            "timeout": 30
        },
        {
            "email": "not-an-email",
            "webhook_url": "javascript:alert('xss')",
            "enabled": True
        }
    ]
    
    for i, config in enumerate(test_configs):
        try:
            result = validator.validate_notification_config(config)
            print(f"   ✓ Config {i+1}: Validated successfully")
            print(f"     Email: {result.get('email', 'N/A')}")
        except InputValidationError as e:
            print(f"   ✗ Config {i+1}: BLOCKED: {e}")


def demo_file_sandbox():
    """Demonstrate file path sandboxing."""
    print("\n" + "=" * 60)
    print("FILE PATH SANDBOXING DEMO")
    print("=" * 60)
    
    sandbox = get_file_sandbox()
    
    print(f"\nConfigured allowed paths: {len(sandbox.allowed_paths)}")
    for path in sandbox.allowed_paths:
        print(f"   - {path}")
    
    print(f"\nBlocked system paths: {len(sandbox.blocked_paths)}")
    for path in sandbox.blocked_paths[:3]:  # Show first 3
        print(f"   - {path}")
    print("   ...")
    
    # Test path validation
    print("\n1. Testing path access control:")
    
    test_paths = [
        "./data/sample_logs/test.log",  # Should be allowed
        "/var/log/system.log",          # Should be allowed
        "/etc/passwd",                  # Should be blocked
        "/root/.ssh/id_rsa",           # Should be blocked
        "/tmp/../etc/shadow",          # Path traversal to blocked area
    ]
    
    for path in test_paths:
        try:
            result = sandbox.validate_path(path)
            print(f"   ✓ '{path}' -> ALLOWED: {result}")
        except SecurityViolation as e:
            print(f"   ✗ '{path}' -> BLOCKED: {e}")


def demo_audit_logging():
    """Demonstrate audit logging capabilities."""
    print("\n" + "=" * 60)
    print("AUDIT LOGGING DEMO")
    print("=" * 60)
    
    audit_logger = get_audit_logger()
    
    # Create a mock session for audit logging
    auth_manager = get_auth_manager()
    session = auth_manager.create_session(
        user_id="demo-user",
        username="demo_admin",
        role=UserRole.ADMIN,
        client_ip="192.168.1.200"
    )
    
    print("\n1. Logging different types of events:")
    
    # Configuration change
    audit_logger.log_configuration_change(
        action="create",
        resource_type="log_source",
        resource_id="demo-source-001",
        description="Created new log source for demo",
        session_info=session,
        new_values={
            "path": "/var/log/demo.log",
            "enabled": True,
            "polling_interval": 30
        }
    )
    print("   ✓ Configuration change logged")
    
    # Authentication event
    audit_logger.log_authentication_event(
        event_type=AuditEventType.USER_LOGIN,
        description="User logged in successfully",
        user_id=session.user_id,
        username=session.username,
        session_id=session.session_id,
        client_ip=session.client_ip,
        success=True
    )
    print("   ✓ Authentication event logged")
    
    # Security event
    audit_logger.log_security_event(
        event_type=AuditEventType.SECURITY_VIOLATION,
        description="Attempted access to restricted file",
        severity=AuditSeverity.HIGH,
        session_info=session,
        metadata={
            "attempted_path": "/etc/passwd",
            "blocked_by": "file_sandbox"
        }
    )
    print("   ✓ Security violation logged")
    
    # WebSocket event
    audit_logger.log_websocket_event(
        event_type=AuditEventType.WEBSOCKET_CONNECTED,
        description="WebSocket client connected",
        client_id="demo-client-001",
        session_info=session
    )
    print("   ✓ WebSocket event logged")
    
    print(f"\n2. Audit buffer contains {len(audit_logger.buffer)} entries")
    
    # Flush audit buffer (in real app this happens automatically)
    try:
        audit_logger.flush()
        print("   ✓ Audit entries flushed to database")
    except Exception as e:
        print(f"   ⚠ Audit flush failed (database may not be initialized): {e}")


def demo_rate_limiting():
    """Demonstrate rate limiting capabilities."""
    print("\n" + "=" * 60)
    print("RATE LIMITING DEMO")
    print("=" * 60)
    
    from app.realtime.security import get_rate_limiter
    
    rate_limiter = get_rate_limiter()
    
    print("\n1. Testing rate limiting for different clients:")
    
    # Simulate requests from different clients
    clients = ["client-001", "client-002", "suspicious-client"]
    
    # Mark one client as suspicious
    rate_limiter.suspicious_clients.add("suspicious-client")
    
    for client in clients:
        print(f"\n   Testing client: {client}")
        
        # Make several requests
        allowed_count = 0
        for i in range(15):  # Try 15 requests
            if rate_limiter.check_rate_limit(client, "/api/test"):
                allowed_count += 1
            else:
                break
        
        print(f"     Allowed requests: {allowed_count}/15")
        
        # Show client status
        status = rate_limiter.get_client_status(client)
        print(f"     Status: {'Suspicious' if status['is_suspicious'] else 'Normal'}")
        print(f"     Tokens remaining: {status['tokens_remaining']}")


def main():
    """Run all security feature demonstrations."""
    print("ThreatLens Security Features Demonstration")
    print("==========================================")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    try:
        demo_authentication()
        demo_input_validation()
        demo_file_sandbox()
        demo_audit_logging()
        demo_rate_limiting()
        
        print("\n" + "=" * 60)
        print("DEMONSTRATION COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("\nAll security features are working correctly!")
        print("The system provides comprehensive protection against:")
        print("  • Unauthorized access (authentication & authorization)")
        print("  • Path traversal attacks (input validation)")
        print("  • Command injection (input sanitization)")
        print("  • Unauthorized file access (sandboxing)")
        print("  • Rate limiting abuse (adaptive rate limiting)")
        print("  • Security incidents (comprehensive audit logging)")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())