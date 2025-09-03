"""
Event broadcaster for real-time event distribution.

This module provides event broadcasting capabilities with filtering,
subscription management, and message queuing for disconnected clients.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set, Callable
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum

from .base import RealtimeComponent, HealthMonitorMixin
from .websocket_server import EventUpdate, WebSocketManager
from .exceptions import BroadcastError

logger = logging.getLogger(__name__)


class EventPriority(int, Enum):
    """Event priority levels."""
    CRITICAL = 10
    HIGH = 8
    MEDIUM = 5
    LOW = 3
    DEBUG = 1


class EventCategory(str, Enum):
    """Event categories for filtering."""
    SECURITY_EVENT = "security_event"
    SYSTEM_STATUS = "system_status"
    PROCESSING_UPDATE = "processing_update"
    HEALTH_CHECK = "health_check"
    USER_ACTION = "user_action"
    ERROR = "error"


@dataclass
class EventFilter:
    """Filter criteria for event subscriptions."""
    event_types: Optional[Set[str]] = None
    categories: Optional[Set[str]] = None
    min_priority: Optional[int] = None
    max_priority: Optional[int] = None
    sources: Optional[Set[str]] = None
    
    def matches(self, event: EventUpdate) -> bool:
        """Check if event matches filter criteria."""
        # Check event type
        if self.event_types and event.event_type not in self.event_types:
            return False
        
        # Check priority
        if self.min_priority and event.priority < self.min_priority:
            return False
        if self.max_priority and event.priority > self.max_priority:
            return False
        
        # Check category (from event data)
        if self.categories:
            event_category = event.data.get('category')
            if not event_category or event_category not in self.categories:
                return False
        
        # Check source (from event data)
        if self.sources:
            event_source = event.data.get('source')
            if not event_source or event_source not in self.sources:
                return False
        
        return True


@dataclass
class QueuedMessage:
    """Queued message for disconnected clients."""
    client_id: str
    event: EventUpdate
    queued_at: datetime
    attempts: int = 0
    max_attempts: int = 3


class EventBroadcaster(RealtimeComponent, HealthMonitorMixin):
    """
    Manages event broadcasting with filtering and subscription management.
    
    Provides advanced event distribution capabilities including:
    - Event filtering and subscription management
    - Message queuing for disconnected clients
    - Event throttling and rate limiting
    - Broadcasting statistics and monitoring
    """
    
    def __init__(self, websocket_manager: WebSocketManager, max_queue_size: int = 1000):
        super().__init__("EventBroadcaster")
        self.websocket_manager = websocket_manager
        self.max_queue_size = max_queue_size
        
        # Client subscriptions and filters
        self.client_filters: Dict[str, EventFilter] = {}
        self.client_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        
        # Message queuing for disconnected clients
        self.message_queue: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.queue_worker_task: Optional[asyncio.Task] = None
        
        # Event throttling
        self.throttle_rules: Dict[str, Dict[str, Any]] = {}
        self.last_sent: Dict[str, datetime] = {}
        
        # Statistics
        self.stats = {
            "events_processed": 0,
            "events_filtered": 0,
            "events_throttled": 0,
            "messages_queued": 0,
            "messages_delivered": 0,
            "queue_overflows": 0
        }
        
        # Event handlers
        self.event_handlers: Dict[str, List[Callable]] = defaultdict(list)
    
    async def _start_impl(self) -> None:
        """Start event broadcaster."""
        logger.info("Starting event broadcaster")
        
        # Start queue worker
        self.queue_worker_task = asyncio.create_task(self._queue_worker())
        
        logger.info("Event broadcaster started")
    
    async def _stop_impl(self) -> None:
        """Stop event broadcaster."""
        logger.info("Stopping event broadcaster")
        
        # Cancel queue worker
        if self.queue_worker_task:
            self.queue_worker_task.cancel()
            try:
                await self.queue_worker_task
            except asyncio.CancelledError:
                pass
        
        # Clear queues
        self.message_queue.clear()
        
        logger.info("Event broadcaster stopped")
    
    def add_client_filter(self, client_id: str, event_filter: EventFilter) -> None:
        """
        Add event filter for a specific client.
        
        Args:
            client_id: Client identifier
            event_filter: Filter criteria
        """
        self.client_filters[client_id] = event_filter
        logger.debug(f"Added filter for client {client_id}")
    
    def remove_client_filter(self, client_id: str) -> None:
        """
        Remove event filter for a specific client.
        
        Args:
            client_id: Client identifier
        """
        if client_id in self.client_filters:
            del self.client_filters[client_id]
            logger.debug(f"Removed filter for client {client_id}")
    
    def subscribe_client(self, client_id: str, event_types: List[str]) -> None:
        """
        Subscribe client to specific event types.
        
        Args:
            client_id: Client identifier
            event_types: List of event types to subscribe to
        """
        self.client_subscriptions[client_id].update(event_types)
        logger.debug(f"Client {client_id} subscribed to: {event_types}")
    
    def unsubscribe_client(self, client_id: str, event_types: List[str]) -> None:
        """
        Unsubscribe client from specific event types.
        
        Args:
            client_id: Client identifier
            event_types: List of event types to unsubscribe from
        """
        self.client_subscriptions[client_id].difference_update(event_types)
        logger.debug(f"Client {client_id} unsubscribed from: {event_types}")
    
    def add_throttle_rule(self, event_type: str, min_interval_seconds: float) -> None:
        """
        Add throttling rule for specific event type.
        
        Args:
            event_type: Event type to throttle
            min_interval_seconds: Minimum interval between events
        """
        self.throttle_rules[event_type] = {
            "min_interval": min_interval_seconds,
            "last_sent": {}
        }
        logger.debug(f"Added throttle rule for {event_type}: {min_interval_seconds}s")
    
    def add_event_handler(self, event_type: str, handler: Callable[[EventUpdate], None]) -> None:
        """
        Add event handler for specific event type.
        
        Args:
            event_type: Event type to handle
            handler: Handler function
        """
        self.event_handlers[event_type].append(handler)
        logger.debug(f"Added event handler for {event_type}")
    
    async def broadcast_event(self, event: EventUpdate) -> Dict[str, Any]:
        """
        Broadcast event to all subscribed and filtered clients.
        
        Args:
            event: Event to broadcast
            
        Returns:
            Dictionary with broadcast results
        """
        try:
            self.stats["events_processed"] += 1
            
            # Check throttling
            if self._is_throttled(event):
                self.stats["events_throttled"] += 1
                logger.debug(f"Event {event.event_type} throttled")
                return {
                    "status": "throttled",
                    "event_type": event.event_type,
                    "clients_targeted": 0
                }
            
            # Get connected clients
            connected_clients = set(self.websocket_manager.get_connected_clients())
            
            # Filter clients based on subscriptions and filters
            target_clients = self._get_target_clients(event, connected_clients)
            
            if not target_clients:
                self.stats["events_filtered"] += 1
                logger.debug(f"Event {event.event_type} filtered out (no target clients)")
                return {
                    "status": "filtered",
                    "event_type": event.event_type,
                    "clients_targeted": 0
                }
            
            # Send to connected clients
            sent_count = 0
            failed_count = 0
            
            for client_id in target_clients:
                if client_id in connected_clients:
                    # Client is connected, send immediately
                    success = await self.websocket_manager.send_to_client(client_id, {
                        "type": event.event_type,
                        "data": event.data,
                        "timestamp": event.timestamp.isoformat(),
                        "priority": event.priority
                    })
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                else:
                    # Client is disconnected, queue message
                    await self._queue_message(client_id, event)
            
            # Update throttling timestamp
            self._update_throttle_timestamp(event)
            
            # Call event handlers
            await self._call_event_handlers(event)
            
            self.stats["messages_delivered"] += sent_count
            
            logger.debug(f"Broadcast {event.event_type}: {sent_count} sent, {failed_count} failed")
            
            return {
                "status": "success",
                "event_type": event.event_type,
                "clients_targeted": len(target_clients),
                "messages_sent": sent_count,
                "messages_failed": failed_count,
                "messages_queued": len(target_clients) - len([c for c in target_clients if c in connected_clients])
            }
            
        except Exception as e:
            self._handle_error(e, f"broadcasting event {event.event_type}")
            raise BroadcastError(f"Failed to broadcast event: {e}")
    
    async def send_to_client(self, client_id: str, event: EventUpdate) -> bool:
        """
        Send event to specific client with filtering.
        
        Args:
            client_id: Target client identifier
            event: Event to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Check if client should receive this event
            if not self._client_should_receive_event(client_id, event):
                logger.debug(f"Event {event.event_type} filtered for client {client_id}")
                return False
            
            # Set target client
            event.client_id = client_id
            
            # Send via WebSocket manager
            success = await self.websocket_manager.send_to_client(client_id, {
                "type": event.event_type,
                "data": event.data,
                "timestamp": event.timestamp.isoformat(),
                "priority": event.priority
            })
            
            if success:
                self.stats["messages_delivered"] += 1
            
            return success
            
        except Exception as e:
            self._handle_error(e, f"sending event to client {client_id}")
            return False
    
    async def _queue_message(self, client_id: str, event: EventUpdate) -> None:
        """
        Queue message for disconnected client.
        
        Args:
            client_id: Client identifier
            event: Event to queue
        """
        try:
            if len(self.message_queue[client_id]) >= self.max_queue_size:
                # Remove oldest message
                self.message_queue[client_id].popleft()
                self.stats["queue_overflows"] += 1
            
            queued_message = QueuedMessage(
                client_id=client_id,
                event=event,
                queued_at=datetime.now(timezone.utc)
            )
            
            self.message_queue[client_id].append(queued_message)
            self.stats["messages_queued"] += 1
            
            logger.debug(f"Queued message for client {client_id}")
            
        except Exception as e:
            self._handle_error(e, f"queuing message for client {client_id}")
    
    async def _queue_worker(self) -> None:
        """Background worker for processing queued messages."""
        logger.info("Starting queue worker")
        
        try:
            while not self._shutdown_event.is_set():
                try:
                    await asyncio.sleep(5)  # Check every 5 seconds
                    
                    # Get connected clients
                    connected_clients = set(client["client_id"] for client in self.websocket_manager.get_connected_clients())
                    
                    # Process queued messages for connected clients
                    for client_id in list(self.message_queue.keys()):
                        if client_id in connected_clients and self.message_queue[client_id]:
                            await self._process_client_queue(client_id)
                    
                    # Clean up old queued messages
                    await self._cleanup_old_messages()
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self._handle_error(e, "in queue worker")
                    
        except asyncio.CancelledError:
            logger.info("Queue worker cancelled")
            raise
        except Exception as e:
            logger.error(f"Queue worker error: {e}")
        finally:
            logger.info("Queue worker stopped")
    
    async def _process_client_queue(self, client_id: str) -> None:
        """
        Process queued messages for a specific client.
        
        Args:
            client_id: Client identifier
        """
        try:
            queue = self.message_queue[client_id]
            processed = 0
            
            while queue and processed < 10:  # Process up to 10 messages per cycle
                message = queue.popleft()
                
                # Check if message is too old
                age = datetime.now(timezone.utc) - message.queued_at
                if age > timedelta(hours=1):  # Discard messages older than 1 hour
                    logger.debug(f"Discarded old queued message for {client_id}")
                    continue
                
                # Try to send message
                success = await self.websocket_manager.send_to_client(client_id, {
                    "type": message.event.event_type,
                    "data": message.event.data,
                    "timestamp": message.event.timestamp.isoformat(),
                    "priority": message.event.priority,
                    "queued": True,
                    "queued_at": message.queued_at.isoformat()
                })
                
                if success:
                    self.stats["messages_delivered"] += 1
                    processed += 1
                else:
                    # Put message back in queue if send failed
                    message.attempts += 1
                    if message.attempts < message.max_attempts:
                        queue.appendleft(message)
                    break
            
            if processed > 0:
                logger.debug(f"Processed {processed} queued messages for client {client_id}")
                
        except Exception as e:
            self._handle_error(e, f"processing queue for client {client_id}")
    
    async def _cleanup_old_messages(self) -> None:
        """Clean up old queued messages."""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
            cleaned_count = 0
            
            for client_id, queue in self.message_queue.items():
                original_size = len(queue)
                
                # Filter out old messages
                filtered_messages = deque(
                    [msg for msg in queue if msg.queued_at > cutoff_time],
                    maxlen=queue.maxlen
                )
                
                self.message_queue[client_id] = filtered_messages
                cleaned_count += original_size - len(filtered_messages)
            
            if cleaned_count > 0:
                logger.debug(f"Cleaned up {cleaned_count} old queued messages")
                
        except Exception as e:
            self._handle_error(e, "cleaning up old messages")
    
    def _get_target_clients(self, event: EventUpdate, connected_clients: Set[str]) -> Set[str]:
        """
        Get list of clients that should receive the event.
        
        Args:
            event: Event to broadcast
            connected_clients: Set of connected client IDs
            
        Returns:
            Set of target client IDs
        """
        target_clients = set()
        
        # Check all clients with subscriptions or filters
        all_clients = set(self.client_subscriptions.keys()) | set(self.client_filters.keys())
        
        for client_id in all_clients:
            if self._client_should_receive_event(client_id, event):
                target_clients.add(client_id)
        
        return target_clients
    
    def _client_should_receive_event(self, client_id: str, event: EventUpdate) -> bool:
        """
        Check if client should receive the event based on subscriptions and filters.
        
        Args:
            client_id: Client identifier
            event: Event to check
            
        Returns:
            True if client should receive event, False otherwise
        """
        # Check subscriptions
        subscriptions = self.client_subscriptions.get(client_id, set())
        if subscriptions and event.event_type not in subscriptions:
            return False
        
        # Check filters
        client_filter = self.client_filters.get(client_id)
        if client_filter and not client_filter.matches(event):
            return False
        
        return True
    
    def _is_throttled(self, event: EventUpdate) -> bool:
        """
        Check if event should be throttled.
        
        Args:
            event: Event to check
            
        Returns:
            True if event should be throttled, False otherwise
        """
        throttle_rule = self.throttle_rules.get(event.event_type)
        if not throttle_rule:
            return False
        
        last_sent = throttle_rule["last_sent"].get(event.event_type)
        if not last_sent:
            return False
        
        min_interval = throttle_rule["min_interval"]
        time_since_last = (datetime.now(timezone.utc) - last_sent).total_seconds()
        
        return time_since_last < min_interval
    
    def _update_throttle_timestamp(self, event: EventUpdate) -> None:
        """
        Update throttle timestamp for event type.
        
        Args:
            event: Event that was sent
        """
        throttle_rule = self.throttle_rules.get(event.event_type)
        if throttle_rule:
            throttle_rule["last_sent"][event.event_type] = datetime.now(timezone.utc)
    
    async def _call_event_handlers(self, event: EventUpdate) -> None:
        """
        Call registered event handlers.
        
        Args:
            event: Event to handle
        """
        handlers = self.event_handlers.get(event.event_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                self._handle_error(e, f"calling event handler for {event.event_type}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get broadcaster statistics.
        
        Returns:
            Dictionary with statistics
        """
        total_queued = sum(len(queue) for queue in self.message_queue.values())
        
        return {
            **self.stats,
            "active_subscriptions": len(self.client_subscriptions),
            "active_filters": len(self.client_filters),
            "throttle_rules": len(self.throttle_rules),
            "total_queued_messages": total_queued,
            "clients_with_queued_messages": len([q for q in self.message_queue.values() if q])
        }
    
    def get_client_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            Client information dictionary or None if not found
        """
        if client_id not in self.client_subscriptions and client_id not in self.client_filters:
            return None
        
        return {
            "client_id": client_id,
            "subscriptions": list(self.client_subscriptions.get(client_id, set())),
            "has_filter": client_id in self.client_filters,
            "queued_messages": len(self.message_queue.get(client_id, [])),
            "filter_details": self.client_filters.get(client_id).__dict__ if client_id in self.client_filters else None
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get detailed health status."""
        base_status = super().get_health_status()
        
        # Add broadcaster-specific health metrics
        total_queued = sum(len(queue) for queue in self.message_queue.values())
        
        base_status.update({
            "subscriptions": {
                "active": len(self.client_subscriptions),
                "total_event_types": len(set().union(*self.client_subscriptions.values())) if self.client_subscriptions else 0
            },
            "message_queue": {
                "total_queued": total_queued,
                "clients_with_messages": len([q for q in self.message_queue.values() if q]),
                "is_healthy": total_queued < self.max_queue_size * 0.8  # 80% threshold
            },
            "throttling": {
                "active_rules": len(self.throttle_rules),
                "events_throttled": self.stats["events_throttled"]
            },
            "statistics": self.get_statistics(),
            "health_metrics": self.get_health_metrics()
        })
        
        return base_status