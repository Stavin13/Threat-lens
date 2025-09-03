"""
Notification system for high-priority events in ThreatLens.

This module provides a comprehensive notification system that can send alerts
through multiple channels (email, webhook, Slack) based on configurable rules.
"""
import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from enum import Enum

import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..database import get_db_session
from ..models import NotificationHistory, Event, AIAnalysis
from ..schemas import EventResponse, AIAnalysis as AIAnalysisSchema


logger = logging.getLogger(__name__)


class NotificationStatus(str, Enum):
    """Status of notification delivery."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    THROTTLED = "throttled"


class NotificationChannelType(str, Enum):
    """Types of notification channels."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"


@dataclass
class NotificationRule:
    """Configuration for notification rules."""
    rule_name: str
    enabled: bool = True
    min_severity: int = 1
    max_severity: int = 10
    categories: List[str] = None
    sources: List[str] = None
    channels: List[str] = None
    throttle_minutes: int = 0
    email_recipients: List[str] = None
    webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None
    
    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.categories is None:
            self.categories = []
        if self.sources is None:
            self.sources = []
        if self.channels is None:
            self.channels = []
        if self.email_recipients is None:
            self.email_recipients = []


@dataclass
class NotificationContext:
    """Context information for notifications."""
    event: EventResponse
    ai_analysis: Optional[AIAnalysisSchema] = None
    rule_name: str = ""
    channel_type: str = ""
    additional_data: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.additional_data is None:
            self.additional_data = {}


class NotificationChannel(ABC):
    """Abstract base class for notification channels."""
    
    def __init__(self, channel_type: NotificationChannelType, config: Dict[str, Any]):
        """Initialize notification channel.
        
        Args:
            channel_type: Type of notification channel
            config: Channel-specific configuration
        """
        self.channel_type = channel_type
        self.config = config
        self.enabled = config.get('enabled', True)
        
    @abstractmethod
    async def send_notification(self, context: NotificationContext) -> bool:
        """Send notification through this channel.
        
        Args:
            context: Notification context with event and analysis data
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate channel configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        pass
    
    def format_message(self, context: NotificationContext) -> Dict[str, str]:
        """Format notification message for this channel.
        
        Args:
            context: Notification context
            
        Returns:
            Dictionary with formatted message components
        """
        event = context.event
        analysis = context.ai_analysis
        
        # Create severity description
        severity_desc = self._get_severity_description(analysis.severity_score if analysis else 5)
        
        # Format timestamp
        timestamp_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Create subject/title
        subject = f"ThreatLens Alert: {severity_desc} - {event.category.upper()}"
        
        # Create message body
        body_parts = [
            f"Security Event Detected",
            f"",
            f"Timestamp: {timestamp_str}",
            f"Source: {event.source}",
            f"Category: {event.category.upper()}",
            f"Message: {event.message}",
        ]
        
        if analysis:
            body_parts.extend([
                f"",
                f"AI Analysis:",
                f"Severity Score: {analysis.severity_score}/10 ({severity_desc})",
                f"Explanation: {analysis.explanation}",
                f"",
                f"Recommendations:",
            ])
            for i, rec in enumerate(analysis.recommendations, 1):
                body_parts.append(f"{i}. {rec}")
        
        body_parts.extend([
            f"",
            f"Event ID: {event.id}",
            f"Generated by ThreatLens Real-time Monitoring"
        ])
        
        return {
            'subject': subject,
            'body': '\n'.join(body_parts),
            'html_body': self._format_html_body(context)
        }
    
    def _get_severity_description(self, severity: int) -> str:
        """Get human-readable severity description."""
        if severity <= 2:
            return "Low"
        elif severity <= 4:
            return "Medium"
        elif severity <= 6:
            return "High"
        elif severity <= 8:
            return "Critical"
        else:
            return "Very Critical"
    
    def _format_html_body(self, context: NotificationContext) -> str:
        """Format HTML version of notification body."""
        event = context.event
        analysis = context.ai_analysis
        
        severity_desc = self._get_severity_description(analysis.severity_score if analysis else 5)
        timestamp_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Determine severity color
        severity_color = self._get_severity_color(analysis.severity_score if analysis else 5)
        
        html_parts = [
            "<html><body>",
            "<h2 style='color: #333;'>ThreatLens Security Alert</h2>",
            "<table style='border-collapse: collapse; width: 100%; font-family: Arial, sans-serif;'>",
            f"<tr><td style='padding: 8px; border: 1px solid #ddd; font-weight: bold;'>Timestamp:</td><td style='padding: 8px; border: 1px solid #ddd;'>{timestamp_str}</td></tr>",
            f"<tr><td style='padding: 8px; border: 1px solid #ddd; font-weight: bold;'>Source:</td><td style='padding: 8px; border: 1px solid #ddd;'>{event.source}</td></tr>",
            f"<tr><td style='padding: 8px; border: 1px solid #ddd; font-weight: bold;'>Category:</td><td style='padding: 8px; border: 1px solid #ddd;'>{event.category.upper()}</td></tr>",
            f"<tr><td style='padding: 8px; border: 1px solid #ddd; font-weight: bold;'>Message:</td><td style='padding: 8px; border: 1px solid #ddd;'>{event.message}</td></tr>",
        ]
        
        if analysis:
            html_parts.extend([
                f"<tr><td style='padding: 8px; border: 1px solid #ddd; font-weight: bold;'>Severity:</td><td style='padding: 8px; border: 1px solid #ddd; color: {severity_color}; font-weight: bold;'>{analysis.severity_score}/10 ({severity_desc})</td></tr>",
                f"<tr><td style='padding: 8px; border: 1px solid #ddd; font-weight: bold;'>Explanation:</td><td style='padding: 8px; border: 1px solid #ddd;'>{analysis.explanation}</td></tr>",
            ])
        
        html_parts.extend([
            "</table>",
        ])
        
        if analysis and analysis.recommendations:
            html_parts.extend([
                "<h3 style='color: #333; margin-top: 20px;'>Recommendations:</h3>",
                "<ul style='font-family: Arial, sans-serif;'>",
            ])
            for rec in analysis.recommendations:
                html_parts.append(f"<li style='margin-bottom: 5px;'>{rec}</li>")
            html_parts.append("</ul>")
        
        html_parts.extend([
            f"<p style='margin-top: 20px; font-size: 12px; color: #666;'>Event ID: {event.id}</p>",
            "<p style='font-size: 12px; color: #666;'>Generated by ThreatLens Real-time Monitoring</p>",
            "</body></html>"
        ])
        
        return ''.join(html_parts)
    
    def _get_severity_color(self, severity: int) -> str:
        """Get color code for severity level."""
        if severity <= 2:
            return "#28a745"  # Green
        elif severity <= 4:
            return "#ffc107"  # Yellow
        elif severity <= 6:
            return "#fd7e14"  # Orange
        elif severity <= 8:
            return "#dc3545"  # Red
        else:
            return "#6f42c1"  # Purple


class EmailNotifier(NotificationChannel):
    """Email notification channel."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize email notifier.
        
        Args:
            config: Email configuration including SMTP settings
        """
        super().__init__(NotificationChannelType.EMAIL, config)
        self.smtp_host = config.get('smtp_host', 'localhost')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_username = config.get('smtp_username', '')
        self.smtp_password = config.get('smtp_password', '')
        self.smtp_use_tls = config.get('smtp_use_tls', True)
        self.from_email = config.get('from_email', 'threatlens@localhost')
        self.from_name = config.get('from_name', 'ThreatLens')
    
    async def send_notification(self, context: NotificationContext) -> bool:
        """Send email notification.
        
        Args:
            context: Notification context
            
        Returns:
            True if email was sent successfully
        """
        try:
            # Get recipients from rule configuration
            recipients = []
            if hasattr(context, 'rule') and hasattr(context.rule, 'email_recipients'):
                recipients = context.rule.email_recipients
            elif 'recipients' in self.config:
                recipients = self.config['recipients']
            
            if not recipients:
                logger.warning("No email recipients configured for notification")
                return False
            
            # Format message
            message_data = self.format_message(context)
            
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = message_data['subject']
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = ', '.join(recipients)
            
            # Add text and HTML parts
            text_part = MIMEText(message_data['body'], 'plain')
            html_part = MIMEText(message_data['html_body'], 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            await self._send_email_async(msg, recipients)
            
            logger.info(f"Email notification sent successfully to {len(recipients)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
            return False
    
    async def _send_email_async(self, msg: MIMEMultipart, recipients: List[str]):
        """Send email asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_email_sync, msg, recipients)
    
    def _send_email_sync(self, msg: MIMEMultipart, recipients: List[str]):
        """Send email synchronously."""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            if self.smtp_use_tls:
                server.starttls()
            
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)
            
            server.send_message(msg, to_addrs=recipients)
    
    def validate_config(self) -> bool:
        """Validate email configuration."""
        required_fields = ['smtp_host', 'from_email']
        for field in required_fields:
            if not self.config.get(field):
                logger.error(f"Missing required email configuration: {field}")
                return False
        
        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, self.from_email):
            logger.error(f"Invalid from_email format: {self.from_email}")
            return False
        
        return True


class WebhookNotifier(NotificationChannel):
    """Webhook notification channel."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize webhook notifier.
        
        Args:
            config: Webhook configuration including URL and headers
        """
        super().__init__(NotificationChannelType.WEBHOOK, config)
        self.webhook_url = config.get('webhook_url', '')
        self.headers = config.get('headers', {'Content-Type': 'application/json'})
        self.timeout = config.get('timeout', 30)
        self.retry_count = config.get('retry_count', 3)
        self.retry_delay = config.get('retry_delay', 1)
    
    async def send_notification(self, context: NotificationContext) -> bool:
        """Send webhook notification.
        
        Args:
            context: Notification context
            
        Returns:
            True if webhook was sent successfully
        """
        try:
            # Format message
            message_data = self.format_message(context)
            
            # Create webhook payload
            payload = {
                'event_id': context.event.id,
                'timestamp': context.event.timestamp.isoformat(),
                'source': context.event.source,
                'category': context.event.category,
                'message': context.event.message,
                'subject': message_data['subject'],
                'body': message_data['body'],
                'rule_name': context.rule_name,
                'channel_type': context.channel_type
            }
            
            if context.ai_analysis:
                payload['ai_analysis'] = {
                    'severity_score': context.ai_analysis.severity_score,
                    'explanation': context.ai_analysis.explanation,
                    'recommendations': context.ai_analysis.recommendations
                }
            
            # Add additional context data
            if context.additional_data:
                payload['additional_data'] = context.additional_data
            
            # Send webhook with retries
            for attempt in range(self.retry_count):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            self.webhook_url,
                            json=payload,
                            headers=self.headers,
                            timeout=aiohttp.ClientTimeout(total=self.timeout)
                        ) as response:
                            if response.status < 400:
                                logger.info(f"Webhook notification sent successfully to {self.webhook_url}")
                                return True
                            else:
                                logger.warning(f"Webhook returned status {response.status}: {await response.text()}")
                                
                except aiohttp.ClientError as e:
                    logger.warning(f"Webhook attempt {attempt + 1} failed: {str(e)}")
                    if attempt < self.retry_count - 1:
                        await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                    
            logger.error(f"Failed to send webhook notification after {self.retry_count} attempts")
            return False
            
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {str(e)}")
            return False
    
    def validate_config(self) -> bool:
        """Validate webhook configuration."""
        if not self.webhook_url:
            logger.error("Missing required webhook configuration: webhook_url")
            return False
        
        # Validate URL format
        import re
        url_pattern = r'^https?://.+'
        if not re.match(url_pattern, self.webhook_url):
            logger.error(f"Invalid webhook_url format: {self.webhook_url}")
            return False
        
        return True


class SlackNotifier(NotificationChannel):
    """Slack notification channel."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Slack notifier.
        
        Args:
            config: Slack configuration including webhook URL and channel
        """
        super().__init__(NotificationChannelType.SLACK, config)
        self.webhook_url = config.get('webhook_url', '')
        self.channel = config.get('channel', '#general')
        self.username = config.get('username', 'ThreatLens')
        self.icon_emoji = config.get('icon_emoji', ':warning:')
        self.timeout = config.get('timeout', 30)
    
    async def send_notification(self, context: NotificationContext) -> bool:
        """Send Slack notification.
        
        Args:
            context: Notification context
            
        Returns:
            True if Slack message was sent successfully
        """
        try:
            # Format message
            message_data = self.format_message(context)
            
            # Create Slack-specific formatting
            slack_message = self._format_slack_message(context, message_data)
            
            # Create Slack payload
            payload = {
                'channel': self.channel,
                'username': self.username,
                'icon_emoji': self.icon_emoji,
                'attachments': [slack_message]
            }
            
            # Send to Slack
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Slack notification sent successfully to {self.channel}")
                        return True
                    else:
                        logger.error(f"Slack webhook returned status {response.status}: {await response.text()}")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {str(e)}")
            return False
    
    def _format_slack_message(self, context: NotificationContext, message_data: Dict[str, str]) -> Dict[str, Any]:
        """Format message for Slack attachment."""
        event = context.event
        analysis = context.ai_analysis
        
        # Determine color based on severity
        color = "good"  # Green
        if analysis:
            if analysis.severity_score >= 8:
                color = "danger"  # Red
            elif analysis.severity_score >= 6:
                color = "warning"  # Yellow
        
        # Create attachment
        attachment = {
            'color': color,
            'title': message_data['subject'],
            'title_link': f"#/events/{event.id}",  # Assuming frontend route
            'fields': [
                {
                    'title': 'Source',
                    'value': event.source,
                    'short': True
                },
                {
                    'title': 'Category',
                    'value': event.category.upper(),
                    'short': True
                },
                {
                    'title': 'Timestamp',
                    'value': event.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    'short': True
                }
            ],
            'text': event.message,
            'footer': 'ThreatLens',
            'ts': int(event.timestamp.timestamp())
        }
        
        if analysis:
            attachment['fields'].extend([
                {
                    'title': 'Severity Score',
                    'value': f"{analysis.severity_score}/10",
                    'short': True
                },
                {
                    'title': 'AI Analysis',
                    'value': analysis.explanation,
                    'short': False
                }
            ])
            
            if analysis.recommendations:
                recommendations_text = '\n'.join([f"• {rec}" for rec in analysis.recommendations])
                attachment['fields'].append({
                    'title': 'Recommendations',
                    'value': recommendations_text,
                    'short': False
                })
        
        return attachment
    
    def validate_config(self) -> bool:
        """Validate Slack configuration."""
        if not self.webhook_url:
            logger.error("Missing required Slack configuration: webhook_url")
            return False
        
        # Validate URL format
        import re
        url_pattern = r'^https://hooks\.slack\.com/services/.+'
        if not re.match(url_pattern, self.webhook_url):
            logger.error(f"Invalid Slack webhook_url format: {self.webhook_url}")
            return False
        
        return True


class NotificationManager:
    """Central manager for notification system."""
    
    def __init__(self):
        """Initialize notification manager."""
        self.channels: Dict[str, NotificationChannel] = {}
        self.rules: List[NotificationRule] = []
        self.throttle_cache: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
    
    def add_channel(self, name: str, channel: NotificationChannel) -> None:
        """Add a notification channel.
        
        Args:
            name: Channel name/identifier
            channel: NotificationChannel instance
        """
        if channel.validate_config():
            self.channels[name] = channel
            logger.info(f"Added notification channel: {name} ({channel.channel_type})")
        else:
            logger.error(f"Failed to add notification channel {name}: invalid configuration")
    
    def remove_channel(self, name: str) -> None:
        """Remove a notification channel.
        
        Args:
            name: Channel name to remove
        """
        if name in self.channels:
            del self.channels[name]
            logger.info(f"Removed notification channel: {name}")
    
    def configure_rules(self, rules: List[NotificationRule]) -> None:
        """Configure notification rules.
        
        Args:
            rules: List of notification rules
        """
        self.rules = rules
        logger.info(f"Configured {len(rules)} notification rules")
    
    def add_rule(self, rule: NotificationRule) -> None:
        """Add a single notification rule.
        
        Args:
            rule: NotificationRule to add
        """
        self.rules.append(rule)
        logger.info(f"Added notification rule: {rule.rule_name}")
    
    def remove_rule(self, rule_name: str) -> None:
        """Remove a notification rule.
        
        Args:
            rule_name: Name of rule to remove
        """
        self.rules = [r for r in self.rules if r.rule_name != rule_name]
        logger.info(f"Removed notification rule: {rule_name}")
    
    async def send_notification(self, event: EventResponse, ai_analysis: Optional[AIAnalysisSchema] = None) -> Dict[str, bool]:
        """Send notifications for an event based on configured rules.
        
        Args:
            event: Event that triggered the notification
            ai_analysis: Optional AI analysis results
            
        Returns:
            Dictionary mapping channel names to success status
        """
        async with self._lock:
            results = {}
            
            # Find matching rules
            matching_rules = self._find_matching_rules(event, ai_analysis)
            
            if not matching_rules:
                logger.debug(f"No notification rules matched for event {event.id}")
                return results
            
            # Process each matching rule
            for rule in matching_rules:
                if not rule.enabled:
                    continue
                
                # Check throttling
                if self._is_throttled(rule, event):
                    logger.info(f"Notification throttled for rule {rule.rule_name}")
                    continue
                
                # Send notifications for each configured channel
                for channel_name in rule.channels:
                    if channel_name not in self.channels:
                        logger.warning(f"Channel {channel_name} not found for rule {rule.rule_name}")
                        continue
                    
                    channel = self.channels[channel_name]
                    if not channel.enabled:
                        continue
                    
                    # Create notification context
                    context = NotificationContext(
                        event=event,
                        ai_analysis=ai_analysis,
                        rule_name=rule.rule_name,
                        channel_type=channel.channel_type.value
                    )
                    
                    # Add rule-specific configuration to context
                    if channel.channel_type == NotificationChannelType.EMAIL and rule.email_recipients:
                        context.additional_data['recipients'] = rule.email_recipients
                    elif channel.channel_type == NotificationChannelType.WEBHOOK and rule.webhook_url:
                        context.additional_data['webhook_url'] = rule.webhook_url
                    elif channel.channel_type == NotificationChannelType.SLACK and rule.slack_channel:
                        context.additional_data['slack_channel'] = rule.slack_channel
                    
                    # Send notification
                    try:
                        success = await channel.send_notification(context)
                        results[f"{rule.rule_name}:{channel_name}"] = success
                        
                        # Record notification history
                        await self._record_notification_history(
                            event.id,
                            rule.rule_name,
                            channel_name,
                            NotificationStatus.SENT if success else NotificationStatus.FAILED
                        )
                        
                        if success:
                            # Update throttle cache
                            self._update_throttle_cache(rule, event)
                        
                    except Exception as e:
                        logger.error(f"Error sending notification via {channel_name}: {str(e)}")
                        results[f"{rule.rule_name}:{channel_name}"] = False
                        
                        await self._record_notification_history(
                            event.id,
                            rule.rule_name,
                            channel_name,
                            NotificationStatus.FAILED,
                            str(e)
                        )
            
            return results
    
    def _find_matching_rules(self, event: EventResponse, ai_analysis: Optional[AIAnalysisSchema]) -> List[NotificationRule]:
        """Find notification rules that match the given event.
        
        Args:
            event: Event to match against
            ai_analysis: Optional AI analysis
            
        Returns:
            List of matching notification rules
        """
        matching_rules = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            # Check severity range
            severity = ai_analysis.severity_score if ai_analysis else 5
            if not (rule.min_severity <= severity <= rule.max_severity):
                continue
            
            # Check categories
            if rule.categories and event.category not in rule.categories:
                continue
            
            # Check sources
            if rule.sources and event.source not in rule.sources:
                continue
            
            matching_rules.append(rule)
        
        return matching_rules
    
    def _is_throttled(self, rule: NotificationRule, event: EventResponse) -> bool:
        """Check if notifications for this rule are throttled.
        
        Args:
            rule: Notification rule
            event: Event being processed
            
        Returns:
            True if throttled, False otherwise
        """
        if rule.throttle_minutes <= 0:
            return False
        
        throttle_key = f"{rule.rule_name}:{event.source}:{event.category}"
        
        if throttle_key in self.throttle_cache:
            last_sent = self.throttle_cache[throttle_key]
            throttle_until = last_sent + timedelta(minutes=rule.throttle_minutes)
            
            if datetime.now() < throttle_until:
                return True
        
        return False
    
    def _update_throttle_cache(self, rule: NotificationRule, event: EventResponse) -> None:
        """Update throttle cache for successful notification.
        
        Args:
            rule: Notification rule
            event: Event that was processed
        """
        if rule.throttle_minutes > 0:
            throttle_key = f"{rule.rule_name}:{event.source}:{event.category}"
            self.throttle_cache[throttle_key] = datetime.now()
    
    async def _record_notification_history(
        self,
        event_id: str,
        rule_name: str,
        channel: str,
        status: NotificationStatus,
        error_message: Optional[str] = None
    ) -> None:
        """Record notification attempt in database.
        
        Args:
            event_id: ID of the event
            rule_name: Name of the notification rule
            channel: Channel name
            status: Notification status
            error_message: Optional error message
        """
        try:
            with get_db_session() as db:
                history_record = NotificationHistory(
                    event_id=event_id,
                    notification_type=rule_name,
                    channel=channel,
                    status=status.value,
                    error_message=error_message
                )
                
                db.add(history_record)
                db.commit()
            
        except Exception as e:
            logger.error(f"Failed to record notification history: {str(e)}")
    
    def get_notification_history(self, event_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get notification history.
        
        Args:
            event_id: Optional event ID to filter by
            limit: Maximum number of records to return
            
        Returns:
            List of notification history records
        """
        try:
            with get_db_session() as db:
                query = db.query(NotificationHistory)
                
                if event_id:
                    query = query.filter(NotificationHistory.event_id == event_id)
                
                records = query.order_by(NotificationHistory.sent_at.desc()).limit(limit).all()
                
                return [
                    {
                        'id': record.id,
                        'event_id': record.event_id,
                        'notification_type': record.notification_type,
                        'channel': record.channel,
                        'status': record.status,
                        'sent_at': record.sent_at,
                        'error_message': record.error_message
                    }
                    for record in records
                ]
            
        except Exception as e:
            logger.error(f"Failed to get notification history: {str(e)}")
            return []
    
    def get_channel_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all configured channels.
        
        Returns:
            Dictionary with channel status information
        """
        status = {}
        
        for name, channel in self.channels.items():
            status[name] = {
                'type': channel.channel_type.value,
                'enabled': channel.enabled,
                'config_valid': channel.validate_config()
            }
        
        return status
    
    def get_rules_summary(self) -> List[Dict[str, Any]]:
        """Get summary of configured notification rules.
        
        Returns:
            List of rule summaries
        """
        return [
            {
                'rule_name': rule.rule_name,
                'enabled': rule.enabled,
                'min_severity': rule.min_severity,
                'max_severity': rule.max_severity,
                'categories': rule.categories,
                'sources': rule.sources,
                'channels': rule.channels,
                'throttle_minutes': rule.throttle_minutes
            }
            for rule in self.rules
        ]
    
    async def send_notification_with_retry(
        self, 
        event: EventResponse, 
        ai_analysis: Optional[AIAnalysisSchema] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Dict[str, bool]:
        """Send notifications with retry logic for failed deliveries.
        
        Args:
            event: Event that triggered the notification
            ai_analysis: Optional AI analysis results
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries in seconds
            
        Returns:
            Dictionary mapping channel names to final success status
        """
        async with self._lock:
            results = {}
            
            # Find matching rules
            matching_rules = self._find_matching_rules(event, ai_analysis)
            
            if not matching_rules:
                logger.debug(f"No notification rules matched for event {event.id}")
                return results
            
            # Process each matching rule
            for rule in matching_rules:
                if not rule.enabled:
                    continue
                
                # Check throttling
                if self._is_throttled(rule, event):
                    logger.info(f"Notification throttled for rule {rule.rule_name}")
                    continue
                
                # Send notifications for each configured channel with retry
                for channel_name in rule.channels:
                    if channel_name not in self.channels:
                        logger.warning(f"Channel {channel_name} not found for rule {rule.rule_name}")
                        continue
                    
                    channel = self.channels[channel_name]
                    if not channel.enabled:
                        continue
                    
                    # Create notification context
                    context = NotificationContext(
                        event=event,
                        ai_analysis=ai_analysis,
                        rule_name=rule.rule_name,
                        channel_type=channel.channel_type.value
                    )
                    
                    # Add rule-specific configuration to context
                    if channel.channel_type == NotificationChannelType.EMAIL and rule.email_recipients:
                        context.additional_data['recipients'] = rule.email_recipients
                    elif channel.channel_type == NotificationChannelType.WEBHOOK and rule.webhook_url:
                        context.additional_data['webhook_url'] = rule.webhook_url
                    elif channel.channel_type == NotificationChannelType.SLACK and rule.slack_channel:
                        context.additional_data['slack_channel'] = rule.slack_channel
                    
                    # Attempt delivery with retries
                    success = False
                    last_error = None
                    
                    for attempt in range(max_retries + 1):  # +1 for initial attempt
                        try:
                            success = await channel.send_notification(context)
                            
                            if success:
                                # Record successful delivery
                                await self._record_notification_history(
                                    event.id,
                                    rule.rule_name,
                                    channel_name,
                                    NotificationStatus.SENT
                                )
                                
                                # Update throttle cache
                                self._update_throttle_cache(rule, event)
                                break
                            else:
                                last_error = "Channel returned failure status"
                                
                        except Exception as e:
                            last_error = str(e)
                            logger.warning(
                                f"Notification attempt {attempt + 1} failed for {channel_name}: {last_error}"
                            )
                        
                        # Wait before retry (except on last attempt)
                        if attempt < max_retries:
                            await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    
                    # Record final result
                    results[f"{rule.rule_name}:{channel_name}"] = success
                    
                    if not success:
                        # Record failed delivery
                        await self._record_notification_history(
                            event.id,
                            rule.rule_name,
                            channel_name,
                            NotificationStatus.FAILED,
                            last_error
                        )
                        
                        logger.error(
                            f"Failed to send notification via {channel_name} after {max_retries + 1} attempts: {last_error}"
                        )
            
            return results
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification delivery statistics.
        
        Returns:
            Dictionary with notification statistics
        """
        try:
            with get_db_session() as db:
                # Get total counts by status
                total_sent = db.query(NotificationHistory).filter(
                    NotificationHistory.status == NotificationStatus.SENT.value
                ).count()
                
                total_failed = db.query(NotificationHistory).filter(
                    NotificationHistory.status == NotificationStatus.FAILED.value
                ).count()
                
                total_pending = db.query(NotificationHistory).filter(
                    NotificationHistory.status == NotificationStatus.PENDING.value
                ).count()
                
                # Get counts by channel
                channel_stats = {}
                for channel_name in self.channels.keys():
                    sent_count = db.query(NotificationHistory).filter(
                        and_(
                            NotificationHistory.channel == channel_name,
                            NotificationHistory.status == NotificationStatus.SENT.value
                        )
                    ).count()
                    
                    failed_count = db.query(NotificationHistory).filter(
                        and_(
                            NotificationHistory.channel == channel_name,
                            NotificationHistory.status == NotificationStatus.FAILED.value
                        )
                    ).count()
                    
                    channel_stats[channel_name] = {
                        'sent': sent_count,
                        'failed': failed_count,
                        'success_rate': sent_count / max(sent_count + failed_count, 1)
                    }
                
                return {
                    'total_sent': total_sent,
                    'total_failed': total_failed,
                    'total_pending': total_pending,
                    'overall_success_rate': total_sent / max(total_sent + total_failed, 1),
                    'channel_stats': channel_stats,
                    'active_rules': len([r for r in self.rules if r.enabled]),
                    'active_channels': len([c for c in self.channels.values() if c.enabled])
                }
            
        except Exception as e:
            logger.error(f"Failed to get notification stats: {str(e)}")
            return {
                'total_sent': 0,
                'total_failed': 0,
                'total_pending': 0,
                'overall_success_rate': 0.0,
                'channel_stats': {},
                'active_rules': len([r for r in self.rules if r.enabled]),
                'active_channels': len([c for c in self.channels.values() if c.enabled])
            }
    
    async def send_test_notification(self, rule: NotificationRule, test_event: Dict[str, Any]) -> bool:
        """Send a test notification for a specific rule.
        
        Args:
            rule: Notification rule to test
            test_event: Mock event data for testing
            
        Returns:
            True if test notification was sent successfully
        """
        try:
            # Create mock EventResponse for testing
            from ..schemas import EventResponse
            from ..models import ParsedEvent, AIAnalysis
            
            # Create mock parsed event
            parsed_event = ParsedEvent(
                id=test_event.get('id', 'test-event'),
                timestamp=test_event.get('timestamp', datetime.now().isoformat()),
                source=test_event.get('source', 'test'),
                message=test_event.get('message', 'Test notification message'),
                category=test_event.get('category', 'security')
            )
            
            # Create mock AI analysis
            ai_analysis = AIAnalysis(
                severity_score=test_event.get('severity', 8),
                explanation="This is a test notification",
                recommendations=["This is a test - no action required"]
            )
            
            # Create EventResponse
            event_response = EventResponse(
                event=parsed_event,
                analysis=ai_analysis
            )
            
            # Send notification through each configured channel
            success_count = 0
            total_channels = len(rule.channels)
            
            for channel_name in rule.channels:
                if channel_name not in self.channels:
                    logger.warning(f"Test notification: Channel {channel_name} not found")
                    continue
                
                channel = self.channels[channel_name]
                if not channel.enabled:
                    logger.warning(f"Test notification: Channel {channel_name} is disabled")
                    continue
                
                # Create notification context
                context = NotificationContext(
                    event=event_response,
                    ai_analysis=ai_analysis,
                    rule_name=f"{rule.rule_name} (TEST)",
                    channel_type=channel.channel_type.value
                )
                
                # Add rule-specific configuration to context
                if channel.channel_type == NotificationChannelType.EMAIL and rule.email_recipients:
                    context.additional_data['recipients'] = rule.email_recipients
                elif channel.channel_type == NotificationChannelType.WEBHOOK and rule.webhook_url:
                    context.additional_data['webhook_url'] = rule.webhook_url
                elif channel.channel_type == NotificationChannelType.SLACK and rule.slack_channel:
                    context.additional_data['slack_channel'] = rule.slack_channel
                
                # Send test notification
                try:
                    success = await channel.send_notification(context)
                    if success:
                        success_count += 1
                        logger.info(f"Test notification sent successfully via {channel_name}")
                    else:
                        logger.warning(f"Test notification failed via {channel_name}")
                        
                    # Record test notification in history
                    await self._record_notification_history(
                        test_event.get('id', 'test-event'),
                        f"{rule.rule_name} (TEST)",
                        channel_name,
                        NotificationStatus.SENT if success else NotificationStatus.FAILED
                    )
                    
                except Exception as e:
                    logger.error(f"Error sending test notification via {channel_name}: {str(e)}")
                    await self._record_notification_history(
                        test_event.get('id', 'test-event'),
                        f"{rule.rule_name} (TEST)",
                        channel_name,
                        NotificationStatus.FAILED,
                        str(e)
                    )
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Failed to send test notification: {str(e)}")
            return False


# Global notification manager instance
notification_manager = NotificationManager()