#!/usr/bin/env python3
"""
Example demonstrating notification integration with event processing pipeline.

This example shows how the enhanced background processor integrates with
the notification system to send alerts for high-priority security events.
"""
import asyncio
from datetime import datetime, timezone
from app.schemas import EventResponse, AIAnalysis as AIAnalysisSchema
from app.realtime.notifications import NotificationManager, NotificationRule, NotificationChannelType
from app.realtime.enhanced_processor import EnhancedBackgroundProcessor


class ExampleNotificationChannel:
    """Example notification channel for demonstration."""
    
    def __init__(self, channel_type: NotificationChannelType, name: str):
        self.channel_type = channel_type
        self.name = name
        self.enabled = True
        self.sent_notifications = []
    
    def validate_config(self) -> bool:
        return True
    
    async def send_notification(self, context) -> bool:
        """Simulate sending a notification."""
        self.sent_notifications.append(context)
        
        print(f"📧 {self.name} Notification Sent!")
        print(f"   Event: {context.event.id}")
        print(f"   Source: {context.event.source}")
        print(f"   Category: {context.event.category}")
        print(f"   Message: {context.event.message}")
        
        if context.ai_analysis:
            print(f"   Severity: {context.ai_analysis.severity_score}/10")
            print(f"   Analysis: {context.ai_analysis.explanation}")
        
        print(f"   Rule: {context.rule_name}")
        print(f"   Channel: {context.channel_type}")
        print()
        
        return True


async def demonstrate_notification_integration():
    """Demonstrate notification integration with various scenarios."""
    print("🔔 ThreatLens Notification Integration Demo")
    print("=" * 50)
    
    # Setup notification manager
    notification_manager = NotificationManager()
    
    # Add notification channels
    email_channel = ExampleNotificationChannel(NotificationChannelType.EMAIL, "Email Alert")
    slack_channel = ExampleNotificationChannel(NotificationChannelType.SLACK, "Slack Alert")
    webhook_channel = ExampleNotificationChannel(NotificationChannelType.WEBHOOK, "Webhook Alert")
    
    notification_manager.add_channel('email', email_channel)
    notification_manager.add_channel('slack', slack_channel)
    notification_manager.add_channel('webhook', webhook_channel)
    
    # Configure notification rules
    rules = [
        NotificationRule(
            rule_name="critical_security_alerts",
            enabled=True,
            min_severity=8,
            max_severity=10,
            categories=[],  # All categories
            sources=[],     # All sources
            channels=['email', 'slack'],
            throttle_minutes=0,
            email_recipients=['security@company.com'],
            slack_channel='#security-alerts'
        ),
        NotificationRule(
            rule_name="high_severity_events",
            enabled=True,
            min_severity=7,
            max_severity=10,
            categories=[],
            sources=[],
            channels=['webhook'],
            throttle_minutes=5,
            webhook_url='https://monitoring.company.com/alerts'
        ),
        NotificationRule(
            rule_name="auth_security_events",
            enabled=True,
            min_severity=5,
            max_severity=10,
            categories=['auth', 'security'],
            sources=[],
            channels=['email'],
            throttle_minutes=10,
            email_recipients=['admin@company.com']
        )
    ]
    
    notification_manager.configure_rules(rules)
    
    # Create enhanced processor with notification integration
    class MockIngestionQueue:
        def set_batch_processor(self, processor): pass
        def set_error_handler(self, handler): pass
    
    processor = EnhancedBackgroundProcessor(
        ingestion_queue=MockIngestionQueue(),
        notification_manager=notification_manager
    )
    
    print("📋 Configured Notification Rules:")
    for rule in notification_manager.get_rules_summary():
        print(f"   • {rule['rule_name']}: severity {rule['min_severity']}-{rule['max_severity']}, channels: {rule['channels']}")
    print()
    
    # Test scenarios
    test_scenarios = [
        {
            "name": "Critical Security Breach",
            "event": EventResponse(
                id="event_001",
                raw_log_id="raw_001",
                timestamp=datetime.now(timezone.utc),
                source="firewall",
                message="CRITICAL: Multiple failed authentication attempts from suspicious IP",
                category="security",
                parsed_at=datetime.now(timezone.utc)
            ),
            "analysis": AIAnalysisSchema(
                id="analysis_001",
                event_id="event_001",
                severity_score=9,
                explanation="Critical security breach detected with multiple attack vectors",
                recommendations=["Block IP immediately", "Review access logs", "Notify security team"],
                analyzed_at=datetime.now(timezone.utc)
            )
        },
        {
            "name": "Authentication Failure",
            "event": EventResponse(
                id="event_002",
                raw_log_id="raw_002",
                timestamp=datetime.now(timezone.utc),
                source="auth_server",
                message="Failed login attempt for admin user",
                category="auth",
                parsed_at=datetime.now(timezone.utc)
            ),
            "analysis": AIAnalysisSchema(
                id="analysis_002",
                event_id="event_002",
                severity_score=6,
                explanation="Suspicious authentication failure for privileged account",
                recommendations=["Monitor account activity", "Check for brute force patterns"],
                analyzed_at=datetime.now(timezone.utc)
            )
        },
        {
            "name": "Low Severity System Event",
            "event": EventResponse(
                id="event_003",
                raw_log_id="raw_003",
                timestamp=datetime.now(timezone.utc),
                source="system",
                message="Disk usage at 75%",
                category="system",
                parsed_at=datetime.now(timezone.utc)
            ),
            "analysis": AIAnalysisSchema(
                id="analysis_003",
                event_id="event_003",
                severity_score=3,
                explanation="Routine system monitoring alert",
                recommendations=["Monitor disk usage trends"],
                analyzed_at=datetime.now(timezone.utc)
            )
        }
    ]
    
    # Process each scenario
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"🔍 Scenario {i}: {scenario['name']}")
        print(f"   Severity: {scenario['analysis'].severity_score}/10")
        print(f"   Category: {scenario['event'].category}")
        
        # Check if notifications should be triggered
        should_notify = processor._should_trigger_notification(scenario['event'], scenario['analysis'])
        print(f"   Should notify: {should_notify}")
        
        if should_notify:
            # Send notifications
            results = await notification_manager.send_notification_with_retry(
                scenario['event'], 
                scenario['analysis'],
                max_retries=1,
                retry_delay=0.1
            )
            
            successful = sum(1 for success in results.values() if success)
            total = len(results)
            print(f"   Notifications sent: {successful}/{total}")
        else:
            print("   No notifications triggered (below threshold)")
        
        print()
    
    # Show final statistics
    print("📊 Final Statistics:")
    stats = notification_manager.get_notification_stats()
    print(f"   Total sent: {stats['total_sent']}")
    print(f"   Total failed: {stats['total_failed']}")
    print(f"   Success rate: {stats['overall_success_rate']:.1%}")
    print(f"   Active rules: {stats['active_rules']}")
    print(f"   Active channels: {stats['active_channels']}")
    
    print("\n📈 Channel Statistics:")
    for channel_name, channel_stats in stats['channel_stats'].items():
        print(f"   {channel_name}: {channel_stats['sent']} sent, {channel_stats['failed']} failed, {channel_stats['success_rate']:.1%} success")
    
    print("\n✅ Notification integration demonstration completed!")


if __name__ == "__main__":
    asyncio.run(demonstrate_notification_integration())