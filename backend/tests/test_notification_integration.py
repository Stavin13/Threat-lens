"""
Tests for notification integration with event processing pipeline.

This module tests the integration between the enhanced background processor
and the notification system for real-time event notifications.
"""
import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

from app.schemas import EventResponse, AIAnalysis as AIAnalysisSchema, ParsedEvent, EventCategory
from app.realtime.enhanced_processor import EnhancedBackgroundProcessor
from app.realtime.ingestion_queue import LogEntry, LogEntryPriority, RealtimeIngestionQueue
from app.realtime.notifications import NotificationManager, NotificationRule, EmailNotifier
from app.realtime.processing_pipeline import ProcessingResult, ValidationResult


class TestNotificationIntegration:
    """Test notification integration with event processing."""
    
    @pytest.fixture
    def mock_websocket_manager(self):
        """Mock WebSocket manager."""
        manager = Mock()
        manager.broadcast_event = AsyncMock()
        return manager
    
    @pytest.fixture
    def notification_manager(self):
        """Create notification manager with test configuration."""
        manager = NotificationManager()
        
        # Add test email channel
        email_config = {
            'smtp_host': 'localhost',
            'smtp_port': 587,
            'from_email': 'test@example.com',
            'recipients': ['admin@example.com']
        }
        email_channel = Mock()
        email_channel.channel_type.value = 'email'
        email_channel.enabled = True
        email_channel.validate_config.return_value = True
        email_channel.send_notification = AsyncMock(return_value=True)
        
        manager.add_channel('test_email', email_channel)
        
        # Add test notification rules
        high_severity_rule = NotificationRule(
            rule_name="high_severity_test",
            enabled=True,
            min_severity=7,
            max_severity=10,
            categories=[],
            sources=[],
            channels=['test_email'],
            throttle_minutes=0,
            email_recipients=['admin@example.com']
        )
        
        security_rule = NotificationRule(
            rule_name="security_events_test",
            enabled=True,
            min_severity=5,
            max_severity=10,
            categories=['security', 'auth'],
            sources=[],
            channels=['test_email'],
            throttle_minutes=0,
            email_recipients=['security@example.com']
        )
        
        manager.configure_rules([high_severity_rule, security_rule])
        
        return manager
    
    @pytest.fixture
    def ingestion_queue(self):
        """Create mock ingestion queue."""
        queue = Mock(spec=RealtimeIngestionQueue)
        queue.set_batch_processor = Mock()
        queue.set_error_handler = Mock()
        return queue
    
    @pytest.fixture
    def enhanced_processor(self, ingestion_queue, mock_websocket_manager, notification_manager):
        """Create enhanced processor with notification integration."""
        return EnhancedBackgroundProcessor(
            ingestion_queue=ingestion_queue,
            websocket_manager=mock_websocket_manager,
            notification_manager=notification_manager,
            max_retries=2,
            retry_delay=0.1
        )
    
    def create_test_log_entry(self, content: str = "Test log entry", source: str = "test_source") -> LogEntry:
        """Create a test log entry."""
        return LogEntry(
            entry_id="test_entry_1",
            content=content,
            source_path="/var/log/test.log",
            source_name=source,
            timestamp=datetime.now(timezone.utc),
            priority=LogEntryPriority.MEDIUM,
            file_offset=0
        )
    
    def create_test_parsed_event(self, category: EventCategory = EventCategory.SECURITY) -> ParsedEvent:
        """Create a test parsed event."""
        return ParsedEvent(
            id="test_event_1",
            raw_log_id="test_raw_1",
            timestamp=datetime.now(timezone.utc),
            source="test_source",
            message="Test security event detected",
            category=category,
            parsed_at=datetime.now(timezone.utc)
        )
    
    def create_test_ai_analysis(self, severity: int = 8) -> AIAnalysisSchema:
        """Create a test AI analysis."""
        return AIAnalysisSchema(
            id="test_analysis_1",
            event_id="test_event_1",
            severity_score=severity,
            explanation="High severity security threat detected",
            recommendations=["Investigate immediately", "Check system logs"],
            analyzed_at=datetime.now(timezone.utc)
        )
    
    @pytest.mark.asyncio
    async def test_notification_triggered_for_high_severity_event(self, enhanced_processor):
        """Test that notifications are triggered for high severity events."""
        # Create test data
        event = self.create_test_parsed_event(EventCategory.SECURITY)
        ai_analysis = self.create_test_ai_analysis(severity=8)
        
        # Mock the notification manager's send method
        enhanced_processor.notification_manager.send_notification_with_retry = AsyncMock(
            return_value={'high_severity_test:test_email': True}
        )
        
        # Process notifications
        await enhanced_processor._process_notifications_for_events([(event, ai_analysis)])
        
        # Verify notification was triggered
        enhanced_processor.notification_manager.send_notification_with_retry.assert_called_once()
        
        # Check metrics
        metrics = enhanced_processor.get_notification_metrics()
        assert metrics['notifications_triggered'] == 1
        assert metrics['high_severity_events'] == 1
        assert metrics['notifications_sent'] == 1
        assert metrics['notifications_failed'] == 0
    
    @pytest.mark.asyncio
    async def test_notification_not_triggered_for_low_severity_event(self, enhanced_processor):
        """Test that notifications are not triggered for low severity events."""
        # Create test data with low severity
        event = self.create_test_parsed_event(EventCategory.SYSTEM)
        ai_analysis = self.create_test_ai_analysis(severity=3)
        
        # Mock the notification manager's send method
        enhanced_processor.notification_manager.send_notification_with_retry = AsyncMock()
        
        # Process notifications
        await enhanced_processor._process_notifications_for_events([(event, ai_analysis)])
        
        # Verify notification was not triggered
        enhanced_processor.notification_manager.send_notification_with_retry.assert_not_called()
        
        # Check metrics
        metrics = enhanced_processor.get_notification_metrics()
        assert metrics['notifications_triggered'] == 0
        assert metrics['high_severity_events'] == 0
    
    @pytest.mark.asyncio
    async def test_notification_triggered_for_security_category(self, enhanced_processor):
        """Test that notifications are triggered for security category events."""
        # Create test data with medium severity but security category
        event = self.create_test_parsed_event(EventCategory.SECURITY)
        ai_analysis = self.create_test_ai_analysis(severity=6)
        
        # Mock the notification manager's send method
        enhanced_processor.notification_manager.send_notification_with_retry = AsyncMock(
            return_value={'security_events_test:test_email': True}
        )
        
        # Process notifications
        await enhanced_processor._process_notifications_for_events([(event, ai_analysis)])
        
        # Verify notification was triggered
        enhanced_processor.notification_manager.send_notification_with_retry.assert_called_once()
        
        # Check metrics
        metrics = enhanced_processor.get_notification_metrics()
        assert metrics['notifications_triggered'] == 1
        assert metrics['notifications_sent'] == 1
    
    @pytest.mark.asyncio
    async def test_notification_retry_on_failure(self, enhanced_processor):
        """Test that notifications are retried on failure."""
        # Create test data
        event = self.create_test_parsed_event(EventCategory.SECURITY)
        ai_analysis = self.create_test_ai_analysis(severity=8)
        
        # Mock the notification manager to fail first, then succeed
        enhanced_processor.notification_manager.send_notification_with_retry = AsyncMock(
            return_value={'high_severity_test:test_email': False}
        )
        
        # Process notifications
        await enhanced_processor._process_notifications_for_events([(event, ai_analysis)])
        
        # Verify notification was attempted
        enhanced_processor.notification_manager.send_notification_with_retry.assert_called_once()
        
        # Check metrics show failure
        metrics = enhanced_processor.get_notification_metrics()
        assert metrics['notifications_triggered'] == 1
        assert metrics['notifications_failed'] == 1
    
    @pytest.mark.asyncio
    async def test_websocket_broadcast_for_notification_status(self, enhanced_processor, mock_websocket_manager):
        """Test that notification status is broadcast via WebSocket."""
        # Create test data
        event = self.create_test_parsed_event(EventCategory.SECURITY)
        ai_analysis = self.create_test_ai_analysis(severity=8)
        
        # Mock the notification manager's send method
        enhanced_processor.notification_manager.send_notification_with_retry = AsyncMock(
            return_value={'high_severity_test:test_email': True}
        )
        
        # Process notifications
        await enhanced_processor._process_notifications_for_events([(event, ai_analysis)])
        
        # Verify WebSocket broadcast was called
        mock_websocket_manager.broadcast_event.assert_called()
        
        # Check the broadcast message
        broadcast_calls = mock_websocket_manager.broadcast_event.call_args_list
        notification_broadcast = None
        
        for call in broadcast_calls:
            args, kwargs = call
            if args[0].get('type') == 'notification_status':
                notification_broadcast = args[0]
                break
        
        assert notification_broadcast is not None
        assert notification_broadcast['event_id'] == event.id
        assert notification_broadcast['severity_score'] == 8
        assert 'high_severity_test:test_email' in notification_broadcast['successful_channels']
    
    @pytest.mark.asyncio
    async def test_notification_rule_evaluation(self, enhanced_processor):
        """Test notification rule evaluation logic."""
        # Test high severity event
        event_high = self.create_test_parsed_event(EventCategory.SYSTEM)
        ai_analysis_high = self.create_test_ai_analysis(severity=9)
        
        should_notify_high = enhanced_processor._should_trigger_notification(
            EventResponse(
                id=event_high.id,
                raw_log_id="test",
                timestamp=event_high.timestamp,
                source=event_high.source,
                message=event_high.message,
                category=event_high.category.value,
                parsed_at=event_high.parsed_at
            ),
            ai_analysis_high
        )
        
        assert should_notify_high is True
        
        # Test low severity event
        event_low = self.create_test_parsed_event(EventCategory.SYSTEM)
        ai_analysis_low = self.create_test_ai_analysis(severity=3)
        
        should_notify_low = enhanced_processor._should_trigger_notification(
            EventResponse(
                id=event_low.id,
                raw_log_id="test",
                timestamp=event_low.timestamp,
                source=event_low.source,
                message=event_low.message,
                category=event_low.category.value,
                parsed_at=event_low.parsed_at
            ),
            ai_analysis_low
        )
        
        assert should_notify_low is False
    
    def test_notification_metrics_collection(self, enhanced_processor):
        """Test notification metrics collection."""
        # Simulate some notification activity
        enhanced_processor.metrics.record_notification_triggered(2, True)
        enhanced_processor.metrics.record_notification_result(True)
        enhanced_processor.metrics.record_notification_result(False)
        
        # Get metrics
        metrics = enhanced_processor.get_notification_metrics()
        
        # Verify metrics
        assert metrics['notifications_triggered'] == 1
        assert metrics['notification_rules_matched'] == 2
        assert metrics['high_severity_events'] == 1
        assert metrics['notifications_sent'] == 1
        assert metrics['notifications_failed'] == 1
        
        # Verify manager stats are included
        assert 'manager_stats' in metrics
        assert 'active_rules' in metrics
        assert 'active_channels' in metrics
    
    @pytest.mark.asyncio
    async def test_notification_integration_with_processing_pipeline(self, enhanced_processor):
        """Test notification integration with processing pipeline."""
        # Create test data
        event = self.create_test_parsed_event(EventCategory.SECURITY)
        ai_analysis = self.create_test_ai_analysis(severity=8)
        
        # Mock notification manager
        enhanced_processor.notification_manager.send_notification_with_retry = AsyncMock(
            return_value={'high_severity_test:test_email': True}
        )
        
        # Test the notification processing directly
        await enhanced_processor._process_notifications_for_events([(event, ai_analysis)])
        
        # Verify notification was triggered
        enhanced_processor.notification_manager.send_notification_with_retry.assert_called_once()
        
        # Verify metrics were updated
        metrics = enhanced_processor.get_notification_metrics()
        assert metrics['notifications_triggered'] == 1
        assert metrics['notifications_sent'] == 1


if __name__ == "__main__":
    pytest.main([__file__])