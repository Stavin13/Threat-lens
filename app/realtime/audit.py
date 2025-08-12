"""
Audit logging system for real-time configuration changes.

This module provides comprehensive audit logging for all configuration changes,
user actions, and security events in the real-time monitoring system.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text, desc

from ..database import get_db_session
from ..models import AuditLog as AuditLogModel
from ..logging_config import get_logger, get_correlation_id
from .auth import SessionInfo, UserRole

logger = get_logger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Configuration events
    CONFIG_CREATED = "config_created"
    CONFIG_UPDATED = "config_updated"
    CONFIG_DELETED = "config_deleted"
    CONFIG_IMPORTED = "config_imported"
    CONFIG_EXPORTED = "config_exported"
    
    # Log source events
    LOG_SOURCE_ADDED = "log_source_added"
    LOG_SOURCE_UPDATED = "log_source_updated"
    LOG_SOURCE_REMOVED = "log_source_removed"
    LOG_SOURCE_ENABLED = "log_source_enabled"
    LOG_SOURCE_DISABLED = "log_source_disabled"
    
    # Notification events
    NOTIFICATION_RULE_CREATED = "notification_rule_created"
    NOTIFICATION_RULE_UPDATED = "notification_rule_updated"
    NOTIFICATION_RULE_DELETED = "notification_rule_deleted"
    NOTIFICATION_SENT = "notification_sent"
    NOTIFICATION_FAILED = "notification_failed"
    
    # Authentication events
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    SESSION_CREATED = "session_created"
    SESSION_EXPIRED = "session_expired"
    AUTH_FAILED = "auth_failed"
    PERMISSION_DENIED = "permission_denied"
    
    # WebSocket events
    WEBSOCKET_CONNECTED = "websocket_connected"
    WEBSOCKET_DISCONNECTED = "websocket_disconnected"
    WEBSOCKET_AUTH_FAILED = "websocket_auth_failed"
    
    # System events
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPED = "system_stopped"
    COMPONENT_FAILED = "component_failed"
    COMPONENT_RECOVERED = "component_recovered"
    
    # Security events
    SECURITY_VIOLATION = "security_violation"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    
    # Data events
    DATA_ACCESSED = "data_accessed"
    DATA_MODIFIED = "data_modified"
    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditEntry(BaseModel):
    """Audit log entry model."""
    
    id: Optional[str] = Field(default=None, description="Audit entry ID")
    event_type: AuditEventType = Field(..., description="Type of audit event")
    severity: AuditSeverity = Field(default=AuditSeverity.MEDIUM, description="Event severity")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # User information
    user_id: Optional[str] = Field(default=None, description="User ID")
    username: Optional[str] = Field(default=None, description="Username")
    user_role: Optional[UserRole] = Field(default=None, description="User role")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    
    # Request information
    client_ip: Optional[str] = Field(default=None, description="Client IP address")
    user_agent: Optional[str] = Field(default=None, description="User agent")
    correlation_id: Optional[str] = Field(default=None, description="Request correlation ID")
    
    # Event details
    resource_type: Optional[str] = Field(default=None, description="Type of resource affected")
    resource_id: Optional[str] = Field(default=None, description="ID of resource affected")
    action: Optional[str] = Field(default=None, description="Action performed")
    description: str = Field(..., description="Human-readable description")
    
    # Change tracking
    old_values: Optional[Dict[str, Any]] = Field(default=None, description="Previous values")
    new_values: Optional[Dict[str, Any]] = Field(default=None, description="New values")
    changes: Optional[List[str]] = Field(default=None, description="List of changed fields")
    
    # Additional metadata
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional event metadata")
    tags: Optional[List[str]] = Field(default=None, description="Event tags")
    
    # Status and outcome
    success: bool = Field(default=True, description="Whether the action was successful")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AuditLogger:
    """
    Comprehensive audit logging system for real-time features.
    
    Provides structured logging of all configuration changes, user actions,
    and security events with database persistence and querying capabilities.
    """
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.AuditLogger")
        self.buffer_size = 100
        self.buffer: List[AuditEntry] = []
        self.auto_flush = True
    
    def log_event(self, event_type: AuditEventType, description: str,
                  session_info: Optional[SessionInfo] = None,
                  severity: AuditSeverity = AuditSeverity.MEDIUM,
                  resource_type: Optional[str] = None,
                  resource_id: Optional[str] = None,
                  action: Optional[str] = None,
                  old_values: Optional[Dict[str, Any]] = None,
                  new_values: Optional[Dict[str, Any]] = None,
                  metadata: Optional[Dict[str, Any]] = None,
                  tags: Optional[List[str]] = None,
                  success: bool = True,
                  error_message: Optional[str] = None,
                  client_ip: Optional[str] = None,
                  user_agent: Optional[str] = None) -> AuditEntry:
        """
        Log an audit event.
        
        Args:
            event_type: Type of audit event
            description: Human-readable description
            session_info: Optional session information
            severity: Event severity level
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            action: Action performed
            old_values: Previous values (for updates)
            new_values: New values (for updates)
            metadata: Additional metadata
            tags: Event tags
            success: Whether the action was successful
            error_message: Error message if failed
            client_ip: Client IP address
            user_agent: User agent string
            
        Returns:
            AuditEntry that was logged
        """
        try:
            # Extract user information from session
            user_id = None
            username = None
            user_role = None
            session_id = None
            
            if session_info:
                user_id = session_info.user_id
                username = session_info.username
                user_role = session_info.role
                session_id = session_info.session_id
                
                # Use session client info if not provided
                if not client_ip:
                    client_ip = session_info.client_ip
                if not user_agent:
                    user_agent = session_info.user_agent
            
            # Get correlation ID
            correlation_id = get_correlation_id()
            
            # Calculate changes if old and new values provided
            changes = None
            if old_values and new_values:
                changes = []
                all_keys = set(old_values.keys()) | set(new_values.keys())
                for key in all_keys:
                    old_val = old_values.get(key)
                    new_val = new_values.get(key)
                    if old_val != new_val:
                        changes.append(key)
            
            # Create audit entry
            audit_entry = AuditEntry(
                event_type=event_type,
                severity=severity,
                user_id=user_id,
                username=username,
                user_role=user_role,
                session_id=session_id,
                client_ip=client_ip,
                user_agent=user_agent,
                correlation_id=correlation_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                description=description,
                old_values=old_values,
                new_values=new_values,
                changes=changes,
                metadata=metadata,
                tags=tags,
                success=success,
                error_message=error_message
            )
            
            # Add to buffer
            self.buffer.append(audit_entry)
            
            # Auto-flush if enabled
            if self.auto_flush:
                self._flush_buffer()
            
            # Log to application logger
            log_level = self._get_log_level(severity)
            self.logger.log(log_level, f"Audit: {event_type.value} - {description}", extra={
                "audit_entry": audit_entry.dict(exclude_none=True)
            })
            
            return audit_entry
            
        except Exception as e:
            self.logger.error(f"Failed to log audit event: {e}")
            # Create minimal audit entry on error
            return AuditEntry(
                event_type=event_type,
                description=f"Audit logging failed: {description}",
                success=False,
                error_message=str(e)
            )
    
    def log_configuration_change(self, action: str, resource_type: str, resource_id: str,
                                description: str, session_info: Optional[SessionInfo] = None,
                                old_values: Optional[Dict[str, Any]] = None,
                                new_values: Optional[Dict[str, Any]] = None,
                                metadata: Optional[Dict[str, Any]] = None) -> AuditEntry:
        """
        Log a configuration change event.
        
        Args:
            action: Action performed (create, update, delete)
            resource_type: Type of resource (log_source, notification_rule, etc.)
            resource_id: ID of the resource
            description: Description of the change
            session_info: Session information
            old_values: Previous values
            new_values: New values
            metadata: Additional metadata
            
        Returns:
            AuditEntry that was logged
        """
        # Map action to event type
        event_type_map = {
            "create": AuditEventType.CONFIG_CREATED,
            "update": AuditEventType.CONFIG_UPDATED,
            "delete": AuditEventType.CONFIG_DELETED
        }
        
        event_type = event_type_map.get(action, AuditEventType.CONFIG_UPDATED)
        severity = AuditSeverity.HIGH if action == "delete" else AuditSeverity.MEDIUM
        
        return self.log_event(
            event_type=event_type,
            description=description,
            session_info=session_info,
            severity=severity,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            metadata=metadata,
            tags=["configuration", resource_type]
        )
    
    def log_authentication_event(self, event_type: AuditEventType, description: str,
                                user_id: Optional[str] = None, username: Optional[str] = None,
                                session_id: Optional[str] = None, client_ip: Optional[str] = None,
                                user_agent: Optional[str] = None, success: bool = True,
                                error_message: Optional[str] = None,
                                metadata: Optional[Dict[str, Any]] = None) -> AuditEntry:
        """
        Log an authentication-related event.
        
        Args:
            event_type: Type of authentication event
            description: Event description
            user_id: User ID
            username: Username
            session_id: Session ID
            client_ip: Client IP address
            user_agent: User agent
            success: Whether the action was successful
            error_message: Error message if failed
            metadata: Additional metadata
            
        Returns:
            AuditEntry that was logged
        """
        severity = AuditSeverity.HIGH if not success else AuditSeverity.MEDIUM
        
        return self.log_event(
            event_type=event_type,
            description=description,
            severity=severity,
            resource_type="authentication",
            action=event_type.value,
            success=success,
            error_message=error_message,
            client_ip=client_ip,
            user_agent=user_agent,
            metadata={
                "user_id": user_id,
                "username": username,
                "session_id": session_id,
                **(metadata or {})
            },
            tags=["authentication", "security"]
        )
    
    def log_security_event(self, event_type: AuditEventType, description: str,
                          severity: AuditSeverity = AuditSeverity.HIGH,
                          session_info: Optional[SessionInfo] = None,
                          client_ip: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> AuditEntry:
        """
        Log a security-related event.
        
        Args:
            event_type: Type of security event
            description: Event description
            severity: Event severity
            session_info: Session information
            client_ip: Client IP address
            metadata: Additional metadata
            
        Returns:
            AuditEntry that was logged
        """
        return self.log_event(
            event_type=event_type,
            description=description,
            session_info=session_info,
            severity=severity,
            resource_type="security",
            action=event_type.value,
            client_ip=client_ip,
            metadata=metadata,
            tags=["security", "threat"]
        )
    
    def log_websocket_event(self, event_type: AuditEventType, description: str,
                           client_id: str, session_info: Optional[SessionInfo] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> AuditEntry:
        """
        Log a WebSocket-related event.
        
        Args:
            event_type: Type of WebSocket event
            description: Event description
            client_id: WebSocket client ID
            session_info: Session information
            metadata: Additional metadata
            
        Returns:
            AuditEntry that was logged
        """
        return self.log_event(
            event_type=event_type,
            description=description,
            session_info=session_info,
            severity=AuditSeverity.LOW,
            resource_type="websocket",
            resource_id=client_id,
            action=event_type.value,
            metadata={
                "client_id": client_id,
                **(metadata or {})
            },
            tags=["websocket", "realtime"]
        )
    
    def query_audit_log(self, limit: int = 100, offset: int = 0,
                       event_types: Optional[List[AuditEventType]] = None,
                       user_id: Optional[str] = None,
                       resource_type: Optional[str] = None,
                       start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None,
                       severity: Optional[AuditSeverity] = None,
                       success_only: Optional[bool] = None) -> List[AuditEntry]:
        """
        Query audit log entries with filtering.
        
        Args:
            limit: Maximum number of entries to return
            offset: Number of entries to skip
            event_types: Filter by event types
            user_id: Filter by user ID
            resource_type: Filter by resource type
            start_time: Filter by start time
            end_time: Filter by end time
            severity: Filter by severity
            success_only: Filter by success status
            
        Returns:
            List of matching audit entries
        """
        try:
            with get_db_session() as db:
                query = db.query(AuditLogModel)
                
                # Apply filters
                if event_types:
                    event_type_values = [et.value for et in event_types]
                    query = query.filter(AuditLogModel.event_type.in_(event_type_values))
                
                if user_id:
                    query = query.filter(AuditLogModel.user_id == user_id)
                
                if resource_type:
                    query = query.filter(AuditLogModel.resource_type == resource_type)
                
                if start_time:
                    query = query.filter(AuditLogModel.timestamp >= start_time)
                
                if end_time:
                    query = query.filter(AuditLogModel.timestamp <= end_time)
                
                if severity:
                    query = query.filter(AuditLogModel.severity == severity.value)
                
                if success_only is not None:
                    query = query.filter(AuditLogModel.success == success_only)
                
                # Order by timestamp descending
                query = query.order_by(desc(AuditLogModel.timestamp))
                
                # Apply pagination
                results = query.offset(offset).limit(limit).all()
                
                # Convert to AuditEntry objects
                audit_entries = []
                for result in results:
                    try:
                        # Parse JSON fields
                        old_values = json.loads(result.old_values) if result.old_values else None
                        new_values = json.loads(result.new_values) if result.new_values else None
                        metadata = json.loads(result.event_metadata) if result.event_metadata else None
                        changes = json.loads(result.changes) if result.changes else None
                        tags = json.loads(result.tags) if result.tags else None
                        
                        audit_entry = AuditEntry(
                            id=result.id,
                            event_type=AuditEventType(result.event_type),
                            severity=AuditSeverity(result.severity),
                            timestamp=result.timestamp,
                            user_id=result.user_id,
                            username=result.username,
                            user_role=UserRole(result.user_role) if result.user_role else None,
                            session_id=result.session_id,
                            client_ip=result.client_ip,
                            user_agent=result.user_agent,
                            correlation_id=result.correlation_id,
                            resource_type=result.resource_type,
                            resource_id=result.resource_id,
                            action=result.action,
                            description=result.description,
                            old_values=old_values,
                            new_values=new_values,
                            changes=changes,
                            metadata=metadata,
                            tags=tags,
                            success=bool(result.success),
                            error_message=result.error_message
                        )
                        audit_entries.append(audit_entry)
                        
                    except Exception as e:
                        self.logger.error(f"Error parsing audit entry {result.id}: {e}")
                        continue
                
                return audit_entries
                
        except Exception as e:
            self.logger.error(f"Failed to query audit log: {e}")
            return []
    
    def get_audit_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get audit log statistics.
        
        Args:
            days: Number of days to include in statistics
            
        Returns:
            Dictionary with audit statistics
        """
        try:
            start_time = datetime.now(timezone.utc) - timedelta(days=days)
            
            with get_db_session() as db:
                # Total events
                total_events = db.query(AuditLogModel).filter(
                    AuditLogModel.timestamp >= start_time
                ).count()
                
                # Events by type
                event_type_query = db.execute(text("""
                    SELECT event_type, COUNT(*) as count
                    FROM audit_logs
                    WHERE timestamp >= :start_time
                    GROUP BY event_type
                    ORDER BY count DESC
                """), {"start_time": start_time})
                
                events_by_type = {row[0]: row[1] for row in event_type_query}
                
                # Events by severity
                severity_query = db.execute(text("""
                    SELECT severity, COUNT(*) as count
                    FROM audit_logs
                    WHERE timestamp >= :start_time
                    GROUP BY severity
                """), {"start_time": start_time})
                
                events_by_severity = {row[0]: row[1] for row in severity_query}
                
                # Events by user
                user_query = db.execute(text("""
                    SELECT username, COUNT(*) as count
                    FROM audit_logs
                    WHERE timestamp >= :start_time AND username IS NOT NULL
                    GROUP BY username
                    ORDER BY count DESC
                    LIMIT 10
                """), {"start_time": start_time})
                
                events_by_user = {row[0]: row[1] for row in user_query}
                
                # Failed events
                failed_events = db.query(AuditLogModel).filter(
                    AuditLogModel.timestamp >= start_time,
                    AuditLogModel.success == False
                ).count()
                
                return {
                    "period_days": days,
                    "total_events": total_events,
                    "failed_events": failed_events,
                    "success_rate": (total_events - failed_events) / total_events if total_events > 0 else 0,
                    "events_by_type": events_by_type,
                    "events_by_severity": events_by_severity,
                    "events_by_user": events_by_user,
                    "generated_at": datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get audit statistics: {e}")
            return {"error": str(e)}
    
    def _flush_buffer(self) -> None:
        """Flush audit entries from buffer to database."""
        if not self.buffer:
            return
        
        try:
            with get_db_session() as db:
                for entry in self.buffer:
                    # Convert to database model
                    audit_record = AuditLogModel(
                        event_type=entry.event_type.value,
                        severity=entry.severity.value,
                        timestamp=entry.timestamp,
                        user_id=entry.user_id,
                        username=entry.username,
                        user_role=entry.user_role.value if entry.user_role else None,
                        session_id=entry.session_id,
                        client_ip=entry.client_ip,
                        user_agent=entry.user_agent,
                        correlation_id=entry.correlation_id,
                        resource_type=entry.resource_type,
                        resource_id=entry.resource_id,
                        action=entry.action,
                        description=entry.description,
                        old_values=json.dumps(entry.old_values) if entry.old_values else None,
                        new_values=json.dumps(entry.new_values) if entry.new_values else None,
                        changes=json.dumps(entry.changes) if entry.changes else None,
                        event_metadata=json.dumps(entry.metadata) if entry.metadata else None,
                        tags=json.dumps(entry.tags) if entry.tags else None,
                        success=entry.success,
                        error_message=entry.error_message
                    )
                    
                    db.add(audit_record)
                
                db.commit()
                self.buffer.clear()
                
        except Exception as e:
            self.logger.error(f"Failed to flush audit buffer: {e}")
    
    def _get_log_level(self, severity: AuditSeverity) -> int:
        """Get logging level for audit severity."""
        level_map = {
            AuditSeverity.LOW: logging.INFO,
            AuditSeverity.MEDIUM: logging.INFO,
            AuditSeverity.HIGH: logging.WARNING,
            AuditSeverity.CRITICAL: logging.ERROR
        }
        return level_map.get(severity, logging.INFO)
    
    def flush(self) -> None:
        """Manually flush the audit buffer."""
        self._flush_buffer()
    
    def set_auto_flush(self, enabled: bool) -> None:
        """Enable or disable automatic buffer flushing."""
        self.auto_flush = enabled


# Global audit logger instance
audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    return audit_logger


# Convenience functions for common audit events

def log_config_change(action: str, resource_type: str, resource_id: str,
                     description: str, session_info: Optional[SessionInfo] = None,
                     old_values: Optional[Dict[str, Any]] = None,
                     new_values: Optional[Dict[str, Any]] = None) -> AuditEntry:
    """Log a configuration change."""
    return audit_logger.log_configuration_change(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        description=description,
        session_info=session_info,
        old_values=old_values,
        new_values=new_values
    )


def log_auth_event(event_type: AuditEventType, description: str,
                  user_id: Optional[str] = None, username: Optional[str] = None,
                  success: bool = True, error_message: Optional[str] = None) -> AuditEntry:
    """Log an authentication event."""
    return audit_logger.log_authentication_event(
        event_type=event_type,
        description=description,
        user_id=user_id,
        username=username,
        success=success,
        error_message=error_message
    )


def log_security_event(event_type: AuditEventType, description: str,
                      severity: AuditSeverity = AuditSeverity.HIGH,
                      session_info: Optional[SessionInfo] = None) -> AuditEntry:
    """Log a security event."""
    return audit_logger.log_security_event(
        event_type=event_type,
        description=description,
        severity=severity,
        session_info=session_info
    )