"""
Health monitoring API endpoints.

This module provides REST API endpoints for health status and metrics,
including Prometheus format export for monitoring integration.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .health_monitor import health_monitor, HealthStatus, SystemMetrics, ComponentMetrics
from .diagnostics import diagnostic_manager, run_system_diagnostics, run_quick_health_check, get_diagnostic_history

logger = logging.getLogger(__name__)

# Create API router
health_router = APIRouter(prefix="/api/health", tags=["health"])


class HealthSummaryResponse(BaseModel):
    """Health summary response model."""
    overall_status: str
    timestamp: str
    uptime_seconds: float
    monitoring_active: bool
    component_health: Dict[str, Dict[str, Any]]
    system_metrics: Optional[Dict[str, Any]]
    component_metrics: Dict[str, Dict[str, Any]]


class ComponentHealthResponse(BaseModel):
    """Individual component health response model."""
    component: str
    status: str
    message: str
    timestamp: str
    metrics: Dict[str, Any]
    latency_ms: Optional[float]


class SystemMetricsResponse(BaseModel):
    """System metrics response model."""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    load_average: List[float]
    timestamp: str


class ComponentMetricsResponse(BaseModel):
    """Component metrics response model."""
    component: str
    processing_rate: float
    average_latency_ms: float
    error_rate: float
    queue_size: int
    active_connections: int
    uptime_seconds: float
    timestamp: str


@health_router.get("/", response_model=HealthSummaryResponse)
async def get_health_summary() -> HealthSummaryResponse:
    """
    Get comprehensive health summary for all components.
    
    Returns overall system health status, component health,
    system metrics, and component performance metrics.
    """
    try:
        summary = health_monitor.get_health_summary()
        return HealthSummaryResponse(**summary)
    except Exception as e:
        logger.error(f"Failed to get health summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve health summary")


@health_router.get("/status")
async def get_overall_status() -> Dict[str, str]:
    """
    Get overall system health status.
    
    Returns a simple status indicator for quick health checks.
    """
    try:
        status = health_monitor.get_overall_health()
        return {
            "status": status.value,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get overall status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system status")


@health_router.get("/components")
async def get_all_component_health() -> Dict[str, ComponentHealthResponse]:
    """
    Get health status for all monitored components.
    
    Returns detailed health information for each component.
    """
    try:
        components = {}
        for component_name, health_check in health_monitor.health_checks.items():
            components[component_name] = ComponentHealthResponse(
                component=health_check.component,
                status=health_check.status.value,
                message=health_check.message,
                timestamp=health_check.timestamp.isoformat(),
                metrics=health_check.metrics,
                latency_ms=health_check.latency_ms
            )
        return components
    except Exception as e:
        logger.error(f"Failed to get component health: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve component health")


@health_router.get("/components/{component_name}", response_model=ComponentHealthResponse)
async def get_component_health(component_name: str) -> ComponentHealthResponse:
    """
    Get health status for a specific component.
    
    Args:
        component_name: Name of the component to check
        
    Returns:
        Detailed health information for the specified component
    """
    try:
        health_check = health_monitor.get_component_health(component_name)
        if not health_check:
            raise HTTPException(status_code=404, detail=f"Component '{component_name}' not found")
            
        return ComponentHealthResponse(
            component=health_check.component,
            status=health_check.status.value,
            message=health_check.message,
            timestamp=health_check.timestamp.isoformat(),
            metrics=health_check.metrics,
            latency_ms=health_check.latency_ms
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get health for component {component_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve component health")


@health_router.get("/metrics/system", response_model=List[SystemMetricsResponse])
async def get_system_metrics(
    hours: int = Query(default=1, ge=1, le=24, description="Hours of metrics to retrieve")
) -> List[SystemMetricsResponse]:
    """
    Get system resource metrics for the specified time period.
    
    Args:
        hours: Number of hours of metrics to retrieve (1-24)
        
    Returns:
        List of system metrics over the specified time period
    """
    try:
        metrics = health_monitor.get_system_metrics(hours=hours)
        return [
            SystemMetricsResponse(
                cpu_percent=m.cpu_percent,
                memory_percent=m.memory_percent,
                memory_used_mb=m.memory_used_mb,
                memory_total_mb=m.memory_total_mb,
                disk_percent=m.disk_percent,
                disk_used_gb=m.disk_used_gb,
                disk_total_gb=m.disk_total_gb,
                load_average=m.load_average,
                timestamp=m.timestamp.isoformat()
            )
            for m in metrics
        ]
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system metrics")


@health_router.get("/metrics/components")
async def get_all_component_metrics() -> Dict[str, ComponentMetricsResponse]:
    """
    Get performance metrics for all components.
    
    Returns performance metrics including processing rates,
    latency, error rates, and resource usage.
    """
    try:
        components = {}
        for component_name, metrics in health_monitor.component_metrics.items():
            components[component_name] = ComponentMetricsResponse(
                component=metrics.component,
                processing_rate=metrics.processing_rate,
                average_latency_ms=metrics.average_latency_ms,
                error_rate=metrics.error_rate,
                queue_size=metrics.queue_size,
                active_connections=metrics.active_connections,
                uptime_seconds=metrics.uptime_seconds,
                timestamp=metrics.timestamp.isoformat()
            )
        return components
    except Exception as e:
        logger.error(f"Failed to get component metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve component metrics")


@health_router.get("/metrics/components/{component_name}", response_model=ComponentMetricsResponse)
async def get_component_metrics(component_name: str) -> ComponentMetricsResponse:
    """
    Get performance metrics for a specific component.
    
    Args:
        component_name: Name of the component
        
    Returns:
        Performance metrics for the specified component
    """
    try:
        metrics = health_monitor.get_component_metrics(component_name)
        if not metrics:
            raise HTTPException(status_code=404, detail=f"Metrics for component '{component_name}' not found")
            
        return ComponentMetricsResponse(
            component=metrics.component,
            processing_rate=metrics.processing_rate,
            average_latency_ms=metrics.average_latency_ms,
            error_rate=metrics.error_rate,
            queue_size=metrics.queue_size,
            active_connections=metrics.active_connections,
            uptime_seconds=metrics.uptime_seconds,
            timestamp=metrics.timestamp.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get metrics for component {component_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve component metrics")


@health_router.get("/metrics/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics() -> str:
    """
    Export metrics in Prometheus format.
    
    Returns metrics in Prometheus text format for scraping
    by Prometheus monitoring systems.
    """
    try:
        metrics_lines = []
        timestamp = int(datetime.now().timestamp() * 1000)
        
        # Overall health status (0=unknown, 1=healthy, 2=warning, 3=critical)
        overall_status = health_monitor.get_overall_health()
        status_value = {
            HealthStatus.UNKNOWN: 0,
            HealthStatus.HEALTHY: 1,
            HealthStatus.WARNING: 2,
            HealthStatus.CRITICAL: 3
        }.get(overall_status, 0)
        
        metrics_lines.append("# HELP threatlens_health_status Overall system health status")
        metrics_lines.append("# TYPE threatlens_health_status gauge")
        metrics_lines.append(f"threatlens_health_status {status_value} {timestamp}")
        
        # Component health status
        metrics_lines.append("# HELP threatlens_component_health Component health status")
        metrics_lines.append("# TYPE threatlens_component_health gauge")
        for component_name, health_check in health_monitor.health_checks.items():
            component_status_value = {
                HealthStatus.UNKNOWN: 0,
                HealthStatus.HEALTHY: 1,
                HealthStatus.WARNING: 2,
                HealthStatus.CRITICAL: 3
            }.get(health_check.status, 0)
            metrics_lines.append(
                f'threatlens_component_health{{component="{component_name}"}} {component_status_value} {timestamp}'
            )
        
        # System metrics
        if health_monitor.system_metrics_history:
            latest_system = health_monitor.system_metrics_history[-1]
            
            metrics_lines.append("# HELP threatlens_cpu_percent CPU usage percentage")
            metrics_lines.append("# TYPE threatlens_cpu_percent gauge")
            metrics_lines.append(f"threatlens_cpu_percent {latest_system.cpu_percent} {timestamp}")
            
            metrics_lines.append("# HELP threatlens_memory_percent Memory usage percentage")
            metrics_lines.append("# TYPE threatlens_memory_percent gauge")
            metrics_lines.append(f"threatlens_memory_percent {latest_system.memory_percent} {timestamp}")
            
            metrics_lines.append("# HELP threatlens_disk_percent Disk usage percentage")
            metrics_lines.append("# TYPE threatlens_disk_percent gauge")
            metrics_lines.append(f"threatlens_disk_percent {latest_system.disk_percent} {timestamp}")
            
            if latest_system.load_average:
                metrics_lines.append("# HELP threatlens_load_average System load average (1 minute)")
                metrics_lines.append("# TYPE threatlens_load_average gauge")
                metrics_lines.append(f"threatlens_load_average {latest_system.load_average[0]} {timestamp}")
        
        # Component performance metrics
        for component_name, metrics in health_monitor.component_metrics.items():
            metrics_lines.append("# HELP threatlens_processing_rate Processing rate (items per second)")
            metrics_lines.append("# TYPE threatlens_processing_rate gauge")
            metrics_lines.append(
                f'threatlens_processing_rate{{component="{component_name}"}} {metrics.processing_rate} {timestamp}'
            )
            
            metrics_lines.append("# HELP threatlens_average_latency Average processing latency (milliseconds)")
            metrics_lines.append("# TYPE threatlens_average_latency gauge")
            metrics_lines.append(
                f'threatlens_average_latency{{component="{component_name}"}} {metrics.average_latency_ms} {timestamp}'
            )
            
            metrics_lines.append("# HELP threatlens_error_rate Error rate (errors per minute)")
            metrics_lines.append("# TYPE threatlens_error_rate gauge")
            metrics_lines.append(
                f'threatlens_error_rate{{component="{component_name}"}} {metrics.error_rate} {timestamp}'
            )
            
            metrics_lines.append("# HELP threatlens_queue_size Current queue size")
            metrics_lines.append("# TYPE threatlens_queue_size gauge")
            metrics_lines.append(
                f'threatlens_queue_size{{component="{component_name}"}} {metrics.queue_size} {timestamp}'
            )
        
        return "\n".join(metrics_lines) + "\n"
        
    except Exception as e:
        logger.error(f"Failed to generate Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate metrics")


@health_router.get("/uptime")
async def get_uptime() -> Dict[str, Any]:
    """
    Get system uptime information.
    
    Returns uptime in seconds and human-readable format.
    """
    try:
        uptime_seconds = (datetime.now() - health_monitor.start_time).total_seconds()
        
        # Convert to human-readable format
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)
        
        return {
            "uptime_seconds": uptime_seconds,
            "uptime_human": f"{days}d {hours}h {minutes}m {seconds}s",
            "start_time": health_monitor.start_time.isoformat(),
            "current_time": datetime.now().isoformat(),
            "monitoring_active": health_monitor.monitoring_active
        }
    except Exception as e:
        logger.error(f"Failed to get uptime: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve uptime information")


# Health check endpoint for load balancers
@health_router.get("/ping")
async def ping() -> Dict[str, str]:
    """
    Simple ping endpoint for load balancer health checks.
    
    Returns a simple OK response if the service is running.
    """
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# Diagnostic endpoints

@health_router.get("/diagnostics/full")
async def run_full_diagnostics() -> Dict[str, Any]:
    """
    Run comprehensive system diagnostics.
    
    Returns detailed diagnostic information including component health,
    performance analysis, error patterns, and troubleshooting recommendations.
    """
    try:
        diagnostics = await run_system_diagnostics()
        
        # Convert to serializable format
        return {
            'timestamp': diagnostics.timestamp.isoformat(),
            'overall_status': diagnostics.overall_status,
            'system_info': diagnostics.system_info,
            'component_diagnostics': {
                name: {
                    'check_name': result.check_name,
                    'status': result.status,
                    'message': result.message,
                    'details': result.details,
                    'timestamp': result.timestamp.isoformat(),
                    'recommendations': result.recommendations,
                    'severity': result.severity
                }
                for name, result in diagnostics.component_diagnostics.items()
            },
            'performance_metrics': diagnostics.performance_metrics,
            'error_analysis': diagnostics.error_analysis,
            'resource_usage': diagnostics.resource_usage,
            'recommendations': diagnostics.recommendations
        }
        
    except Exception as e:
        logger.error(f"Failed to run full diagnostics: {e}")
        raise HTTPException(status_code=500, detail=f"Diagnostic failed: {str(e)}")


@health_router.get("/diagnostics/quick")
async def run_quick_diagnostics() -> Dict[str, Any]:
    """
    Run quick health diagnostics for immediate status check.
    
    Returns basic system status and resource usage information.
    """
    try:
        return await run_quick_health_check()
    except Exception as e:
        logger.error(f"Failed to run quick diagnostics: {e}")
        raise HTTPException(status_code=500, detail=f"Quick diagnostic failed: {str(e)}")


@health_router.get("/diagnostics/history")
async def get_diagnostics_history(
    limit: int = Query(default=10, ge=1, le=100, description="Number of diagnostic records to return")
) -> List[Dict[str, Any]]:
    """
    Get diagnostic history.
    
    Args:
        limit: Number of diagnostic records to return
        
    Returns:
        List of recent diagnostic summaries
    """
    try:
        return get_diagnostic_history(limit)
    except Exception as e:
        logger.error(f"Failed to get diagnostic history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get diagnostic history: {str(e)}")


@health_router.get("/diagnostics/errors")
async def get_error_diagnostics() -> Dict[str, Any]:
    """
    Get detailed error analysis and troubleshooting information.
    
    Returns error statistics, patterns, and recovery information.
    """
    try:
        # Get error statistics from health monitor's error handler
        from .error_handler import error_handler
        
        stats = error_handler.get_error_statistics()
        history = error_handler.get_error_history(limit=50)
        
        # Analyze error patterns
        error_patterns = {}
        category_trends = {}
        
        for error in history:
            category = error['category']
            if category not in category_trends:
                category_trends[category] = []
            category_trends[category].append(error['timestamp'])
        
        # Calculate error rates by category
        for category, timestamps in category_trends.items():
            recent_count = len([ts for ts in timestamps[-10:]])  # Last 10 errors
            error_patterns[category] = {
                'total_count': len(timestamps),
                'recent_count': recent_count,
                'trend': 'increasing' if recent_count > len(timestamps) * 0.5 else 'stable'
            }
        
        return {
            'error_statistics': stats,
            'error_patterns': error_patterns,
            'recent_errors': history[-20:],  # Last 20 errors
            'troubleshooting_tips': [
                'Check system resource usage if errors are increasing',
                'Review error patterns to identify recurring issues',
                'Monitor recovery success rate for system stability',
                'Investigate critical errors immediately',
                'Check component health if specific categories dominate'
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get error diagnostics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get error diagnostics: {str(e)}")


@health_router.get("/diagnostics/performance")
async def get_performance_diagnostics() -> Dict[str, Any]:
    """
    Get performance analysis and optimization recommendations.
    
    Returns performance metrics, trends, and optimization suggestions.
    """
    try:
        # Get system metrics from health monitor
        if not health_monitor.system_metrics_history:
            return {
                'error': 'No performance metrics available',
                'recommendations': ['Start health monitoring to collect performance data']
            }
        
        # Analyze recent performance
        recent_metrics = health_monitor.system_metrics_history[-20:]  # Last 20 samples
        
        if not recent_metrics:
            return {
                'error': 'No recent performance metrics available',
                'recommendations': ['Wait for metrics collection to begin']
            }
        
        # Calculate performance statistics
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        disk_values = [m.disk_percent for m in recent_metrics]
        
        performance_analysis = {
            'cpu_stats': {
                'average': sum(cpu_values) / len(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values),
                'current': cpu_values[-1] if cpu_values else 0
            },
            'memory_stats': {
                'average': sum(memory_values) / len(memory_values),
                'max': max(memory_values),
                'min': min(memory_values),
                'current': memory_values[-1] if memory_values else 0
            },
            'disk_stats': {
                'average': sum(disk_values) / len(disk_values),
                'max': max(disk_values),
                'min': min(disk_values),
                'current': disk_values[-1] if disk_values else 0
            },
            'sample_count': len(recent_metrics),
            'time_span_minutes': (recent_metrics[-1].timestamp - recent_metrics[0].timestamp).total_seconds() / 60 if len(recent_metrics) > 1 else 0
        }
        
        # Generate performance recommendations
        recommendations = []
        
        if performance_analysis['cpu_stats']['average'] > 80:
            recommendations.append('High CPU usage detected - consider optimizing processing algorithms')
        
        if performance_analysis['memory_stats']['average'] > 85:
            recommendations.append('High memory usage detected - check for memory leaks or reduce queue sizes')
        
        if performance_analysis['disk_stats']['current'] > 90:
            recommendations.append('Disk space critically low - clean up old files or add storage')
        
        if not recommendations:
            recommendations.append('System performance is within normal parameters')
        
        return {
            'performance_analysis': performance_analysis,
            'recommendations': recommendations,
            'optimization_tips': [
                'Monitor CPU usage trends to identify processing bottlenecks',
                'Track memory usage patterns to detect potential leaks',
                'Implement log rotation to manage disk space',
                'Consider scaling resources if usage consistently high',
                'Use performance profiling for detailed optimization'
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get performance diagnostics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get performance diagnostics: {str(e)}")


@health_router.post("/diagnostics/clear-history")
async def clear_diagnostic_history() -> Dict[str, str]:
    """
    Clear diagnostic and error history.
    
    This endpoint clears all stored diagnostic history and error records.
    Use with caution as this will remove troubleshooting data.
    """
    try:
        # Clear diagnostic history
        diagnostic_manager.diagnostic_history.clear()
        
        # Clear error history
        from .error_handler import error_handler
        error_handler.clear_error_history()
        
        logger.info("Cleared diagnostic and error history")
        
        return {
            'message': 'Diagnostic and error history cleared successfully',
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to clear diagnostic history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear history: {str(e)}")