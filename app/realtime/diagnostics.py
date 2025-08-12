"""
Diagnostic utilities for troubleshooting real-time monitoring issues.

This module provides comprehensive diagnostic tools for identifying,
analyzing, and resolving issues in the real-time log processing system.
"""

import asyncio
import logging
import psutil
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict, deque

from .error_handler import ErrorHandler, ErrorRecord, ErrorSeverity, ErrorCategory
from .health_monitor import HealthMonitor, HealthStatus, SystemMetrics, ComponentMetrics
from .ingestion_queue import RealtimeIngestionQueue
from .file_monitor import LogFileMonitor
from .websocket_server import WebSocketManager
from .enhanced_processor import EnhancedBackgroundProcessor

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticResult:
    """Result of a diagnostic check."""
    
    check_name: str
    status: str  # 'pass', 'warning', 'fail'
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    recommendations: List[str]
    severity: str = 'info'  # 'info', 'warning', 'error', 'critical'


@dataclass
class SystemDiagnostics:
    """Comprehensive system diagnostic information."""
    
    timestamp: datetime
    overall_status: str
    system_info: Dict[str, Any]
    component_diagnostics: Dict[str, DiagnosticResult]
    performance_metrics: Dict[str, Any]
    error_analysis: Dict[str, Any]
    resource_usage: Dict[str, Any]
    recommendations: List[str]


class DiagnosticManager:
    """
    Comprehensive diagnostic manager for troubleshooting system issues.
    
    Provides automated diagnostics, performance analysis, error pattern
    detection, and troubleshooting recommendations.
    """
    
    def __init__(
        self,
        health_monitor: Optional[HealthMonitor] = None,
        error_handler: Optional[ErrorHandler] = None,
        file_monitor: Optional[LogFileMonitor] = None,
        ingestion_queue: Optional[RealtimeIngestionQueue] = None,
        websocket_manager: Optional[WebSocketManager] = None,
        enhanced_processor: Optional[EnhancedBackgroundProcessor] = None
    ):
        """
        Initialize diagnostic manager.
        
        Args:
            health_monitor: Health monitoring system
            error_handler: Error handling system
            file_monitor: File monitoring component
            ingestion_queue: Ingestion queue component
            websocket_manager: WebSocket manager
            enhanced_processor: Enhanced background processor
        """
        self.health_monitor = health_monitor
        self.error_handler = error_handler
        self.file_monitor = file_monitor
        self.ingestion_queue = ingestion_queue
        self.websocket_manager = websocket_manager
        self.enhanced_processor = enhanced_processor
        
        # Diagnostic history
        self.diagnostic_history: deque = deque(maxlen=100)
        
        # Performance tracking
        self.performance_samples: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Issue patterns
        self.known_issues: Dict[str, Dict[str, Any]] = self._load_known_issues()
        
    def _load_known_issues(self) -> Dict[str, Dict[str, Any]]:
        """Load known issues and their solutions."""
        return {
            'high_memory_usage': {
                'description': 'System memory usage is critically high',
                'threshold': 90.0,
                'recommendations': [
                    'Reduce queue size limits',
                    'Increase processing batch size',
                    'Check for memory leaks in processing pipeline',
                    'Consider adding more memory to the system'
                ],
                'severity': 'critical'
            },
            'high_cpu_usage': {
                'description': 'CPU usage is consistently high',
                'threshold': 85.0,
                'recommendations': [
                    'Optimize processing algorithms',
                    'Reduce processing frequency',
                    'Check for infinite loops or blocking operations',
                    'Consider scaling to multiple processes'
                ],
                'severity': 'warning'
            },
            'disk_space_low': {
                'description': 'Disk space is running low',
                'threshold': 90.0,
                'recommendations': [
                    'Clean up old log files',
                    'Implement log rotation',
                    'Archive processed logs',
                    'Add more disk space'
                ],
                'severity': 'error'
            },
            'queue_backlog': {
                'description': 'Processing queue has significant backlog',
                'threshold': 1000,
                'recommendations': [
                    'Increase processing workers',
                    'Optimize processing pipeline',
                    'Check for bottlenecks in analysis',
                    'Implement priority-based processing'
                ],
                'severity': 'warning'
            },
            'websocket_disconnections': {
                'description': 'High rate of WebSocket disconnections',
                'threshold': 10,
                'recommendations': [
                    'Check network stability',
                    'Implement better reconnection logic',
                    'Optimize message size and frequency',
                    'Check client-side connection handling'
                ],
                'severity': 'warning'
            },
            'parsing_failures': {
                'description': 'High rate of log parsing failures',
                'threshold': 0.1,  # 10% failure rate
                'recommendations': [
                    'Review log format detection algorithms',
                    'Add support for new log formats',
                    'Implement better fallback parsing',
                    'Check log source configuration'
                ],
                'severity': 'error'
            },
            'analysis_timeouts': {
                'description': 'AI analysis operations timing out frequently',
                'threshold': 0.05,  # 5% timeout rate
                'recommendations': [
                    'Increase analysis timeout limits',
                    'Optimize AI model performance',
                    'Check network connectivity to AI service',
                    'Implement analysis result caching'
                ],
                'severity': 'error'
            }
        }
    
    async def run_full_diagnostics(self) -> SystemDiagnostics:
        """
        Run comprehensive system diagnostics.
        
        Returns:
            SystemDiagnostics with complete system analysis
        """
        logger.info("Starting full system diagnostics")
        start_time = time.time()
        
        # Collect system information
        system_info = await self._collect_system_info()
        
        # Run component diagnostics
        component_diagnostics = await self._run_component_diagnostics()
        
        # Analyze performance metrics
        performance_metrics = await self._analyze_performance_metrics()
        
        # Analyze error patterns
        error_analysis = await self._analyze_error_patterns()
        
        # Check resource usage
        resource_usage = await self._check_resource_usage()
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            component_diagnostics, performance_metrics, error_analysis, resource_usage
        )
        
        # Determine overall status
        overall_status = self._determine_overall_status(component_diagnostics)
        
        # Create diagnostic result
        diagnostics = SystemDiagnostics(
            timestamp=datetime.now(timezone.utc),
            overall_status=overall_status,
            system_info=system_info,
            component_diagnostics=component_diagnostics,
            performance_metrics=performance_metrics,
            error_analysis=error_analysis,
            resource_usage=resource_usage,
            recommendations=recommendations
        )
        
        # Store in history
        self.diagnostic_history.append(diagnostics)
        
        duration = time.time() - start_time
        logger.info(f"Completed full diagnostics in {duration:.2f}s - Status: {overall_status}")
        
        return diagnostics
    
    async def _collect_system_info(self) -> Dict[str, Any]:
        """Collect basic system information."""
        try:
            import sys
            return {
                'platform': 'linux' if 'linux' in sys.platform else sys.platform,
                'python_version': f"{sys.version_info.major}.{sys.version_info.minor}",
                'cpu_count': psutil.cpu_count(),
                'memory_total_gb': psutil.virtual_memory().total / (1024**3),
                'disk_total_gb': psutil.disk_usage('/').total / (1024**3),
                'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                'process_count': len(psutil.pids()),
                'network_interfaces': len(psutil.net_if_addrs())
            }
        except Exception as e:
            logger.error(f"Failed to collect system info: {e}")
            return {'error': str(e)}
    
    async def _run_component_diagnostics(self) -> Dict[str, DiagnosticResult]:
        """Run diagnostics for each component."""
        diagnostics = {}
        
        # Health monitor diagnostics
        if self.health_monitor:
            diagnostics['health_monitor'] = await self._diagnose_health_monitor()
        
        # Error handler diagnostics
        if self.error_handler:
            diagnostics['error_handler'] = await self._diagnose_error_handler()
        
        # File monitor diagnostics
        if self.file_monitor:
            diagnostics['file_monitor'] = await self._diagnose_file_monitor()
        
        # Ingestion queue diagnostics
        if self.ingestion_queue:
            diagnostics['ingestion_queue'] = await self._diagnose_ingestion_queue()
        
        # WebSocket manager diagnostics
        if self.websocket_manager:
            diagnostics['websocket_manager'] = await self._diagnose_websocket_manager()
        
        # Enhanced processor diagnostics
        if self.enhanced_processor:
            diagnostics['enhanced_processor'] = await self._diagnose_enhanced_processor()
        
        return diagnostics
    
    async def _diagnose_health_monitor(self) -> DiagnosticResult:
        """Diagnose health monitoring system."""
        try:
            if not self.health_monitor.monitoring_active:
                return DiagnosticResult(
                    check_name='health_monitor',
                    status='fail',
                    message='Health monitoring is not active',
                    details={'monitoring_active': False},
                    timestamp=datetime.now(timezone.utc),
                    recommendations=['Start health monitoring system'],
                    severity='error'
                )
            
            # Check if health checks are running
            health_checks_count = len(self.health_monitor.health_checks)
            uptime = (datetime.now() - self.health_monitor.start_time).total_seconds()
            
            details = {
                'monitoring_active': self.health_monitor.monitoring_active,
                'health_checks_count': health_checks_count,
                'uptime_seconds': uptime,
                'metrics_history_count': len(self.health_monitor.system_metrics_history)
            }
            
            if health_checks_count == 0:
                return DiagnosticResult(
                    check_name='health_monitor',
                    status='warning',
                    message='No health checks registered',
                    details=details,
                    timestamp=datetime.now(timezone.utc),
                    recommendations=['Register health checks for components'],
                    severity='warning'
                )
            
            return DiagnosticResult(
                check_name='health_monitor',
                status='pass',
                message=f'Health monitoring active with {health_checks_count} checks',
                details=details,
                timestamp=datetime.now(timezone.utc),
                recommendations=[],
                severity='info'
            )
            
        except Exception as e:
            return DiagnosticResult(
                check_name='health_monitor',
                status='fail',
                message=f'Health monitor diagnostic failed: {e}',
                details={'error': str(e)},
                timestamp=datetime.now(timezone.utc),
                recommendations=['Check health monitor configuration'],
                severity='error'
            )
    
    async def _diagnose_error_handler(self) -> DiagnosticResult:
        """Diagnose error handling system."""
        try:
            stats = self.error_handler.get_error_statistics()
            
            details = {
                'total_errors': stats['total_errors'],
                'recovery_success_rate': stats.get('recovery_success_rate', 0),
                'critical_error_rate': stats.get('critical_error_rate', 0),
                'recent_errors_count': len(stats.get('recent_errors', []))
            }
            
            # Check for high error rates
            if stats.get('critical_error_rate', 0) > 0.1:  # More than 10% critical errors
                return DiagnosticResult(
                    check_name='error_handler',
                    status='fail',
                    message=f'High critical error rate: {stats["critical_error_rate"]:.1%}',
                    details=details,
                    timestamp=datetime.now(timezone.utc),
                    recommendations=[
                        'Investigate critical errors',
                        'Review error patterns',
                        'Check system stability'
                    ],
                    severity='critical'
                )
            
            # Check recovery success rate
            if stats.get('recovery_success_rate', 1) < 0.8:  # Less than 80% recovery success
                return DiagnosticResult(
                    check_name='error_handler',
                    status='warning',
                    message=f'Low recovery success rate: {stats["recovery_success_rate"]:.1%}',
                    details=details,
                    timestamp=datetime.now(timezone.utc),
                    recommendations=[
                        'Review recovery strategies',
                        'Improve error handling logic',
                        'Check component reliability'
                    ],
                    severity='warning'
                )
            
            return DiagnosticResult(
                check_name='error_handler',
                status='pass',
                message=f'Error handling operational - {stats["total_errors"]} total errors',
                details=details,
                timestamp=datetime.now(timezone.utc),
                recommendations=[],
                severity='info'
            )
            
        except Exception as e:
            return DiagnosticResult(
                check_name='error_handler',
                status='fail',
                message=f'Error handler diagnostic failed: {e}',
                details={'error': str(e)},
                timestamp=datetime.now(timezone.utc),
                recommendations=['Check error handler configuration'],
                severity='error'
            )
    
    async def _diagnose_file_monitor(self) -> DiagnosticResult:
        """Diagnose file monitoring system."""
        try:
            # This would check file monitor status in a real implementation
            # For now, return a basic diagnostic
            return DiagnosticResult(
                check_name='file_monitor',
                status='pass',
                message='File monitor diagnostic not fully implemented',
                details={'status': 'placeholder'},
                timestamp=datetime.now(timezone.utc),
                recommendations=['Implement file monitor diagnostics'],
                severity='info'
            )
        except Exception as e:
            return DiagnosticResult(
                check_name='file_monitor',
                status='fail',
                message=f'File monitor diagnostic failed: {e}',
                details={'error': str(e)},
                timestamp=datetime.now(timezone.utc),
                recommendations=['Check file monitor configuration'],
                severity='error'
            )
    
    async def _diagnose_ingestion_queue(self) -> DiagnosticResult:
        """Diagnose ingestion queue system."""
        try:
            # This would check queue status in a real implementation
            return DiagnosticResult(
                check_name='ingestion_queue',
                status='pass',
                message='Ingestion queue diagnostic not fully implemented',
                details={'status': 'placeholder'},
                timestamp=datetime.now(timezone.utc),
                recommendations=['Implement ingestion queue diagnostics'],
                severity='info'
            )
        except Exception as e:
            return DiagnosticResult(
                check_name='ingestion_queue',
                status='fail',
                message=f'Ingestion queue diagnostic failed: {e}',
                details={'error': str(e)},
                timestamp=datetime.now(timezone.utc),
                recommendations=['Check ingestion queue configuration'],
                severity='error'
            )
    
    async def _diagnose_websocket_manager(self) -> DiagnosticResult:
        """Diagnose WebSocket manager."""
        try:
            # This would check WebSocket status in a real implementation
            return DiagnosticResult(
                check_name='websocket_manager',
                status='pass',
                message='WebSocket manager diagnostic not fully implemented',
                details={'status': 'placeholder'},
                timestamp=datetime.now(timezone.utc),
                recommendations=['Implement WebSocket manager diagnostics'],
                severity='info'
            )
        except Exception as e:
            return DiagnosticResult(
                check_name='websocket_manager',
                status='fail',
                message=f'WebSocket manager diagnostic failed: {e}',
                details={'error': str(e)},
                timestamp=datetime.now(timezone.utc),
                recommendations=['Check WebSocket manager configuration'],
                severity='error'
            )
    
    async def _diagnose_enhanced_processor(self) -> DiagnosticResult:
        """Diagnose enhanced processor."""
        try:
            # This would check processor status in a real implementation
            return DiagnosticResult(
                check_name='enhanced_processor',
                status='pass',
                message='Enhanced processor diagnostic not fully implemented',
                details={'status': 'placeholder'},
                timestamp=datetime.now(timezone.utc),
                recommendations=['Implement enhanced processor diagnostics'],
                severity='info'
            )
        except Exception as e:
            return DiagnosticResult(
                check_name='enhanced_processor',
                status='fail',
                message=f'Enhanced processor diagnostic failed: {e}',
                details={'error': str(e)},
                timestamp=datetime.now(timezone.utc),
                recommendations=['Check enhanced processor configuration'],
                severity='error'
            )
    
    async def _analyze_performance_metrics(self) -> Dict[str, Any]:
        """Analyze system performance metrics."""
        try:
            if not self.health_monitor or not self.health_monitor.system_metrics_history:
                return {'error': 'No performance metrics available'}
            
            # Get recent metrics
            recent_metrics = self.health_monitor.system_metrics_history[-10:]  # Last 10 samples
            
            if not recent_metrics:
                return {'error': 'No recent metrics available'}
            
            # Calculate averages
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
            avg_disk = sum(m.disk_percent for m in recent_metrics) / len(recent_metrics)
            
            # Calculate trends
            cpu_trend = self._calculate_trend([m.cpu_percent for m in recent_metrics])
            memory_trend = self._calculate_trend([m.memory_percent for m in recent_metrics])
            
            return {
                'average_cpu_percent': avg_cpu,
                'average_memory_percent': avg_memory,
                'average_disk_percent': avg_disk,
                'cpu_trend': cpu_trend,
                'memory_trend': memory_trend,
                'samples_count': len(recent_metrics),
                'time_span_minutes': (recent_metrics[-1].timestamp - recent_metrics[0].timestamp).total_seconds() / 60
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze performance metrics: {e}")
            return {'error': str(e)}
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from a list of values."""
        if len(values) < 2:
            return 'stable'
        
        # Simple linear trend calculation
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        
        if slope > 0.1:
            return 'increasing'
        elif slope < -0.1:
            return 'decreasing'
        else:
            return 'stable'
    
    async def _analyze_error_patterns(self) -> Dict[str, Any]:
        """Analyze error patterns and trends."""
        try:
            if not self.error_handler:
                return {'error': 'No error handler available'}
            
            stats = self.error_handler.get_error_statistics()
            
            # Analyze error patterns
            error_patterns = {}
            for pattern, count in stats.get('error_patterns', {}).items():
                if count >= 3:  # Only patterns with 3+ occurrences
                    error_patterns[pattern] = count
            
            # Get recent error trends
            recent_errors = stats.get('recent_errors', [])
            error_rate_per_hour = len(recent_errors)  # Simplified calculation
            
            return {
                'total_errors': stats['total_errors'],
                'error_patterns': error_patterns,
                'recent_error_rate': error_rate_per_hour,
                'recovery_success_rate': stats.get('recovery_success_rate', 0),
                'critical_errors': stats['errors_by_severity'].get('critical', 0),
                'high_severity_errors': stats['errors_by_severity'].get('high', 0),
                'most_common_category': max(stats['errors_by_category'].items(), key=lambda x: x[1])[0] if stats['errors_by_category'] else None
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze error patterns: {e}")
            return {'error': str(e)}
    
    async def _check_resource_usage(self) -> Dict[str, Any]:
        """Check system resource usage against thresholds."""
        try:
            # Get current system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Check against thresholds
            issues = []
            
            if memory.percent > self.known_issues['high_memory_usage']['threshold']:
                issues.append('high_memory_usage')
            
            if cpu_percent > self.known_issues['high_cpu_usage']['threshold']:
                issues.append('high_cpu_usage')
            
            if (disk.used / disk.total * 100) > self.known_issues['disk_space_low']['threshold']:
                issues.append('disk_space_low')
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_gb': memory.available / (1024**3),
                'disk_percent': disk.used / disk.total * 100,
                'disk_free_gb': disk.free / (1024**3),
                'resource_issues': issues,
                'load_average': list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            }
            
        except Exception as e:
            logger.error(f"Failed to check resource usage: {e}")
            return {'error': str(e)}
    
    def _generate_recommendations(
        self,
        component_diagnostics: Dict[str, DiagnosticResult],
        performance_metrics: Dict[str, Any],
        error_analysis: Dict[str, Any],
        resource_usage: Dict[str, Any]
    ) -> List[str]:
        """Generate troubleshooting recommendations."""
        recommendations = []
        
        # Component-based recommendations
        for component, diagnostic in component_diagnostics.items():
            if diagnostic.status in ['fail', 'warning']:
                recommendations.extend(diagnostic.recommendations)
        
        # Performance-based recommendations
        if 'average_cpu_percent' in performance_metrics:
            if performance_metrics['average_cpu_percent'] > 80:
                recommendations.append('High CPU usage detected - consider optimizing processing algorithms')
            
            if performance_metrics['average_memory_percent'] > 85:
                recommendations.append('High memory usage detected - check for memory leaks or reduce queue sizes')
        
        # Error-based recommendations
        if 'critical_errors' in error_analysis and error_analysis['critical_errors'] > 0:
            recommendations.append('Critical errors detected - immediate investigation required')
        
        if 'recovery_success_rate' in error_analysis and error_analysis['recovery_success_rate'] < 0.8:
            recommendations.append('Low error recovery rate - review recovery strategies')
        
        # Resource-based recommendations
        for issue in resource_usage.get('resource_issues', []):
            if issue in self.known_issues:
                recommendations.extend(self.known_issues[issue]['recommendations'])
        
        # Remove duplicates and return
        return list(set(recommendations))
    
    def _determine_overall_status(self, component_diagnostics: Dict[str, DiagnosticResult]) -> str:
        """Determine overall system status from component diagnostics."""
        if not component_diagnostics:
            return 'unknown'
        
        statuses = [diag.status for diag in component_diagnostics.values()]
        
        if 'fail' in statuses:
            return 'critical'
        elif 'warning' in statuses:
            return 'warning'
        elif all(status == 'pass' for status in statuses):
            return 'healthy'
        else:
            return 'unknown'
    
    def get_diagnostic_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent diagnostic history."""
        return [
            {
                'timestamp': diag.timestamp.isoformat(),
                'overall_status': diag.overall_status,
                'component_count': len(diag.component_diagnostics),
                'recommendations_count': len(diag.recommendations),
                'failed_components': [
                    name for name, result in diag.component_diagnostics.items()
                    if result.status == 'fail'
                ]
            }
            for diag in list(self.diagnostic_history)[-limit:]
        ]
    
    async def run_quick_health_check(self) -> Dict[str, Any]:
        """Run a quick health check for immediate status."""
        try:
            # Check basic system resources
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            # Check component availability
            components_status = {}
            if self.health_monitor:
                components_status['health_monitor'] = 'available'
            if self.error_handler:
                components_status['error_handler'] = 'available'
            
            # Quick status determination
            status = 'healthy'
            issues = []
            
            if memory.percent > 90:
                status = 'critical'
                issues.append('Critical memory usage')
            elif memory.percent > 80:
                status = 'warning'
                issues.append('High memory usage')
            
            if cpu_percent > 90:
                status = 'critical'
                issues.append('Critical CPU usage')
            elif cpu_percent > 80:
                status = 'warning'
                issues.append('High CPU usage')
            
            return {
                'status': status,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'components_available': len(components_status),
                'issues': issues,
                'uptime_seconds': time.time() - psutil.boot_time()
            }
            
        except Exception as e:
            logger.error(f"Quick health check failed: {e}")
            return {
                'status': 'error',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': str(e)
            }


# Global diagnostic manager instance
diagnostic_manager = DiagnosticManager()


def set_diagnostic_components(
    health_monitor: Optional[HealthMonitor] = None,
    error_handler: Optional[ErrorHandler] = None,
    file_monitor: Optional[LogFileMonitor] = None,
    ingestion_queue: Optional[RealtimeIngestionQueue] = None,
    websocket_manager: Optional[WebSocketManager] = None,
    enhanced_processor: Optional[EnhancedBackgroundProcessor] = None
) -> None:
    """Set components for diagnostic manager."""
    if health_monitor:
        diagnostic_manager.health_monitor = health_monitor
    if error_handler:
        diagnostic_manager.error_handler = error_handler
    if file_monitor:
        diagnostic_manager.file_monitor = file_monitor
    if ingestion_queue:
        diagnostic_manager.ingestion_queue = ingestion_queue
    if websocket_manager:
        diagnostic_manager.websocket_manager = websocket_manager
    if enhanced_processor:
        diagnostic_manager.enhanced_processor = enhanced_processor


async def run_system_diagnostics() -> SystemDiagnostics:
    """Run comprehensive system diagnostics."""
    return await diagnostic_manager.run_full_diagnostics()


async def run_quick_health_check() -> Dict[str, Any]:
    """Run quick health check."""
    return await diagnostic_manager.run_quick_health_check()


def get_diagnostic_history(limit: int = 10) -> List[Dict[str, Any]]:
    """Get diagnostic history."""
    return diagnostic_manager.get_diagnostic_history(limit)