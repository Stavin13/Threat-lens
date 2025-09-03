"""
WebSocket API endpoints and event types.

This module defines WebSocket message protocols, event types,
and provides FastAPI WebSocket endpoints for real-time communication.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, ValidationError
from fastapi import WebSocket, WebSocketDisconnect, HTTPException, Depends

from .websocket_server import WebSocketManager, EventUpdate
from .event_broadcaster import EventBroadcaster, EventFilter, EventPriority, EventCategory
from .exceptions import WebSocketError, BroadcastError, AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types."""
    # Client to server messages
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SET_FILTER = "set_filter"
    CLEAR_FILTER = "clear_filter"
    PING = "ping"
    GET_STATUS = "get_status"
    
    # Server to client messages
    CONNECTION_ESTABLISHED = "connection_established"
    SUBSCRIPTION_UPDATED = "subscription_updated"
    FILTER_UPDATED = "filter_updated"
    PONG = "pong"
    STATUS_RESPONSE = "status_response"
    ERROR = "error"
    
    # Event messages
    SECURITY_EVENT = "security_event"
    SYSTEM_STATUS = "system_status"
    PROCESSING_UPDATE = "processing_update"
    HEALTH_CHECK = "health_check"
    USER_ACTION = "user_action"


class WebSocketMessage(BaseModel):
    """Base WebSocket message model."""
    
    type: str = Field(..., description="Message type")
    data: Dict[str, Any] = Field(default_factory=dict, description="Message data")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message_id: Optional[str] = Field(default=None, description="Optional message ID")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SubscriptionRequest(BaseModel):
    """Subscription request message."""
    
    event_types: List[str] = Field(..., description="Event types to subscribe to")
    replace_existing: bool = Field(default=False, description="Replace existing subscriptions")


class FilterRequest(BaseModel):
    """Filter request message."""
    
    event_types: Optional[List[str]] = Field(default=None, description="Event types to filter")
    categories: Optional[List[str]] = Field(default=None, description="Event categories to filter")
    min_priority: Optional[int] = Field(default=None, ge=1, le=10, description="Minimum priority")
    max_priority: Optional[int] = Field(default=None, ge=1, le=10, description="Maximum priority")
    sources: Optional[List[str]] = Field(default=None, description="Event sources to filter")


class SecurityEventData(BaseModel):
    """Security event data model."""
    
    event_id: str = Field(..., description="Event identifier")
    severity: int = Field(..., ge=1, le=10, description="Severity score")
    category: str = Field(..., description="Event category")
    source: str = Field(..., description="Event source")
    message: str = Field(..., description="Event message")
    timestamp: datetime = Field(..., description="Event timestamp")
    analysis: Optional[Dict[str, Any]] = Field(default=None, description="AI analysis results")
    recommendations: Optional[List[str]] = Field(default=None, description="Recommendations")


class SystemStatusData(BaseModel):
    """System status data model."""
    
    component: str = Field(..., description="Component name")
    status: str = Field(..., description="Status (healthy, degraded, unhealthy)")
    uptime: Optional[float] = Field(default=None, description="Uptime in seconds")
    metrics: Optional[Dict[str, Any]] = Field(default=None, description="Component metrics")
    last_error: Optional[str] = Field(default=None, description="Last error message")


class ProcessingUpdateData(BaseModel):
    """Processing update data model."""
    
    raw_log_id: str = Field(..., description="Raw log identifier")
    stage: str = Field(..., description="Processing stage")
    status: str = Field(..., description="Processing status")
    progress: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Progress percentage")
    events_created: Optional[int] = Field(default=None, description="Number of events created")
    processing_time: Optional[float] = Field(default=None, description="Processing time in seconds")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")


class HealthCheckData(BaseModel):
    """Health check data model."""
    
    overall_status: str = Field(..., description="Overall system health")
    components: Dict[str, Dict[str, Any]] = Field(..., description="Component health details")
    timestamp: datetime = Field(..., description="Health check timestamp")
    alerts: Optional[List[str]] = Field(default=None, description="Active alerts")


class WebSocketAPI:
    """
    WebSocket API handler for real-time communication.
    
    Manages WebSocket connections, message handling, and event broadcasting
    with proper error handling and client management.
    """
    
    def __init__(self, websocket_manager: WebSocketManager, event_broadcaster: EventBroadcaster):
        self.websocket_manager = websocket_manager
        self.event_broadcaster = event_broadcaster
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Message handlers
        self.message_handlers = {
            MessageType.SUBSCRIBE: self._handle_subscribe,
            MessageType.UNSUBSCRIBE: self._handle_unsubscribe,
            MessageType.SET_FILTER: self._handle_set_filter,
            MessageType.CLEAR_FILTER: self._handle_clear_filter,
            MessageType.PING: self._handle_ping,
            MessageType.GET_STATUS: self._handle_get_status
        }
    
    async def handle_websocket_connection(self, websocket: WebSocket, client_id: Optional[str] = None,
                                        token: Optional[str] = None) -> None:
        """
        Handle WebSocket connection lifecycle with authentication.
        
        Args:
            websocket: WebSocket connection
            client_id: Optional client identifier
            token: Optional authentication token
        """
        actual_client_id = None
        
        try:
            # Connect client with authentication
            actual_client_id = await self.websocket_manager.connect(websocket, client_id, token)
            self.active_connections[actual_client_id] = websocket
            
            logger.info(f"WebSocket client connected: {actual_client_id}")
            
            # Handle messages
            await self._message_loop(websocket, actual_client_id)
            
        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: {actual_client_id}")
        except (AuthenticationError, AuthorizationError) as e:
            logger.warning(f"WebSocket authentication error for {actual_client_id}: {e}")
            # Connection already closed by websocket_manager
        except Exception as e:
            logger.error(f"WebSocket connection error for {actual_client_id}: {e}")
            await self._send_error(websocket, f"Connection error: {e}")
        finally:
            # Clean up connection
            if actual_client_id:
                await self.websocket_manager.disconnect(actual_client_id, "Connection closed")
                if actual_client_id in self.active_connections:
                    del self.active_connections[actual_client_id]
    
    async def _message_loop(self, websocket: WebSocket, client_id: str) -> None:
        """
        Handle incoming WebSocket messages.
        
        Args:
            websocket: WebSocket connection
            client_id: Client identifier
        """
        try:
            while True:
                # Receive message
                try:
                    message_text = await websocket.receive_text()
                    message_data = json.loads(message_text)
                except json.JSONDecodeError as e:
                    await self._send_error(websocket, f"Invalid JSON: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error receiving message from {client_id}: {e}")
                    break
                
                # Validate message structure
                try:
                    message = WebSocketMessage(**message_data)
                except ValidationError as e:
                    await self._send_error(websocket, f"Invalid message format: {e}")
                    continue
                
                # Handle message
                await self._handle_message(websocket, client_id, message)
                
        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error(f"Message loop error for {client_id}: {e}")
            raise
    
    async def _handle_message(self, websocket: WebSocket, client_id: str, message: WebSocketMessage) -> None:
        """
        Handle individual WebSocket message.
        
        Args:
            websocket: WebSocket connection
            client_id: Client identifier
            message: Parsed message
        """
        try:
            handler = self.message_handlers.get(message.type)
            if handler:
                await handler(websocket, client_id, message)
            else:
                await self._send_error(websocket, f"Unknown message type: {message.type}")
                
        except Exception as e:
            logger.error(f"Error handling message {message.type} from {client_id}: {e}")
            await self._send_error(websocket, f"Error handling message: {e}")
    
    async def _handle_subscribe(self, websocket: WebSocket, client_id: str, message: WebSocketMessage) -> None:
        """Handle subscription request."""
        try:
            request = SubscriptionRequest(**message.data)
            
            # Update WebSocket manager subscriptions
            await self.websocket_manager.subscribe(client_id, request.event_types)
            
            # Update event broadcaster subscriptions
            if request.replace_existing:
                # Clear existing subscriptions first
                existing_subs = list(self.event_broadcaster.client_subscriptions.get(client_id, set()))
                if existing_subs:
                    self.event_broadcaster.unsubscribe_client(client_id, existing_subs)
            
            self.event_broadcaster.subscribe_client(client_id, request.event_types)
            
            # Send confirmation
            await self._send_response(websocket, MessageType.SUBSCRIPTION_UPDATED, {
                "subscriptions": request.event_types,
                "action": "subscribed",
                "replace_existing": request.replace_existing
            })
            
            logger.debug(f"Client {client_id} subscribed to: {request.event_types}")
            
        except ValidationError as e:
            await self._send_error(websocket, f"Invalid subscription request: {e}")
        except Exception as e:
            await self._send_error(websocket, f"Subscription failed: {e}")
    
    async def _handle_unsubscribe(self, websocket: WebSocket, client_id: str, message: WebSocketMessage) -> None:
        """Handle unsubscription request."""
        try:
            request = SubscriptionRequest(**message.data)
            
            # Update WebSocket manager subscriptions
            await self.websocket_manager.unsubscribe(client_id, request.event_types)
            
            # Update event broadcaster subscriptions
            self.event_broadcaster.unsubscribe_client(client_id, request.event_types)
            
            # Send confirmation
            await self._send_response(websocket, MessageType.SUBSCRIPTION_UPDATED, {
                "subscriptions": request.event_types,
                "action": "unsubscribed"
            })
            
            logger.debug(f"Client {client_id} unsubscribed from: {request.event_types}")
            
        except ValidationError as e:
            await self._send_error(websocket, f"Invalid unsubscription request: {e}")
        except Exception as e:
            await self._send_error(websocket, f"Unsubscription failed: {e}")
    
    async def _handle_set_filter(self, websocket: WebSocket, client_id: str, message: WebSocketMessage) -> None:
        """Handle filter setting request."""
        try:
            request = FilterRequest(**message.data)
            
            # Create event filter
            event_filter = EventFilter(
                event_types=set(request.event_types) if request.event_types else None,
                categories=set(request.categories) if request.categories else None,
                min_priority=request.min_priority,
                max_priority=request.max_priority,
                sources=set(request.sources) if request.sources else None
            )
            
            # Set filter in event broadcaster
            self.event_broadcaster.add_client_filter(client_id, event_filter)
            
            # Send confirmation
            await self._send_response(websocket, MessageType.FILTER_UPDATED, {
                "filter": request.dict(exclude_none=True),
                "action": "set"
            })
            
            logger.debug(f"Filter set for client {client_id}")
            
        except ValidationError as e:
            await self._send_error(websocket, f"Invalid filter request: {e}")
        except Exception as e:
            await self._send_error(websocket, f"Filter setting failed: {e}")
    
    async def _handle_clear_filter(self, websocket: WebSocket, client_id: str, message: WebSocketMessage) -> None:
        """Handle filter clearing request."""
        try:
            # Remove filter from event broadcaster
            self.event_broadcaster.remove_client_filter(client_id)
            
            # Send confirmation
            await self._send_response(websocket, MessageType.FILTER_UPDATED, {
                "action": "cleared"
            })
            
            logger.debug(f"Filter cleared for client {client_id}")
            
        except Exception as e:
            await self._send_error(websocket, f"Filter clearing failed: {e}")
    
    async def _handle_ping(self, websocket: WebSocket, client_id: str, message: WebSocketMessage) -> None:
        """Handle ping request."""
        try:
            # Send pong response
            await self._send_response(websocket, MessageType.PONG, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "client_id": client_id
            })
            
        except Exception as e:
            logger.error(f"Error handling ping from {client_id}: {e}")
    
    async def _handle_get_status(self, websocket: WebSocket, client_id: str, message: WebSocketMessage) -> None:
        """Handle status request."""
        try:
            # Get client info from event broadcaster
            client_info = self.event_broadcaster.get_client_info(client_id)
            
            # Get WebSocket manager stats
            ws_stats = self.websocket_manager.get_statistics()
            
            # Get broadcaster stats
            broadcaster_stats = self.event_broadcaster.get_statistics()
            
            status_data = {
                "client_info": client_info,
                "websocket_stats": ws_stats,
                "broadcaster_stats": broadcaster_stats,
                "server_time": datetime.now(timezone.utc).isoformat()
            }
            
            await self._send_response(websocket, MessageType.STATUS_RESPONSE, status_data)
            
        except Exception as e:
            await self._send_error(websocket, f"Status request failed: {e}")
    
    async def _send_response(self, websocket: WebSocket, message_type: str, data: Dict[str, Any]) -> None:
        """
        Send response message to client.
        
        Args:
            websocket: WebSocket connection
            message_type: Response message type
            data: Response data
        """
        try:
            response = WebSocketMessage(
                type=message_type,
                data=data
            )
            
            await websocket.send_text(response.json())
            
        except Exception as e:
            logger.error(f"Error sending response: {e}")
    
    async def _send_error(self, websocket: WebSocket, error_message: str) -> None:
        """
        Send error message to client.
        
        Args:
            websocket: WebSocket connection
            error_message: Error message
        """
        try:
            error_response = WebSocketMessage(
                type=MessageType.ERROR,
                data={
                    "error": error_message,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            await websocket.send_text(error_response.json())
            
        except Exception as e:
            logger.error(f"Error sending error message: {e}")
    
    # Event creation helpers
    
    def create_security_event(self, event_data: SecurityEventData) -> EventUpdate:
        """
        Create security event update.
        
        Args:
            event_data: Security event data
            
        Returns:
            EventUpdate for security event
        """
        return EventUpdate(
            event_type=MessageType.SECURITY_EVENT,
            data=event_data.dict(),
            priority=event_data.severity,
            timestamp=event_data.timestamp
        )
    
    def create_system_status_event(self, status_data: SystemStatusData) -> EventUpdate:
        """
        Create system status event update.
        
        Args:
            status_data: System status data
            
        Returns:
            EventUpdate for system status
        """
        priority = EventPriority.HIGH if status_data.status != "healthy" else EventPriority.LOW
        
        return EventUpdate(
            event_type=MessageType.SYSTEM_STATUS,
            data=status_data.dict(),
            priority=priority
        )
    
    def create_processing_update_event(self, processing_data: ProcessingUpdateData) -> EventUpdate:
        """
        Create processing update event.
        
        Args:
            processing_data: Processing update data
            
        Returns:
            EventUpdate for processing update
        """
        priority = EventPriority.HIGH if processing_data.error_message else EventPriority.MEDIUM
        
        return EventUpdate(
            event_type=MessageType.PROCESSING_UPDATE,
            data=processing_data.dict(),
            priority=priority
        )
    
    def create_health_check_event(self, health_data: HealthCheckData) -> EventUpdate:
        """
        Create health check event.
        
        Args:
            health_data: Health check data
            
        Returns:
            EventUpdate for health check
        """
        priority = EventPriority.CRITICAL if health_data.overall_status == "unhealthy" else EventPriority.LOW
        
        return EventUpdate(
            event_type=MessageType.HEALTH_CHECK,
            data=health_data.dict(),
            priority=priority,
            timestamp=health_data.timestamp
        )
    
    # Broadcast helpers
    
    async def broadcast_security_event(self, event_data: SecurityEventData) -> Dict[str, Any]:
        """
        Broadcast security event to all subscribed clients.
        
        Args:
            event_data: Security event data
            
        Returns:
            Broadcast result
        """
        event = self.create_security_event(event_data)
        return await self.event_broadcaster.broadcast_event(event)
    
    async def broadcast_system_status(self, status_data: SystemStatusData) -> Dict[str, Any]:
        """
        Broadcast system status to all subscribed clients.
        
        Args:
            status_data: System status data
            
        Returns:
            Broadcast result
        """
        event = self.create_system_status_event(status_data)
        return await self.event_broadcaster.broadcast_event(event)
    
    async def broadcast_processing_update(self, processing_data: ProcessingUpdateData) -> Dict[str, Any]:
        """
        Broadcast processing update to all subscribed clients.
        
        Args:
            processing_data: Processing update data
            
        Returns:
            Broadcast result
        """
        event = self.create_processing_update_event(processing_data)
        return await self.event_broadcaster.broadcast_event(event)
    
    async def broadcast_health_check(self, health_data: HealthCheckData) -> Dict[str, Any]:
        """
        Broadcast health check to all subscribed clients.
        
        Args:
            health_data: Health check data
            
        Returns:
            Broadcast result
        """
        event = self.create_health_check_event(health_data)
        return await self.event_broadcaster.broadcast_event(event)
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get information about active WebSocket connections.
        
        Returns:
            Connection information
        """
        return {
            "active_connections": len(self.active_connections),
            "websocket_manager_stats": self.websocket_manager.get_statistics(),
            "broadcaster_stats": self.event_broadcaster.get_statistics(),
            "connected_clients": self.websocket_manager.get_connected_clients()
        }