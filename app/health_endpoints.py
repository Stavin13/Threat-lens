"""
Health check endpoints for ThreatLens system monitoring.

This module provides comprehensive health check endpoints for monitoring
system status, component health, and performance metrics.
"""
import asyncio
import psutil
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_database_session, check_database_health
from app.logging_config import get_logger
from app.error_handling import create_health_check_error, with_error_handling
from app.middleware import get_metrics_middleware
from app.schemas import HealthCheckResponse

logger = get_logger(__name__)

# Create router for health endpoints
health_router = APIRouter(prefix="/api/health", tags=["health"])


class HealthChecker:
    """Comprehensive health checking system."""
    
    def __init__(self):
        self.start_time = time.time()
        self.logger = get_logger(f"{__name__}.HealthChecker")
        self.component_checkers = {}
        self.last_check_results = {}
        self.check_cache_duration = 30  # Cache results for 30 seconds
    
    def register_component_checker(self, name: str, checker_func):
        """
        Register a health checker for a component.
        
        Args:
            name: Component name
            checker_func: Async function that returns health status
        """
        self.component_checkers[name] = checker_func
        self.logger.info(f"Registered health checker for component: {name}")
    
    async def check_component_health(self, component_name: str) -> Dict[str, Any]:
        """
        Check health of a specific component.
        
        Args:
            component_name: Name of component to check
            
        Returns:
            Health status dictionary
        """
        if component_name not in self.component_checkers:
            return {
                'status': 'unknown',
                'message': f'No health checker registered for {component_name}',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        
        try:
            start_time = time.time()
            checker = self.component_checkers[component_name]
            
            # Run the health check with timeout
            result = await asyncio.wait_for(checker(), timeout=10.0)
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Ensure result has required fields
            if isinstance(result, dict):
                result.setdefault('status', 'healthy')
                result.setdefault('timestamp', datetime.now(timezone.utc).isoformat())
                result['latency_ms'] = latency_ms
                result['last_check'] = datetime.now(timezone.utc).isoformat()
            else:
                result = {
                    'status': 'healthy' if result else 'unhealthy',
                    'message': str(result),
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'latency_ms': latency_ms,
                    'last_check': datetime.now(timezone.utc).isoformat()
                }
            
            return result
            
        except asyncio.TimeoutError:
            return create_health_check_error(
                component_name,
                Exception("Health check timeout")
            )
        except Exception as e:
            return create_health_check_error(component_name, e)
    
    async def check_all_components(self) -> Dict[str, Dict[str, Any]]:
        """
        Check health of all registered components.
        
        Returns:
            Dictionary of component health statuses
        """
        # Check cache first
        current_time = time.time()
        if (hasattr(self, '_last_full_check_time') and 
            current_time - self._last_full_check_time < self.check_cache_duration and
            self.last_check_results):
            return self.last_check_results
        
        results = {}
        
        # Run all health checks concurrently
        if self.component_checkers:
            tasks = {
                name: self.check_component_health(name)
                for name in self.component_checkers.keys()
            }
            
            completed_results = await asyncio.gather(
                *tasks.values(),
                return_exceptions=True
            )
            
            for name, result in zip(tasks.keys(), completed_results):
                if isinstance(result, Exception):
                    results[name] = create_health_check_error(name, result)
                else:
                    results[name] = result
        
        # Cache results
        self.last_check_results = results
        self._last_full_check_time = current_time
        
        return results
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system resource metrics.
        
        Returns:
            System metrics dictionary
        """
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Network metrics (if available)
            network_io = psutil.net_io_counters()
            
            return {
                'cpu_percent': cpu_percent,
                'load_average': list(load_avg),
                'memory_percent': memory.percent,
                'memory_used_mb': memory.used / (1024 * 1024),
                'memory_total_mb': memory.total / (1024 * 1024),
                'memory_available_mb': memory.available / (1024 * 1024),
                'disk_percent': (disk.used / disk.total) * 100,
                'disk_used_gb': disk.used / (1024 ** 3),
                'disk_total_gb': disk.total / (1024 ** 3),
                'disk_free_gb': disk.free / (1024 ** 3),
                'network_bytes_sent': network_io.bytes_sent if network_io else 0,
                'network_bytes_recv': network_io.bytes_recv if network_io else 0,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get system metrics: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def get_uptime(self) -> float:
        """Get system uptime in seconds."""
        return time.time() - self.start_time


# Global health checker instance
health_checker = HealthChecker()


# Database health checker
async def check_database_health_async() -> Dict[str, Any]:
    """Check database health asynchronously."""
    try:
        health_status = check_database_health()
        return {
            'status': health_status['status'],
            'message': f"Database connection: {health_status['status']}",
            'details': health_status
        }
    except Exception as e:
        return create_health_check_error('database', e)


# Register built-in health checkers
health_checker.register_component_checker('database', check_database_health_async)


@health_router.get("/", response_model=HealthCheckResponse)
async def health_check_summary():
    """
    Get overall system health summary.
    
    Returns:
        Comprehensive health check response
    """
    try:
        # Check all components
        component_health = await health_checker.check_all_components()
        
        # Determine overall status
        overall_status = "healthy"
        for component_status in component_health.values():
            if component_status.get('status') == 'critical':
                overall_status = "critical"
                break
            elif component_status.get('status') in ['unhealthy', 'warning']:
                overall_status = "degraded"
        
        # Get system metrics
        system_metrics = health_checker.get_system_metrics()
        
        # Get component metrics from middleware
        component_metrics = {}
        metrics_middleware = get_metrics_middleware()
        if metrics_middleware:
            api_metrics = metrics_middleware.get_metrics()
            component_metrics['api'] = {
                'component': 'api',
                'processing_rate': api_metrics['total_requests'] / max(health_checker.get_uptime(), 1),
                'average_latency_ms': api_metrics['average_processing_time'] * 1000,
                'error_rate': api_metrics['error_rate'] * 60,  # errors per minute
                'queue_size': 0,  # API doesn't have a queue
                'active_connections': 0,  # Would need WebSocket manager for this
                'uptime_seconds': health_checker.get_uptime(),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        
        return HealthCheckResponse(
            status=overall_status,
            database=check_database_health(),
            realtime={
                'overall_status': overall_status,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'uptime_seconds': health_checker.get_uptime(),
                'monitoring_active': True,
                'component_health': component_health,
                'system_metrics': system_metrics,
                'component_metrics': component_metrics
            },
            timestamp=datetime.now(timezone.utc)
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@health_router.get("/components")
async def get_component_health():
    """
    Get detailed health status for all components.
    
    Returns:
        Dictionary of component health statuses
    """
    try:
        return await health_checker.check_all_components()
    except Exception as e:
        logger.error(f"Component health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Component health check failed: {str(e)}"
        )


@health_router.get("/components/{component_name}")
async def get_component_health_detail(component_name: str):
    """
    Get detailed health status for a specific component.
    
    Args:
        component_name: Name of the component to check
        
    Returns:
        Component health status
    """
    try:
        result = await health_checker.check_component_health(component_name)
        if result.get('status') == 'unknown':
            raise HTTPException(
                status_code=404,
                detail=f"Component '{component_name}' not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Component health check failed for {component_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed for component '{component_name}': {str(e)}"
        )


@health_router.get("/metrics/system")
async def get_system_metrics(hours: int = Query(1, ge=1, le=24)):
    """
    Get system resource metrics.
    
    Args:
        hours: Number of hours of historical data (placeholder for future implementation)
        
    Returns:
        System metrics data
    """
    try:
        metrics = health_checker.get_system_metrics()
        
        # For now, return current metrics
        # In the future, this could return historical data
        return {
            'current': metrics,
            'period_hours': hours,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system metrics: {str(e)}"
        )


@health_router.get("/metrics/components")
async def get_component_metrics():
    """
    Get performance metrics for all components.
    
    Returns:
        Component performance metrics
    """
    try:
        metrics = {}
        
        # Get API metrics from middleware
        metrics_middleware = get_metrics_middleware()
        if metrics_middleware:
            api_metrics = metrics_middleware.get_metrics()
            metrics['api'] = {
                'component': 'api',
                'total_requests': api_metrics['total_requests'],
                'total_errors': api_metrics['total_errors'],
                'error_rate': api_metrics['error_rate'],
                'average_processing_time_ms': api_metrics['average_processing_time'] * 1000,
                'endpoint_metrics': api_metrics['endpoint_metrics'],
                'uptime_seconds': health_checker.get_uptime(),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        
        # Add database metrics
        try:
            with get_database_session() as db:
                db_stats = db.execute(text("""
                    SELECT 
                        'database' as component,
                        COUNT(*) as total_records,
                        0 as error_count,
                        0 as average_latency_ms
                    FROM (
                        SELECT id FROM raw_logs
                        UNION ALL
                        SELECT id FROM events
                        UNION ALL
                        SELECT id FROM ai_analysis
                    ) combined
                """)).first()
                
                if db_stats:
                    metrics['database'] = {
                        'component': 'database',
                        'total_records': db_stats[1],
                        'error_count': db_stats[2],
                        'average_latency_ms': db_stats[3],
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
        except Exception as db_error:
            logger.warning(f"Failed to get database metrics: {db_error}")
            metrics['database'] = {
                'component': 'database',
                'error': str(db_error),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get component metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get component metrics: {str(e)}"
        )


@health_router.get("/metrics/prometheus")
async def get_prometheus_metrics():
    """
    Get metrics in Prometheus format for monitoring integration.
    
    Returns:
        Prometheus-formatted metrics
    """
    try:
        metrics_lines = []
        
        # System metrics
        system_metrics = health_checker.get_system_metrics()
        if 'error' not in system_metrics:
            metrics_lines.extend([
                f"# HELP threatlens_cpu_percent CPU usage percentage",
                f"# TYPE threatlens_cpu_percent gauge",
                f"threatlens_cpu_percent {system_metrics['cpu_percent']}",
                f"",
                f"# HELP threatlens_memory_percent Memory usage percentage",
                f"# TYPE threatlens_memory_percent gauge",
                f"threatlens_memory_percent {system_metrics['memory_percent']}",
                f"",
                f"# HELP threatlens_disk_percent Disk usage percentage",
                f"# TYPE threatlens_disk_percent gauge",
                f"threatlens_disk_percent {system_metrics['disk_percent']}",
                f"",
                f"# HELP threatlens_uptime_seconds System uptime in seconds",
                f"# TYPE threatlens_uptime_seconds counter",
                f"threatlens_uptime_seconds {health_checker.get_uptime()}",
                f""
            ])
        
        # API metrics
        metrics_middleware = get_metrics_middleware()
        if metrics_middleware:
            api_metrics = metrics_middleware.get_metrics()
            metrics_lines.extend([
                f"# HELP threatlens_http_requests_total Total HTTP requests",
                f"# TYPE threatlens_http_requests_total counter",
                f"threatlens_http_requests_total {api_metrics['total_requests']}",
                f"",
                f"# HELP threatlens_http_errors_total Total HTTP errors",
                f"# TYPE threatlens_http_errors_total counter",
                f"threatlens_http_errors_total {api_metrics['total_errors']}",
                f"",
                f"# HELP threatlens_http_request_duration_seconds Average HTTP request duration",
                f"# TYPE threatlens_http_request_duration_seconds gauge",
                f"threatlens_http_request_duration_seconds {api_metrics['average_processing_time']}",
                f""
            ])
        
        # Component health metrics
        component_health = await health_checker.check_all_components()
        metrics_lines.extend([
            f"# HELP threatlens_component_health Component health status (1=healthy, 0=unhealthy)",
            f"# TYPE threatlens_component_health gauge"
        ])
        
        for component, health in component_health.items():
            health_value = 1 if health.get('status') == 'healthy' else 0
            metrics_lines.append(f'threatlens_component_health{{component="{component}"}} {health_value}')
        
        return "\n".join(metrics_lines)
        
    except Exception as e:
        logger.error(f"Failed to generate Prometheus metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate Prometheus metrics: {str(e)}"
        )


@health_router.post("/components/{component_name}/register")
async def register_component_checker(component_name: str):
    """
    Register a new component health checker.
    
    Args:
        component_name: Name of the component
        
    Returns:
        Registration confirmation
    """
    # This is a placeholder for dynamic component registration
    # In a real implementation, this would accept a health check function
    return {
        'message': f'Component registration endpoint for {component_name}',
        'note': 'Dynamic registration not implemented in this version',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


# Export the health checker for use in other modules
__all__ = ['health_router', 'health_checker']