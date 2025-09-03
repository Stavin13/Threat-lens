"""
WebSocket server for real-time updates.

This module provides WebSocket connection management, event broadcasting,
and real-time communication with frontend clients with authentication support.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set
from uuid import uuid4
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .base import RealtimeComponent, HealthMonitorMixin
from .exceptions import WebSocketError, AuthenticationError, AuthorizationError
from .auth import get_auth_manager, WebSocketAuthInfo, SessionInfo
from .audit import get_audit_logger, AuditEventType

logger = logging.getLogger(__name__)


class EventUpdate(BaseModel):
    """Model for WebSocket event updates."""
    
    event_type: str = Field(..., description="Type of event update")
    data: Dict[str, Any] = Field(..., description="Event data")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    priority: int = Field(default=5, ge=1, le=10, description="Event priority")
    client_id: Optional[str] = Field(default=None, description="Target client ID (None for broadcast)")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ClientConnection(BaseModel):
    """Model for WebSocket client connection."""
    
    client_id: str = Field(..., description="Unique client identifier")
    websocket: WebSocket = Field(..., description="WebSocket connection")
    connected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    subscriptions: Set[str] = Field(default_factory=set, description="Event type subscriptions")
    last_ping: Optional[datetime] = Field(default=None, description="Last ping timestamp")
    user_agent: Optional[str] = Field(default=None, description="Client user agent")
    auth_info: Optional[WebSocketAuthInfo] = Field(default=None, description="Authentication information")
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WebSocketManager(RealtimeComponent, HealthMonitorMixin):
    """
    Manages WebSocket connections and handles real-time communication.
    
    Provides connection lifecycle management, message broadcasting,
    and client subscription handling.
    """
    
    def __init__(self, max_connections: int = 100, require_auth: bool = True):
        super().__init__("WebSocketManager")
        self.max_connections = max_connections
        self.require_auth = require_auth
        self.connections: Dict[str, ClientConnection] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.broadcast_task: Optional[asyncio.Task] = None
        self.ping_task: Optional[asyncio.Task] = None
        self.auth_manager = get_auth_manager()
        self.audit_logger = get_audit_logger()
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "authenticated_connections": 0,
            "messages_sent": 0,
            "messages_failed": 0,
            "broadcasts_sent": 0,
            "auth_failures": 0
        }
    
    async def _start_impl(self) -> None:
        """Start WebSocket manager."""
        logger.info("Starting WebSocket manager")
        
        # Start background tasks
        self.broadcast_task = asyncio.create_task(self._broadcast_worker())
        self.ping_task = asyncio.create_task(self._ping_worker())
        
        logger.info(f"WebSocket manager started (max connections: {self.max_connections})")
    
    async def _stop_impl(self) -> None:
        """Stop WebSocket manager."""
        logger.info("Stopping WebSocket manager")
        
        # Cancel background tasks
        if self.broadcast_task:
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                pass
        
        if self.ping_task:
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect all clients
        await self._disconnect_all_clients()
        
        logger.info("WebSocket manager stopped")
    
    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None, 
                     token: Optional[str] = None) -> str:
        """
        Accept a new WebSocket connection with authentication.
        
        Args:
            websocket: WebSocket connection
            client_id: Optional client identifier
            token: Optional authentication token
            
        Returns:
            Client ID for the connection
            
        Raises:
            WebSocketError: If connection limit reached or connection fails
            AuthenticationError: If authentication is required but fails
        """
        try:
            # Check connection limit
            if len(self.connections) >= self.max_connections:
                await websocket.close(code=1013, reason="Connection limit reached")
                raise WebSocketError(f"Connection limit reached ({self.max_connections})")
            
            # Generate client ID if not provided
            if not client_id:
                client_id = str(uuid4())
            
            # Accept WebSocket connection first
            await websocket.accept()
            
            # Get client info
            user_agent = None
            if hasattr(websocket, 'headers'):
                user_agent = websocket.headers.get('user-agent')
            
            # Handle authentication if required
            auth_info = None
            if self.require_auth:
                try:
                    auth_info = await self.auth_manager.authenticate_websocket(
                        websocket, client_id, token
                    )
                    self.stats["authenticated_connections"] += 1
                    
                    # Log successful authentication
                    self.audit_logger.log_websocket_event(
                        AuditEventType.WEBSOCKET_CONNECTED,
                        f"WebSocket client authenticated: {client_id}",
                        client_id,
                        auth_info.session_info
                    )
                    
                except (AuthenticationError, AuthorizationError) as e:
                    self.stats["auth_failures"] += 1
                    
                    # Log authentication failure
                    self.audit_logger.log_websocket_event(
                        AuditEventType.WEBSOCKET_AUTH_FAILED,
                        f"WebSocket authentication failed: {client_id} - {str(e)}",
                        client_id
                    )
                    
                    await websocket.close(code=1008, reason=f"Authentication failed: {str(e)}")
                    raise AuthenticationError(f"WebSocket authentication failed: {e}")
            
            # Create client connection
            connection = ClientConnection(
                client_id=client_id,
                websocket=websocket,
                user_agent=user_agent,
                auth_info=auth_info
            )
            
            self.connections[client_id] = connection
            self.stats["total_connections"] += 1
            self.stats["active_connections"] = len(self.connections)
            
            # Send welcome message with authentication status
            welcome_message = {
                "type": "connection_established",
                "client_id": client_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "server_info": {
                    "name": "ThreatLens WebSocket Server",
                    "version": "1.0.0",
                    "authentication_required": self.require_auth
                }
            }
            
            if auth_info:
                welcome_message["user_info"] = {
                    "username": auth_info.session_info.username,
                    "role": auth_info.session_info.role.value,
                    "permissions": [p.value for p in auth_info.session_info.permissions]
                }
            
            await self._send_to_client(client_id, welcome_message)
            
            logger.info(f"WebSocket client connected: {client_id}" + 
                       (f" (user: {auth_info.session_info.username})" if auth_info else " (unauthenticated)"))
            self.update_health_metric("active_connections", len(self.connections))
            
            return client_id
            
        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            self._handle_error(e, f"connecting client {client_id}")
            raise WebSocketError(f"Failed to connect client: {e}")
    
    async def disconnect(self, client_id: str, reason: str = "Client disconnected") -> None:
        """
        Disconnect a WebSocket client.
        
        Args:
            client_id: Client identifier
            reason: Disconnection reason
        """
        if client_id not in self.connections:
            logger.warning(f"Attempted to disconnect unknown client: {client_id}")
            return
        
        try:
            connection = self.connections[client_id]
            
            # Log disconnection if authenticated
            if connection.auth_info:
                self.audit_logger.log_websocket_event(
                    AuditEventType.WEBSOCKET_DISCONNECTED,
                    f"WebSocket client disconnected: {client_id} - {reason}",
                    client_id,
                    connection.auth_info.session_info
                )
                
                # Remove WebSocket authentication
                self.auth_manager.remove_websocket_auth(client_id)
                self.stats["authenticated_connections"] = max(0, self.stats["authenticated_connections"] - 1)
            
            # Close WebSocket connection
            try:
                await connection.websocket.close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket for {client_id}: {e}")
            
            # Remove from connections
            del self.connections[client_id]
            self.stats["active_connections"] = len(self.connections)
            
            logger.info(f"WebSocket client disconnected: {client_id} ({reason})")
            self.update_health_metric("active_connections", len(self.connections))
            
        except Exception as e:
            self._handle_error(e, f"disconnecting client {client_id}")
    
    async def subscribe(self, client_id: str, event_types: List[str]) -> bool:
        """
        Subscribe a client to specific event types.
        
        Args:
            client_id: Client identifier
            event_types: List of event types to subscribe to
            
        Returns:
            True if subscription successful, False otherwise
        """
        if client_id not in self.connections:
            logger.warning(f"Attempted to subscribe unknown client: {client_id}")
            return False
        
        try:
            connection = self.connections[client_id]
            connection.subscriptions.update(event_types)
            
            # Send subscription confirmation
            await self._send_to_client(client_id, {
                "type": "subscription_updated",
                "subscriptions": list(connection.subscriptions),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            logger.debug(f"Client {client_id} subscribed to: {event_types}")
            return True
            
        except Exception as e:
            self._handle_error(e, f"subscribing client {client_id}")
            return False
    
    async def unsubscribe(self, client_id: str, event_types: List[str]) -> bool:
        """
        Unsubscribe a client from specific event types.
        
        Args:
            client_id: Client identifier
            event_types: List of event types to unsubscribe from
            
        Returns:
            True if unsubscription successful, False otherwise
        """
        if client_id not in self.connections:
            logger.warning(f"Attempted to unsubscribe unknown client: {client_id}")
            return False
        
        try:
            connection = self.connections[client_id]
            connection.subscriptions.difference_update(event_types)
            
            # Send subscription confirmation
            await self._send_to_client(client_id, {
                "type": "subscription_updated",
                "subscriptions": list(connection.subscriptions),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            logger.debug(f"Client {client_id} unsubscribed from: {event_types}")
            return True
            
        except Exception as e:
            self._handle_error(e, f"unsubscribing client {client_id}")
            return False
    
    async def send_to_client(self, client_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to a specific client.
        
        Args:
            client_id: Target client identifier
            message: Message to send
            
        Returns:
            True if message sent successfully, False otherwise
        """
        return await self._send_to_client(client_id, message)
    
    async def broadcast_event(self, event: EventUpdate) -> int:
        """
        Broadcast an event to all subscribed clients.
        
        Args:
            event: Event to broadcast
            
        Returns:
            Number of clients that received the event
        """
        try:
            # Add to message queue for processing
            await self.message_queue.put(event)
            return len(self.connections)
            
        except Exception as e:
            self._handle_error(e, "broadcasting event")
            return 0
    
    async def _send_to_client(self, client_id: str, message: Dict[str, Any]) -> bool:
        """
        Internal method to send message to a specific client.
        
        Args:
            client_id: Target client identifier
            message: Message to send
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if client_id not in self.connections:
            logger.warning(f"Attempted to send message to unknown client: {client_id}")
            return False
        
        try:
            connection = self.connections[client_id]
            message_json = json.dumps(message, default=str)
            
            await connection.websocket.send_text(message_json)
            self.stats["messages_sent"] += 1
            
            return True
            
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected during message send")
            await self.disconnect(client_id, "WebSocket disconnected")
            return False
        except Exception as e:
            self.stats["messages_failed"] += 1
            self._handle_error(e, f"sending message to client {client_id}")
            await self.disconnect(client_id, f"Send error: {e}")
            return False
    
    async def _broadcast_worker(self) -> None:
        """Background worker for processing broadcast messages."""
        logger.info("Starting broadcast worker")
        
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(
                        self.message_queue.get(),
                        timeout=1.0
                    )
                    
                    await self._process_broadcast_event(event)
                    
                except asyncio.TimeoutError:
                    # Timeout is normal, continue loop
                    continue
                except Exception as e:
                    self._handle_error(e, "in broadcast worker")
                    await asyncio.sleep(1)  # Brief pause on error
                    
        except asyncio.CancelledError:
            logger.info("Broadcast worker cancelled")
            raise
        except Exception as e:
            logger.error(f"Broadcast worker error: {e}")
        finally:
            logger.info("Broadcast worker stopped")
    
    async def _process_broadcast_event(self, event: EventUpdate) -> None:
        """
        Process a broadcast event and send to subscribed clients.
        
        Args:
            event: Event to process and broadcast
        """
        try:
            sent_count = 0
            failed_count = 0
            
            # If event has specific client_id, send only to that client
            if event.client_id:
                success = await self._send_to_client(event.client_id, {
                    "type": event.event_type,
                    "data": event.data,
                    "timestamp": event.timestamp.isoformat(),
                    "priority": event.priority
                })
                if success:
                    sent_count = 1
                else:
                    failed_count = 1
            else:
                # Broadcast to all subscribed clients
                for client_id, connection in list(self.connections.items()):
                    # Check if client is subscribed to this event type
                    if not connection.subscriptions or event.event_type in connection.subscriptions:
                        success = await self._send_to_client(client_id, {
                            "type": event.event_type,
                            "data": event.data,
                            "timestamp": event.timestamp.isoformat(),
                            "priority": event.priority
                        })
                        if success:
                            sent_count += 1
                        else:
                            failed_count += 1
            
            self.stats["broadcasts_sent"] += 1
            
            if failed_count > 0:
                logger.warning(f"Broadcast event {event.event_type}: {sent_count} sent, {failed_count} failed")
            else:
                logger.debug(f"Broadcast event {event.event_type}: {sent_count} clients")
                
        except Exception as e:
            self._handle_error(e, f"processing broadcast event {event.event_type}")
    
    async def _ping_worker(self) -> None:
        """Background worker for sending ping messages to maintain connections."""
        logger.info("Starting ping worker")
        
        try:
            while not self._shutdown_event.is_set():
                try:
                    await asyncio.sleep(30)  # Ping every 30 seconds
                    
                    if not self.connections:
                        continue
                    
                    # Send ping to all connected clients
                    ping_message = {
                        "type": "ping",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    for client_id in list(self.connections.keys()):
                        await self._send_to_client(client_id, ping_message)
                    
                    logger.debug(f"Sent ping to {len(self.connections)} clients")
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self._handle_error(e, "in ping worker")
                    
        except asyncio.CancelledError:
            logger.info("Ping worker cancelled")
            raise
        except Exception as e:
            logger.error(f"Ping worker error: {e}")
        finally:
            logger.info("Ping worker stopped")
    
    async def _disconnect_all_clients(self) -> None:
        """Disconnect all connected clients."""
        logger.info(f"Disconnecting {len(self.connections)} clients")
        
        for client_id in list(self.connections.keys()):
            await self.disconnect(client_id, "Server shutdown")
    
    def get_connected_clients(self) -> List[Dict[str, Any]]:
        """
        Get information about connected clients.
        
        Returns:
            List of client information dictionaries
        """
        clients = []
        for client_id, connection in self.connections.items():
            clients.append({
                "client_id": client_id,
                "connected_at": connection.connected_at.isoformat(),
                "subscriptions": list(connection.subscriptions),
                "user_agent": connection.user_agent,
                "last_ping": connection.last_ping.isoformat() if connection.last_ping else None
            })
        return clients
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get WebSocket server statistics.
        
        Returns:
            Dictionary with server statistics
        """
        return {
            **self.stats,
            "max_connections": self.max_connections,
            "queue_size": self.message_queue.qsize()
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get detailed health status."""
        base_status = super().get_health_status()
        
        # Add WebSocket-specific health metrics
        base_status.update({
            "connections": {
                "active": len(self.connections),
                "max": self.max_connections,
                "utilization": len(self.connections) / self.max_connections if self.max_connections > 0 else 0
            },
            "queue": {
                "size": self.message_queue.qsize(),
                "is_healthy": self.message_queue.qsize() < 1000  # Arbitrary threshold
            },
            "statistics": self.get_statistics(),
            "health_metrics": self.get_health_metrics()
        })
        
        return base_status