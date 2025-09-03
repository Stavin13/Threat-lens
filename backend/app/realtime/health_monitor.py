"""
Health monitoring system for real-time log detection components.

This module provides comprehensive health monitoring for all real-time components
including file monitoring, queue processing, WebSocket server, and system resources.
"""

import asyncio
import time
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Individual health check result."""
    component: str
    status: HealthStatus
    message: str
    timestamp: datetime
    metrics: Dict[str, Any]
    latency_ms: Optional[float] = None


@dataclass
class SystemMetrics:
    """System resource metrics."""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    load_average: List[float]
    timestamp: datetime


@dataclass
class ComponentMetrics:
    """Component-specific performance metrics."""
    component: str
    processing_rate: float  # items per second
    average_latency_ms: float
    error_rate: float  # errors per minute
    queue_size: int
    active_connections: int
    uptime_seconds: float
    timestamp: datetime


class HealthMonitor:
    """
    Comprehensive health monitoring system for real-time components.
    
    Monitors:
    - File monitoring system health
    - Queue processing performance
    - WebSocket server status
    - System resource usage
    - Component-specific metrics
    """
    
    def __init__(self):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.component_metrics: Dict[str, ComponentMetrics] = {}
        self.system_metrics_history: List[SystemMetrics] = []
        self.health_check_callbacks: Dict[str, Callable] = {}
        self.monitoring_active = False
        self.check_interval = 30  # seconds
        self.metrics_retention_hours = 24
        self.start_time = datetime.now()
        
        # Performance tracking
        self.processing_rates: Dict[str, List[float]] = {}
        self.latency_samples: Dict[str, List[float]] = {}
        self.error_counts: Dict[str, int] = {}
        
    async def start_monitoring(self) -> None:
        """Start the health monitoring system."""
        if self.monitoring_active:
            logger.warning("Health monitoring is already active")
            return
            
        self.monitoring_active = True
        self.start_time = datetime.now()
        logger.info("Starting health monitoring system")
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
        
    async def stop_monitoring(self) -> None:
        """Stop the health monitoring system."""
        self.monitoring_active = False
        logger.info("Stopping health monitoring system")
        
    def register_health_check(self, component: str, callback: Callable) -> None:
        """Register a health check callback for a component."""
        self.health_check_callbacks[component] = callback
        logger.info(f"Registered health check for component: {component}")
        
    def record_processing_event(self, component: str, latency_ms: float) -> None:
        """Record a processing event for metrics calculation."""
        current_time = time.time()
        
        # Initialize tracking lists if needed
        if component not in self.processing_rates:
            self.processing_rates[component] = []
            self.latency_samples[component] = []
            
        # Record processing rate (events per second)
        self.processing_rates[component].append(current_time)
        
        # Record latency
        self.latency_samples[component].append(latency_ms)
        
        # Clean old samples (keep last 5 minutes)
        cutoff_time = current_time - 300
        self.processing_rates[component] = [
            t for t in self.processing_rates[component] if t > cutoff_time
        ]
        self.latency_samples[component] = self.latency_samples[component][-1000:]
        
    def record_error(self, component: str) -> None:
        """Record an error for a component."""
        if component not in self.error_counts:
            self.error_counts[component] = 0
        self.error_counts[component] += 1
        
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                await self._perform_health_checks()
                await self._collect_system_metrics()
                await self._update_component_metrics()
                await self._cleanup_old_metrics()
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                
            await asyncio.sleep(self.check_interval)
            
    async def _perform_health_checks(self) -> None:
        """Perform all registered health checks."""
        for component, callback in self.health_check_callbacks.items():
            try:
                start_time = time.time()
                result = await callback() if asyncio.iscoroutinefunction(callback) else callback()
                latency_ms = (time.time() - start_time) * 1000
                
                if isinstance(result, dict):
                    status = HealthStatus(result.get('status', 'unknown'))
                    message = result.get('message', 'No message')
                    metrics = result.get('metrics', {})
                else:
                    status = HealthStatus.HEALTHY if result else HealthStatus.CRITICAL
                    message = "Health check passed" if result else "Health check failed"
                    metrics = {}
                    
                health_check = HealthCheck(
                    component=component,
                    status=status,
                    message=message,
                    timestamp=datetime.now(),
                    metrics=metrics,
                    latency_ms=latency_ms
                )
                
                self.health_checks[component] = health_check
                
            except Exception as e:
                logger.error(f"Health check failed for {component}: {e}")
                self.health_checks[component] = HealthCheck(
                    component=component,
                    status=HealthStatus.CRITICAL,
                    message=f"Health check error: {str(e)}",
                    timestamp=datetime.now(),
                    metrics={}
                )
                
    async def _collect_system_metrics(self) -> None:
        """Collect system resource metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / (1024 * 1024)
            memory_total_mb = memory.total / (1024 * 1024)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_used_gb = disk.used / (1024 * 1024 * 1024)
            disk_total_gb = disk.total / (1024 * 1024 * 1024)
            
            # Load average (Unix-like systems)
            try:
                load_average = list(psutil.getloadavg())
            except AttributeError:
                # Windows doesn't have load average
                load_average = [0.0, 0.0, 0.0]
                
            metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                memory_total_mb=memory_total_mb,
                disk_percent=disk_percent,
                disk_used_gb=disk_used_gb,
                disk_total_gb=disk_total_gb,
                load_average=load_average,
                timestamp=datetime.now()
            )
            
            self.system_metrics_history.append(metrics)
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            
    async def _update_component_metrics(self) -> None:
        """Update component-specific performance metrics."""
        current_time = time.time()
        
        for component in self.processing_rates.keys():
            try:
                # Calculate processing rate (events per second)
                recent_events = [
                    t for t in self.processing_rates[component] 
                    if t > current_time - 60  # Last minute
                ]
                processing_rate = len(recent_events) / 60.0
                
                # Calculate average latency
                recent_latencies = self.latency_samples[component][-100:]  # Last 100 samples
                avg_latency = sum(recent_latencies) / len(recent_latencies) if recent_latencies else 0.0
                
                # Calculate error rate (errors per minute)
                error_count = self.error_counts.get(component, 0)
                error_rate = error_count / max(1, (current_time - self.start_time.timestamp()) / 60)
                
                # Get component-specific metrics from health checks
                health_check = self.health_checks.get(component, {})
                health_metrics = getattr(health_check, 'metrics', {}) if health_check else {}
                
                queue_size = health_metrics.get('queue_size', 0)
                active_connections = health_metrics.get('active_connections', 0)
                uptime_seconds = current_time - self.start_time.timestamp()
                
                component_metrics = ComponentMetrics(
                    component=component,
                    processing_rate=processing_rate,
                    average_latency_ms=avg_latency,
                    error_rate=error_rate,
                    queue_size=queue_size,
                    active_connections=active_connections,
                    uptime_seconds=uptime_seconds,
                    timestamp=datetime.now()
                )
                
                self.component_metrics[component] = component_metrics
                
            except Exception as e:
                logger.error(f"Failed to update metrics for {component}: {e}")
                
    async def _cleanup_old_metrics(self) -> None:
        """Clean up old metrics to prevent memory growth."""
        cutoff_time = datetime.now() - timedelta(hours=self.metrics_retention_hours)
        
        # Clean system metrics history
        self.system_metrics_history = [
            m for m in self.system_metrics_history 
            if m.timestamp > cutoff_time
        ]
        
        # Reset error counts periodically (every hour)
        if len(self.system_metrics_history) % 120 == 0:  # Every 120 checks (1 hour at 30s intervals)
            self.error_counts.clear()
            
    def get_overall_health(self) -> HealthStatus:
        """Get overall system health status."""
        if not self.health_checks:
            return HealthStatus.UNKNOWN
            
        statuses = [check.status for check in self.health_checks.values()]
        
        if any(status == HealthStatus.CRITICAL for status in statuses):
            return HealthStatus.CRITICAL
        elif any(status == HealthStatus.WARNING for status in statuses):
            return HealthStatus.WARNING
        elif all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN
            
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary."""
        overall_status = self.get_overall_health()
        
        # Get latest system metrics
        latest_system_metrics = self.system_metrics_history[-1] if self.system_metrics_history else None
        
        return {
            'overall_status': overall_status.value,
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
            'monitoring_active': self.monitoring_active,
            'component_health': {
                component: {
                    'status': check.status.value,
                    'message': check.message,
                    'latency_ms': check.latency_ms,
                    'last_check': check.timestamp.isoformat()
                }
                for component, check in self.health_checks.items()
            },
            'system_metrics': asdict(latest_system_metrics) if latest_system_metrics else None,
            'component_metrics': {
                component: asdict(metrics)
                for component, metrics in self.component_metrics.items()
            }
        }
        
    def get_component_health(self, component: str) -> Optional[HealthCheck]:
        """Get health status for a specific component."""
        return self.health_checks.get(component)
        
    def get_system_metrics(self, hours: int = 1) -> List[SystemMetrics]:
        """Get system metrics for the specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            m for m in self.system_metrics_history 
            if m.timestamp > cutoff_time
        ]
        
    def get_component_metrics(self, component: str) -> Optional[ComponentMetrics]:
        """Get performance metrics for a specific component."""
        return self.component_metrics.get(component)


# Global health monitor instance
health_monitor = HealthMonitor()