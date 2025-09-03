"""
Test utilities for the notification system.

This module provides utilities for testing notification channels and rules.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from ..schemas import EventResponse, AIAnalysis, EventCategory
from .notifications import NotificationContext, NotificationManager
from .notification_config import NotificationConfigManager

logger = logging.getLogger(__name__)


class NotificationTester:
    """Utility class for testing notification functionality."""
    
    def __init__(self, config_manager: NotificationConfigManager):
        """Initialize notification tester.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.notification_manager = config_manager.get_notification_manager()
    
    def create_test_event(self, severity: int = 8, category: str = "security") -> EventResponse:
        """Create a test event for notification testing.
        
        Args:
            severity: Severity level for the test event
            category: Event category
            
        Returns:
            Test EventResponse object
        """
        return EventResponse(
            id="test-event-001",
            raw_log_id="test-raw-log-001",
            timestamp=datetime.now(),
            source="test-source",
            message="Test security event for notification testing",
            category=EventCategory(category),
            parsed_at=datetime.now()
        )
    
    def create_test_analysis(self, severity: int = 8) -> AIAnalysis:
        """Create a test AI analysis for notification testing.
        
        Args:
            severity: Severity score for the analysis
            
        Returns:
            Test AIAnalysis object
        """
        return AIAnalysis(
            id="test-analysis-001",
            event_id="test-event-001",
            severity_score=severity,
            explanation=f"This is a test security event with severity {severity}. "
                       "The event appears to be a simulated threat for testing purposes.",
            recommendations=[
                "Review system logs for additional suspicious activity",
                "Verify user authentication patterns",
                "Consider implementing additional monitoring"
            ],
            analyzed_at=datetime.now()
        )
    
    async def test_all_channels(self, severity: int = 8) -> Dict[str, bool]:
        """Test all configured notification channels.
        
        Args:
            severity: Severity level for test notifications
            
        Returns:
            Dictionary mapping channel names to test results
        """
        results = {}
        
        # Create test event and analysis
        test_event = self.create_test_event(severity)
        test_analysis = self.create_test_analysis(severity)
        
        # Test each channel individually
        for channel_name, channel in self.notification_manager.channels.items():
            try:
                logger.info(f"Testing notification channel: {channel_name}")
                
                # Create test context
                context = NotificationContext(
                    event=test_event,
                    ai_analysis=test_analysis,
                    rule_name="test_rule",
                    channel_type=channel.channel_type.value,
                    additional_data={"test_mode": True}
                )
                
                # Send test notification
                success = await channel.send_notification(context)
                results[channel_name] = success
                
                if success:
                    logger.info(f"✓ Channel {channel_name} test successful")
                else:
                    logger.error(f"✗ Channel {channel_name} test failed")
                    
            except Exception as e:
                logger.error(f"✗ Channel {channel_name} test error: {str(e)}")
                results[channel_name] = False
        
        return results
    
    async def test_notification_rules(self, severity: int = 8) -> Dict[str, Any]:
        """Test notification rules with a test event.
        
        Args:
            severity: Severity level for test event
            
        Returns:
            Dictionary with test results
        """
        # Create test event and analysis
        test_event = self.create_test_event(severity)
        test_analysis = self.create_test_analysis(severity)
        
        logger.info(f"Testing notification rules with severity {severity} event")
        
        # Send notification through the manager
        results = await self.notification_manager.send_notification(test_event, test_analysis)
        
        # Log results
        if results:
            logger.info(f"Notification rules test completed:")
            for rule_channel, success in results.items():
                status = "✓" if success else "✗"
                logger.info(f"  {status} {rule_channel}: {'Success' if success else 'Failed'}")
        else:
            logger.warning("No notification rules matched the test event")
        
        return {
            'test_event': {
                'id': test_event.id,
                'severity': severity,
                'category': test_event.category,
                'source': test_event.source
            },
            'matching_rules': len([r for r in self.notification_manager.rules if r.enabled]),
            'notification_results': results,
            'total_sent': sum(1 for success in results.values() if success),
            'total_failed': sum(1 for success in results.values() if not success)
        }
    
    async def test_channel_by_name(self, channel_name: str, severity: int = 8) -> bool:
        """Test a specific notification channel by name.
        
        Args:
            channel_name: Name of the channel to test
            severity: Severity level for test notification
            
        Returns:
            True if test was successful
        """
        if channel_name not in self.notification_manager.channels:
            logger.error(f"Channel {channel_name} not found")
            return False
        
        channel = self.notification_manager.channels[channel_name]
        
        # Create test event and analysis
        test_event = self.create_test_event(severity)
        test_analysis = self.create_test_analysis(severity)
        
        # Create test context
        context = NotificationContext(
            event=test_event,
            ai_analysis=test_analysis,
            rule_name="manual_test",
            channel_type=channel.channel_type.value,
            additional_data={"test_mode": True, "manual_test": True}
        )
        
        try:
            logger.info(f"Testing channel: {channel_name}")
            success = await channel.send_notification(context)
            
            if success:
                logger.info(f"✓ Channel {channel_name} test successful")
            else:
                logger.error(f"✗ Channel {channel_name} test failed")
            
            return success
            
        except Exception as e:
            logger.error(f"✗ Channel {channel_name} test error: {str(e)}")
            return False
    
    def validate_all_configurations(self) -> Dict[str, bool]:
        """Validate configurations for all channels.
        
        Returns:
            Dictionary mapping channel names to validation results
        """
        results = {}
        
        for channel_name, channel in self.notification_manager.channels.items():
            try:
                is_valid = channel.validate_config()
                results[channel_name] = is_valid
                
                status = "✓" if is_valid else "✗"
                logger.info(f"{status} Channel {channel_name} configuration: {'Valid' if is_valid else 'Invalid'}")
                
            except Exception as e:
                logger.error(f"✗ Channel {channel_name} validation error: {str(e)}")
                results[channel_name] = False
        
        return results
    
    def get_test_summary(self) -> Dict[str, Any]:
        """Get a summary of the notification system configuration.
        
        Returns:
            Dictionary with system summary
        """
        return {
            'channels': {
                'total': len(self.notification_manager.channels),
                'enabled': sum(1 for c in self.notification_manager.channels.values() if c.enabled),
                'types': list(set(c.channel_type.value for c in self.notification_manager.channels.values()))
            },
            'rules': {
                'total': len(self.notification_manager.rules),
                'enabled': sum(1 for r in self.notification_manager.rules if r.enabled),
                'rule_names': [r.rule_name for r in self.notification_manager.rules if r.enabled]
            },
            'channel_details': {
                name: {
                    'type': channel.channel_type.value,
                    'enabled': channel.enabled,
                    'config_valid': channel.validate_config()
                }
                for name, channel in self.notification_manager.channels.items()
            }
        }


async def run_notification_tests(config_file: Optional[str] = None) -> Dict[str, Any]:
    """Run comprehensive notification system tests.
    
    Args:
        config_file: Optional path to configuration file
        
    Returns:
        Dictionary with test results
    """
    # Initialize configuration manager
    config_manager = NotificationConfigManager(config_file)
    
    # Load configuration
    config_loaded = config_manager.load_configuration()
    if not config_loaded:
        logger.error("Failed to load notification configuration")
        return {'error': 'Configuration load failed'}
    
    # Initialize tester
    tester = NotificationTester(config_manager)
    
    # Get system summary
    summary = tester.get_test_summary()
    logger.info(f"Notification system summary: {summary['channels']['total']} channels, {summary['rules']['total']} rules")
    
    # Validate configurations
    logger.info("Validating channel configurations...")
    validation_results = tester.validate_all_configurations()
    
    # Test individual channels
    logger.info("Testing individual channels...")
    channel_test_results = await tester.test_all_channels()
    
    # Test notification rules
    logger.info("Testing notification rules...")
    rules_test_results = await tester.test_notification_rules()
    
    # Compile results
    results = {
        'timestamp': datetime.now().isoformat(),
        'configuration_loaded': config_loaded,
        'system_summary': summary,
        'validation_results': validation_results,
        'channel_test_results': channel_test_results,
        'rules_test_results': rules_test_results,
        'overall_success': all(validation_results.values()) and any(channel_test_results.values())
    }
    
    # Log final summary
    total_channels = len(channel_test_results)
    successful_channels = sum(1 for success in channel_test_results.values() if success)
    
    logger.info(f"Notification system test completed:")
    logger.info(f"  Channels tested: {total_channels}")
    logger.info(f"  Channels successful: {successful_channels}")
    logger.info(f"  Rules tested: {rules_test_results.get('total_sent', 0) + rules_test_results.get('total_failed', 0)}")
    logger.info(f"  Overall success: {results['overall_success']}")
    
    return results


if __name__ == "__main__":
    # Run tests if executed directly
    import sys
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run tests
    config_file = sys.argv[1] if len(sys.argv) > 1 else None
    results = asyncio.run(run_notification_tests(config_file))
    
    # Print results
    print("\nTest Results:")
    print(f"Overall Success: {results['overall_success']}")
    print(f"Channels: {results['system_summary']['channels']}")
    print(f"Rules: {results['system_summary']['rules']}")