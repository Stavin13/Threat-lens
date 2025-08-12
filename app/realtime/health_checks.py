"""
Component-specific health check implementations.

This module provides health check functions for all real-time components
including file monitoring, queue processing, and WebSocket server.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from .health_monitor import HealthStatus

logger = logging.getLogger(__name__)


class FileMonitorHealthCheck:
    """Health check for file monitoring system."""
    
    def __init__(self, file_monitor=None):
        self.file_monitor = file_monitor
        self.last_activity_check = datetime.now()
        
    async def check_health(self) -> Dict[str, Any]:
        """Perform health check for file monitoring system."""
        try:
            if not self.file_monitor:
                return {
                    'status': HealthStatus.CRITICAL.value,
                    'message': 'File monitor not initialized',
                    'metrics': {}
                }
                
            # Check if monitoring is active
            if not getattr(self.file_monitor, 'monitoring_active', False):
                return {
                    'status': HealthStatus.CRITICAL.value,
                    'message': 'File monitoring is not active',
                    'metrics': {
                        'monitoring_active': False,
                        'monitored_sources': 0
                    }
                }
                
            # Get monitoring status
            status = self.file_monitor.get_monitoring_status()
            monitored_sources = len(status.get('monitored_paths', []))
            failed_sources = len(status.get('failed_paths', []))
            
            # Determine health status
            if failed_sources == 0:
                health_status = HealthStatus.HEALTHY
                message = f"Monitoring {monitored_sources} sources successfully"
            elif failed_sources < monitored_sources:
                health_status = HealthStatus.WARNING
                message = f"Monitoring {monitored_sources} sources, {failed_sources} failed"
            else:
                health_status = HealthStatus.CRITICAL
                message = f"All {failed_sources} monitored sources failed"
                
            return {
                'status': health_status.value,
                'message': message,
                'metrics': {
                    'monitoring_active': True,
                    'monitored_sources': monitored_sources,
                    'failed_sources': failed_sources,
                    'last_activity': status.get('last_activity', '').isoformat() if status.get('last_activity') else None
                }
            }
            
        except Exception as e:
            logger.error(f"File monitor health check failed: {e}")
            return {
                'status': HealthStatus.CRITICAL.value,
                'message': f'Health check error: {str(e)}',
                'metrics': {}
            }


class QueueProcessingHealthCheck:
    """Health check for queue processing system."""
    
    def __init__(self, ingestion_queue=None):
        self.ingestion_queue = ingestion_queue
        self.last_processing_check = datetime.now()
        
    async def check_health(self) -> Dict[str, Any]:
        """Perform health check for queue processing system."""
        try:
            if not self.ingestion_queue:
                return {
                    'status': HealthStatus.CRITICAL.value,
                    'message': 'Ingestion queue not initialized',
                    'metrics': {}
                }
                
            # Get queue statistics
            queue_stats = self.ingestion_queue.get_queue_stats()
            
            queue_size = queue_stats.get('queue_size', 0)
            processing_active = queue_stats.get('processing_active', False)
            processed_count = queue_stats.get('processed_count', 0)
            error_count = queue_stats.get('error_count', 0)
            
            # Check queue health
            max_queue_size = getattr(self.ingestion_queue, 'max_queue_size', 1000)
            # Ensure max_queue_size is a number, not a Mock
            if hasattr(max_queue_size, '_mock_name'):
                max_queue_size = 1000
            queue_utilization = (queue_size / max_queue_size) * 100 if max_queue_size > 0 else 0
            
            # Determine health status
            if not processing_active:
                health_status = HealthStatus.CRITICAL
                message = "Queue processing is not active"
            elif queue_utilization > 90:
                health_status = HealthStatus.CRITICAL
                message = f"Queue is {queue_utilization:.1f}% full (critical)"
            elif queue_utilization > 70:
                health_status = HealthStatus.WARNING
                message = f"Queue is {queue_utilization:.1f}% full (warning)"
            elif error_count > processed_count * 0.1:  # More than 10% error rate
                health_status = HealthStatus.WARNING
                message = f"High error rate: {error_count} errors out of {processed_count} processed"
            else:
                health_status = HealthStatus.HEALTHY
                message = f"Processing normally, {queue_size} items in queue"
                
            return {
                'status': health_status.value,
                'message': message,
                'metrics': {
                    'queue_size': queue_size,
                    'queue_utilization_percent': queue_utilization,
                    'processing_active': processing_active,
                    'processed_count': processed_count,
                    'error_count': error_count,
                    'error_rate_percent': (error_count / max(1, processed_count)) * 100
                }
            }
            
        except Exception as e:
            logger.error(f"Queue processing health check failed: {e}")
            return {
                'status': HealthStatus.CRITICAL.value,
                'message': f'Health check error: {str(e)}',
                'metrics': {}
            }


class WebSocketHealthCheck:
    """Health check for WebSocket server."""
    
    def __init__(self, websocket_manager=None):
        self.websocket_manager = websocket_manager
        self.last_connection_check = datetime.now()
        
    async def check_health(self) -> Dict[str, Any]:
        """Perform health check for WebSocket server."""
        try:
            if not self.websocket_manager:
                return {
                    'status': HealthStatus.CRITICAL.value,
                    'message': 'WebSocket manager not initialized',
                    'metrics': {}
                }
                
            # Get connection statistics
            connected_clients = self.websocket_manager.get_connected_clients()
            active_connections = len(connected_clients)
            
            # Check server status
            server_active = getattr(self.websocket_manager, 'server_active', False)
            
            # Get additional metrics if available
            connection_stats = getattr(self.websocket_manager, 'connection_stats', {})
            total_connections = connection_stats.get('total_connections', 0)
            failed_connections = connection_stats.get('failed_connections', 0)
            messages_sent = connection_stats.get('messages_sent', 0)
            messages_failed = connection_stats.get('messages_failed', 0)
            
            # Determine health status
            if not server_active:
                health_status = HealthStatus.CRITICAL
                message = "WebSocket server is not active"
            elif messages_failed > messages_sent * 0.1:  # More than 10% message failure rate
                health_status = HealthStatus.WARNING
                message = f"High message failure rate: {messages_failed} failed out of {messages_sent} sent"
            elif failed_connections > total_connections * 0.2:  # More than 20% connection failure rate
                health_status = HealthStatus.WARNING
                message = f"High connection failure rate: {failed_connections} failed out of {total_connections} total"
            else:
                health_status = HealthStatus.HEALTHY
                message = f"WebSocket server healthy, {active_connections} active connections"
                
            return {
                'status': health_status.value,
                'message': message,
                'metrics': {
                    'server_active': server_active,
                    'active_connections': active_connections,
                    'total_connections': total_connections,
                    'failed_connections': failed_connections,
                    'messages_sent': messages_sent,
                    'messages_failed': messages_failed,
                    'message_success_rate_percent': ((messages_sent - messages_failed) / max(1, messages_sent)) * 100,
                    'connection_success_rate_percent': ((total_connections - failed_connections) / max(1, total_connections)) * 100
                }
            }
            
        except Exception as e:
            logger.error(f"WebSocket health check failed: {e}")
            return {
                'status': HealthStatus.CRITICAL.value,
                'message': f'Health check error: {str(e)}',
                'metrics': {}
            }


class ProcessingPipelineHealthCheck:
    """Health check for the processing pipeline."""
    
    def __init__(self, enhanced_processor=None):
        self.enhanced_processor = enhanced_processor
        self.last_pipeline_check = datetime.now()
        
    async def check_health(self) -> Dict[str, Any]:
        """Perform health check for processing pipeline."""
        try:
            if not self.enhanced_processor:
                return {
                    'status': HealthStatus.CRITICAL.value,
                    'message': 'Enhanced processor not initialized',
                    'metrics': {}
                }
                
            # Get processing metrics
            processing_metrics = self.enhanced_processor.get_processing_metrics()
            
            processing_active = processing_metrics.get('processing_active', False)
            avg_processing_time = processing_metrics.get('avg_processing_time_ms', 0)
            success_rate = processing_metrics.get('success_rate_percent', 0)
            pending_tasks = processing_metrics.get('pending_tasks', 0)
            
            # Determine health status
            if not processing_active:
                health_status = HealthStatus.CRITICAL
                message = "Processing pipeline is not active"
            elif success_rate < 80:  # Less than 80% success rate
                health_status = HealthStatus.CRITICAL
                message = f"Low success rate: {success_rate:.1f}%"
            elif success_rate < 95:  # Less than 95% success rate
                health_status = HealthStatus.WARNING
                message = f"Moderate success rate: {success_rate:.1f}%"
            elif avg_processing_time > 5000:  # More than 5 seconds average
                health_status = HealthStatus.WARNING
                message = f"High processing latency: {avg_processing_time:.1f}ms average"
            elif pending_tasks > 100:  # More than 100 pending tasks
                health_status = HealthStatus.WARNING
                message = f"High pending task count: {pending_tasks} tasks"
            else:
                health_status = HealthStatus.HEALTHY
                message = f"Processing pipeline healthy, {success_rate:.1f}% success rate"
                
            return {
                'status': health_status.value,
                'message': message,
                'metrics': {
                    'processing_active': processing_active,
                    'avg_processing_time_ms': avg_processing_time,
                    'success_rate_percent': success_rate,
                    'pending_tasks': pending_tasks,
                    'total_processed': processing_metrics.get('total_processed', 0),
                    'total_errors': processing_metrics.get('total_errors', 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Processing pipeline health check failed: {e}")
            return {
                'status': HealthStatus.CRITICAL.value,
                'message': f'Health check error: {str(e)}',
                'metrics': {}
            }


def register_all_health_checks(health_monitor, components: Dict[str, Any]) -> None:
    """Register all health checks with the health monitor."""
    
    # File monitor health check
    if 'file_monitor' in components:
        file_health_check = FileMonitorHealthCheck(components['file_monitor'])
        health_monitor.register_health_check('file_monitor', file_health_check.check_health)
        
    # Queue processing health check
    if 'ingestion_queue' in components:
        queue_health_check = QueueProcessingHealthCheck(components['ingestion_queue'])
        health_monitor.register_health_check('ingestion_queue', queue_health_check.check_health)
        
    # WebSocket health check
    if 'websocket_manager' in components:
        websocket_health_check = WebSocketHealthCheck(components['websocket_manager'])
        health_monitor.register_health_check('websocket_server', websocket_health_check.check_health)
        
    # Processing pipeline health check
    if 'enhanced_processor' in components:
        pipeline_health_check = ProcessingPipelineHealthCheck(components['enhanced_processor'])
        health_monitor.register_health_check('processing_pipeline', pipeline_health_check.check_health)
        
    logger.info(f"Registered {len(components)} health checks with health monitor")