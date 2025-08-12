"""
Performance integration module for real-time log processing.

This module integrates all performance optimizations and provides
a unified interface for managing performance across the real-time system.
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
from dataclasses import dataclass

from .performance_optimizer import PerformanceOptimizer, get_performance_optimizer
from .optimized_file_monitor import OptimizedLogFileMonitor
from .optimized_ingestion_queue import OptimizedRealtimeIngestionQueue
from .optimized_config_manager import OptimizedConfigManager, get_optimized_config_manager
from .base import RealtimeComponent, HealthMonitorMixin
from .exceptions import PerformanceError

logger = logging.getLogger(__name__)


@dataclass
class SystemPerformanceReport:
    """Comprehensive system performance report."""
    
    # Overall metrics
    system_health_score: float  # 0.0 to 1.0
    performance_grade: str      # A, B, C, D, F
    
    # Component performance
    file_monitor_performance: Dict[str, Any]
    ingestion_queue_performance: Dict[str, Any]
    config_manager_performance: Dict[str, Any]
    
    # Resource utilization
    cpu_utilization: float
    memory_utilization: float
    io_utilization: float
    
    # Processing metrics
    throughput_per_second: float
    avg_latency_ms: float
    error_rate: float
    
    # Optimization recommendations
    recommendations: List[str]
    
    # Timestamp
    generated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'system_health_score': self.system_health_score,
            'performance_grade': self.performance_grade,
            'file_monitor_performance': self.file_monitor_performance,
            'ingestion_queue_performance': self.ingestion_queue_performance,
            'config_manager_performance': self.config_manager_performance,
            'cpu_utilization': self.cpu_utilization,
            'memory_utilization': self.memory_utilization,
            'io_utilization': self.io_utilization,
            'throughput_per_second': self.throughput_per_second,
            'avg_latency_ms': self.avg_latency_ms,
            'error_rate': self.error_rate,
            'recommendations': self.recommendations,
            'generated_at': self.generated_at.isoformat()
        }


class PerformanceIntegrationManager(RealtimeComponent, HealthMonitorMixin):
    """
    Manages performance integration across all real-time components.
    
    Coordinates performance optimization, monitoring, and reporting
    for the entire real-time log processing system.
    """
    
    def __init__(self):
        """Initialize the performance integration manager."""
        RealtimeComponent.__init__(self, "PerformanceIntegrationManager")
        HealthMonitorMixin.__init__(self)
        
        # Core components
        self.performance_optimizer = get_performance_optimizer()
        self.config_manager = get_optimized_config_manager()
        
        # Component instances (will be set by system)
        self.file_monitor: Optional[OptimizedLogFileMonitor] = None
        self.ingestion_queue: Optional[OptimizedRealtimeIngestionQueue] = None
        
        # Performance monitoring
        self._performance_reports: List[SystemPerformanceReport] = []
        self._max_reports = 100
        
        # Integration tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._optimization_task: Optional[asyncio.Task] = None
        
        # Performance thresholds
        self.performance_thresholds = {
            'cpu_warning': 0.8,
            'cpu_critical': 0.9,
            'memory_warning': 0.8,
            'memory_critical': 0.9,
            'error_rate_warning': 0.05,
            'error_rate_critical': 0.1,
            'latency_warning_ms': 1000,
            'latency_critical_ms': 5000
        }
        
        # Optimization settings
        self.auto_optimization = True
        self.optimization_interval = 60.0  # seconds
        self.monitoring_interval = 30.0    # seconds
    
    async def _start_impl(self) -> None:
        """Start the performance integration manager."""
        logger.info("Starting performance integration manager")
        
        # Start core optimizer
        if not self.performance_optimizer.is_running:
            await self.performance_optimizer.start()
        
        # Start optimized config manager
        await self.config_manager.start_optimization()
        
        # Start monitoring and optimization tasks
        self._monitoring_task = asyncio.create_task(self._monitor_performance_continuously())
        
        if self.auto_optimization:
            self._optimization_task = asyncio.create_task(self._optimize_continuously())
        
        # Initialize health metrics
        self.update_health_metric("integration_active", True)
        self.update_health_metric("auto_optimization", self.auto_optimization)
    
    async def _stop_impl(self) -> None:
        """Stop the performance integration manager."""
        logger.info("Stopping performance integration manager")
        
        # Cancel tasks
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        if self._optimization_task:
            self._optimization_task.cancel()
            try:
                await self._optimization_task
            except asyncio.CancelledError:
                pass
        
        # Stop config manager optimization
        await self.config_manager.stop_optimization()
        
        # Stop core optimizer
        if self.performance_optimizer.is_running:
            await self.performance_optimizer.stop()
    
    def register_file_monitor(self, file_monitor: OptimizedLogFileMonitor) -> None:
        """Register the file monitor for performance integration."""
        self.file_monitor = file_monitor
        logger.info("File monitor registered for performance integration")
    
    def register_ingestion_queue(self, ingestion_queue: OptimizedRealtimeIngestionQueue) -> None:
        """Register the ingestion queue for performance integration."""
        self.ingestion_queue = ingestion_queue
        logger.info("Ingestion queue registered for performance integration")
    
    async def generate_performance_report(self) -> SystemPerformanceReport:
        """Generate comprehensive performance report."""
        try:
            # Collect metrics from all components
            optimizer_metrics = self.performance_optimizer.get_performance_metrics()
            
            file_monitor_stats = {}
            if self.file_monitor:
                file_monitor_stats = self.file_monitor.get_optimization_stats()
            
            queue_stats = {}
            if self.ingestion_queue:
                queue_stats = self.ingestion_queue.get_optimization_stats()
            
            config_stats = self.config_manager.get_optimization_stats()
            
            # Calculate overall health score
            health_score = self._calculate_health_score(
                optimizer_metrics, file_monitor_stats, queue_stats, config_stats
            )
            
            # Generate performance grade
            performance_grade = self._calculate_performance_grade(health_score)
            
            # Calculate processing metrics
            throughput = await self._calculate_throughput()
            latency = await self._calculate_average_latency()
            error_rate = await self._calculate_error_rate()
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                optimizer_metrics, file_monitor_stats, queue_stats, config_stats
            )
            
            # Create report
            report = SystemPerformanceReport(
                system_health_score=health_score,
                performance_grade=performance_grade,
                file_monitor_performance=file_monitor_stats,
                ingestion_queue_performance=queue_stats,
                config_manager_performance=config_stats,
                cpu_utilization=optimizer_metrics.cpu_usage / 100.0,
                memory_utilization=optimizer_metrics.memory_usage,
                io_utilization=self._calculate_io_utilization(),
                throughput_per_second=throughput,
                avg_latency_ms=latency,
                error_rate=error_rate,
                recommendations=recommendations,
                generated_at=datetime.now(timezone.utc)
            )
            
            # Store report
            self._performance_reports.append(report)
            if len(self._performance_reports) > self._max_reports:
                self._performance_reports = self._performance_reports[-self._max_reports:]
            
            return report
        
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            raise PerformanceError(f"Failed to generate performance report: {e}")
    
    def _calculate_health_score(
        self, 
        optimizer_metrics, 
        file_monitor_stats: Dict[str, Any], 
        queue_stats: Dict[str, Any], 
        config_stats: Dict[str, Any]
    ) -> float:
        """Calculate overall system health score (0.0 to 1.0)."""
        try:
            scores = []
            
            # CPU score (lower is better)
            cpu_score = max(0.0, 1.0 - (optimizer_metrics.cpu_usage / 100.0))
            scores.append(cpu_score * 0.2)  # 20% weight
            
            # Memory score (lower is better)
            memory_score = max(0.0, 1.0 - optimizer_metrics.memory_usage)
            scores.append(memory_score * 0.2)  # 20% weight
            
            # Cache performance score
            cache_score = optimizer_metrics.cache_hit_rate
            scores.append(cache_score * 0.15)  # 15% weight
            
            # Queue performance score
            if queue_stats and 'resource_usage' in queue_stats:
                queue_utilization = queue_stats['resource_usage'].get('total_queue_size', 0)
                max_queue_size = 10000  # Default max size
                queue_score = max(0.0, 1.0 - (queue_utilization / max_queue_size))
                scores.append(queue_score * 0.15)  # 15% weight
            else:
                scores.append(0.8 * 0.15)  # Default score
            
            # File monitor performance score
            if file_monitor_stats and 'resource_usage' in file_monitor_stats:
                processing_rate = file_monitor_stats['resource_usage'].get('avg_processing_rate', 0)
                # Normalize processing rate (higher is better, up to a point)
                rate_score = min(1.0, processing_rate / 1000.0)  # Normalize to 1000 entries/sec
                scores.append(rate_score * 0.15)  # 15% weight
            else:
                scores.append(0.8 * 0.15)  # Default score
            
            # Configuration performance score
            if config_stats and 'batch_operations' in config_stats:
                batch_enabled = config_stats['batch_operations'].get('enabled', False)
                config_score = 1.0 if batch_enabled else 0.7
                scores.append(config_score * 0.15)  # 15% weight
            else:
                scores.append(0.8 * 0.15)  # Default score
            
            # Calculate weighted average
            total_score = sum(scores)
            return min(1.0, max(0.0, total_score))
        
        except Exception as e:
            logger.warning(f"Error calculating health score: {e}")
            return 0.5  # Default middle score
    
    def _calculate_performance_grade(self, health_score: float) -> str:
        """Calculate performance grade based on health score."""
        if health_score >= 0.9:
            return "A"
        elif health_score >= 0.8:
            return "B"
        elif health_score >= 0.7:
            return "C"
        elif health_score >= 0.6:
            return "D"
        else:
            return "F"
    
    async def _calculate_throughput(self) -> float:
        """Calculate system throughput in entries per second."""
        try:
            if self.ingestion_queue:
                stats = await self.ingestion_queue.get_queue_stats()
                if hasattr(stats, 'throughput_per_second'):
                    return stats.throughput_per_second
            
            # Fallback calculation
            if self.file_monitor:
                return getattr(self.file_monitor, 'entries_processed', 0) / max(
                    getattr(self.file_monitor, 'last_processing_time', 1), 1
                )
            
            return 0.0
        except Exception as e:
            logger.warning(f"Error calculating throughput: {e}")
            return 0.0
    
    async def _calculate_average_latency(self) -> float:
        """Calculate average processing latency in milliseconds."""
        try:
            if self.ingestion_queue:
                stats = await self.ingestion_queue.get_queue_stats()
                if hasattr(stats, 'avg_processing_time'):
                    return stats.avg_processing_time * 1000  # Convert to ms
            
            return 0.0
        except Exception as e:
            logger.warning(f"Error calculating latency: {e}")
            return 0.0
    
    async def _calculate_error_rate(self) -> float:
        """Calculate system error rate."""
        try:
            if self.ingestion_queue:
                stats = await self.ingestion_queue.get_queue_stats()
                if hasattr(stats, 'error_rate'):
                    return stats.error_rate
            
            return 0.0
        except Exception as e:
            logger.warning(f"Error calculating error rate: {e}")
            return 0.0
    
    def _calculate_io_utilization(self) -> float:
        """Calculate I/O utilization estimate."""
        try:
            # This is a simplified estimate based on file operations
            if self.file_monitor:
                file_stats = self.file_monitor.get_optimization_stats()
                if 'file_handles' in file_stats:
                    handle_utilization = file_stats['file_handles'].get('handle_utilization', 0.0)
                    return handle_utilization
            
            return 0.0
        except Exception as e:
            logger.warning(f"Error calculating I/O utilization: {e}")
            return 0.0
    
    def _generate_recommendations(
        self, 
        optimizer_metrics, 
        file_monitor_stats: Dict[str, Any], 
        queue_stats: Dict[str, Any], 
        config_stats: Dict[str, Any]
    ) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []
        
        try:
            # CPU recommendations
            if optimizer_metrics.cpu_usage > self.performance_thresholds['cpu_warning'] * 100:
                recommendations.append(
                    "High CPU usage detected. Consider reducing batch sizes or increasing processing intervals."
                )
            
            # Memory recommendations
            if optimizer_metrics.memory_usage > self.performance_thresholds['memory_warning']:
                recommendations.append(
                    "High memory usage detected. Enable memory optimization and consider reducing cache sizes."
                )
            
            # Cache recommendations
            if optimizer_metrics.cache_hit_rate < 0.7:
                recommendations.append(
                    "Low cache hit rate. Consider increasing cache TTL or cache size."
                )
            
            # Queue recommendations
            if queue_stats and 'resource_usage' in queue_stats:
                if queue_stats['resource_usage'].get('backpressure_active', False):
                    recommendations.append(
                        "Queue backpressure is active. Consider increasing queue size or processing capacity."
                    )
                
                if not queue_stats.get('adaptive_batching', {}).get('enabled', False):
                    recommendations.append(
                        "Adaptive batching is disabled. Enable it for better performance optimization."
                    )
            
            # File monitor recommendations
            if file_monitor_stats and 'file_handles' in file_monitor_stats:
                handle_util = file_monitor_stats['file_handles'].get('handle_utilization', 0.0)
                if handle_util > 0.9:
                    recommendations.append(
                        "High file handle utilization. Consider increasing max_open_handles limit."
                    )
            
            # Configuration recommendations
            if config_stats and 'batch_operations' in config_stats:
                if not config_stats['batch_operations'].get('enabled', False):
                    recommendations.append(
                        "Batch operations are disabled. Enable them for better database performance."
                    )
            
            # Connection pool recommendations
            if optimizer_metrics.pool_utilization > 0.9:
                recommendations.append(
                    "High connection pool utilization. Consider increasing max_connections."
                )
            
            # General recommendations
            if not recommendations:
                recommendations.append("System is performing well. No immediate optimizations needed.")
        
        except Exception as e:
            logger.warning(f"Error generating recommendations: {e}")
            recommendations.append("Unable to generate specific recommendations due to analysis error.")
        
        return recommendations
    
    async def _monitor_performance_continuously(self) -> None:
        """Continuously monitor system performance."""
        while not self._shutdown_event.is_set():
            try:
                # Generate performance report
                report = await self.generate_performance_report()
                
                # Check for critical issues
                await self._check_critical_issues(report)
                
                # Update health metrics
                self.update_health_metric("system_health_score", report.system_health_score)
                self.update_health_metric("performance_grade", report.performance_grade)
                self.update_health_metric("cpu_utilization", report.cpu_utilization)
                self.update_health_metric("memory_utilization", report.memory_utilization)
                
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    async def _check_critical_issues(self, report: SystemPerformanceReport) -> None:
        """Check for critical performance issues and take action."""
        try:
            # Critical CPU usage
            if report.cpu_utilization > self.performance_thresholds['cpu_critical']:
                logger.critical(f"Critical CPU usage: {report.cpu_utilization:.1%}")
                await self._handle_critical_cpu()
            
            # Critical memory usage
            if report.memory_utilization > self.performance_thresholds['memory_critical']:
                logger.critical(f"Critical memory usage: {report.memory_utilization:.1%}")
                await self._handle_critical_memory()
            
            # Critical error rate
            if report.error_rate > self.performance_thresholds['error_rate_critical']:
                logger.critical(f"Critical error rate: {report.error_rate:.1%}")
                await self._handle_critical_errors()
            
            # Critical latency
            if report.avg_latency_ms > self.performance_thresholds['latency_critical_ms']:
                logger.critical(f"Critical latency: {report.avg_latency_ms:.1f}ms")
                await self._handle_critical_latency()
        
        except Exception as e:
            logger.error(f"Error checking critical issues: {e}")
    
    async def _handle_critical_cpu(self) -> None:
        """Handle critical CPU usage."""
        # Reduce batch sizes
        if self.ingestion_queue:
            current_size = self.ingestion_queue._optimal_batch_size
            new_size = max(1, current_size // 2)
            self.ingestion_queue._optimal_batch_size = new_size
            logger.info(f"Reduced batch size from {current_size} to {new_size} due to high CPU")
    
    async def _handle_critical_memory(self) -> None:
        """Handle critical memory usage."""
        # Trigger immediate memory cleanup
        await self.performance_optimizer.perform_memory_cleanup()
        
        # Clear old performance reports
        if len(self._performance_reports) > 10:
            self._performance_reports = self._performance_reports[-10:]
        
        logger.info("Performed emergency memory cleanup")
    
    async def _handle_critical_errors(self) -> None:
        """Handle critical error rate."""
        # This could trigger error analysis or system restart
        logger.critical("Critical error rate detected - system may need attention")
    
    async def _handle_critical_latency(self) -> None:
        """Handle critical latency."""
        # Increase processing capacity
        if self.ingestion_queue:
            # Increase concurrent batch processing
            current_max = self.ingestion_queue.max_concurrent_batches
            new_max = min(10, current_max + 1)
            self.ingestion_queue.max_concurrent_batches = new_max
            logger.info(f"Increased max concurrent batches from {current_max} to {new_max}")
    
    async def _optimize_continuously(self) -> None:
        """Continuously optimize system performance."""
        while not self._shutdown_event.is_set():
            try:
                await self._perform_optimization_cycle()
                await asyncio.sleep(self.optimization_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in continuous optimization: {e}")
                await asyncio.sleep(self.optimization_interval)
    
    async def _perform_optimization_cycle(self) -> None:
        """Perform one optimization cycle."""
        try:
            # Generate current performance report
            report = await self.generate_performance_report()
            
            # Apply optimizations based on report
            optimizations_applied = []
            
            # Optimize batch sizes
            if self.ingestion_queue:
                old_size = self.ingestion_queue._optimal_batch_size
                # Let the queue's adaptive batching handle this
                new_size = self.ingestion_queue._optimal_batch_size
                if old_size != new_size:
                    optimizations_applied.append(f"Batch size: {old_size} -> {new_size}")
            
            # Optimize cache settings
            if report.system_health_score < 0.8:
                # Trigger cache optimization
                cache_stats = self.performance_optimizer.config_cache.get_stats()
                if cache_stats['hit_rate'] < 0.7:
                    # Increase cache TTL
                    old_ttl = self.performance_optimizer.config_cache.ttl_seconds
                    new_ttl = min(600, old_ttl + 60)  # Increase by 1 minute, max 10 minutes
                    self.performance_optimizer.config_cache.ttl_seconds = new_ttl
                    optimizations_applied.append(f"Cache TTL: {old_ttl}s -> {new_ttl}s")
            
            # Log optimizations
            if optimizations_applied:
                logger.info(f"Applied optimizations: {', '.join(optimizations_applied)}")
            
        except Exception as e:
            logger.error(f"Error in optimization cycle: {e}")
    
    def get_recent_reports(self, count: int = 10) -> List[SystemPerformanceReport]:
        """Get recent performance reports."""
        return self._performance_reports[-count:]
    
    def get_performance_trends(self) -> Dict[str, Any]:
        """Get performance trends analysis."""
        if len(self._performance_reports) < 2:
            return {"error": "Insufficient data for trend analysis"}
        
        try:
            recent_reports = self._performance_reports[-10:]
            
            # Calculate trends
            health_scores = [r.system_health_score for r in recent_reports]
            cpu_utilizations = [r.cpu_utilization for r in recent_reports]
            memory_utilizations = [r.memory_utilization for r in recent_reports]
            throughputs = [r.throughput_per_second for r in recent_reports]
            
            return {
                'health_score_trend': self._calculate_trend(health_scores),
                'cpu_trend': self._calculate_trend(cpu_utilizations),
                'memory_trend': self._calculate_trend(memory_utilizations),
                'throughput_trend': self._calculate_trend(throughputs),
                'latest_grade': recent_reports[-1].performance_grade,
                'grade_changes': len(set(r.performance_grade for r in recent_reports[-5:])),
                'report_count': len(recent_reports)
            }
        
        except Exception as e:
            logger.error(f"Error calculating performance trends: {e}")
            return {"error": str(e)}
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction for a list of values."""
        if len(values) < 2:
            return "insufficient_data"
        
        # Simple trend calculation
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        diff_percent = (second_avg - first_avg) / first_avg * 100 if first_avg > 0 else 0
        
        if diff_percent > 5:
            return "improving"
        elif diff_percent < -5:
            return "declining"
        else:
            return "stable"


# Global performance integration manager instance
_performance_integration_manager: Optional[PerformanceIntegrationManager] = None


def get_performance_integration_manager() -> PerformanceIntegrationManager:
    """Get the global performance integration manager instance."""
    global _performance_integration_manager
    if _performance_integration_manager is None:
        _performance_integration_manager = PerformanceIntegrationManager()
    return _performance_integration_manager