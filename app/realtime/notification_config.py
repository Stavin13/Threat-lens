"""
Configuration utilities for the notification system.

This module provides utilities for configuring and managing notification
channels and rules in ThreatLens.
"""
import os
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import asdict

from .notifications import (
    NotificationManager,
    NotificationRule,
    EmailNotifier,
    WebhookNotifier,
    SlackNotifier,
    NotificationChannelType
)

logger = logging.getLogger(__name__)


class NotificationConfigManager:
    """Manager for notification system configuration."""
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration manager.
        
        Args:
            config_file: Optional path to configuration file
        """
        self.config_file = config_file or os.getenv('NOTIFICATION_CONFIG_FILE', 'notification_config.json')
        self.notification_manager = NotificationManager()
        
    def load_configuration(self) -> bool:
        """Load notification configuration from file or environment.
        
        Returns:
            True if configuration was loaded successfully
        """
        try:
            # Try to load from file first
            if os.path.exists(self.config_file):
                return self._load_from_file()
            else:
                # Load from environment variables
                return self._load_from_environment()
                
        except Exception as e:
            logger.error(f"Failed to load notification configuration: {str(e)}")
            return False
    
    def _load_from_file(self) -> bool:
        """Load configuration from JSON file.
        
        Returns:
            True if loaded successfully
        """
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            # Load channels
            channels_config = config.get('channels', {})
            for channel_name, channel_config in channels_config.items():
                self._create_channel(channel_name, channel_config)
            
            # Load rules
            rules_config = config.get('rules', [])
            rules = []
            for rule_config in rules_config:
                rule = NotificationRule(**rule_config)
                rules.append(rule)
            
            self.notification_manager.configure_rules(rules)
            
            logger.info(f"Loaded notification configuration from {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load configuration from file: {str(e)}")
            return False
    
    def _load_from_environment(self) -> bool:
        """Load configuration from environment variables.
        
        Returns:
            True if loaded successfully
        """
        try:
            # Load email channel if configured
            if self._is_email_configured():
                email_config = self._get_email_config()
                email_channel = EmailNotifier(email_config)
                self.notification_manager.add_channel('email', email_channel)
            
            # Load webhook channel if configured
            if self._is_webhook_configured():
                webhook_config = self._get_webhook_config()
                webhook_channel = WebhookNotifier(webhook_config)
                self.notification_manager.add_channel('webhook', webhook_channel)
            
            # Load Slack channel if configured
            if self._is_slack_configured():
                slack_config = self._get_slack_config()
                slack_channel = SlackNotifier(slack_config)
                self.notification_manager.add_channel('slack', slack_channel)
            
            # Load default rules
            default_rules = self._get_default_rules()
            self.notification_manager.configure_rules(default_rules)
            
            logger.info("Loaded notification configuration from environment variables")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load configuration from environment: {str(e)}")
            return False
    
    def _create_channel(self, channel_name: str, channel_config: Dict[str, Any]) -> None:
        """Create a notification channel from configuration.
        
        Args:
            channel_name: Name of the channel
            channel_config: Channel configuration dictionary
        """
        channel_type = channel_config.get('type', '').lower()
        
        if channel_type == 'email':
            channel = EmailNotifier(channel_config)
        elif channel_type == 'webhook':
            channel = WebhookNotifier(channel_config)
        elif channel_type == 'slack':
            channel = SlackNotifier(channel_config)
        else:
            logger.error(f"Unknown channel type: {channel_type}")
            return
        
        self.notification_manager.add_channel(channel_name, channel)
    
    def _is_email_configured(self) -> bool:
        """Check if email configuration is available in environment."""
        return bool(os.getenv('SMTP_HOST') and os.getenv('FROM_EMAIL'))
    
    def _get_email_config(self) -> Dict[str, Any]:
        """Get email configuration from environment variables."""
        return {
            'smtp_host': os.getenv('SMTP_HOST', 'localhost'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'smtp_username': os.getenv('SMTP_USERNAME', ''),
            'smtp_password': os.getenv('SMTP_PASSWORD', ''),
            'smtp_use_tls': os.getenv('SMTP_USE_TLS', 'true').lower() == 'true',
            'from_email': os.getenv('FROM_EMAIL', ''),
            'from_name': os.getenv('FROM_NAME', 'ThreatLens'),
            'recipients': os.getenv('EMAIL_RECIPIENTS', '').split(',') if os.getenv('EMAIL_RECIPIENTS') else []
        }
    
    def _is_webhook_configured(self) -> bool:
        """Check if webhook configuration is available in environment."""
        return bool(os.getenv('WEBHOOK_URL'))
    
    def _get_webhook_config(self) -> Dict[str, Any]:
        """Get webhook configuration from environment variables."""
        headers = {'Content-Type': 'application/json'}
        
        # Parse additional headers from environment
        headers_env = os.getenv('WEBHOOK_HEADERS', '')
        if headers_env:
            try:
                additional_headers = json.loads(headers_env)
                headers.update(additional_headers)
            except json.JSONDecodeError:
                logger.warning("Invalid WEBHOOK_HEADERS format, using defaults")
        
        return {
            'webhook_url': os.getenv('WEBHOOK_URL', ''),
            'headers': headers,
            'timeout': int(os.getenv('WEBHOOK_TIMEOUT', '30')),
            'retry_count': int(os.getenv('WEBHOOK_RETRY_COUNT', '3')),
            'retry_delay': int(os.getenv('WEBHOOK_RETRY_DELAY', '1'))
        }
    
    def _is_slack_configured(self) -> bool:
        """Check if Slack configuration is available in environment."""
        return bool(os.getenv('SLACK_WEBHOOK_URL'))
    
    def _get_slack_config(self) -> Dict[str, Any]:
        """Get Slack configuration from environment variables."""
        return {
            'webhook_url': os.getenv('SLACK_WEBHOOK_URL', ''),
            'channel': os.getenv('SLACK_CHANNEL', '#general'),
            'username': os.getenv('SLACK_USERNAME', 'ThreatLens'),
            'icon_emoji': os.getenv('SLACK_ICON_EMOJI', ':warning:'),
            'timeout': int(os.getenv('SLACK_TIMEOUT', '30'))
        }
    
    def _get_default_rules(self) -> List[NotificationRule]:
        """Get default notification rules from environment or create sensible defaults."""
        rules = []
        
        # High severity rule
        high_severity_channels = []
        if self._is_email_configured():
            high_severity_channels.append('email')
        if self._is_webhook_configured():
            high_severity_channels.append('webhook')
        if self._is_slack_configured():
            high_severity_channels.append('slack')
        
        if high_severity_channels:
            high_severity_rule = NotificationRule(
                rule_name="high_severity_alerts",
                enabled=True,
                min_severity=7,
                max_severity=10,
                categories=[],  # All categories
                sources=[],     # All sources
                channels=high_severity_channels,
                throttle_minutes=int(os.getenv('HIGH_SEVERITY_THROTTLE_MINUTES', '5')),
                email_recipients=os.getenv('EMAIL_RECIPIENTS', '').split(',') if os.getenv('EMAIL_RECIPIENTS') else [],
                webhook_url=os.getenv('WEBHOOK_URL'),
                slack_channel=os.getenv('SLACK_CHANNEL', '#general')
            )
            rules.append(high_severity_rule)
        
        # Critical security events rule
        if high_severity_channels:
            security_rule = NotificationRule(
                rule_name="critical_security_events",
                enabled=True,
                min_severity=6,
                max_severity=10,
                categories=['security', 'auth'],
                sources=[],     # All sources
                channels=high_severity_channels,
                throttle_minutes=int(os.getenv('SECURITY_THROTTLE_MINUTES', '10')),
                email_recipients=os.getenv('EMAIL_RECIPIENTS', '').split(',') if os.getenv('EMAIL_RECIPIENTS') else [],
                webhook_url=os.getenv('WEBHOOK_URL'),
                slack_channel=os.getenv('SLACK_CHANNEL', '#security')
            )
            rules.append(security_rule)
        
        return rules
    
    def save_configuration(self, config: Dict[str, Any]) -> bool:
        """Save notification configuration to file.
        
        Args:
            config: Configuration dictionary to save
            
        Returns:
            True if saved successfully
        """
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2, default=str)
            
            logger.info(f"Saved notification configuration to {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")
            return False
    
    def export_configuration(self) -> Dict[str, Any]:
        """Export current configuration to dictionary.
        
        Returns:
            Configuration dictionary
        """
        config = {
            'channels': {},
            'rules': []
        }
        
        # Export channel configurations (without sensitive data)
        for name, channel in self.notification_manager.channels.items():
            channel_config = {
                'type': channel.channel_type.value,
                'enabled': channel.enabled
            }
            
            # Add non-sensitive configuration
            if channel.channel_type == NotificationChannelType.EMAIL:
                channel_config.update({
                    'smtp_host': channel.smtp_host,
                    'smtp_port': channel.smtp_port,
                    'smtp_use_tls': channel.smtp_use_tls,
                    'from_email': channel.from_email,
                    'from_name': channel.from_name
                })
            elif channel.channel_type == NotificationChannelType.WEBHOOK:
                channel_config.update({
                    'timeout': channel.timeout,
                    'retry_count': channel.retry_count,
                    'retry_delay': channel.retry_delay
                })
            elif channel.channel_type == NotificationChannelType.SLACK:
                channel_config.update({
                    'channel': channel.channel,
                    'username': channel.username,
                    'icon_emoji': channel.icon_emoji,
                    'timeout': channel.timeout
                })
            
            config['channels'][name] = channel_config
        
        # Export rules
        for rule in self.notification_manager.rules:
            config['rules'].append(asdict(rule))
        
        return config
    
    def test_channels(self) -> Dict[str, bool]:
        """Test all configured notification channels.
        
        Returns:
            Dictionary mapping channel names to test results
        """
        results = {}
        
        for name, channel in self.notification_manager.channels.items():
            try:
                # Test configuration validation
                is_valid = channel.validate_config()
                results[name] = is_valid
                
                if is_valid:
                    logger.info(f"Channel {name} configuration is valid")
                else:
                    logger.error(f"Channel {name} configuration is invalid")
                    
            except Exception as e:
                logger.error(f"Error testing channel {name}: {str(e)}")
                results[name] = False
        
        return results
    
    def get_notification_manager(self) -> NotificationManager:
        """Get the configured notification manager.
        
        Returns:
            NotificationManager instance
        """
        return self.notification_manager


def create_sample_config() -> Dict[str, Any]:
    """Create a sample notification configuration.
    
    Returns:
        Sample configuration dictionary
    """
    return {
        "channels": {
            "email": {
                "type": "email",
                "enabled": True,
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "smtp_use_tls": True,
                "from_email": "alerts@yourdomain.com",
                "from_name": "ThreatLens Security Alerts"
            },
            "webhook": {
                "type": "webhook",
                "enabled": True,
                "webhook_url": "https://your-webhook-endpoint.com/alerts",
                "timeout": 30,
                "retry_count": 3,
                "retry_delay": 1,
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer your-token-here"
                }
            },
            "slack": {
                "type": "slack",
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
                "channel": "#security-alerts",
                "username": "ThreatLens",
                "icon_emoji": ":warning:",
                "timeout": 30
            }
        },
        "rules": [
            {
                "rule_name": "high_severity_alerts",
                "enabled": True,
                "min_severity": 7,
                "max_severity": 10,
                "categories": [],
                "sources": [],
                "channels": ["email", "slack"],
                "throttle_minutes": 5,
                "email_recipients": ["admin@yourdomain.com", "security@yourdomain.com"],
                "webhook_url": None,
                "slack_channel": "#security-alerts"
            },
            {
                "rule_name": "critical_security_events",
                "enabled": True,
                "min_severity": 6,
                "max_severity": 10,
                "categories": ["security", "auth"],
                "sources": [],
                "channels": ["email", "webhook", "slack"],
                "throttle_minutes": 10,
                "email_recipients": ["security@yourdomain.com"],
                "webhook_url": "https://your-webhook-endpoint.com/security-alerts",
                "slack_channel": "#security-incidents"
            },
            {
                "rule_name": "system_errors",
                "enabled": True,
                "min_severity": 5,
                "max_severity": 10,
                "categories": ["system", "kernel"],
                "sources": [],
                "channels": ["webhook"],
                "throttle_minutes": 15,
                "email_recipients": [],
                "webhook_url": "https://your-monitoring-system.com/alerts",
                "slack_channel": None
            }
        ]
    }


# Global configuration manager instance
config_manager = NotificationConfigManager()