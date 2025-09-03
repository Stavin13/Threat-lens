"""
Authentication API endpoints for real-time features.

This module provides REST API endpoints for user authentication,
session management, and authorization for real-time monitoring features.
"""

import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from uuid import uuid4
from pydantic import BaseModel, Field, EmailStr
from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ..database import get_database_session
from ..models import User as UserModel, UserSession as UserSessionModel
from ..logging_config import get_logger
from .auth import (
    get_auth_manager, get_authz_manager, 
    AuthenticationManager, AuthorizationManager,
    SessionInfo, AuthToken, UserRole, Permission,
    get_current_session, require_permission, require_role
)
from .audit import get_audit_logger, AuditEventType, AuditSeverity

logger = get_logger(__name__)

# Create router
auth_router = APIRouter(prefix="/auth", tags=["authentication"])

# Security scheme
security = HTTPBearer(auto_error=False)


# Request/Response models

class LoginRequest(BaseModel):
    """Login request model."""
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)
    remember_me: bool = Field(default=False)


class LoginResponse(BaseModel):
    """Login response model."""
    success: bool
    message: str
    token: Optional[AuthToken] = None
    user_info: Optional[Dict[str, Any]] = None


class LogoutRequest(BaseModel):
    """Logout request model."""
    session_id: Optional[str] = None


class LogoutResponse(BaseModel):
    """Logout response model."""
    success: bool
    message: str


class UserCreateRequest(BaseModel):
    """User creation request model."""
    username: str = Field(..., min_length=3, max_length=255)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=8)
    role: UserRole = Field(default=UserRole.VIEWER)
    enabled: bool = Field(default=True)


class UserResponse(BaseModel):
    """User response model."""
    id: str
    username: str
    email: Optional[str]
    role: UserRole
    enabled: bool
    created_at: datetime
    last_login: Optional[datetime]


class SessionResponse(BaseModel):
    """Session response model."""
    session_id: str
    user_id: str
    username: str
    role: UserRole
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    client_ip: Optional[str]


class PermissionCheckRequest(BaseModel):
    """Permission check request model."""
    permissions: List[Permission]


class PermissionCheckResponse(BaseModel):
    """Permission check response model."""
    has_permissions: bool
    missing_permissions: List[Permission]


# Authentication endpoints

@auth_router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: Session = Depends(get_database_session)
):
    """
    Authenticate user and create session.
    
    Args:
        request: Login request data
        http_request: HTTP request object
        db: Database session
        
    Returns:
        LoginResponse with authentication token
    """
    auth_manager = get_auth_manager()
    audit_logger = get_audit_logger()
    
    client_ip = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")
    
    try:
        # Check rate limiting
        identifier = client_ip or "unknown"
        if auth_manager.check_rate_limit(identifier):
            audit_logger.log_authentication_event(
                AuditEventType.AUTH_FAILED,
                f"Rate limit exceeded for login attempt: {request.username}",
                username=request.username,
                client_ip=client_ip,
                user_agent=user_agent,
                success=False,
                error_message="Rate limit exceeded"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please try again later."
            )
        
        # Find user in database
        user = db.query(UserModel).filter(UserModel.username == request.username).first()
        
        if not user:
            auth_manager.record_failed_attempt(identifier)
            audit_logger.log_authentication_event(
                AuditEventType.AUTH_FAILED,
                f"Login attempt for non-existent user: {request.username}",
                username=request.username,
                client_ip=client_ip,
                user_agent=user_agent,
                success=False,
                error_message="User not found"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Check if user is enabled
        if not user.enabled:
            audit_logger.log_authentication_event(
                AuditEventType.AUTH_FAILED,
                f"Login attempt for disabled user: {request.username}",
                user_id=user.id,
                username=request.username,
                client_ip=client_ip,
                user_agent=user_agent,
                success=False,
                error_message="User account disabled"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled"
            )
        
        # Check if user is locked
        if user.locked_until and datetime.now(timezone.utc) < user.locked_until:
            audit_logger.log_authentication_event(
                AuditEventType.AUTH_FAILED,
                f"Login attempt for locked user: {request.username}",
                user_id=user.id,
                username=request.username,
                client_ip=client_ip,
                user_agent=user_agent,
                success=False,
                error_message="User account locked"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is temporarily locked"
            )
        
        # Verify password (simple hash for demo - use bcrypt in production)
        password_hash = hashlib.sha256(request.password.encode()).hexdigest()
        if user.password_hash != password_hash:
            auth_manager.record_failed_attempt(identifier)
            
            # Increment failed login attempts
            user.failed_login_attempts += 1
            
            # Lock account after too many failures
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
            
            db.commit()
            
            audit_logger.log_authentication_event(
                AuditEventType.AUTH_FAILED,
                f"Invalid password for user: {request.username}",
                user_id=user.id,
                username=request.username,
                client_ip=client_ip,
                user_agent=user_agent,
                success=False,
                error_message="Invalid password"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Clear failed attempts on successful login
        auth_manager.clear_failed_attempts(identifier)
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)
        db.commit()
        
        # Create session
        session_timeout = 7200 if request.remember_me else 3600  # 2 hours vs 1 hour
        auth_manager.session_timeout = session_timeout
        
        session_info = auth_manager.create_session(
            user_id=user.id,
            username=user.username,
            role=UserRole(user.role),
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        # Generate token
        token = auth_manager.generate_token(session_info)
        
        # Log successful login
        audit_logger.log_authentication_event(
            AuditEventType.USER_LOGIN,
            f"User logged in successfully: {request.username}",
            user_id=user.id,
            username=request.username,
            session_id=session_info.session_id,
            client_ip=client_ip,
            user_agent=user_agent,
            success=True
        )
        
        return LoginResponse(
            success=True,
            message="Login successful",
            token=token,
            user_info={
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "permissions": [p.value for p in session_info.permissions]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for user {request.username}: {e}")
        audit_logger.log_authentication_event(
            AuditEventType.AUTH_FAILED,
            f"Login system error for user: {request.username}",
            username=request.username,
            client_ip=client_ip,
            user_agent=user_agent,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication system error"
        )


@auth_router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: LogoutRequest,
    session_info: SessionInfo = Depends(get_current_session)
):
    """
    Logout user and invalidate session.
    
    Args:
        request: Logout request data
        session_info: Current session information
        
    Returns:
        LogoutResponse confirming logout
    """
    auth_manager = get_auth_manager()
    audit_logger = get_audit_logger()
    
    try:
        # Use session from request or current session
        session_id = request.session_id or session_info.session_id
        
        # Invalidate session
        await auth_manager._invalidate_session(session_id, "User logout")
        
        # Log logout
        audit_logger.log_authentication_event(
            AuditEventType.USER_LOGOUT,
            f"User logged out: {session_info.username}",
            user_id=session_info.user_id,
            username=session_info.username,
            session_id=session_id,
            success=True
        )
        
        return LogoutResponse(
            success=True,
            message="Logout successful"
        )
        
    except Exception as e:
        logger.error(f"Logout error for session {session_info.session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@auth_router.get("/me", response_model=Dict[str, Any])
async def get_current_user(session_info: SessionInfo = Depends(get_current_session)):
    """
    Get current user information.
    
    Args:
        session_info: Current session information
        
    Returns:
        Current user information
    """
    return {
        "user_id": session_info.user_id,
        "username": session_info.username,
        "role": session_info.role.value,
        "permissions": [p.value for p in session_info.permissions],
        "session_id": session_info.session_id,
        "created_at": session_info.created_at.isoformat(),
        "expires_at": session_info.expires_at.isoformat(),
        "last_activity": session_info.last_activity.isoformat()
    }


@auth_router.post("/check-permissions", response_model=PermissionCheckResponse)
async def check_permissions(
    request: PermissionCheckRequest,
    session_info: SessionInfo = Depends(get_current_session)
):
    """
    Check if current user has specific permissions.
    
    Args:
        request: Permission check request
        session_info: Current session information
        
    Returns:
        Permission check results
    """
    authz_manager = get_authz_manager()
    
    missing_permissions = []
    for permission in request.permissions:
        if not authz_manager.check_permission(session_info, permission):
            missing_permissions.append(permission)
    
    return PermissionCheckResponse(
        has_permissions=len(missing_permissions) == 0,
        missing_permissions=missing_permissions
    )


# User management endpoints (admin only)

@auth_router.post("/users", response_model=UserResponse)
async def create_user(
    request: UserCreateRequest,
    session_info: SessionInfo = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_database_session)
):
    """
    Create a new user (admin only).
    
    Args:
        request: User creation request
        session_info: Current session information
        db: Database session
        
    Returns:
        Created user information
    """
    audit_logger = get_audit_logger()
    
    try:
        # Check if username already exists
        existing_user = db.query(UserModel).filter(UserModel.username == request.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        
        # Check if email already exists
        if request.email:
            existing_email = db.query(UserModel).filter(UserModel.email == request.email).first()
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )
        
        # Create user
        user_id = str(uuid4())
        password_hash = hashlib.sha256(request.password.encode()).hexdigest()
        
        user = UserModel(
            id=user_id,
            username=request.username,
            email=request.email,
            password_hash=password_hash,
            role=request.role.value,
            enabled=int(request.enabled)
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Log user creation
        audit_logger.log_configuration_change(
            action="create",
            resource_type="user",
            resource_id=user_id,
            description=f"User created: {request.username} (role: {request.role.value})",
            session_info=session_info,
            new_values={
                "username": request.username,
                "email": request.email,
                "role": request.role.value,
                "enabled": request.enabled
            }
        )
        
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=UserRole(user.role),
            enabled=bool(user.enabled),
            created_at=user.created_at,
            last_login=user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user {request.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User creation failed"
        )


@auth_router.get("/users", response_model=List[UserResponse])
async def list_users(
    session_info: SessionInfo = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_database_session)
):
    """
    List all users (admin only).
    
    Args:
        session_info: Current session information
        db: Database session
        
    Returns:
        List of users
    """
    try:
        users = db.query(UserModel).all()
        
        return [
            UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                role=UserRole(user.role),
                enabled=bool(user.enabled),
                created_at=user.created_at,
                last_login=user.last_login
            )
            for user in users
        ]
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


@auth_router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    session_info: SessionInfo = Depends(require_role(UserRole.ADMIN))
):
    """
    List active sessions (admin only).
    
    Args:
        session_info: Current session information
        
    Returns:
        List of active sessions
    """
    auth_manager = get_auth_manager()
    
    try:
        sessions = []
        for session in auth_manager.active_sessions.values():
            sessions.append(SessionResponse(
                session_id=session.session_id,
                user_id=session.user_id,
                username=session.username,
                role=session.role,
                created_at=session.created_at,
                expires_at=session.expires_at,
                last_activity=session.last_activity,
                client_ip=session.client_ip
            ))
        
        return sessions
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list sessions"
        )


@auth_router.get("/stats", response_model=Dict[str, Any])
async def get_auth_stats(
    session_info: SessionInfo = Depends(require_role(UserRole.ADMIN))
):
    """
    Get authentication statistics (admin only).
    
    Args:
        session_info: Current session information
        
    Returns:
        Authentication statistics
    """
    auth_manager = get_auth_manager()
    
    try:
        return auth_manager.get_session_statistics()
        
    except Exception as e:
        logger.error(f"Error getting auth stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get authentication statistics"
        )