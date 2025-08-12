"""
Authentication and authorization for real-time features.

This module provides authentication, session management, and role-based
access control for WebSocket connections and real-time configuration management.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set, Union
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field, ValidationError
from fastapi import HTTPException, Depends, Request, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..database import get_db_session
from ..models import User, UserSession, AuditLog
from ..logging_config import get_logger, get_correlation_id
from .exceptions import AuthenticationError, AuthorizationError

logger = get_logger(__name__)


class UserRole(str, Enum):
    """User roles for access control."""
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    SYSTEM = "system"


class Permission(str, Enum):
    """System permissions."""
    # Configuration permissions
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"
    CONFIG_DELETE = "config:delete"
    
    # Log source permissions
    LOG_SOURCE_READ = "log_source:read"
    LOG_SOURCE_WRITE = "log_source:write"
    LOG_SOURCE_DELETE = "log_source:delete"
    
    # Notification permissions
    NOTIFICATION_READ = "notification:read"
    NOTIFICATION_WRITE = "notification:write"
    NOTIFICATION_DELETE = "notification:delete"
    
    # WebSocket permissions
    WEBSOCKET_CONNECT = "websocket:connect"
    WEBSOCKET_SUBSCRIBE = "websocket:subscribe"
    WEBSOCKET_ADMIN = "websocket:admin"
    
    # System permissions
    SYSTEM_HEALTH = "system:health"
    SYSTEM_METRICS = "system:metrics"
    SYSTEM_ADMIN = "system:admin"
    
    # Event permissions
    EVENT_READ = "event:read"
    EVENT_WRITE = "event:write"


class SessionInfo(BaseModel):
    """Session information model."""
    
    session_id: str = Field(..., description="Session identifier")
    user_id: str = Field(..., description="User identifier")
    username: str = Field(..., description="Username")
    role: UserRole = Field(..., description="User role")
    permissions: Set[Permission] = Field(..., description="User permissions")
    created_at: datetime = Field(..., description="Session creation time")
    expires_at: datetime = Field(..., description="Session expiration time")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    client_ip: Optional[str] = Field(default=None, description="Client IP address")
    user_agent: Optional[str] = Field(default=None, description="Client user agent")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            set: lambda v: list(v)
        }


class AuthToken(BaseModel):
    """Authentication token model."""
    
    token: str = Field(..., description="Authentication token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    session_id: str = Field(..., description="Associated session ID")
    permissions: List[str] = Field(..., description="Token permissions")


class WebSocketAuthInfo(BaseModel):
    """WebSocket authentication information."""
    
    client_id: str = Field(..., description="Client identifier")
    session_info: SessionInfo = Field(..., description="Session information")
    authenticated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    connection_metadata: Dict[str, Any] = Field(default_factory=dict)


# Role-based permission mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: {
        Permission.CONFIG_READ, Permission.CONFIG_WRITE, Permission.CONFIG_DELETE,
        Permission.LOG_SOURCE_READ, Permission.LOG_SOURCE_WRITE, Permission.LOG_SOURCE_DELETE,
        Permission.NOTIFICATION_READ, Permission.NOTIFICATION_WRITE, Permission.NOTIFICATION_DELETE,
        Permission.WEBSOCKET_CONNECT, Permission.WEBSOCKET_SUBSCRIBE, Permission.WEBSOCKET_ADMIN,
        Permission.SYSTEM_HEALTH, Permission.SYSTEM_METRICS, Permission.SYSTEM_ADMIN,
        Permission.EVENT_READ, Permission.EVENT_WRITE
    },
    UserRole.ANALYST: {
        Permission.CONFIG_READ,
        Permission.LOG_SOURCE_READ, Permission.LOG_SOURCE_WRITE,
        Permission.NOTIFICATION_READ, Permission.NOTIFICATION_WRITE,
        Permission.WEBSOCKET_CONNECT, Permission.WEBSOCKET_SUBSCRIBE,
        Permission.SYSTEM_HEALTH, Permission.SYSTEM_METRICS,
        Permission.EVENT_READ, Permission.EVENT_WRITE
    },
    UserRole.VIEWER: {
        Permission.CONFIG_READ,
        Permission.LOG_SOURCE_READ,
        Permission.NOTIFICATION_READ,
        Permission.WEBSOCKET_CONNECT, Permission.WEBSOCKET_SUBSCRIBE,
        Permission.SYSTEM_HEALTH,
        Permission.EVENT_READ
    },
    UserRole.SYSTEM: {
        Permission.CONFIG_READ, Permission.CONFIG_WRITE,
        Permission.LOG_SOURCE_READ, Permission.LOG_SOURCE_WRITE,
        Permission.NOTIFICATION_READ, Permission.NOTIFICATION_WRITE,
        Permission.WEBSOCKET_CONNECT, Permission.WEBSOCKET_SUBSCRIBE,
        Permission.SYSTEM_HEALTH, Permission.SYSTEM_METRICS,
        Permission.EVENT_READ, Permission.EVENT_WRITE
    }
}


class AuthenticationManager:
    """
    Manages authentication and session handling for real-time features.
    
    Provides secure session management, token validation, and user authentication
    with support for both HTTP and WebSocket connections.
    """
    
    def __init__(self, secret_key: Optional[str] = None, session_timeout: int = 3600):
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.session_timeout = session_timeout  # seconds
        self.active_sessions: Dict[str, SessionInfo] = {}
        self.websocket_auth: Dict[str, WebSocketAuthInfo] = {}
        self.failed_attempts: Dict[str, List[datetime]] = {}
        self.max_failed_attempts = 5
        self.lockout_duration = 300  # 5 minutes
        
        # Security settings
        self.token_algorithm = "HS256"
        self.session_cleanup_interval = 300  # 5 minutes
        
        # Start cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_started = False
    
    def _start_cleanup_task(self) -> None:
        """Start background task for session cleanup."""
        if not self._cleanup_started:
            try:
                if self._cleanup_task is None or self._cleanup_task.done():
                    self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
                    self._cleanup_started = True
            except RuntimeError:
                # No event loop running, will start later
                pass
    
    async def _cleanup_expired_sessions(self) -> None:
        """Background task to clean up expired sessions."""
        try:
            while True:
                await asyncio.sleep(self.session_cleanup_interval)
                await self._remove_expired_sessions()
        except asyncio.CancelledError:
            logger.info("Session cleanup task cancelled")
        except Exception as e:
            logger.error(f"Session cleanup task error: {e}")
    
    async def _remove_expired_sessions(self) -> None:
        """Remove expired sessions from memory and database."""
        try:
            current_time = datetime.now(timezone.utc)
            expired_sessions = []
            
            # Find expired sessions
            for session_id, session_info in self.active_sessions.items():
                if current_time > session_info.expires_at:
                    expired_sessions.append(session_id)
            
            # Remove expired sessions
            for session_id in expired_sessions:
                await self._invalidate_session(session_id, "Session expired")
            
            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
    
    def create_session(self, user_id: str, username: str, role: UserRole,
                      client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> SessionInfo:
        """
        Create a new authenticated session.
        
        Args:
            user_id: User identifier
            username: Username
            role: User role
            client_ip: Client IP address
            user_agent: Client user agent
            
        Returns:
            SessionInfo for the new session
        """
        try:
            # Start cleanup task if not already started
            if not self._cleanup_started:
                self._start_cleanup_task()
            
            session_id = str(uuid4())
            current_time = datetime.now(timezone.utc)
            expires_at = current_time + timedelta(seconds=self.session_timeout)
            
            # Get permissions for role
            permissions = ROLE_PERMISSIONS.get(role, set())
            
            session_info = SessionInfo(
                session_id=session_id,
                user_id=user_id,
                username=username,
                role=role,
                permissions=permissions,
                created_at=current_time,
                expires_at=expires_at,
                last_activity=current_time,
                client_ip=client_ip,
                user_agent=user_agent
            )
            
            # Store session
            self.active_sessions[session_id] = session_info
            
            # Log session creation
            self._log_auth_event("session_created", {
                "session_id": session_id,
                "user_id": user_id,
                "username": username,
                "role": role.value,
                "client_ip": client_ip
            })
            
            logger.info(f"Session created for user {username} ({role.value}): {session_id}")
            return session_info
            
        except Exception as e:
            logger.error(f"Failed to create session for user {username}: {e}")
            raise AuthenticationError(f"Session creation failed: {e}")
    
    def validate_session(self, session_id: str) -> Optional[SessionInfo]:
        """
        Validate and refresh a session.
        
        Args:
            session_id: Session identifier to validate
            
        Returns:
            SessionInfo if valid, None otherwise
        """
        try:
            session_info = self.active_sessions.get(session_id)
            if not session_info:
                return None
            
            current_time = datetime.now(timezone.utc)
            
            # Check if session is expired
            if current_time > session_info.expires_at:
                asyncio.create_task(self._invalidate_session(session_id, "Session expired"))
                return None
            
            # Update last activity and extend expiration
            session_info.last_activity = current_time
            session_info.expires_at = current_time + timedelta(seconds=self.session_timeout)
            
            return session_info
            
        except Exception as e:
            logger.error(f"Error validating session {session_id}: {e}")
            return None
    
    async def _invalidate_session(self, session_id: str, reason: str = "Session invalidated") -> None:
        """
        Invalidate a session.
        
        Args:
            session_id: Session identifier
            reason: Reason for invalidation
        """
        try:
            session_info = self.active_sessions.get(session_id)
            if session_info:
                # Remove from active sessions
                del self.active_sessions[session_id]
                
                # Remove associated WebSocket auth
                websocket_clients_to_remove = []
                for client_id, ws_auth in self.websocket_auth.items():
                    if ws_auth.session_info.session_id == session_id:
                        websocket_clients_to_remove.append(client_id)
                
                for client_id in websocket_clients_to_remove:
                    del self.websocket_auth[client_id]
                
                # Log session invalidation
                self._log_auth_event("session_invalidated", {
                    "session_id": session_id,
                    "user_id": session_info.user_id,
                    "username": session_info.username,
                    "reason": reason
                })
                
                logger.info(f"Session invalidated: {session_id} ({reason})")
                
        except Exception as e:
            logger.error(f"Error invalidating session {session_id}: {e}")
    
    def generate_token(self, session_info: SessionInfo) -> AuthToken:
        """
        Generate an authentication token for a session.
        
        Args:
            session_info: Session information
            
        Returns:
            AuthToken with JWT token
        """
        try:
            import jwt
            
            # Token payload
            payload = {
                "session_id": session_info.session_id,
                "user_id": session_info.user_id,
                "username": session_info.username,
                "role": session_info.role.value,
                "permissions": [p.value for p in session_info.permissions],
                "iat": int(time.time()),
                "exp": int(session_info.expires_at.timestamp())
            }
            
            # Generate JWT token
            token = jwt.encode(payload, self.secret_key, algorithm=self.token_algorithm)
            
            expires_in = int((session_info.expires_at - datetime.now(timezone.utc)).total_seconds())
            
            return AuthToken(
                token=token,
                expires_in=expires_in,
                session_id=session_info.session_id,
                permissions=[p.value for p in session_info.permissions]
            )
            
        except Exception as e:
            logger.error(f"Failed to generate token for session {session_info.session_id}: {e}")
            raise AuthenticationError(f"Token generation failed: {e}")
    
    def validate_token(self, token: str) -> Optional[SessionInfo]:
        """
        Validate an authentication token.
        
        Args:
            token: JWT token to validate
            
        Returns:
            SessionInfo if valid, None otherwise
        """
        try:
            import jwt
            
            # Decode and validate token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.token_algorithm])
            
            session_id = payload.get("session_id")
            if not session_id:
                return None
            
            # Validate associated session
            return self.validate_session(session_id)
            
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return None
    
    async def authenticate_websocket(self, websocket: WebSocket, client_id: str,
                                   token: Optional[str] = None) -> WebSocketAuthInfo:
        """
        Authenticate a WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            client_id: Client identifier
            token: Optional authentication token
            
        Returns:
            WebSocketAuthInfo if authenticated
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Extract token from query parameters if not provided
            if not token:
                query_params = dict(websocket.query_params)
                token = query_params.get("token")
            
            if not token:
                raise AuthenticationError("Authentication token required for WebSocket connection")
            
            # Validate token
            session_info = self.validate_token(token)
            if not session_info:
                raise AuthenticationError("Invalid or expired authentication token")
            
            # Check WebSocket permission
            if Permission.WEBSOCKET_CONNECT not in session_info.permissions:
                raise AuthorizationError("Insufficient permissions for WebSocket connection")
            
            # Get connection metadata
            connection_metadata = {
                "client_host": websocket.client.host if websocket.client else None,
                "headers": dict(websocket.headers) if hasattr(websocket, 'headers') else {}
            }
            
            # Create WebSocket auth info
            ws_auth = WebSocketAuthInfo(
                client_id=client_id,
                session_info=session_info,
                connection_metadata=connection_metadata
            )
            
            # Store WebSocket authentication
            self.websocket_auth[client_id] = ws_auth
            
            # Log WebSocket authentication
            self._log_auth_event("websocket_authenticated", {
                "client_id": client_id,
                "session_id": session_info.session_id,
                "user_id": session_info.user_id,
                "username": session_info.username,
                "client_host": connection_metadata.get("client_host")
            })
            
            logger.info(f"WebSocket authenticated: {client_id} (user: {session_info.username})")
            return ws_auth
            
        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"WebSocket authentication error for {client_id}: {e}")
            raise AuthenticationError(f"WebSocket authentication failed: {e}")
    
    def get_websocket_auth(self, client_id: str) -> Optional[WebSocketAuthInfo]:
        """
        Get WebSocket authentication information.
        
        Args:
            client_id: Client identifier
            
        Returns:
            WebSocketAuthInfo if authenticated, None otherwise
        """
        return self.websocket_auth.get(client_id)
    
    def remove_websocket_auth(self, client_id: str) -> None:
        """
        Remove WebSocket authentication.
        
        Args:
            client_id: Client identifier
        """
        if client_id in self.websocket_auth:
            ws_auth = self.websocket_auth[client_id]
            del self.websocket_auth[client_id]
            
            # Log WebSocket disconnection
            self._log_auth_event("websocket_disconnected", {
                "client_id": client_id,
                "session_id": ws_auth.session_info.session_id,
                "user_id": ws_auth.session_info.user_id,
                "username": ws_auth.session_info.username
            })
            
            logger.info(f"WebSocket auth removed: {client_id}")
    
    def check_rate_limit(self, identifier: str, max_attempts: int = None, 
                        window_seconds: int = 300) -> bool:
        """
        Check if an identifier is rate limited.
        
        Args:
            identifier: Identifier to check (IP, user ID, etc.)
            max_attempts: Maximum attempts allowed
            window_seconds: Time window in seconds
            
        Returns:
            True if rate limited, False otherwise
        """
        try:
            max_attempts = max_attempts or self.max_failed_attempts
            current_time = datetime.now(timezone.utc)
            cutoff_time = current_time - timedelta(seconds=window_seconds)
            
            # Get recent attempts
            attempts = self.failed_attempts.get(identifier, [])
            recent_attempts = [attempt for attempt in attempts if attempt > cutoff_time]
            
            # Update stored attempts
            self.failed_attempts[identifier] = recent_attempts
            
            return len(recent_attempts) >= max_attempts
            
        except Exception as e:
            logger.error(f"Error checking rate limit for {identifier}: {e}")
            return False
    
    def record_failed_attempt(self, identifier: str) -> None:
        """
        Record a failed authentication attempt.
        
        Args:
            identifier: Identifier for the attempt
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            if identifier not in self.failed_attempts:
                self.failed_attempts[identifier] = []
            
            self.failed_attempts[identifier].append(current_time)
            
            # Log failed attempt
            self._log_auth_event("authentication_failed", {
                "identifier": identifier,
                "attempt_count": len(self.failed_attempts[identifier])
            })
            
        except Exception as e:
            logger.error(f"Error recording failed attempt for {identifier}: {e}")
    
    def clear_failed_attempts(self, identifier: str) -> None:
        """
        Clear failed attempts for an identifier.
        
        Args:
            identifier: Identifier to clear
        """
        if identifier in self.failed_attempts:
            del self.failed_attempts[identifier]
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """
        Get session statistics.
        
        Returns:
            Dictionary with session statistics
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            # Count sessions by role
            role_counts = {}
            active_count = 0
            
            for session_info in self.active_sessions.values():
                if current_time <= session_info.expires_at:
                    active_count += 1
                    role = session_info.role.value
                    role_counts[role] = role_counts.get(role, 0) + 1
            
            return {
                "total_sessions": len(self.active_sessions),
                "active_sessions": active_count,
                "websocket_connections": len(self.websocket_auth),
                "sessions_by_role": role_counts,
                "failed_attempt_sources": len(self.failed_attempts)
            }
            
        except Exception as e:
            logger.error(f"Error getting session statistics: {e}")
            return {"error": str(e)}
    
    def _log_auth_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """
        Log authentication event for audit purposes.
        
        Args:
            event_type: Type of authentication event
            details: Event details
        """
        try:
            # Add correlation ID if available
            correlation_id = get_correlation_id()
            if correlation_id:
                details["correlation_id"] = correlation_id
            
            logger.info(f"Auth event: {event_type}", extra={
                "auth_event": {
                    "event_type": event_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **details
                }
            })
            
        except Exception as e:
            logger.error(f"Error logging auth event: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown the authentication manager."""
        try:
            # Cancel cleanup task
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Invalidate all sessions
            session_ids = list(self.active_sessions.keys())
            for session_id in session_ids:
                await self._invalidate_session(session_id, "System shutdown")
            
            logger.info("Authentication manager shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during authentication manager shutdown: {e}")


class AuthorizationManager:
    """
    Manages role-based access control and permissions.
    
    Provides permission checking, role validation, and access control
    for real-time features and configuration management.
    """
    
    def __init__(self):
        self.permission_cache: Dict[str, Set[Permission]] = {}
        self.cache_ttl = 300  # 5 minutes
        self.cache_timestamps: Dict[str, datetime] = {}
    
    def check_permission(self, session_info: SessionInfo, required_permission: Permission) -> bool:
        """
        Check if a session has a required permission.
        
        Args:
            session_info: Session information
            required_permission: Required permission
            
        Returns:
            True if permission granted, False otherwise
        """
        try:
            return required_permission in session_info.permissions
        except Exception as e:
            logger.error(f"Error checking permission {required_permission}: {e}")
            return False
    
    def check_permissions(self, session_info: SessionInfo, required_permissions: List[Permission]) -> bool:
        """
        Check if a session has all required permissions.
        
        Args:
            session_info: Session information
            required_permissions: List of required permissions
            
        Returns:
            True if all permissions granted, False otherwise
        """
        try:
            return all(perm in session_info.permissions for perm in required_permissions)
        except Exception as e:
            logger.error(f"Error checking permissions: {e}")
            return False
    
    def check_role(self, session_info: SessionInfo, required_roles: Union[UserRole, List[UserRole]]) -> bool:
        """
        Check if a session has one of the required roles.
        
        Args:
            session_info: Session information
            required_roles: Required role(s)
            
        Returns:
            True if role matches, False otherwise
        """
        try:
            if isinstance(required_roles, UserRole):
                required_roles = [required_roles]
            
            return session_info.role in required_roles
        except Exception as e:
            logger.error(f"Error checking role: {e}")
            return False
    
    def get_permissions_for_role(self, role: UserRole) -> Set[Permission]:
        """
        Get permissions for a specific role.
        
        Args:
            role: User role
            
        Returns:
            Set of permissions for the role
        """
        return ROLE_PERMISSIONS.get(role, set())
    
    def validate_configuration_access(self, session_info: SessionInfo, operation: str) -> bool:
        """
        Validate access to configuration operations.
        
        Args:
            session_info: Session information
            operation: Operation type (read, write, delete)
            
        Returns:
            True if access granted, False otherwise
        """
        try:
            permission_map = {
                "read": Permission.CONFIG_READ,
                "write": Permission.CONFIG_WRITE,
                "delete": Permission.CONFIG_DELETE
            }
            
            required_permission = permission_map.get(operation)
            if not required_permission:
                return False
            
            return self.check_permission(session_info, required_permission)
            
        except Exception as e:
            logger.error(f"Error validating configuration access: {e}")
            return False
    
    def validate_log_source_access(self, session_info: SessionInfo, operation: str) -> bool:
        """
        Validate access to log source operations.
        
        Args:
            session_info: Session information
            operation: Operation type (read, write, delete)
            
        Returns:
            True if access granted, False otherwise
        """
        try:
            permission_map = {
                "read": Permission.LOG_SOURCE_READ,
                "write": Permission.LOG_SOURCE_WRITE,
                "delete": Permission.LOG_SOURCE_DELETE
            }
            
            required_permission = permission_map.get(operation)
            if not required_permission:
                return False
            
            return self.check_permission(session_info, required_permission)
            
        except Exception as e:
            logger.error(f"Error validating log source access: {e}")
            return False
    
    def validate_websocket_access(self, session_info: SessionInfo, operation: str) -> bool:
        """
        Validate access to WebSocket operations.
        
        Args:
            session_info: Session information
            operation: Operation type (connect, subscribe, admin)
            
        Returns:
            True if access granted, False otherwise
        """
        try:
            permission_map = {
                "connect": Permission.WEBSOCKET_CONNECT,
                "subscribe": Permission.WEBSOCKET_SUBSCRIBE,
                "admin": Permission.WEBSOCKET_ADMIN
            }
            
            required_permission = permission_map.get(operation)
            if not required_permission:
                return False
            
            return self.check_permission(session_info, required_permission)
            
        except Exception as e:
            logger.error(f"Error validating WebSocket access: {e}")
            return False


# Global instances
auth_manager = AuthenticationManager()
authz_manager = AuthorizationManager()


# FastAPI dependencies

security = HTTPBearer(auto_error=False)


async def get_current_session(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> SessionInfo:
    """
    FastAPI dependency to get current authenticated session.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        SessionInfo for authenticated session
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    session_info = auth_manager.validate_token(credentials.credentials)
    if not session_info:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return session_info


def require_permission(permission: Permission):
    """
    FastAPI dependency factory to require specific permission.
    
    Args:
        permission: Required permission
        
    Returns:
        Dependency function
    """
    async def check_permission_dependency(session_info: SessionInfo = Depends(get_current_session)) -> SessionInfo:
        if not authz_manager.check_permission(session_info, permission):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {permission.value}"
            )
        return session_info
    
    return check_permission_dependency


def require_role(roles: Union[UserRole, List[UserRole]]):
    """
    FastAPI dependency factory to require specific role(s).
    
    Args:
        roles: Required role(s)
        
    Returns:
        Dependency function
    """
    async def check_role_dependency(session_info: SessionInfo = Depends(get_current_session)) -> SessionInfo:
        if not authz_manager.check_role(session_info, roles):
            role_names = [r.value for r in (roles if isinstance(roles, list) else [roles])]
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient role. Required: {', '.join(role_names)}"
            )
        return session_info
    
    return check_role_dependency


# Utility functions

def get_auth_manager() -> AuthenticationManager:
    """Get the global authentication manager."""
    return auth_manager


def get_authz_manager() -> AuthorizationManager:
    """Get the global authorization manager."""
    return authz_manager