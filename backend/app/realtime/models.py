"""
Data models for real-time log monitoring configuration.

This module defines Pydantic models for log source configuration,
monitoring settings, and related data structures used in the
real-time log detection system.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
from pathlib import Path
import re
import os
from enum import Enum

from .exceptions import ConfigurationError


class LogSourceType(str, Enum):
    """Types of log sources that can be monitored."""
    FILE = "file"
    DIRECTORY = "directory"


class MonitoringStatus(str, Enum):
    """Status of log source monitoring."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PAUSED = "paused"


class NotificationChannel(str, Enum):
    """Available notification channels."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"


class LogSourceConfig(BaseModel):
    """
    Configuration for a single log source to be monitored.
    
    Defines how a specific log file or directory should be monitored,
    including file patterns, polling settings, and processing options.
    """
    
    # Basic identification
    source_name: str = Field(
        ..., 
        min_length=1, 
        max_length=255,
        description="Human-readable name for the log source"
    )
    path: str = Field(
        ..., 
        min_length=1, 
        max_length=1000,
        description="File system path to monitor"
    )
    source_type: LogSourceType = Field(
        default=LogSourceType.FILE,
        description="Type of source (file or directory)"
    )
    
    # Monitoring configuration
    enabled: bool = Field(
        default=True,
        description="Whether monitoring is enabled for this source"
    )
    recursive: bool = Field(
        default=False,
        description="Monitor subdirectories recursively (directory sources only)"
    )
    file_pattern: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Glob pattern for files to monitor (directory sources only)"
    )
    
    # Processing settings
    polling_interval: float = Field(
        default=1.0,
        ge=0.1,
        le=3600.0,
        description="Polling interval in seconds"
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Number of log entries to process in a batch"
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Processing priority (1=lowest, 10=highest)"
    )
    
    # Metadata
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional description of the log source"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorizing the log source"
    )
    
    # Status tracking (read-only fields)
    status: MonitoringStatus = Field(
        default=MonitoringStatus.INACTIVE,
        description="Current monitoring status"
    )
    last_monitored: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last successful monitoring check"
    )
    file_size: Optional[int] = Field(
        default=None,
        ge=0,
        description="Last known file size in bytes"
    )
    last_offset: Optional[int] = Field(
        default=0,
        ge=0,
        description="Last processed file offset"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Last error message if status is ERROR"
    )
    
    @field_validator('source_name')
    @classmethod
    def validate_source_name(cls, v):
        """Validate source name format."""
        if not v or not v.strip():
            raise ValueError("Source name cannot be empty")
        
        # Allow alphanumeric, spaces, hyphens, underscores
        if not re.match(r'^[a-zA-Z0-9\s_\-]+$', v.strip()):
            raise ValueError("Source name can only contain letters, numbers, spaces, hyphens, and underscores")
        
        return v.strip()
    
    @field_validator('path')
    @classmethod
    def validate_path(cls, v):
        """Validate file system path."""
        if not v or not v.strip():
            raise ValueError("Path cannot be empty")
        
        path_str = v.strip()
        
        # Basic path validation - prevent directory traversal
        if '..' in path_str or path_str.startswith('/'):
            # Allow absolute paths but validate they're safe
            try:
                path_obj = Path(path_str).resolve()
                # Ensure path is within allowed directories (basic security)
                path_str = str(path_obj)
            except Exception:
                raise ValueError("Invalid file path")
        
        return path_str
    
    @field_validator('file_pattern')
    @classmethod
    def validate_file_pattern(cls, v):
        """Validate glob pattern."""
        if v is None:
            return v
        
        if not v.strip():
            return None
        
        # Basic validation of glob pattern
        pattern = v.strip()
        if len(pattern) > 255:
            raise ValueError("File pattern too long")
        
        # Ensure pattern doesn't contain dangerous characters
        if any(char in pattern for char in ['..', '/']):
            raise ValueError("File pattern cannot contain '..' or '/'")
        
        return pattern
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate tags list."""
        if not v:
            return []
        
        validated_tags = []
        for tag in v:
            if not isinstance(tag, str):
                raise ValueError("All tags must be strings")
            
            tag = tag.strip().lower()
            if not tag:
                continue
            
            if not re.match(r'^[a-zA-Z0-9_\-]+$', tag):
                raise ValueError("Tags can only contain letters, numbers, hyphens, and underscores")
            
            if tag not in validated_tags:  # Remove duplicates
                validated_tags.append(tag)
        
        return validated_tags
    
    @model_validator(mode='after')
    def validate_source_config(self):
        """Validate the complete source configuration."""
        # File pattern only valid for directory sources
        if self.source_type == LogSourceType.FILE and self.file_pattern:
            raise ValueError("File pattern can only be specified for directory sources")
        
        # Recursive only valid for directory sources
        if self.source_type == LogSourceType.FILE and self.recursive:
            raise ValueError("Recursive monitoring can only be enabled for directory sources")
        
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return self.dict()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogSourceConfig':
        """Create instance from dictionary."""
        return cls(**data)


class NotificationRule(BaseModel):
    """
    Configuration for notification rules based on event severity and category.
    """
    
    rule_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the notification rule"
    )
    enabled: bool = Field(
        default=True,
        description="Whether the rule is enabled"
    )
    
    # Trigger conditions
    min_severity: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Minimum severity score to trigger notification"
    )
    max_severity: int = Field(
        default=10,
        ge=1,
        le=10,
        description="Maximum severity score to trigger notification"
    )
    categories: List[str] = Field(
        default_factory=list,
        description="Event categories to match (empty = all categories)"
    )
    sources: List[str] = Field(
        default_factory=list,
        description="Log sources to match (empty = all sources)"
    )
    
    # Notification settings
    channels: List[NotificationChannel] = Field(
        default_factory=list,
        description="Notification channels to use"
    )
    throttle_minutes: int = Field(
        default=0,
        ge=0,
        le=1440,
        description="Minutes to wait before sending duplicate notifications"
    )
    
    # Channel-specific configuration
    email_recipients: List[str] = Field(
        default_factory=list,
        description="Email addresses for email notifications"
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for HTTP notifications"
    )
    slack_channel: Optional[str] = Field(
        default=None,
        description="Slack channel for Slack notifications"
    )
    
    @field_validator('rule_name')
    @classmethod
    def validate_rule_name(cls, v):
        """Validate rule name."""
        if not v or not v.strip():
            raise ValueError("Rule name cannot be empty")
        return v.strip()
    
    @model_validator(mode='after')
    def validate_severity_range(self):
        """Validate severity range."""
        if self.max_severity < self.min_severity:
            raise ValueError("max_severity must be >= min_severity")
        return self
    
    @field_validator('email_recipients')
    @classmethod
    def validate_email_recipients(cls, v):
        """Validate email addresses."""
        if not v:
            return []
        
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        validated_emails = []
        
        for email in v:
            if not isinstance(email, str):
                raise ValueError("Email addresses must be strings")
            
            email = email.strip().lower()
            if not email_pattern.match(email):
                raise ValueError(f"Invalid email address: {email}")
            
            if email not in validated_emails:
                validated_emails.append(email)
        
        return validated_emails
    
    @field_validator('webhook_url')
    @classmethod
    def validate_webhook_url(cls, v):
        """Validate webhook URL."""
        if not v:
            return None
        
        url = v.strip()
        if not url.startswith(('http://', 'https://')):
            raise ValueError("Webhook URL must start with http:// or https://")
        
        return url
    
    @field_validator('slack_channel')
    @classmethod
    def validate_slack_channel(cls, v):
        """Validate Slack channel."""
        if not v:
            return None
        
        channel = v.strip()
        if not channel.startswith('#'):
            channel = '#' + channel
        
        if not re.match(r'^#[a-z0-9_\-]+$', channel):
            raise ValueError("Invalid Slack channel format")
        
        return channel


class MonitoringConfig(BaseModel):
    """
    Global configuration for the real-time monitoring system.
    
    Contains system-wide settings, log source configurations,
    and notification rules.
    """
    
    # System settings
    enabled: bool = Field(
        default=True,
        description="Global enable/disable for real-time monitoring"
    )
    max_concurrent_sources: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum number of log sources to monitor concurrently"
    )
    processing_batch_size: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Default batch size for processing log entries"
    )
    max_queue_size: int = Field(
        default=10000,
        ge=100,
        le=1000000,
        description="Maximum size of the ingestion queue"
    )
    
    # Health monitoring
    health_check_interval: int = Field(
        default=30,
        ge=5,
        le=3600,
        description="Health check interval in seconds"
    )
    max_error_count: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Maximum errors before marking source as unhealthy"
    )
    retry_interval: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Retry interval for failed operations in seconds"
    )
    
    # Performance settings
    file_read_chunk_size: int = Field(
        default=8192,
        ge=1024,
        le=1048576,
        description="File read chunk size in bytes"
    )
    websocket_max_connections: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum WebSocket connections"
    )
    
    # Configuration data
    log_sources: List[LogSourceConfig] = Field(
        default_factory=list,
        description="List of configured log sources"
    )
    notification_rules: List[NotificationRule] = Field(
        default_factory=list,
        description="List of notification rules"
    )
    
    # Metadata
    config_version: str = Field(
        default="1.0",
        description="Configuration schema version"
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Configuration creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last update timestamp"
    )
    
    def __init__(self, **data):
        """Initialize with current timestamp."""
        if 'created_at' not in data:
            data['created_at'] = datetime.now(timezone.utc)
        if 'updated_at' not in data:
            data['updated_at'] = datetime.now(timezone.utc)
        super().__init__(**data)
    
    def add_log_source(self, source_config: LogSourceConfig) -> bool:
        """Add a new log source configuration."""
        # Check for duplicate names or paths
        for existing in self.log_sources:
            if existing.source_name == source_config.source_name:
                raise ConfigurationError(f"Log source with name '{source_config.source_name}' already exists")
            if existing.path == source_config.path:
                raise ConfigurationError(f"Log source with path '{source_config.path}' already exists")
        
        # Check limits
        if len(self.log_sources) >= self.max_concurrent_sources:
            raise ConfigurationError(f"Maximum number of log sources ({self.max_concurrent_sources}) reached")
        
        self.log_sources.append(source_config)
        self.updated_at = datetime.now(timezone.utc)
        return True
    
    def remove_log_source(self, source_name: str) -> bool:
        """Remove a log source by name."""
        for i, source in enumerate(self.log_sources):
            if source.source_name == source_name:
                del self.log_sources[i]
                self.updated_at = datetime.now(timezone.utc)
                return True
        return False
    
    def get_log_source(self, source_name: str) -> Optional[LogSourceConfig]:
        """Get a log source by name."""
        for source in self.log_sources:
            if source.source_name == source_name:
                return source
        return None
    
    def update_log_source(self, source_name: str, updated_config: LogSourceConfig) -> bool:
        """Update an existing log source configuration."""
        for i, source in enumerate(self.log_sources):
            if source.source_name == source_name:
                # Ensure the name hasn't changed to conflict with another source
                if updated_config.source_name != source_name:
                    for other in self.log_sources:
                        if other.source_name == updated_config.source_name and other != source:
                            raise ConfigurationError(f"Log source with name '{updated_config.source_name}' already exists")
                
                self.log_sources[i] = updated_config
                self.updated_at = datetime.now(timezone.utc)
                return True
        return False
    
    def add_notification_rule(self, rule: NotificationRule) -> bool:
        """Add a new notification rule."""
        # Check for duplicate names
        for existing in self.notification_rules:
            if existing.rule_name == rule.rule_name:
                raise ConfigurationError(f"Notification rule with name '{rule.rule_name}' already exists")
        
        self.notification_rules.append(rule)
        self.updated_at = datetime.now(timezone.utc)
        return True
    
    def remove_notification_rule(self, rule_name: str) -> bool:
        """Remove a notification rule by name."""
        for i, rule in enumerate(self.notification_rules):
            if rule.rule_name == rule_name:
                del self.notification_rules[i]
                self.updated_at = datetime.now(timezone.utc)
                return True
        return False
    
    def get_enabled_sources(self) -> List[LogSourceConfig]:
        """Get all enabled log sources."""
        return [source for source in self.log_sources if source.enabled]
    
    def get_enabled_notification_rules(self) -> List[NotificationRule]:
        """Get all enabled notification rules."""
        return [rule for rule in self.notification_rules if rule.enabled]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return self.dict()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MonitoringConfig':
        """Create instance from dictionary."""
        return cls(**data)
    
    def validate_configuration(self) -> List[str]:
        """Validate the entire configuration and return any issues."""
        issues = []
        
        # Check for duplicate source names
        source_names = [source.source_name for source in self.log_sources]
        if len(source_names) != len(set(source_names)):
            issues.append("Duplicate log source names found")
        
        # Check for duplicate source paths
        source_paths = [source.path for source in self.log_sources]
        if len(source_paths) != len(set(source_paths)):
            issues.append("Duplicate log source paths found")
        
        # Check for duplicate rule names
        rule_names = [rule.rule_name for rule in self.notification_rules]
        if len(rule_names) != len(set(rule_names)):
            issues.append("Duplicate notification rule names found")
        
        # Validate file paths exist (basic check)
        for source in self.log_sources:
            if source.enabled:
                try:
                    path_obj = Path(source.path)
                    if source.source_type == LogSourceType.FILE:
                        if not path_obj.exists() or not path_obj.is_file():
                            issues.append(f"Log file does not exist: {source.path}")
                    elif source.source_type == LogSourceType.DIRECTORY:
                        if not path_obj.exists() or not path_obj.is_dir():
                            issues.append(f"Log directory does not exist: {source.path}")
                except Exception as e:
                    issues.append(f"Invalid path for source '{source.source_name}': {e}")
        
        return issues


class ProcessingMetrics(BaseModel):
    """
    Model for tracking real-time processing metrics.
    """
    
    source_name: str = Field(..., description="Name of the log source")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Processing statistics
    entries_processed: int = Field(default=0, ge=0)
    processing_time_ms: float = Field(default=0.0, ge=0.0)
    queue_size: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    
    # File monitoring statistics
    file_size_bytes: Optional[int] = Field(default=None, ge=0)
    bytes_processed: int = Field(default=0, ge=0)
    last_offset: int = Field(default=0, ge=0)
    
    # Health indicators
    is_healthy: bool = Field(default=True)
    last_error: Optional[str] = Field(default=None)
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }