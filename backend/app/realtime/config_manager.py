"""
Configuration management for real-time log monitoring.

This module provides centralized configuration management for log sources,
monitoring settings, and notification rules with database persistence.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..database import get_db_session
from ..models import MonitoringConfigDB, LogSource as LogSourceDB
from .models import MonitoringConfig, LogSourceConfig, NotificationRule, LogSourceType, MonitoringStatus
from .exceptions import ConfigurationError
from .exceptions import InputValidationError as ValidationError, SecurityViolation

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages configuration for real-time log monitoring system.
    
    Provides methods to load, save, and manage log source configurations,
    monitoring settings, and notification rules with database persistence.
    """
    
    def __init__(self):
        self._config_cache: Optional[MonitoringConfig] = None
        self._cache_timestamp: Optional[datetime] = None
        self.cache_ttl_seconds = 300  # 5 minutes cache TTL
    
    def load_config(self, force_reload: bool = False) -> MonitoringConfig:
        """
        Load monitoring configuration from database.
        
        Args:
            force_reload: Force reload from database, ignoring cache
            
        Returns:
            MonitoringConfig instance
        """
        try:
            # Check cache validity
            if not force_reload and self._is_cache_valid():
                return self._config_cache
            
            # Load from database
            with get_db_session() as db:
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
                    self.save_config(config)
                
                # Load log sources from database
                config.log_sources = self._load_log_sources_from_db(db)
                
                # Update cache
                self._config_cache = config
                self._cache_timestamp = datetime.now(timezone.utc)
                
                logger.debug("Configuration loaded successfully")
                return config
        
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            # Return default configuration on error
            return MonitoringConfig()
    
    def save_config(self, config: MonitoringConfig) -> bool:
        """
        Save monitoring configuration to database.
        
        Args:
            config: MonitoringConfig to save
            
        Returns:
            True if saved successfully
        """
        try:
            with get_db_session() as db:
                # Update timestamp
                config.updated_at = datetime.now(timezone.utc)
                
                # Save main configuration (without log sources)
                config_dict = config.to_dict()
                config_dict['log_sources'] = []  # Save log sources separately
                
                config_record = MonitoringConfigDB(
                    config_data=json.dumps(config_dict, default=str)
                )
                db.add(config_record)
                
                # Save log sources separately
                self._save_log_sources_to_db(db, config.log_sources)
                
                db.commit()
                
                # Update cache
                self._config_cache = config
                self._cache_timestamp = datetime.now(timezone.utc)
                
                logger.info("Configuration saved successfully")
                return True
        
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def add_log_source(self, source_config: LogSourceConfig) -> bool:
        """
        Add a new log source configuration with security validation.
        
        Args:
            source_config: LogSourceConfig to add
            
        Returns:
            True if added successfully
        """
        try:
            # Import security components
            from .security import get_input_validator, get_file_sandbox
            
            validator = get_input_validator()
            sandbox = get_file_sandbox()
            
            # Validate log source name
            validated_name = validator.validate_log_source_name(source_config.source_name)
            source_config.source_name = validated_name
            
            # Validate and sandbox file path
            validated_path = validator.validate_file_path(source_config.path, allow_relative=False)
            sandboxed_path = sandbox.validate_path(validated_path)
            source_config.path = str(sandboxed_path)
            
            # Load current configuration
            config = self.load_config()
            
            # Add the source
            config.add_log_source(source_config)
            
            # Save updated configuration
            return self.save_config(config)
        
        except (ValidationError, SecurityViolation) as e:
            logger.error(f"Security validation error adding log source: {e}")
            raise ConfigurationError(f"Security validation failed: {e}")
        except ConfigurationError as e:
            logger.error(f"Configuration error adding log source: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to add log source: {e}")
            return False
    
    def remove_log_source(self, source_name: str) -> bool:
        """
        Remove a log source configuration.
        
        Args:
            source_name: Name of the source to remove
            
        Returns:
            True if removed successfully
        """
        try:
            # Load current configuration
            config = self.load_config()
            
            # Remove the source
            success = config.remove_log_source(source_name)
            
            if success:
                # Also remove from database
                with get_db_session() as db:
                    db.query(LogSourceDB).filter(
                        LogSourceDB.source_name == source_name
                    ).delete()
                    db.commit()
                
                # Save updated configuration
                self.save_config(config)
            
            return success
        
        except Exception as e:
            logger.error(f"Failed to remove log source: {e}")
            return False
    
    def update_log_source(self, source_name: str, updated_config: LogSourceConfig) -> bool:
        """
        Update an existing log source configuration.
        
        Args:
            source_name: Name of the source to update
            updated_config: Updated LogSourceConfig
            
        Returns:
            True if updated successfully
        """
        try:
            # Load current configuration
            config = self.load_config()
            
            # Update the source
            success = config.update_log_source(source_name, updated_config)
            
            if success:
                # Save updated configuration
                return self.save_config(config)
            
            return False
        
        except ConfigurationError as e:
            logger.error(f"Configuration error updating log source: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to update log source: {e}")
            return False
    
    def get_log_source(self, source_name: str) -> Optional[LogSourceConfig]:
        """
        Get a specific log source configuration.
        
        Args:
            source_name: Name of the source to retrieve
            
        Returns:
            LogSourceConfig if found, None otherwise
        """
        try:
            config = self.load_config()
            return config.get_log_source(source_name)
        except Exception as e:
            logger.error(f"Failed to get log source {source_name}: {e}")
            return None
    
    def get_log_sources(self) -> List[LogSourceConfig]:
        """
        Get all log source configurations.
        
        Returns:
            List of LogSourceConfig instances
        """
        try:
            config = self.load_config()
            return config.log_sources
        except Exception as e:
            logger.error(f"Failed to get log sources: {e}")
            return []
    
    def get_enabled_log_sources(self) -> List[LogSourceConfig]:
        """
        Get all enabled log source configurations.
        
        Returns:
            List of enabled LogSourceConfig instances
        """
        try:
            config = self.load_config()
            return config.get_enabled_sources()
        except Exception as e:
            logger.error(f"Failed to get enabled log sources: {e}")
            return []
    
    def update_source_status(self, source_name: str, status: MonitoringStatus, 
                           error_message: Optional[str] = None) -> bool:
        """
        Update the status of a log source.
        
        Args:
            source_name: Name of the source
            status: New monitoring status
            error_message: Optional error message
            
        Returns:
            True if updated successfully
        """
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
                    self._config_cache = None
                    
                    return True
                
                return False
        
        except Exception as e:
            logger.error(f"Failed to update source status: {e}")
            return False
    
    def update_source_metrics(self, source_name: str, file_size: Optional[int] = None,
                            last_offset: Optional[int] = None) -> bool:
        """
        Update metrics for a log source.
        
        Args:
            source_name: Name of the source
            file_size: Current file size in bytes
            last_offset: Last processed file offset
            
        Returns:
            True if updated successfully
        """
        try:
            with get_db_session() as db:
                source_record = db.query(LogSourceDB).filter(
                    LogSourceDB.source_name == source_name
                ).first()
                
                if source_record:
                    if file_size is not None:
                        source_record.file_size = file_size
                    if last_offset is not None:
                        source_record.last_offset = last_offset
                    
                    source_record.last_monitored = datetime.now(timezone.utc)
                    source_record.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    
                    return True
                
                return False
        
        except Exception as e:
            logger.error(f"Failed to update source metrics: {e}")
            return False
    
    def validate_configuration(self) -> List[str]:
        """
        Validate the current configuration.
        
        Returns:
            List of validation issues (empty if valid)
        """
        try:
            config = self.load_config()
            return config.validate_configuration()
        except Exception as e:
            logger.error(f"Failed to validate configuration: {e}")
            return [f"Configuration validation failed: {e}"]
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current configuration.
        
        Returns:
            Dictionary with configuration summary
        """
        try:
            config = self.load_config()
            
            enabled_sources = config.get_enabled_sources()
            
            return {
                "total_sources": len(config.log_sources),
                "enabled_sources": len(enabled_sources),
                "disabled_sources": len(config.log_sources) - len(enabled_sources),
                "notification_rules": len(config.notification_rules),
                "enabled_notification_rules": len(config.get_enabled_notification_rules()),
                "max_concurrent_sources": config.max_concurrent_sources,
                "processing_batch_size": config.processing_batch_size,
                "max_queue_size": config.max_queue_size,
                "config_version": config.config_version,
                "last_updated": config.updated_at.isoformat() if config.updated_at else None
            }
        
        except Exception as e:
            logger.error(f"Failed to get configuration summary: {e}")
            return {"error": str(e)}
    
    def _is_cache_valid(self) -> bool:
        """Check if the configuration cache is still valid."""
        if self._config_cache is None or self._cache_timestamp is None:
            return False
        
        age = (datetime.now(timezone.utc) - self._cache_timestamp).total_seconds()
        return age < self.cache_ttl_seconds
    
    def _load_log_sources_from_db(self, db: Session) -> List[LogSourceConfig]:
        """Load log sources from database."""
        sources = []
        
        try:
            source_records = db.query(LogSourceDB).all()
            
            for record in source_records:
                # Convert database record to LogSourceConfig
                source_config = LogSourceConfig(
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
                sources.append(source_config)
        
        except Exception as e:
            logger.error(f"Failed to load log sources from database: {e}")
        
        return sources
    
    def _save_log_sources_to_db(self, db: Session, sources: List[LogSourceConfig]) -> None:
        """Save log sources to database."""
        try:
            # Get existing sources
            existing_sources = {s.source_name: s for s in db.query(LogSourceDB).all()}
            
            # Update or create sources
            for source_config in sources:
                if source_config.source_name in existing_sources:
                    # Update existing
                    record = existing_sources[source_config.source_name]
                    record.path = source_config.path
                    record.enabled = int(source_config.enabled)
                    record.status = source_config.status.value
                    record.last_monitored = source_config.last_monitored
                    record.file_size = source_config.file_size
                    record.last_offset = source_config.last_offset
                    record.error_message = source_config.error_message
                    record.updated_at = datetime.now(timezone.utc)
                else:
                    # Create new
                    record = LogSourceDB(
                        source_name=source_config.source_name,
                        path=source_config.path,
                        enabled=int(source_config.enabled),
                        status=source_config.status.value,
                        last_monitored=source_config.last_monitored,
                        file_size=source_config.file_size,
                        last_offset=source_config.last_offset,
                        error_message=source_config.error_message
                    )
                    db.add(record)
            
            # Remove sources that are no longer in the configuration
            current_names = {s.source_name for s in sources}
            for name, record in existing_sources.items():
                if name not in current_names:
                    db.delete(record)
        
        except Exception as e:
            logger.error(f"Failed to save log sources to database: {e}")
            raise


# Global configuration manager instance
config_manager = ConfigManager()


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    return config_manager