"""
Middleware for ThreatLens FastAPI application.

This module provides middleware for request correlation IDs, error handling,
logging, and other cross-cutting concerns.
"""
import time
import uuid
import logging
import re
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from app.logging_config import get_logger, set_correlation_id, get_correlation_id

logger = get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation IDs to requests."""
    
    def __init__(self, app, header_name: str = "X-Correlation-ID"):
        super().__init__(app)
        self.header_name = header_name
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        # Get correlation ID from header or generate new one
        correlation_id = request.headers.get(self.header_name)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Set correlation ID in context
        set_correlation_id(correlation_id)
        
        # Process request
        response = await call_next(request)
        
        # Add correlation ID to response headers
        response.headers[self.header_name] = correlation_id
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses."""
    
    def __init__(self, app, log_body: bool = False, max_body_size: int = 1024):
        super().__init__(app)
        self.log_body = log_body
        self.max_body_size = max_body_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        start_time = time.time()
        correlation_id = get_correlation_id()
        
        # Log request
        request_data = {
            'method': request.method,
            'url': str(request.url),
            'path': request.url.path,
            'query_params': dict(request.query_params),
            'headers': dict(request.headers),
            'client_host': request.client.host if request.client else None,
            'correlation_id': correlation_id
        }
        
        # Optionally log request body for non-GET requests
        if self.log_body and request.method not in ['GET', 'HEAD', 'OPTIONS']:
            try:
                body = await request.body()
                if len(body) <= self.max_body_size:
                    request_data['body_size'] = len(body)
                    # Don't log actual body content for security reasons
                else:
                    request_data['body_size'] = len(body)
                    request_data['body_truncated'] = True
            except Exception as e:
                request_data['body_error'] = str(e)
        
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={'request_data': request_data}
        )
        
        # Process request
        try:
            response = await call_next(request)
            processing_time = time.time() - start_time
            
            # Log response
            response_data = {
                'status_code': response.status_code,
                'processing_time_seconds': processing_time,
                'response_headers': dict(response.headers),
                'correlation_id': correlation_id
            }
            
            # Log level based on status code
            if response.status_code >= 500:
                log_level = 'error'
            elif response.status_code >= 400:
                log_level = 'warning'
            else:
                log_level = 'info'
            
            getattr(logger, log_level)(
                f"Request completed: {request.method} {request.url.path} - {response.status_code} ({processing_time:.3f}s)",
                extra={'response_data': response_data}
            )
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {type(e).__name__} ({processing_time:.3f}s)",
                exc_info=True,
                extra={
                    'error_data': {
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'processing_time_seconds': processing_time,
                        'correlation_id': correlation_id
                    }
                }
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add comprehensive security headers to responses."""
    
    def __init__(self, app, strict_csp: bool = False):
        super().__init__(app)
        self.strict_csp = strict_csp
        
        # Base security headers
        self.security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'X-Permitted-Cross-Domain-Policies': 'none',
            'X-Download-Options': 'noopen',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=(), payment=(), usb=(), magnetometer=(), gyroscope=()',
        }
        
        # Content Security Policy
        if strict_csp:
            # Strict CSP for production
            self.security_headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self' ws: wss:; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
        else:
            # Relaxed CSP for development
            self.security_headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "font-src 'self' data:; "
                "connect-src 'self' ws: wss: http://localhost:* http://127.0.0.1:*; "
                "frame-ancestors 'none'; "
                "base-uri 'self';"
            )
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        response = await call_next(request)
        
        # Add security headers
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        # Add server header obfuscation
        response.headers['Server'] = 'ThreatLens/1.0'
        
        # Remove potentially sensitive headers
        sensitive_headers = ['X-Powered-By', 'X-AspNet-Version', 'X-AspNetMvc-Version']
        for header in sensitive_headers:
            if header in response.headers:
                del response.headers[header]
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enhanced rate limiting middleware with multiple strategies."""
    
    def __init__(self, app, requests_per_minute: int = 60, burst_limit: int = 10, block_duration: int = 300):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit  # Max requests in 10 seconds
        self.block_duration = block_duration  # Block duration in seconds for repeated violations
        self.request_counts = {}
        self.window_start = {}
        self.burst_counts = {}
        self.burst_window_start = {}
        self.blocked_clients = {}  # Track blocked clients
        self.violation_counts = {}  # Track repeated violations
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        client_ip = request.client.host if request.client else 'unknown'
        current_time = time.time()
        window_duration = 60  # 1 minute window
        burst_window = 10  # 10 second burst window
        
        # Check if client is currently blocked
        if client_ip in self.blocked_clients:
            if current_time < self.blocked_clients[client_ip]:
                remaining_time = int(self.blocked_clients[client_ip] - current_time)
                logger.warning(
                    f"Blocked client {client_ip} attempted request",
                    extra={
                        'blocked_client_data': {
                            'client_ip': client_ip,
                            'remaining_block_time': remaining_time,
                            'correlation_id': get_correlation_id()
                        }
                    }
                )
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=429,
                    detail=f"Client blocked due to repeated rate limit violations. Try again in {remaining_time} seconds.",
                    headers={"Retry-After": str(remaining_time)}
                )
            else:
                # Block expired, remove from blocked list
                del self.blocked_clients[client_ip]
        
        # Initialize or reset burst window for client
        if client_ip not in self.burst_window_start or current_time - self.burst_window_start[client_ip] >= burst_window:
            self.burst_window_start[client_ip] = current_time
            self.burst_counts[client_ip] = 0
        
        # Initialize or reset main window for client
        if client_ip not in self.window_start or current_time - self.window_start[client_ip] >= window_duration:
            self.window_start[client_ip] = current_time
            self.request_counts[client_ip] = 0
        
        # Check burst limit (10 requests in 10 seconds)
        self.burst_counts[client_ip] += 1
        if self.burst_counts[client_ip] > self.burst_limit:
            self._handle_rate_limit_violation(client_ip, "burst", current_time)
            from fastapi import HTTPException
            raise HTTPException(
                status_code=429,
                detail="Burst rate limit exceeded. Please slow down your requests.",
                headers={"Retry-After": "10"}
            )
        
        # Check main rate limit
        self.request_counts[client_ip] += 1
        if self.request_counts[client_ip] > self.requests_per_minute:
            self._handle_rate_limit_violation(client_ip, "rate", current_time)
            from fastapi import HTTPException
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": "60"}
            )
        
        return await call_next(request)
    
    def _handle_rate_limit_violation(self, client_ip: str, violation_type: str, current_time: float):
        """Handle rate limit violations and implement progressive blocking."""
        # Track violations
        if client_ip not in self.violation_counts:
            self.violation_counts[client_ip] = {'count': 0, 'last_violation': 0}
        
        self.violation_counts[client_ip]['count'] += 1
        self.violation_counts[client_ip]['last_violation'] = current_time
        
        violation_count = self.violation_counts[client_ip]['count']
        
        # Progressive blocking: more violations = longer blocks
        if violation_count >= 5:
            block_duration = self.block_duration * 2  # 10 minutes
        elif violation_count >= 3:
            block_duration = self.block_duration  # 5 minutes
        else:
            block_duration = 0  # No blocking for first few violations
        
        if block_duration > 0:
            self.blocked_clients[client_ip] = current_time + block_duration
            logger.error(
                f"Client {client_ip} blocked for {block_duration} seconds due to repeated violations",
                extra={
                    'blocking_data': {
                        'client_ip': client_ip,
                        'violation_type': violation_type,
                        'violation_count': violation_count,
                        'block_duration': block_duration,
                        'correlation_id': get_correlation_id()
                    }
                }
            )
        
        logger.warning(
            f"Rate limit violation for client {client_ip}: {violation_type}",
            extra={
                'rate_limit_data': {
                    'client_ip': client_ip,
                    'violation_type': violation_type,
                    'requests_in_window': self.request_counts.get(client_ip, 0),
                    'burst_requests': self.burst_counts.get(client_ip, 0),
                    'limit': self.requests_per_minute,
                    'burst_limit': self.burst_limit,
                    'violation_count': violation_count,
                    'correlation_id': get_correlation_id()
                }
            }
        )


class HealthCheckMiddleware(BaseHTTPMiddleware):
    """Middleware to handle health check requests efficiently."""
    
    def __init__(self, app, health_path: str = "/health"):
        super().__init__(app)
        self.health_path = health_path
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        # Quick health check response without full processing
        if request.url.path == self.health_path and request.method == "GET":
            from fastapi.responses import JSONResponse
            return JSONResponse(
                content={
                    "status": "healthy",
                    "timestamp": time.time(),
                    "correlation_id": get_correlation_id()
                },
                status_code=200
            )
        
        return await call_next(request)


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate and sanitize request inputs."""
    
    def __init__(self, app, max_request_size: int = 50 * 1024 * 1024):
        super().__init__(app)
        self.max_request_size = max_request_size
        self.dangerous_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',               # JavaScript protocol
            r'vbscript:',                # VBScript protocol
            r'on\w+\s*=',                # Event handlers
            r'expression\s*\(',          # CSS expressions
            r'@import',                  # CSS imports
            r'<iframe[^>]*>',            # Iframes
            r'<object[^>]*>',            # Objects
            r'<embed[^>]*>',             # Embeds
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        # Validate request size
        content_length = request.headers.get('content-length')
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_request_size:
                    logger.warning(
                        f"Request size too large: {size} bytes from {request.client.host if request.client else 'unknown'}",
                        extra={
                            'validation_data': {
                                'client_ip': request.client.host if request.client else 'unknown',
                                'request_size': size,
                                'max_size': self.max_request_size,
                                'correlation_id': get_correlation_id()
                            }
                        }
                    )
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=413,
                        detail=f"Request too large. Maximum size: {self.max_request_size} bytes"
                    )
            except ValueError:
                pass  # Invalid content-length header, let it pass
        
        # Validate query parameters
        for param_name, param_value in request.query_params.items():
            if self._contains_dangerous_patterns(param_value):
                logger.warning(
                    f"Dangerous pattern detected in query parameter '{param_name}': {param_value[:100]}",
                    extra={
                        'validation_data': {
                            'client_ip': request.client.host if request.client else 'unknown',
                            'parameter': param_name,
                            'correlation_id': get_correlation_id()
                        }
                    }
                )
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid characters detected in parameter: {param_name}"
                )
        
        # Validate headers for suspicious content
        suspicious_headers = ['user-agent', 'referer', 'x-forwarded-for']
        for header_name in suspicious_headers:
            header_value = request.headers.get(header_name, '')
            if self._contains_dangerous_patterns(header_value):
                logger.warning(
                    f"Dangerous pattern detected in header '{header_name}': {header_value[:100]}",
                    extra={
                        'validation_data': {
                            'client_ip': request.client.host if request.client else 'unknown',
                            'header': header_name,
                            'correlation_id': get_correlation_id()
                        }
                    }
                )
                # Don't block on headers, just log
        
        return await call_next(request)
    
    def _contains_dangerous_patterns(self, text: str) -> bool:
        """Check if text contains dangerous patterns."""
        if not isinstance(text, str):
            return False
        
        text_lower = text.lower()
        for pattern in self.dangerous_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL):
                return True
        
        return False


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics."""
    
    def __init__(self, app):
        super().__init__(app)
        self.request_count = 0
        self.error_count = 0
        self.total_processing_time = 0.0
        self.endpoint_metrics = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        start_time = time.time()
        endpoint = f"{request.method} {request.url.path}"
        
        # Initialize endpoint metrics if not exists
        if endpoint not in self.endpoint_metrics:
            self.endpoint_metrics[endpoint] = {
                'count': 0,
                'errors': 0,
                'total_time': 0.0,
                'avg_time': 0.0
            }
        
        try:
            response = await call_next(request)
            processing_time = time.time() - start_time
            
            # Update metrics
            self.request_count += 1
            self.total_processing_time += processing_time
            
            endpoint_data = self.endpoint_metrics[endpoint]
            endpoint_data['count'] += 1
            endpoint_data['total_time'] += processing_time
            endpoint_data['avg_time'] = endpoint_data['total_time'] / endpoint_data['count']
            
            if response.status_code >= 400:
                self.error_count += 1
                endpoint_data['errors'] += 1
            
            # Add metrics to response headers (for debugging)
            if logger.isEnabledFor(logging.DEBUG):
                response.headers['X-Processing-Time'] = f"{processing_time:.3f}"
                response.headers['X-Request-Count'] = str(self.request_count)
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            # Update error metrics
            self.error_count += 1
            self.endpoint_metrics[endpoint]['errors'] += 1
            
            logger.debug(
                f"Request metrics - Error in {endpoint}: {processing_time:.3f}s",
                extra={
                    'metrics_data': {
                        'endpoint': endpoint,
                        'processing_time': processing_time,
                        'error_type': type(e).__name__,
                        'total_requests': self.request_count,
                        'total_errors': self.error_count
                    }
                }
            )
            
            raise
    
    def get_metrics(self) -> dict:
        """Get current metrics data."""
        avg_processing_time = (
            self.total_processing_time / self.request_count 
            if self.request_count > 0 else 0.0
        )
        
        return {
            'total_requests': self.request_count,
            'total_errors': self.error_count,
            'error_rate': self.error_count / self.request_count if self.request_count > 0 else 0.0,
            'average_processing_time': avg_processing_time,
            'endpoint_metrics': self.endpoint_metrics.copy()
        }
    
    def reset_metrics(self):
        """Reset all metrics."""
        self.request_count = 0
        self.error_count = 0
        self.total_processing_time = 0.0
        self.endpoint_metrics.clear()


# Global metrics instance
metrics_middleware_instance = None


def get_metrics_middleware() -> MetricsMiddleware:
    """Get the global metrics middleware instance."""
    global metrics_middleware_instance
    return metrics_middleware_instance


def set_metrics_middleware(instance: MetricsMiddleware):
    """Set the global metrics middleware instance."""
    global metrics_middleware_instance
    metrics_middleware_instance = instance