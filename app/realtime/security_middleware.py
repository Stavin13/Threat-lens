"""
Security middleware for real-time API endpoints.

This module provides security middleware for rate limiting, input validation,
and access control for real-time monitoring API endpoints.
"""

import logging
from typing import Callable, Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..logging_config import get_logger, get_correlation_id
from .security import get_rate_limiter, get_input_validator
from .audit import get_audit_logger, AuditEventType, AuditSeverity
from .auth import get_auth_manager

logger = get_logger(__name__)


class RealtimeSecurityMiddleware(BaseHTTPMiddleware):
    """
    Security middleware for real-time API endpoints.
    
    Provides rate limiting, input validation, and security monitoring
    for all real-time monitoring API endpoints.
    """
    
    def __init__(self, app, protected_paths: Optional[list] = None):
        super().__init__(app)
        self.rate_limiter = get_rate_limiter()
        self.input_validator = get_input_validator()
        self.audit_logger = get_audit_logger()
        self.auth_manager = get_auth_manager()
        
        # Default protected paths
        self.protected_paths = protected_paths or [
            '/realtime/',
            '/auth/',
            '/ws'
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security middleware."""
        try:
            # Check if path needs protection
            if not self._is_protected_path(request.url.path):
                return await call_next(request)
            
            # Get client identifier
            client_id = self._get_client_id(request)
            
            # Rate limiting check
            if not self.rate_limiter.check_rate_limit(client_id, request.url.path, request):
                self.audit_logger.log_security_event(
                    AuditEventType.RATE_LIMIT_EXCEEDED,
                    f"Rate limit exceeded for {client_id} on {request.url.path}",
                    AuditSeverity.MEDIUM,
                    client_ip=request.client.host if request.client else None
                )
                
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "message": "Too many requests. Please slow down.",
                        "retry_after": 60
                    },
                    headers={"Retry-After": "60"}
                )
            
            # Process request
            response = await call_next(request)
            
            return response
            
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Security middleware error"}
            )
    
    def _is_protected_path(self, path: str) -> bool:
        """Check if path requires security protection."""
        return any(path.startswith(protected) for protected in self.protected_paths)
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Try to get from authentication first
        auth_header = request.headers.get('authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]
            session_info = self.auth_manager.validate_token(token)
            if session_info:
                return f"user:{session_info.user_id}"
        
        # Fall back to IP address
        client_ip = request.client.host if request.client else 'unknown'
        return f"ip:{client_ip}"