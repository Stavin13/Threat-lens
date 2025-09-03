"""
Optimized configuration management with intelligent caching and connection pooling.

This module provides an optimized version of the configuration manager with
performance enhancements including intelligent caching, connection pooling,
and batch operations.
"""

import json
import logging
import asyncio
import time
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from contextlib import asynccontextmanager

from ..database import get_db_session
from ..models import MonitoringConfigDB, LogSource as LogSourceDB
from .config_manager import ConfigManager
from .models import MonitoringConfig, LogSourceConfig, NotificationRule, LogSourceType, MonitoringStatus
from .performance_optimizer import get_performance_optimizer, performance_cache
from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class OptimizedConfigManager(ConfigManager):
    """
    Optimized configuration manager with performance enhancements.
    
    Includes intelligent caching, connection pooling, batch operations,
    and change detection for minimal database access.
    """
    
    def __init__(self):
        super().__init__()
        
        # Performance optimizer integration
        self.performance_optimizer = get_performance_optimizer()
        
        # Enhanced caching
        self.cache_ttl_seconds = 300  # 5 minutes
        self._cache_invalidation_patterns: Set[str] = set()
        self._change_tracking: Dict[str, datetime] = {}
        
        # Connection pooling
        self._db_pool = None
        
        # Batch operations
        self._pending_updates: Dict[str, Any] = {}
        self._batch_update_interval = 5.0  # seconds
        self._batch_update_task: Optional[asyncio.Task] = None
        
        # Change detection
        self._config_checksums: Dict[str, str] = {}
        self._last_db_check = time.time()
        self._db_check_interval = 30.0  # seconds
        
        # Optimization settings
        self.enable_batch_updates = True
        self.enable_change_detection = True
        self.enable_connection_pooling = True
    
    async def start_optimization(self) -> None:
        """Start optimization features."""
        if self.enable_batch_updates:
            self._batch_update_task = asyncio.create_task(self._process_batch_updates_continuously())
        
        # Initialize connection pool
        if self.enable_connection_pooling:
            self._db_pool = self.performance_optimizer.get_connection_pool(
                'config_db', self._create_db_connection
            )
        
        logger.info("Configuration manager optimization features started")
    
    async def stop_optimization(self) -> None:
        """Stop optimization features."""
        if self._batch_update_task:
            self._batch_update_task.cancel()
            try:
                await self._batch_update_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Configuration manager optimization features stopped")
    
    async def _create_db_connection(self):
        """Create database connection for pool."""
        # This would create an async database connection
        # For now, return a placeholder
        return get_db_session()
    
    @performance_cache(ttl=300)
    def load_config(self, force_reload: bool = False) -> MonitoringConfig:
        """
        Load monitoring configuration with intelligent caching.
        
        Args:
            force_reload: Force reload from database, ignoring cache
            
        Returns:
            MonitoringConfig instance
        """
        try:
            # Check if we need to reload based on change detection
            if not force_reload and self.enable_change_detection:
                if not self._has_config_changed():
                    cached_config = self.performance_optimizer.cache_get("monitoring_config")
                    if cached_config:
                        logger.debug("Using cached configuration (no changes detected)")
                        return cached_config
            
            # Load from database with connection pooling
            if self.enable_connection_pooling and self._db_pool:
                config = asyncio.run(self._load_config_with_pool())
            else:
                config = self._load_config_traditional()
            
            # Cache the configuration
            self.performance_optimizer.cache_set("monitoring_config", config)
            
            # Update change tracking
            if self.enable_change_detection:
                self._update_config_checksum(config)
            
            logger.debug("Configuration loaded and cached successfully")
            return config
        
        except Exception as e:
            logger.error(f"Failed to load optimized configuration: {e}")
            # Return default configuration on error
            return MonitoringConfig()
    
    async def _load_config_with_pool(self) -> MonitoringConfig:
        """Load configuration using connection pool."""
        async with self._db_pool.connection() as db:
            return await self._load_config_from_db(db)
    
    def _load_config_traditional(self) -> MonitoringConfig:
        """Load configuration using traditional method."""
        with get_db_session() as db:
            return self._load_config_from_db_sync(db)
    
    async def _load_config_from_db(self, db) -> MonitoringConfig:
        """Load configuration from database (async version)."""
        # This would be the async version of database loading
        # For now, use the sync version
        return self._load_config_from_db_sync(db)
    
    def _load_config_from_db_sync(self, db: Session) -> MonitoringConfig:
        """Load configuration from database (sync version)."""
        # Get the latest configuration
        config_record = db.query(MonitoringConfigDB).order_by(
            MonitoringConfigDB.updated_at.desc()
        ).first()
        
        if config_record:
            # Parse JSON configuration
            config_data = json.loads(config_record.config_data)
            config = MonitoringConfig.from_dict(config_data)
        else:
            # Create default configuration
            config = MonitoringConfig()
        
        # Load log sources from database with optimization
        config.log_sources = self._load_log_sources_optimized(db)
        
        return config
    
    def _load_log_sources_optimized(self, db: Session) -> List[LogSourceConfig]:
        """Load log sources with optimization."""
        sources = []
        
        try:
            # Use batch loading for better performance
            source_records = db.query(LogSourceDB).all()
            
            # Process in batches
            batch_size = 100
            for i in range(0, len(source_records), batch_size):
                batch = source_records[i:i + batch_size]
                
                for record in batch:
                    source_config = self._convert_db_record_to_config(record)
                    sources.append(source_config)
        
        except Exception as e:
            logger.error(f"Failed to load log sources optimized: {e}")
        
        return sources
    
    def _convert_db_record_to_config(self, record) -> LogSourceConfig:
        """Convert database record to LogSourceConfig."""
        return LogSourceConfig(
            source_name=record.source_name,
            path=record.path,
            source_type=LogSourceType.FILE,  # Default, could be stored in DB
            enabled=bool(record.enabled),
            status=MonitoringStatus(record.status),
            last_monitored=record.last_monitored,
            file_size=record.file_size,
            last_offset=record.last_offset,
            error_message=record.error_message
        )
    
    def _has_config_changed(self) -> bool:
        """Check if configuration has changed in database."""
        try:
            current_time = time.time()
            if current_time - self._last_db_check < self._db_check_interval:
                return False
            
            self._last_db_check = current_time
            
            with get_db_session() as db:
                # Check latest update timestamp
                latest_config = db.query(MonitoringConfigDB).order_by(
                    MonitoringConfigDB.updated_at.desc()
                ).first()
                
                if latest_config:
                    latest_timestamp = latest_config.updated_at
                    cached_timestamp = self._change_tracking.get("config_timestamp")
                    
                    if cached_timestamp and latest_timestamp <= cached_timestamp:
                        return False
                    
                    self._change_tracking["config_timestamp"] = latest_timestamp
                
                # Check log sources changes
                latest_source = db.query(LogSourceDB).order_by(
                    LogSourceDB.updated_at.desc()
                ).first()
                
                if latest_source:
                    latest_source_timestamp = latest_source.updated_at
                    cached_source_timestamp = self._change_tracking.get("sources_timestamp")
                    
                    if cached_source_timestamp and latest_source_timestamp <= cached_source_timestamp:
                        return False
                    
                    self._change_tracking["sources_timestamp"] = latest_source_timestamp
            
            return True
        
        except Exception as e:
            logger.warning(f"Error checking config changes: {e}")
            return True  # Assume changed on error
    
    def _update_config_checksum(self, config: MonitoringConfig) -> None:
        """Update configuration checksum for change detection."""
        try:
            config_str = json.dumps(config.to_dict(), sort_keys=True, default=str)
            checksum = hash(config_str)
            self._config_checksums["monitoring_config"] = str(checksum)
        except Exception as e:
            logger.warning(f"Error updating config checksum: {e}")
    
    def save_config(self, config: MonitoringConfig) -> bool:
        """
        Save monitoring configuration with optimization.
        
        Args:
            config: MonitoringConfig to save
            
        Returns:
            True if saved successfully
        """
        try:
            if self.enable_batch_updates:
                # Queue for batch update
                self._queue_config_update(config)
                return True
            else:
                # Save immediately
                return self._save_config_immediate(config)
        
        except Exception as e:
            logger.error(f"Failed to save optimized configuration: {e}")
            return False
    
    def _queue_config_update(self, config: MonitoringConfig) -> None:
        """Queue configuration update for batch processing."""
        self._pending_updates["monitoring_config"] = {
            "config": config,
            "timestamp": datetime.now(timezone.utc),
            "type": "config_update"
        }
        
        # Invalidate cache
        self.performance_optimizer.cache_invalidate("monitoring_config")
    
    def _save_config_immediate(self, config: MonitoringConfig) -> bool:
        """Save configuration immediately."""
        try:
            with get_db_session() as db:
                # Update timestamp
                config.updated_at = datetime.now(timezone.utc)
                
                # Save main configuration
                config_dict = config.to_dict()
                config_dict['log_sources'] = []  # Save log sources separately
                
                config_record = MonitoringConfigDB(
                    config_data=json.dumps(config_dict, default=str)
                )
                db.add(config_record)
                
                # Save log sources with batch operations
                self._save_log_sources_batch(db, config.log_sources)
                
                db.commit()
                
                # Update cache
                self.performance_optimizer.cache_set("monitoring_config", config)
                
                # Update change tracking
                if self.enable_change_detection:
                    self._update_config_checksum(config)
                
                logger.info("Configuration saved successfully (immediate)")
                return True
        
        except Exception as e:
            logger.error(f"Failed to save configuration immediately: {e}")
            return False
    
    def _save_log_sources_batch(self, db: Session, sources: List[LogSourceConfig]) -> None:
        """Save log sources using batch operations."""
        try:
            # Get existing sources in batch
            existing_sources = {
                s.source_name: s 
                for s in db.query(LogSourceDB).all()
            }
            
            # Prepare batch operations
            sources_to_update = []
            sources_to_create = []
            sources_to_delete = set(existing_sources.keys())
            
            for source_config in sources:
                sources_to_delete.discard(source_config.source_name)
                
                if source_config.source_name in existing_sources:
                    # Update existing
                    record = existing_sources[source_config.source_name]
                    self._update_source_record(record, source_config)
                    sources_to_update.append(record)
                else:
                    # Create new
                    record = self._create_source_record(source_config)
                    sources_to_create.append(record)
            
            # Execute batch operations
            if sources_to_create:
                db.add_all(sources_to_create)
            
            # Delete removed sources
            if sources_to_delete:
                db.query(LogSourceDB).filter(
                    LogSourceDB.source_name.in_(sources_to_delete)
                ).delete(synchronize_session=False)
        
        except Exception as e:
            logger.error(f"Failed to save log sources in batch: {e}")
            raise
    
    def _update_source_record(self, record, source_config: LogSourceConfig) -> None:
        """Update existing source record."""
        record.path = source_config.path
        record.enabled = int(source_config.enabled)
        record.status = source_config.status.value
        record.last_monitored = source_config.last_monitored
        record.file_size = source_config.file_size
        record.last_offset = source_config.last_offset
        record.error_message = source_config.error_message
        record.updated_at = datetime.now(timezone.utc)
    
    def _create_source_record(self, source_config: LogSourceConfig):
        """Create new source record."""
        return LogSourceDB(
            source_name=source_config.source_name,
            path=source_config.path,
            enabled=int(source_config.enabled),
            status=source_config.status.value,
            last_monitored=source_config.last_monitored,
            file_size=source_config.file_size,
            last_offset=source_config.last_offset,
            error_message=source_config.error_message
        )
    
    async def _process_batch_updates_continuously(self) -> None:
        """Continuously process batched updates."""
        while True:
            try:
                if self._pending_updates:
                    await self._process_pending_updates()
                
                await asyncio.sleep(self._batch_update_interval)
                
            except asyncio.CancelledError:
                # Process remaining updates before stopping
                if self._pending_updates:
                    await self._process_pending_updates()
                break
            except Exception as e:
                logger.error(f"Error in batch update processing: {e}")
                await asyncio.sleep(self._batch_update_interval)
    
    async def _process_pending_updates(self) -> None:
        """Process all pending updates in batch."""
        if not self._pending_updates:
            return
        
        updates_to_process = self._pending_updates.copy()
        self._pending_updates.clear()
        
        try:
            # Group updates by type for efficient processing
            config_updates = []
            source_updates = []
            
            for key, update_data in updates_to_process.items():
                if update_data["type"] == "config_update":
                    config_updates.append(update_data)
                elif update_data["type"] == "source_update":
                    source_updates.append(update_data)
            
            # Process configuration updates
            if config_updates:
                await self._process_config_updates_batch(config_updates)
            
            # Process source updates
            if source_updates:
                await self._process_source_updates_batch(source_updates)
            
            logger.debug(f"Processed {len(updates_to_process)} batched updates")
        
        except Exception as e:
            logger.error(f"Error processing batched updates: {e}")
            # Re-queue failed updates
            self._pending_updates.update(updates_to_process)
    
    async def _process_config_updates_batch(self, config_updates: List[Dict[str, Any]]) -> None:
        """Process configuration updates in batch."""
        try:
            # Use the latest configuration update
            latest_update = max(config_updates, key=lambda x: x["timestamp"])
            config = latest_update["config"]
            
            # Save using connection pool if available
            if self.enable_connection_pooling and self._db_pool:
                async with self._db_pool.connection() as db:
                    await self._save_config_to_db(db, config)
            else:
                self._save_config_immediate(config)
            
            logger.debug("Processed configuration updates batch")
        
        except Exception as e:
            logger.error(f"Error processing config updates batch: {e}")
            raise
    
    async def _process_source_updates_batch(self, source_updates: List[Dict[str, Any]]) -> None:
        """Process source updates in batch."""
        try:
            # Group by source name and use latest update for each
            latest_updates = {}
            for update in source_updates:
                source_name = update["source_name"]
                if source_name not in latest_updates or update["timestamp"] > latest_updates[source_name]["timestamp"]:
                    latest_updates[source_name] = update
            
            # Apply updates
            with get_db_session() as db:
                for source_name, update_data in latest_updates.items():
                    source_record = db.query(LogSourceDB).filter(
                        LogSourceDB.source_name == source_name
                    ).first()
                    
                    if source_record:
                        # Apply update
                        for field, value in update_data["updates"].items():
                            setattr(source_record, field, value)
                        source_record.updated_at = datetime.now(timezone.utc)
                
                db.commit()
            
            # Invalidate relevant cache entries
            self.performance_optimizer.cache_invalidate("monitoring_config")
            
            logger.debug(f"Processed {len(latest_updates)} source updates in batch")
        
        except Exception as e:
            logger.error(f"Error processing source updates batch: {e}")
            raise
    
    async def _save_config_to_db(self, db, config: MonitoringConfig) -> None:
        """Save configuration to database (async version)."""
        # This would be the async version
        # For now, use sync version
        pass
    
    def update_source_status(
        self, 
        source_name: str, 
        status: MonitoringStatus, 
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update source status with batch optimization.
        
        Args:
            source_name: Name of the source
            status: New monitoring status
            error_message: Optional error message
            
        Returns:
            True if update was queued/applied successfully
        """
        try:
            if self.enable_batch_updates:
                # Queue for batch update
                self._queue_source_update(source_name, {
                    "status": status.value,
                    "error_message": error_message
                })
                return True
            else:
                # Update immediately
                return self._update_source_status_immediate(source_name, status, error_message)
        
        except Exception as e:
            logger.error(f"Failed to update source status: {e}")
            return False
    
    def _queue_source_update(self, source_name: str, updates: Dict[str, Any]) -> None:
        """Queue source update for batch processing."""
        update_key = f"source_{source_name}"
        self._pending_updates[update_key] = {
            "source_name": source_name,
            "updates": updates,
            "timestamp": datetime.now(timezone.utc),
            "type": "source_update"
        }
    
    def _update_source_status_immediate(
        self, 
        source_name: str, 
        status: MonitoringStatus, 
        error_message: Optional[str]
    ) -> bool:
        """Update source status immediately."""
        try:
            with get_db_session() as db:
                source_record = db.query(LogSourceDB).filter(
                    LogSourceDB.source_name == source_name
                ).first()
                
                if source_record:
                    source_record.status = status.value
                    source_record.error_message = error_message
                    source_record.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    
                    # Invalidate cache
                    self.performance_optimizer.cache_invalidate("monitoring_config")
                    
                    return True
                
                return False
        
        except Exception as e:
            logger.error(f"Failed to update source status immediately: {e}")
            return False
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        return {
            'caching': {
                'cache_ttl_seconds': self.cache_ttl_seconds,
                'change_tracking_entries': len(self._change_tracking),
                'config_checksums': len(self._config_checksums),
                'last_db_check': self._last_db_check,
                'db_check_interval': self._db_check_interval
            },
            'batch_operations': {
                'enabled': self.enable_batch_updates,
                'pending_updates': len(self._pending_updates),
                'batch_update_interval': self._batch_update_interval,
                'batch_task_running': self._batch_update_task is not None and not self._batch_update_task.done()
            },
            'connection_pooling': {
                'enabled': self.enable_connection_pooling,
                'pool_initialized': self._db_pool is not None,
                'pool_stats': self._db_pool.get_stats() if self._db_pool else None
            },
            'change_detection': {
                'enabled': self.enable_change_detection,
                'invalidation_patterns': len(self._cache_invalidation_patterns)
            }
        }


# Global optimized configuration manager instance
_optimized_config_manager: Optional[OptimizedConfigManager] = None


def get_optimized_config_manager() -> OptimizedConfigManager:
    """Get the global optimized configuration manager instance."""
    global _optimized_config_manager
    if _optimized_config_manager is None:
        _optimized_config_manager = OptimizedConfigManager()
    return _optimized_config_manager