"""
Integration module for real-time queue with existing background processing.

This module provides the integration layer between the new real-time
ingestion queue system and the existing background processing pipeline.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from app.background_tasks import BackgroundTaskManager, process_raw_log
from .ingestion_queue import RealtimeIngestionQueue, LogEntry, LogEntryPriority
from .enhanced_processor import EnhancedBackgroundProcessor, create_enhanced_processor
from .processing_pipeline import get_processing_metrics, get_entry_processing_status
from .base import RealtimeComponent, HealthMonitorMixin

logger = logging.getLogger(__name__)


class QueueIntegrationManager(RealtimeComponent):
    """
    Manager for integrating real-time queue with background processing.
    
    Provides a unified interface for managing both real-time and
    traditional batch processing workflows.
    """
    
    def __init__(
        self,
        max_queue_size: int = 10000,
        batch_size: int = 100,
        websocket_manager: Optional[Any] = None
    ):
        """
        Initialize the integration manager.
        
        Args:
            max_queue_size: Maximum size of the ingestion queue
            batch_size: Batch size for processing
            websocket_manager: Optional WebSocket manager for real-time updates
        """
        RealtimeComponent.__init__(self, "QueueIntegrationManager")
        HealthMonitorMixin.__init__(self)
        
        # Initialize components
        self.ingestion_queue = RealtimeIngestionQueue(
            max_queue_size=max_queue_size,
            batch_size=batch_size
        )
        
        self.enhanced_processor: Optional[EnhancedBackgroundProcessor] = None
        self.websocket_manager = websocket_manager
        
        # Keep reference to traditional background manager for compatibility
        self.background_manager = BackgroundTaskManager()
        
        # Integration metrics
        self.integration_metrics = {
            'realtime_entries_processed': 0,
            'traditional_logs_processed': 0,
            'total_processing_time': 0.0,
            'integration_start_time': None
        }
    
    async def _start_impl(self) -> None:
        """Start the integration manager."""
        logger.info("Starting queue integration manager")
        
        # Start ingestion queue
        await self.ingestion_queue.start()
        
        # Create and start enhanced processor
        self.enhanced_processor = await create_enhanced_processor(
            self.ingestion_queue,
            self.websocket_manager
        )
        
        # Set up integration callbacks
        self._setup_integration_callbacks()
        
        # Record start time
        self.integration_metrics['integration_start_time'] = datetime.now(timezone.utc)
        
        # Update health metrics
        self.update_health_metric("queue_running", True)
        self.update_health_metric("processor_running", True)
        self.update_health_metric("integration_active", True)
    
    async def _stop_impl(self) -> None:
        """Stop the integration manager."""
        logger.info("Stopping queue integration manager")
        
        # Stop enhanced processor
        if self.enhanced_processor:
            await self.enhanced_processor.stop()
        
        # Stop ingestion queue
        await self.ingestion_queue.stop()
        
        # Update health metrics
        self.update_health_metric("queue_running", False)
        self.update_health_metric("processor_running", False)
        self.update_health_metric("integration_active", False)
    
    def _setup_integration_callbacks(self):
        """Set up callbacks for integration monitoring."""
        if not self.enhanced_processor:
            return
        
        def track_realtime_processing(entry: LogEntry, result):
            """Track real-time processing for metrics."""
            self.integration_metrics['realtime_entries_processed'] += 1
            self.integration_metrics['total_processing_time'] += result.processing_time
            
            # Update health metrics
            self.update_health_metric(
                "realtime_entries_processed", 
                self.integration_metrics['realtime_entries_processed']
            )
        
        self.enhanced_processor.add_processing_callback(track_realtime_processing)
    
    async def enqueue_log_entry(
        self,
        content: str,
        source_path: str,
        source_name: str,
        priority: LogEntryPriority = LogEntryPriority.MEDIUM,
        file_offset: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Enqueue a log entry for real-time processing.
        
        Args:
            content: Log content
            source_path: Path to the log source
            source_name: Name of the log source
            priority: Processing priority
            file_offset: File offset for the entry
            metadata: Additional metadata
            
        Returns:
            True if entry was enqueued successfully
        """
        if not self.is_running:
            logger.error("Integration manager is not running")
            return False
        
        # Create log entry
        entry = LogEntry(
            content=content,
            source_path=source_path,
            source_name=source_name,
            timestamp=datetime.now(timezone.utc),
            priority=priority,
            file_offset=file_offset,
            metadata=metadata or {}
        )
        
        # Add real-time processing metadata
        entry.metadata['processing_mode'] = 'realtime'
        entry.metadata['enqueued_at'] = datetime.now(timezone.utc).isoformat()
        
        try:
            return await self.ingestion_queue.enqueue_log_entry(entry)
        except Exception as e:
            logger.error(f"Error enqueuing log entry: {e}")
            return False
    
    async def process_traditional_log(self, raw_log_id: str) -> Dict[str, Any]:
        """
        Process a traditional raw log using the existing pipeline.
        
        Args:
            raw_log_id: ID of the raw log to process
            
        Returns:
            Processing result dictionary
        """
        try:
            result = await process_raw_log(raw_log_id)
            
            # Update integration metrics
            self.integration_metrics['traditional_logs_processed'] += 1
            
            # Update health metrics
            self.update_health_metric(
                "traditional_logs_processed",
                self.integration_metrics['traditional_logs_processed']
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing traditional log {raw_log_id}: {e}")
            return {
                'success': False,
                'raw_log_id': raw_log_id,
                'error': str(e)
            }
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get comprehensive queue status."""
        if not self.is_running:
            return {'error': 'Integration manager is not running'}
        
        try:
            # Get queue statistics
            queue_stats = await self.ingestion_queue.get_queue_stats()
            
            # Get processing metrics
            processing_metrics = {}
            if self.enhanced_processor:
                processing_metrics = self.enhanced_processor.get_processing_metrics()
            
            # Get traditional background manager stats
            background_stats = self.background_manager.get_stats()
            
            return {
                'integration_status': {
                    'is_running': self.is_running,
                    'queue_running': self.ingestion_queue.is_running,
                    'processor_running': self.enhanced_processor.is_running if self.enhanced_processor else False,
                    'integration_metrics': self.integration_metrics.copy()
                },
                'queue_stats': queue_stats.to_dict(),
                'realtime_processing': processing_metrics,
                'traditional_processing': background_stats,
                'health_status': self.get_health_status(),
                'health_metrics': self.get_health_metrics()
            }
            
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return {'error': str(e)}
    
    async def get_entry_status(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific log entry.
        
        Args:
            entry_id: ID of the entry to check
            
        Returns:
            Entry status dictionary or None if not found
        """
        if not self.is_running:
            return None
        
        try:
            # Check in queue first
            entry = await self.ingestion_queue.get_entry_by_id(entry_id)
            if entry:
                return {
                    'entry_id': entry_id,
                    'found_in': 'queue',
                    'status': entry.status.value,
                    'priority': entry.priority.name,
                    'created_at': entry.created_at.isoformat(),
                    'retry_count': entry.retry_count,
                    'last_error': entry.last_error,
                    'metadata': entry.metadata
                }
            
            # Check processing pipeline status
            pipeline_status = get_entry_processing_status(entry_id)
            if pipeline_status:
                return {
                    'entry_id': entry_id,
                    'found_in': 'processing_pipeline',
                    **pipeline_status
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting entry status for {entry_id}: {e}")
            return {'error': str(e)}
    
    async def clear_completed_entries(self, max_age_hours: int = 24) -> Dict[str, int]:
        """
        Clear completed entries from queue and processing history.
        
        Args:
            max_age_hours: Maximum age in hours for completed entries
            
        Returns:
            Dictionary with counts of cleared entries
        """
        if not self.is_running:
            return {'error': 'Integration manager is not running'}
        
        try:
            # Clear from queue
            queue_cleared = await self.ingestion_queue.clear_completed_entries(max_age_hours)
            
            # Clear from processing pipeline (if implemented)
            pipeline_cleared = 0  # Would implement if processing pipeline supports it
            
            logger.info(f"Cleared {queue_cleared} entries from queue, "
                       f"{pipeline_cleared} from processing pipeline")
            
            return {
                'queue_cleared': queue_cleared,
                'pipeline_cleared': pipeline_cleared,
                'total_cleared': queue_cleared + pipeline_cleared
            }
            
        except Exception as e:
            logger.error(f"Error clearing completed entries: {e}")
            return {'error': str(e)}
    
    def get_integration_info(self) -> Dict[str, Any]:
        """Get comprehensive integration information."""
        return {
            'name': self.name,
            'is_running': self.is_running,
            'components': {
                'ingestion_queue': {
                    'name': self.ingestion_queue.name,
                    'is_running': self.ingestion_queue.is_running,
                    'info': self.ingestion_queue.get_queue_info()
                },
                'enhanced_processor': {
                    'name': self.enhanced_processor.name if self.enhanced_processor else None,
                    'is_running': self.enhanced_processor.is_running if self.enhanced_processor else False,
                    'health': self.enhanced_processor.get_health_status() if self.enhanced_processor else None
                },
                'background_manager': {
                    'stats': self.background_manager.get_stats()
                }
            },
            'integration_metrics': self.integration_metrics.copy(),
            'health_status': self.get_health_status(),
            'health_metrics': self.get_health_metrics()
        }


# Global integration manager instance
_integration_manager: Optional[QueueIntegrationManager] = None


async def get_integration_manager(
    max_queue_size: int = 10000,
    batch_size: int = 100,
    websocket_manager: Optional[Any] = None
) -> QueueIntegrationManager:
    """
    Get or create the global integration manager.
    
    Args:
        max_queue_size: Maximum size of the ingestion queue
        batch_size: Batch size for processing
        websocket_manager: Optional WebSocket manager
        
    Returns:
        QueueIntegrationManager instance
    """
    global _integration_manager
    
    if _integration_manager is None:
        _integration_manager = QueueIntegrationManager(
            max_queue_size=max_queue_size,
            batch_size=batch_size,
            websocket_manager=websocket_manager
        )
        await _integration_manager.start()
    
    return _integration_manager


async def shutdown_integration_manager():
    """Shutdown the global integration manager."""
    global _integration_manager
    
    if _integration_manager:
        await _integration_manager.stop()
        _integration_manager = None


# Convenience functions for backward compatibility
async def enqueue_realtime_log(
    content: str,
    source_path: str,
    source_name: str,
    priority: LogEntryPriority = LogEntryPriority.MEDIUM
) -> bool:
    """
    Enqueue a log for real-time processing.
    
    Args:
        content: Log content
        source_path: Path to the log source
        source_name: Name of the log source
        priority: Processing priority
        
    Returns:
        True if enqueued successfully
    """
    manager = await get_integration_manager()
    return await manager.enqueue_log_entry(
        content=content,
        source_path=source_path,
        source_name=source_name,
        priority=priority
    )


async def get_realtime_processing_status() -> Dict[str, Any]:
    """Get real-time processing status."""
    try:
        manager = await get_integration_manager()
        return await manager.get_queue_status()
    except Exception as e:
        logger.error(f"Error getting realtime processing status: {e}")
        return {'error': str(e)}


async def get_combined_processing_metrics() -> Dict[str, Any]:
    """Get combined metrics from both real-time and traditional processing."""
    try:
        # Get real-time metrics
        realtime_status = await get_realtime_processing_status()
        
        # Get processing pipeline metrics
        pipeline_metrics = get_processing_metrics()
        
        return {
            'realtime': realtime_status,
            'pipeline': pipeline_metrics,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting combined processing metrics: {e}")
        return {'error': str(e)}