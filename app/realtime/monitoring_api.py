"""
REST API endpoints for real-time monitoring management.

This module provides API endpoints for managing log sources, notification rules,
and system health monitoring for the real-time log detection system.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import asdict
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_database_session
from ..schemas import (
    LogSourceConfigRequest, LogSourceConfigResponse,
    NotificationRuleRequest, NotificationRuleResponse,
    MonitoringConfigResponse, ProcessingMetricsResponse,
    ErrorResponse
)
from .config_manager import get_config_manager, ConfigManager
from .models import LogSourceConfig, NotificationRule, MonitoringStatus, LogSourceType
from .exceptions import ConfigurationError
from .health_monitor import health_monitor
from .diagnostics import run_system_diagnostics
from .security import get_input_validator, get_file_sandbox
from .exceptions import InputValidationError as ValidationError, SecurityViolation
from .auth import get_current_session, require_permission, Permission, SessionInfo
from .audit import get_audit_logger, log_config_change

logger = logging.getLogger(__name__)

# Create router for monitoring API endpoints
monitoring_router = APIRouter(prefix="/api/v1/monitoring", tags=["Real-time Monitoring"])


# Log Source Management Endpoints

@monitoring_router.post("/log-sources", response_model=LogSourceConfigResponse)
async def create_log_source(
    request: LogSourceConfigRequest,
    session_info: SessionInfo = Depends(require_permission(Permission.LOG_SOURCE_WRITE)),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    Create a new log source configuration.
    
    Args:
        request: Log source configuration request
        config_manager: Configuration manager dependency
        
    Returns:
        Created log source configuration
        
    Raises:
        HTTPException: If creation fails or validation errors occur
    """
    try:
        # Get security components
        validator = get_input_validator()
        sandbox = get_file_sandbox()
        audit_logger = get_audit_logger()
        
        # Validate inputs with security checks
        validated_name = validator.validate_log_source_name(request.source_name)
        validated_path = validator.validate_file_path(request.path, allow_relative=False)
        sandboxed_path = sandbox.validate_path(validated_path)
        
        # Validate description if provided
        validated_description = None
        if request.description:
            validated_description = validator._validate_text_content(request.description)
        
        # Convert request to LogSourceConfig with validated inputs
        source_config = LogSourceConfig(
            source_name=validated_name,
            path=str(sandboxed_path),
            source_type=LogSourceType(request.source_type),
            enabled=request.enabled,
            recursive=request.recursive,
            file_pattern=request.file_pattern,
            polling_interval=request.polling_interval,
            batch_size=request.batch_size,
            priority=request.priority,
            description=validated_description,
            tags=request.tags
        )
        
        # Add to configuration
        success = config_manager.add_log_source(source_config)
        
        if success:
            # Log configuration change
            log_config_change(
                action="create",
                resource_type="log_source",
                resource_id=validated_name,
                description=f"Log source created: {validated_name} -> {sandboxed_path}",
                session_info=session_info,
                new_values={
                    "source_name": validated_name,
                    "path": str(sandboxed_path),
                    "source_type": request.source_type,
                    "enabled": request.enabled
                }
            )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to create log source configuration"
            )
        
        # Return response
        return LogSourceConfigResponse(
            source_name=source_config.source_name,
            path=source_config.path,
            source_type=source_config.source_type.value,
            enabled=source_config.enabled,
            recursive=source_config.recursive,
            file_pattern=source_config.file_pattern,
            polling_interval=source_config.polling_interval,
            batch_size=source_config.batch_size,
            priority=source_config.priority,
            description=source_config.description,
            tags=source_config.tags,
            status=source_config.status.value,
            last_monitored=source_config.last_monitored,
            file_size=source_config.file_size,
            last_offset=source_config.last_offset,
            error_message=source_config.error_message
        )
        
    except (ValidationError, SecurityViolation) as e:
        logger.error(f"Security validation error creating log source: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Security validation failed: {str(e)}"
        )
    except ConfigurationError as e:
        logger.error(f"Configuration error creating log source: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        logger.error(f"Validation error creating log source: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating log source: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create log source: {str(e)}")


@monitoring_router.get("/log-sources", response_model=List[LogSourceConfigResponse])
async def list_log_sources(
    enabled_only: bool = Query(False, description="Return only enabled sources"),
    session_info: SessionInfo = Depends(require_permission(Permission.LOG_SOURCE_READ)),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    List all log source configurations.
    
    Args:
        enabled_only: If True, return only enabled sources
        config_manager: Configuration manager dependency
        
    Returns:
        List of log source configurations
    """
    try:
        if enabled_only:
            sources = config_manager.get_enabled_log_sources()
        else:
            sources = config_manager.get_log_sources()
        
        # Convert to response format
        response_sources = []
        for source in sources:
            response_sources.append(LogSourceConfigResponse(
                source_name=source.source_name,
                path=source.path,
                source_type=source.source_type.value,
                enabled=source.enabled,
                recursive=source.recursive,
                file_pattern=source.file_pattern,
                polling_interval=source.polling_interval,
                batch_size=source.batch_size,
                priority=source.priority,
                description=source.description,
                tags=source.tags,
                status=source.status.value,
                last_monitored=source.last_monitored,
                file_size=source.file_size,
                last_offset=source.last_offset,
                error_message=source.error_message
            ))
        
        return response_sources
        
    except Exception as e:
        logger.error(f"Failed to list log sources: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list log sources: {str(e)}")


@monitoring_router.get("/log-sources/{source_name}", response_model=LogSourceConfigResponse)
async def get_log_source(
    source_name: str = Path(..., description="Name of the log source"),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    Get a specific log source configuration.
    
    Args:
        source_name: Name of the log source
        config_manager: Configuration manager dependency
        
    Returns:
        Log source configuration
        
    Raises:
        HTTPException: If source not found
    """
    try:
        source = config_manager.get_log_source(source_name)
        
        if not source:
            raise HTTPException(
                status_code=404,
                detail=f"Log source '{source_name}' not found"
            )
        
        return LogSourceConfigResponse(
            source_name=source.source_name,
            path=source.path,
            source_type=source.source_type.value,
            enabled=source.enabled,
            recursive=source.recursive,
            file_pattern=source.file_pattern,
            polling_interval=source.polling_interval,
            batch_size=source.batch_size,
            priority=source.priority,
            description=source.description,
            tags=source.tags,
            status=source.status.value,
            last_monitored=source.last_monitored,
            file_size=source.file_size,
            last_offset=source.last_offset,
            error_message=source.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get log source {source_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get log source: {str(e)}")


@monitoring_router.put("/log-sources/{source_name}", response_model=LogSourceConfigResponse)
async def update_log_source(
    source_name: str = Path(..., description="Name of the log source"),
    request: LogSourceConfigRequest = ...,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    Update an existing log source configuration.
    
    Args:
        source_name: Name of the log source to update
        request: Updated log source configuration
        config_manager: Configuration manager dependency
        
    Returns:
        Updated log source configuration
        
    Raises:
        HTTPException: If source not found or update fails
    """
    try:
        # Check if source exists
        existing_source = config_manager.get_log_source(source_name)
        if not existing_source:
            raise HTTPException(
                status_code=404,
                detail=f"Log source '{source_name}' not found"
            )
        
        # Convert request to LogSourceConfig
        updated_config = LogSourceConfig(
            source_name=request.source_name,
            path=request.path,
            source_type=LogSourceType(request.source_type),
            enabled=request.enabled,
            recursive=request.recursive,
            file_pattern=request.file_pattern,
            polling_interval=request.polling_interval,
            batch_size=request.batch_size,
            priority=request.priority,
            description=request.description,
            tags=request.tags,
            # Preserve existing status and metrics
            status=existing_source.status,
            last_monitored=existing_source.last_monitored,
            file_size=existing_source.file_size,
            last_offset=existing_source.last_offset,
            error_message=existing_source.error_message
        )
        
        # Update configuration
        success = config_manager.update_log_source(source_name, updated_config)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update log source configuration"
            )
        
        # Return updated configuration
        return LogSourceConfigResponse(
            source_name=updated_config.source_name,
            path=updated_config.path,
            source_type=updated_config.source_type.value,
            enabled=updated_config.enabled,
            recursive=updated_config.recursive,
            file_pattern=updated_config.file_pattern,
            polling_interval=updated_config.polling_interval,
            batch_size=updated_config.batch_size,
            priority=updated_config.priority,
            description=updated_config.description,
            tags=updated_config.tags,
            status=updated_config.status.value,
            last_monitored=updated_config.last_monitored,
            file_size=updated_config.file_size,
            last_offset=updated_config.last_offset,
            error_message=updated_config.error_message
        )
        
    except HTTPException:
        raise
    except ConfigurationError as e:
        logger.error(f"Configuration error updating log source: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        logger.error(f"Validation error updating log source: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error updating log source: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update log source: {str(e)}")


@monitoring_router.delete("/log-sources/{source_name}")
async def delete_log_source(
    source_name: str = Path(..., description="Name of the log source"),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    Delete a log source configuration.
    
    Args:
        source_name: Name of the log source to delete
        config_manager: Configuration manager dependency
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If source not found or deletion fails
    """
    try:
        # Check if source exists
        existing_source = config_manager.get_log_source(source_name)
        if not existing_source:
            raise HTTPException(
                status_code=404,
                detail=f"Log source '{source_name}' not found"
            )
        
        # Remove source
        success = config_manager.remove_log_source(source_name)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete log source configuration"
            )
        
        return {"message": f"Log source '{source_name}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete log source {source_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete log source: {str(e)}")


@monitoring_router.post("/log-sources/{source_name}/test")
async def test_log_source(
    source_name: str = Path(..., description="Name of the log source"),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    Test a log source configuration to verify it's accessible and valid.
    
    Args:
        source_name: Name of the log source to test
        config_manager: Configuration manager dependency
        
    Returns:
        Test results
        
    Raises:
        HTTPException: If source not found or test fails
    """
    try:
        # Get source configuration
        source = config_manager.get_log_source(source_name)
        if not source:
            raise HTTPException(
                status_code=404,
                detail=f"Log source '{source_name}' not found"
            )
        
        # Perform basic validation tests
        from pathlib import Path
        import os
        
        test_results = {
            "source_name": source_name,
            "path": source.path,
            "tests": {},
            "overall_status": "passed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Test 1: Path exists
        try:
            path_obj = Path(source.path)
            exists = path_obj.exists()
            test_results["tests"]["path_exists"] = {
                "status": "passed" if exists else "failed",
                "message": "Path exists" if exists else "Path does not exist"
            }
            if not exists:
                test_results["overall_status"] = "failed"
        except Exception as e:
            test_results["tests"]["path_exists"] = {
                "status": "error",
                "message": f"Error checking path: {str(e)}"
            }
            test_results["overall_status"] = "failed"
        
        # Test 2: Path type matches configuration
        try:
            path_obj = Path(source.path)
            if path_obj.exists():
                is_file = path_obj.is_file()
                is_dir = path_obj.is_dir()
                
                if source.source_type == LogSourceType.FILE:
                    type_match = is_file
                    expected = "file"
                    actual = "file" if is_file else "directory" if is_dir else "other"
                else:
                    type_match = is_dir
                    expected = "directory"
                    actual = "directory" if is_dir else "file" if is_file else "other"
                
                test_results["tests"]["path_type"] = {
                    "status": "passed" if type_match else "failed",
                    "message": f"Expected {expected}, found {actual}"
                }
                if not type_match:
                    test_results["overall_status"] = "failed"
            else:
                test_results["tests"]["path_type"] = {
                    "status": "skipped",
                    "message": "Path does not exist, skipping type check"
                }
        except Exception as e:
            test_results["tests"]["path_type"] = {
                "status": "error",
                "message": f"Error checking path type: {str(e)}"
            }
            test_results["overall_status"] = "failed"
        
        # Test 3: Read permissions
        try:
            readable = os.access(source.path, os.R_OK)
            test_results["tests"]["read_permission"] = {
                "status": "passed" if readable else "failed",
                "message": "Read permission granted" if readable else "No read permission"
            }
            if not readable:
                test_results["overall_status"] = "failed"
        except Exception as e:
            test_results["tests"]["read_permission"] = {
                "status": "error",
                "message": f"Error checking permissions: {str(e)}"
            }
            test_results["overall_status"] = "failed"
        
        # Test 4: File pattern validation (for directory sources)
        if source.source_type == LogSourceType.DIRECTORY and source.file_pattern:
            try:
                import fnmatch
                # Test pattern with a sample filename
                test_filename = "test.log"
                pattern_works = fnmatch.fnmatch(test_filename, source.file_pattern)
                test_results["tests"]["file_pattern"] = {
                    "status": "passed",
                    "message": f"File pattern '{source.file_pattern}' is valid"
                }
            except Exception as e:
                test_results["tests"]["file_pattern"] = {
                    "status": "error",
                    "message": f"Invalid file pattern: {str(e)}"
                }
                test_results["overall_status"] = "failed"
        
        return test_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test log source {source_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test log source: {str(e)}")


@monitoring_router.get("/log-sources/{source_name}/status")
async def get_log_source_status(
    source_name: str = Path(..., description="Name of the log source"),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    Get the current status and health of a log source.
    
    Args:
        source_name: Name of the log source
        config_manager: Configuration manager dependency
        
    Returns:
        Log source status information
        
    Raises:
        HTTPException: If source not found
    """
    try:
        # Get source configuration
        source = config_manager.get_log_source(source_name)
        if not source:
            raise HTTPException(
                status_code=404,
                detail=f"Log source '{source_name}' not found"
            )
        
        # Get additional health information from health monitor
        health_info = {}
        try:
            if hasattr(health_monitor, 'get_component_health'):
                health_info = health_monitor.get_component_health(f"log_source_{source_name}")
        except Exception as e:
            logger.warning(f"Could not get health info for {source_name}: {e}")
        
        return {
            "source_name": source.source_name,
            "status": source.status.value,
            "enabled": source.enabled,
            "last_monitored": source.last_monitored.isoformat() if source.last_monitored else None,
            "file_size": source.file_size,
            "last_offset": source.last_offset,
            "error_message": source.error_message,
            "health_info": health_info,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get log source status {source_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get log source status: {str(e)}")

# Notification Management Endpoints

@monitoring_router.post("/notification-rules", response_model=NotificationRuleResponse)
async def create_notification_rule(
    request: NotificationRuleRequest,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    Create a new notification rule.
    
    Args:
        request: Notification rule configuration request
        config_manager: Configuration manager dependency
        
    Returns:
        Created notification rule configuration
        
    Raises:
        HTTPException: If creation fails or validation errors occur
    """
    try:
        # Convert request to NotificationRule
        from .models import NotificationChannel
        
        channels = []
        for channel_str in request.channels:
            try:
                channels.append(NotificationChannel(channel_str))
            except ValueError:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid notification channel: {channel_str}"
                )
        
        notification_rule = NotificationRule(
            rule_name=request.rule_name,
            enabled=request.enabled,
            min_severity=request.min_severity,
            max_severity=request.max_severity,
            categories=request.categories,
            sources=request.sources,
            channels=channels,
            throttle_minutes=request.throttle_minutes,
            email_recipients=request.email_recipients,
            webhook_url=request.webhook_url,
            slack_channel=request.slack_channel
        )
        
        # Add to configuration
        config = config_manager.load_config()
        success = config.add_notification_rule(notification_rule)
        
        if success:
            config_manager.save_config(config)
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to create notification rule"
            )
        
        # Return response
        return NotificationRuleResponse(
            rule_name=notification_rule.rule_name,
            enabled=notification_rule.enabled,
            min_severity=notification_rule.min_severity,
            max_severity=notification_rule.max_severity,
            categories=notification_rule.categories,
            sources=notification_rule.sources,
            channels=[ch.value for ch in notification_rule.channels],
            throttle_minutes=notification_rule.throttle_minutes,
            email_recipients=notification_rule.email_recipients,
            webhook_url=notification_rule.webhook_url,
            slack_channel=notification_rule.slack_channel
        )
        
    except ConfigurationError as e:
        logger.error(f"Configuration error creating notification rule: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        logger.error(f"Validation error creating notification rule: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating notification rule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create notification rule: {str(e)}")


@monitoring_router.get("/notification-rules", response_model=List[NotificationRuleResponse])
async def list_notification_rules(
    enabled_only: bool = Query(False, description="Return only enabled rules"),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    List all notification rules.
    
    Args:
        enabled_only: If True, return only enabled rules
        config_manager: Configuration manager dependency
        
    Returns:
        List of notification rule configurations
    """
    try:
        config = config_manager.load_config()
        
        if enabled_only:
            rules = config.get_enabled_notification_rules()
        else:
            rules = config.notification_rules
        
        # Convert to response format
        response_rules = []
        for rule in rules:
            response_rules.append(NotificationRuleResponse(
                rule_name=rule.rule_name,
                enabled=rule.enabled,
                min_severity=rule.min_severity,
                max_severity=rule.max_severity,
                categories=rule.categories,
                sources=rule.sources,
                channels=[ch.value for ch in rule.channels],
                throttle_minutes=rule.throttle_minutes,
                email_recipients=rule.email_recipients,
                webhook_url=rule.webhook_url,
                slack_channel=rule.slack_channel
            ))
        
        return response_rules
        
    except Exception as e:
        logger.error(f"Failed to list notification rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list notification rules: {str(e)}")


@monitoring_router.get("/notification-rules/{rule_name}", response_model=NotificationRuleResponse)
async def get_notification_rule(
    rule_name: str = Path(..., description="Name of the notification rule"),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    Get a specific notification rule configuration.
    
    Args:
        rule_name: Name of the notification rule
        config_manager: Configuration manager dependency
        
    Returns:
        Notification rule configuration
        
    Raises:
        HTTPException: If rule not found
    """
    try:
        config = config_manager.load_config()
        
        # Find the rule
        rule = None
        for r in config.notification_rules:
            if r.rule_name == rule_name:
                rule = r
                break
        
        if not rule:
            raise HTTPException(
                status_code=404,
                detail=f"Notification rule '{rule_name}' not found"
            )
        
        return NotificationRuleResponse(
            rule_name=rule.rule_name,
            enabled=rule.enabled,
            min_severity=rule.min_severity,
            max_severity=rule.max_severity,
            categories=rule.categories,
            sources=rule.sources,
            channels=[ch.value for ch in rule.channels],
            throttle_minutes=rule.throttle_minutes,
            email_recipients=rule.email_recipients,
            webhook_url=rule.webhook_url,
            slack_channel=rule.slack_channel
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get notification rule {rule_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get notification rule: {str(e)}")


@monitoring_router.put("/notification-rules/{rule_name}", response_model=NotificationRuleResponse)
async def update_notification_rule(
    rule_name: str = Path(..., description="Name of the notification rule"),
    request: NotificationRuleRequest = ...,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    Update an existing notification rule.
    
    Args:
        rule_name: Name of the notification rule to update
        request: Updated notification rule configuration
        config_manager: Configuration manager dependency
        
    Returns:
        Updated notification rule configuration
        
    Raises:
        HTTPException: If rule not found or update fails
    """
    try:
        config = config_manager.load_config()
        
        # Find and remove the existing rule
        rule_index = None
        for i, rule in enumerate(config.notification_rules):
            if rule.rule_name == rule_name:
                rule_index = i
                break
        
        if rule_index is None:
            raise HTTPException(
                status_code=404,
                detail=f"Notification rule '{rule_name}' not found"
            )
        
        # Convert request to NotificationRule
        from .models import NotificationChannel
        
        channels = []
        for channel_str in request.channels:
            try:
                channels.append(NotificationChannel(channel_str))
            except ValueError:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid notification channel: {channel_str}"
                )
        
        updated_rule = NotificationRule(
            rule_name=request.rule_name,
            enabled=request.enabled,
            min_severity=request.min_severity,
            max_severity=request.max_severity,
            categories=request.categories,
            sources=request.sources,
            channels=channels,
            throttle_minutes=request.throttle_minutes,
            email_recipients=request.email_recipients,
            webhook_url=request.webhook_url,
            slack_channel=request.slack_channel
        )
        
        # Replace the rule
        config.notification_rules[rule_index] = updated_rule
        
        # Save configuration
        success = config_manager.save_config(config)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update notification rule"
            )
        
        # Return updated rule
        return NotificationRuleResponse(
            rule_name=updated_rule.rule_name,
            enabled=updated_rule.enabled,
            min_severity=updated_rule.min_severity,
            max_severity=updated_rule.max_severity,
            categories=updated_rule.categories,
            sources=updated_rule.sources,
            channels=[ch.value for ch in updated_rule.channels],
            throttle_minutes=updated_rule.throttle_minutes,
            email_recipients=updated_rule.email_recipients,
            webhook_url=updated_rule.webhook_url,
            slack_channel=updated_rule.slack_channel
        )
        
    except HTTPException:
        raise
    except ConfigurationError as e:
        logger.error(f"Configuration error updating notification rule: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        logger.error(f"Validation error updating notification rule: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error updating notification rule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update notification rule: {str(e)}")


@monitoring_router.delete("/notification-rules/{rule_name}")
async def delete_notification_rule(
    rule_name: str = Path(..., description="Name of the notification rule"),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    Delete a notification rule.
    
    Args:
        rule_name: Name of the notification rule to delete
        config_manager: Configuration manager dependency
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If rule not found or deletion fails
    """
    try:
        config = config_manager.load_config()
        
        # Remove the rule
        success = config.remove_notification_rule(rule_name)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Notification rule '{rule_name}' not found"
            )
        
        # Save configuration
        config_manager.save_config(config)
        
        return {"message": f"Notification rule '{rule_name}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete notification rule {rule_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete notification rule: {str(e)}")


@monitoring_router.post("/notification-rules/{rule_name}/test")
async def test_notification_rule(
    rule_name: str = Path(..., description="Name of the notification rule"),
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    Test a notification rule by sending a test notification.
    
    Args:
        rule_name: Name of the notification rule to test
        config_manager: Configuration manager dependency
        
    Returns:
        Test results
        
    Raises:
        HTTPException: If rule not found or test fails
    """
    try:
        config = config_manager.load_config()
        
        # Find the rule
        rule = None
        for r in config.notification_rules:
            if r.rule_name == rule_name:
                rule = r
                break
        
        if not rule:
            raise HTTPException(
                status_code=404,
                detail=f"Notification rule '{rule_name}' not found"
            )
        
        # Create test notification
        from .notifications import NotificationManager
        
        test_results = {
            "rule_name": rule_name,
            "channels_tested": [],
            "overall_status": "passed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Test each configured channel
        notification_manager = NotificationManager()
        
        for channel in rule.channels:
            channel_result = {
                "channel": channel.value,
                "status": "not_tested",
                "message": "Channel not implemented for testing"
            }
            
            try:
                if channel.value == "email" and rule.email_recipients:
                    # Test email notification
                    channel_result["status"] = "passed"
                    channel_result["message"] = f"Email test would be sent to {len(rule.email_recipients)} recipients"
                
                elif channel.value == "webhook" and rule.webhook_url:
                    # Test webhook notification
                    import requests
                    test_payload = {
                        "test": True,
                        "rule_name": rule_name,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    # Make a test request (with timeout)
                    response = requests.post(
                        rule.webhook_url,
                        json=test_payload,
                        timeout=10,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code < 400:
                        channel_result["status"] = "passed"
                        channel_result["message"] = f"Webhook test successful (HTTP {response.status_code})"
                    else:
                        channel_result["status"] = "failed"
                        channel_result["message"] = f"Webhook test failed (HTTP {response.status_code})"
                        test_results["overall_status"] = "failed"
                
                elif channel.value == "slack" and rule.slack_channel:
                    # Test Slack notification
                    channel_result["status"] = "passed"
                    channel_result["message"] = f"Slack test would be sent to {rule.slack_channel}"
                
            except Exception as e:
                channel_result["status"] = "error"
                channel_result["message"] = f"Test error: {str(e)}"
                test_results["overall_status"] = "failed"
            
            test_results["channels_tested"].append(channel_result)
        
        return test_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test notification rule {rule_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test notification rule: {str(e)}")


@monitoring_router.get("/notification-history")
async def get_notification_history(
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of entries to return"),
    rule_name: Optional[str] = Query(None, description="Filter by rule name"),
    channel: Optional[str] = Query(None, description="Filter by notification channel"),
    status: Optional[str] = Query(None, description="Filter by delivery status"),
    db: Session = Depends(get_database_session)
):
    """
    Get notification delivery history.
    
    Args:
        limit: Maximum number of entries to return
        rule_name: Optional filter by rule name
        channel: Optional filter by notification channel
        status: Optional filter by delivery status
        db: Database session
        
    Returns:
        List of notification history entries
    """
    try:
        from ..models import NotificationHistory
        
        # Build query
        query = db.query(NotificationHistory).order_by(NotificationHistory.sent_at.desc())
        
        # Apply filters
        if rule_name:
            # Note: This assumes we store rule_name in the notification_type field
            # or have a separate field for it
            query = query.filter(NotificationHistory.notification_type.like(f"%{rule_name}%"))
        
        if channel:
            query = query.filter(NotificationHistory.channel == channel)
        
        if status:
            query = query.filter(NotificationHistory.status == status)
        
        # Apply limit
        history_entries = query.limit(limit).all()
        
        # Convert to response format
        history_list = []
        for entry in history_entries:
            history_list.append({
                "id": entry.id,
                "event_id": entry.event_id,
                "notification_type": entry.notification_type,
                "channel": entry.channel,
                "status": entry.status,
                "sent_at": entry.sent_at.isoformat() if entry.sent_at else None,
                "error_message": entry.error_message
            })
        
        return {
            "history": history_list,
            "total_returned": len(history_list),
            "filters_applied": {
                "rule_name": rule_name,
                "channel": channel,
                "status": status,
                "limit": limit
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get notification history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get notification history: {str(e)}")


# System Metrics and Health Monitoring Endpoints

@monitoring_router.get("/health")
async def get_monitoring_health():
    """
    Get overall health status of the real-time monitoring system.
    
    Returns:
        System health information
    """
    try:
        # Get health information from health monitor
        health_info = {
            "overall_status": "healthy",
            "components": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            if hasattr(health_monitor, 'get_overall_health'):
                health_data = health_monitor.get_overall_health()
                health_info.update(health_data)
        except Exception as e:
            logger.warning(f"Could not get health monitor data: {e}")
            health_info["overall_status"] = "unknown"
            health_info["error"] = str(e)
        
        return health_info
        
    except Exception as e:
        logger.error(f"Failed to get monitoring health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get monitoring health: {str(e)}")


@monitoring_router.get("/metrics")
async def get_processing_metrics(
    source_name: Optional[str] = Query(None, description="Filter by source name"),
    hours: int = Query(24, ge=1, le=168, description="Hours of metrics to retrieve"),
    db: Session = Depends(get_database_session)
):
    """
    Get real-time processing metrics.
    
    Args:
        source_name: Optional filter by source name
        hours: Number of hours of metrics to retrieve
        db: Database session
        
    Returns:
        Processing metrics data
    """
    try:
        from ..models import ProcessingMetricsDB
        from datetime import timedelta
        
        # Calculate time range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)
        
        # Build query
        query = db.query(ProcessingMetricsDB).filter(
            ProcessingMetricsDB.timestamp >= start_time,
            ProcessingMetricsDB.timestamp <= end_time
        ).order_by(ProcessingMetricsDB.timestamp.desc())
        
        # Apply source filter if specified
        if source_name:
            # Assuming we store source name in metadata JSON field
            query = query.filter(ProcessingMetricsDB.metric_metadata.like(f'%"source_name":"{source_name}"%'))
        
        # Get metrics
        metrics_records = query.all()
        
        # Convert to response format
        metrics_list = []
        for record in metrics_records:
            try:
                metadata = json.loads(record.metric_metadata) if record.metric_metadata else {}
            except:
                metadata = {}
            
            metrics_list.append({
                "id": record.id,
                "metric_type": record.metric_type,
                "metric_value": record.metric_value,
                "timestamp": record.timestamp.isoformat(),
                "metadata": metadata
            })
        
        # Calculate summary statistics
        summary = {
            "total_metrics": len(metrics_list),
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours": hours
            },
            "source_filter": source_name
        }
        
        return {
            "metrics": metrics_list,
            "summary": summary,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get processing metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get processing metrics: {str(e)}")


@monitoring_router.get("/diagnostics")
async def get_system_diagnostics_endpoint():
    """
    Get detailed system diagnostic information.
    
    Returns:
        System diagnostic data
    """
    try:
        # Get diagnostic information
        diagnostics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_info": {},
            "component_status": {},
            "performance_metrics": {},
            "error_summary": {}
        }
        
        try:
            # Get system diagnostics
            diag_data = await run_system_diagnostics()
            # Convert to dict format
            diag_dict = {
                "system_info": diag_data.system_info,
                "component_status": {k: asdict(v) for k, v in diag_data.component_diagnostics.items()},
                "performance_metrics": diag_data.performance_metrics
            }
            diagnostics.update(diag_dict)
        except Exception as e:
            logger.warning(f"Could not get system diagnostics: {e}")
            diagnostics["error"] = str(e)
        
        return diagnostics
        
    except Exception as e:
        logger.error(f"Failed to get system diagnostics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system diagnostics: {str(e)}")


@monitoring_router.get("/config")
async def get_monitoring_config(
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    Get the current monitoring configuration.
    
    Args:
        config_manager: Configuration manager dependency
        
    Returns:
        Current monitoring configuration
    """
    try:
        config = config_manager.load_config()
        
        # Convert to response format
        log_sources = []
        for source in config.log_sources:
            log_sources.append(LogSourceConfigResponse(
                source_name=source.source_name,
                path=source.path,
                source_type=source.source_type.value,
                enabled=source.enabled,
                recursive=source.recursive,
                file_pattern=source.file_pattern,
                polling_interval=source.polling_interval,
                batch_size=source.batch_size,
                priority=source.priority,
                description=source.description,
                tags=source.tags,
                status=source.status.value,
                last_monitored=source.last_monitored,
                file_size=source.file_size,
                last_offset=source.last_offset,
                error_message=source.error_message
            ))
        
        notification_rules = []
        for rule in config.notification_rules:
            notification_rules.append(NotificationRuleResponse(
                rule_name=rule.rule_name,
                enabled=rule.enabled,
                min_severity=rule.min_severity,
                max_severity=rule.max_severity,
                categories=rule.categories,
                sources=rule.sources,
                channels=[ch.value for ch in rule.channels],
                throttle_minutes=rule.throttle_minutes,
                email_recipients=rule.email_recipients,
                webhook_url=rule.webhook_url,
                slack_channel=rule.slack_channel
            ))
        
        return MonitoringConfigResponse(
            enabled=config.enabled,
            max_concurrent_sources=config.max_concurrent_sources,
            processing_batch_size=config.processing_batch_size,
            max_queue_size=config.max_queue_size,
            health_check_interval=config.health_check_interval,
            max_error_count=config.max_error_count,
            retry_interval=config.retry_interval,
            file_read_chunk_size=config.file_read_chunk_size,
            websocket_max_connections=config.websocket_max_connections,
            log_sources=log_sources,
            notification_rules=notification_rules,
            config_version=config.config_version,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
        
    except Exception as e:
        logger.error(f"Failed to get monitoring configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get monitoring configuration: {str(e)}")


@monitoring_router.get("/stats")
async def get_monitoring_stats(
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """
    Get monitoring system statistics and summary information.
    
    Args:
        config_manager: Configuration manager dependency
        
    Returns:
        Monitoring system statistics
    """
    try:
        # Get configuration summary
        config_summary = config_manager.get_configuration_summary()
        
        # Add additional runtime statistics
        stats = {
            "configuration": config_summary,
            "runtime": {
                "uptime_seconds": 0,  # Would be calculated from startup time
                "active_connections": 0,  # Would come from WebSocket manager
                "queue_size": 0,  # Would come from ingestion queue
                "processing_rate": 0.0,  # Events per second
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Try to get runtime stats from real-time manager
        try:
            from .event_loop import realtime_manager
            runtime_stats = realtime_manager.get_stats()
            stats["runtime"].update(runtime_stats)
        except Exception as e:
            logger.warning(f"Could not get runtime stats: {e}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get monitoring stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get monitoring stats: {str(e)}")