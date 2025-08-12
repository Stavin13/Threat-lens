"""
Unit tests for WebSocketManager connection and broadcasting functionality.

Tests WebSocket connection management, client subscriptions, message broadcasting,
and connection lifecycle management.
"""

import pytest
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import WebSocket, WebSocketDisconnect

from app.realtime.websocket_server import (
    WebSocketManager, EventUpdate, ClientConnection
)
from app.realtime.exceptions import WebSocketError


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self, should_fail_accept=False, should_fail_send=False, should_disconnect=False):
        self.messages = []
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.headers = {"user-agent": "test-client/1.0"}
        self.should_fail_accept = should_fail_accept
        self.should_fail_send = should_fail_send
        self.should_disconnect = should_disconnect
        self.accept_called = False
        self.send_count = 0
    
    async def accept(self):
        """Mock accept method."""
        self.accept_called = True
        if self.should_fail_accept:
            raise Exception("Accept failed")
    
    async def send_text(self, message: str):
        """Mock send_text method."""
        self.send_count += 1
        if self.should_disconnect and self.send_count > 1:
            raise WebSocketDisconnect(code=1000, reason="Client disconnected")
        if self.should_fail_send:
            raise Exception("Send failed")
        if self.closed:
            raise Exception("WebSocket is closed")
        self.messages.append(message)
    
    async def close(self, code=None, reason=None):
        """Mock close method."""
        self.closed = True
        self.close_code = code
        self.close_reason = reason


class TestEventUpdate:
    """Test EventUpdate data model."""
    
    def test_event_update_creation(self):
        """Test basic event update creation."""
        data = {"message": "test", "severity": 5}
        event = EventUpdate(
            event_type="security_event",
            data=data,
            priority=8
        )
        
        assert event.event_type == "security_event"
        assert event.data == data
        assert event.priority == 8
        assert event.client_id is None
        assert isinstance(event.timestamp, datetime)
    
    def test_event_update_with_client_id(self):
        """Test event update with specific client ID."""
        event = EventUpdate(
            event_type="system_status",
            data={"status": "healthy"},
            client_id="client_123"
        )
        
        assert event.client_id == "client_123"
    
    def test_event_update_defaults(self):
        """Test event update with default values."""
        event = EventUpdate(
            event_type="test_event",
            data={}
        )
        
        assert event.priority == 5  # Default priority
        assert event.client_id is None
        assert event.timestamp is not None


class TestClientConnection:
    """Test ClientConnection data model."""
    
    def test_client_connection_creation(self):
        """Test basic client connection creation."""
        mock_ws = MockWebSocket()
        connection = ClientConnection(
            client_id="test_client",
            websocket=mock_ws,
            user_agent="test-browser/1.0"
        )
        
        assert connection.client_id == "test_client"
        assert connection.websocket == mock_ws
        assert connection.user_agent == "test-browser/1.0"
        assert len(connection.subscriptions) == 0
        assert connection.last_ping is None
        assert isinstance(connection.connected_at, datetime)
    
    def test_client_connection_subscriptions(self):
        """Test client connection subscription management."""
        mock_ws = MockWebSocket()
        connection = ClientConnection(
            client_id="test_client",
            websocket=mock_ws
        )
        
        # Add subscriptions
        connection.subscriptions.add("security_event")
        connection.subscriptions.add("system_status")
        
        assert len(connection.subscriptions) == 2
        assert "security_event" in connection.subscriptions
        assert "system_status" in connection.subscriptions


class TestWebSocketManager:
    """Test WebSocketManager functionality."""
    
    @pytest.fixture
    async def manager(self):
        """Create a WebSocket manager for testing."""
        manager = WebSocketManager(max_connections=10)
        await manager.start()
        yield manager
        await manager.stop()
    
    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        return MockWebSocket()
    
    @pytest.mark.asyncio
    async def test_manager_lifecycle(self):
        """Test WebSocket manager start and stop lifecycle."""
        manager = WebSocketManager(max_connections=5)
        
        # Initial state
        assert not manager.is_running
        assert len(manager.connections) == 0
        assert manager.broadcast_task is None
        assert manager.ping_task is None
        
        # Start manager
        await manager.start()
        assert manager.is_running
        assert manager.broadcast_task is not None
        assert manager.ping_task is not None
        
        # Stop manager
        await manager.stop()
        assert not manager.is_running
    
    @pytest.mark.asyncio
    async def test_client_connection_success(self, manager, mock_websocket):
        """Test successful client connection."""
        client_id = await manager.connect(mock_websocket)
        
        assert client_id is not None
        assert len(manager.connections) == 1
        assert client_id in manager.connections
        assert mock_websocket.accept_called
        
        # Check welcome message was sent
        assert len(mock_websocket.messages) == 1
        welcome_msg = json.loads(mock_websocket.messages[0])
        assert welcome_msg["type"] == "connection_established"
        assert welcome_msg["client_id"] == client_id
    
    @pytest.mark.asyncio
    async def test_client_connection_with_custom_id(self, manager, mock_websocket):
        """Test client connection with custom client ID."""
        custom_id = "custom_client_123"
        client_id = await manager.connect(mock_websocket, custom_id)
        
        assert client_id == custom_id
        assert custom_id in manager.connections
    
    @pytest.mark.asyncio
    async def test_connection_limit_enforcement(self, mock_websocket):
        """Test connection limit enforcement."""
        manager = WebSocketManager(max_connections=2)
        await manager.start()
        
        try:
            # Connect up to limit
            client1 = await manager.connect(MockWebSocket())
            client2 = await manager.connect(MockWebSocket())
            
            assert len(manager.connections) == 2
            
            # Try to exceed limit
            with pytest.raises(WebSocketError, match="Connection limit reached"):
                await manager.connect(MockWebSocket())
            
        finally:
            await manager.stop()
    
    @pytest.mark.asyncio
    async def test_connection_accept_failure(self, manager):
        """Test handling of WebSocket accept failure."""
        failing_websocket = MockWebSocket(should_fail_accept=True)
        
        with pytest.raises(WebSocketError):
            await manager.connect(failing_websocket)
        
        # Should not have added to connections
        assert len(manager.connections) == 0
    
    @pytest.mark.asyncio
    async def test_client_disconnection(self, manager, mock_websocket):
        """Test client disconnection."""
        client_id = await manager.connect(mock_websocket)
        assert len(manager.connections) == 1
        
        await manager.disconnect(client_id)
        
        assert len(manager.connections) == 0
        assert client_id not in manager.connections
        assert mock_websocket.closed
    
    @pytest.mark.asyncio
    async def test_disconnect_unknown_client(self, manager):
        """Test disconnecting unknown client."""
        # Should not raise exception
        await manager.disconnect("unknown_client")
        assert len(manager.connections) == 0
    
    @pytest.mark.asyncio
    async def test_client_subscription_management(self, manager, mock_websocket):
        """Test client subscription management."""
        client_id = await manager.connect(mock_websocket)
        
        # Subscribe to event types
        event_types = ["security_event", "system_status"]
        result = await manager.subscribe(client_id, event_types)
        assert result is True
        
        # Check subscription was recorded
        connection = manager.connections[client_id]
        assert "security_event" in connection.subscriptions
        assert "system_status" in connection.subscriptions
        
        # Check subscription confirmation was sent
        assert len(mock_websocket.messages) >= 2  # Welcome + subscription
        sub_msg = json.loads(mock_websocket.messages[-1])
        assert sub_msg["type"] == "subscription_updated"
        assert set(sub_msg["subscriptions"]) == set(event_types)
    
    @pytest.mark.asyncio
    async def test_client_unsubscription(self, manager, mock_websocket):
        """Test client unsubscription."""
        client_id = await manager.connect(mock_websocket)
        
        # Subscribe first
        await manager.subscribe(client_id, ["security_event", "system_status"])
        
        # Unsubscribe from one event type
        result = await manager.unsubscribe(client_id, ["security_event"])
        assert result is True
        
        # Check subscription was updated
        connection = manager.connections[client_id]
        assert "security_event" not in connection.subscriptions
        assert "system_status" in connection.subscriptions
        
        # Check unsubscription confirmation was sent
        unsub_msg = json.loads(mock_websocket.messages[-1])
        assert unsub_msg["type"] == "subscription_updated"
        assert "system_status" in unsub_msg["subscriptions"]
        assert "security_event" not in unsub_msg["subscriptions"]
    
    @pytest.mark.asyncio
    async def test_subscribe_unknown_client(self, manager):
        """Test subscribing unknown client."""
        result = await manager.subscribe("unknown_client", ["security_event"])
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_message_to_client(self, manager, mock_websocket):
        """Test sending message to specific client."""
        client_id = await manager.connect(mock_websocket)
        
        test_message = {
            "type": "test_message",
            "data": {"content": "Hello, World!"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        result = await manager.send_to_client(client_id, test_message)
        assert result is True
        
        # Check message was sent
        assert len(mock_websocket.messages) >= 2  # Welcome + test message
        sent_msg = json.loads(mock_websocket.messages[-1])
        assert sent_msg["type"] == "test_message"
        assert sent_msg["data"]["content"] == "Hello, World!"
    
    @pytest.mark.asyncio
    async def test_send_message_to_unknown_client(self, manager):
        """Test sending message to unknown client."""
        test_message = {"type": "test", "data": {}}
        result = await manager.send_to_client("unknown_client", test_message)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_message_failure(self, manager):
        """Test handling of message send failure."""
        failing_websocket = MockWebSocket(should_fail_send=True)
        client_id = await manager.connect(failing_websocket)
        
        test_message = {"type": "test", "data": {}}
        result = await manager.send_to_client(client_id, test_message)
        assert result is False
        
        # Client should be disconnected due to send failure
        assert len(manager.connections) == 0
    
    @pytest.mark.asyncio
    async def test_websocket_disconnect_during_send(self, manager):
        """Test handling WebSocket disconnect during send."""
        disconnecting_websocket = MockWebSocket(should_disconnect=True)
        client_id = await manager.connect(disconnecting_websocket)
        
        # First message should succeed (welcome message)
        # Second message should trigger disconnect
        test_message = {"type": "test", "data": {}}
        result = await manager.send_to_client(client_id, test_message)
        assert result is False
        
        # Client should be automatically disconnected
        assert len(manager.connections) == 0
    
    @pytest.mark.asyncio
    async def test_broadcast_event(self, manager):
        """Test broadcasting event to all clients."""
        # Connect multiple clients
        clients = []
        for i in range(3):
            mock_ws = MockWebSocket()
            client_id = await manager.connect(mock_ws)
            clients.append((client_id, mock_ws))
        
        # Create test event
        event = EventUpdate(
            event_type="test_broadcast",
            data={"message": "Broadcast test"},
            priority=5
        )
        
        # Broadcast event
        result = await manager.broadcast_event(event)
        assert result == 3  # Number of connected clients
        
        # Wait for broadcast processing
        await asyncio.sleep(0.2)
        
        # Verify all clients received the event
        for client_id, mock_ws in clients:
            # Should have welcome message + broadcast message
            assert len(mock_ws.messages) >= 2
    
    @pytest.mark.asyncio
    async def test_broadcast_to_specific_client(self, manager):
        """Test broadcasting to specific client."""
        # Connect two clients
        client1_ws = MockWebSocket()
        client1_id = await manager.connect(client1_ws)
        
        client2_ws = MockWebSocket()
        client2_id = await manager.connect(client2_ws)
        
        # Create event for specific client
        event = EventUpdate(
            event_type="specific_message",
            data={"message": "Only for client1"},
            client_id=client1_id
        )
        
        # Broadcast event
        await manager.broadcast_event(event)
        await asyncio.sleep(0.2)
        
        # Only client1 should receive the message
        # (Both have welcome message, but only client1 should have the specific message)
        assert len(client1_ws.messages) >= 2
        assert len(client2_ws.messages) == 1  # Only welcome message
    
    @pytest.mark.asyncio
    async def test_subscription_filtering(self, manager):
        """Test event filtering based on subscriptions."""
        # Connect client and subscribe to specific events
        mock_ws = MockWebSocket()
        client_id = await manager.connect(mock_ws)
        await manager.subscribe(client_id, ["security_event"])
        
        # Broadcast subscribed event
        subscribed_event = EventUpdate(
            event_type="security_event",
            data={"severity": 8}
        )
        await manager.broadcast_event(subscribed_event)
        await asyncio.sleep(0.2)
        
        # Broadcast non-subscribed event
        non_subscribed_event = EventUpdate(
            event_type="system_status",
            data={"status": "healthy"}
        )
        await manager.broadcast_event(non_subscribed_event)
        await asyncio.sleep(0.2)
        
        # Client should receive welcome + subscription confirmation + security_event
        # but not system_status
        messages = [json.loads(msg) for msg in mock_ws.messages]
        event_types = [msg["type"] for msg in messages]
        
        assert "security_event" in event_types
        assert "system_status" not in event_types
    
    @pytest.mark.asyncio
    async def test_no_subscription_receives_all(self, manager):
        """Test that clients with no subscriptions receive all events."""
        # Connect client without subscriptions
        mock_ws = MockWebSocket()
        client_id = await manager.connect(mock_ws)
        
        # Broadcast different event types
        events = [
            EventUpdate(event_type="security_event", data={}),
            EventUpdate(event_type="system_status", data={})
        ]
        
        for event in events:
            await manager.broadcast_event(event)
        
        await asyncio.sleep(0.2)
        
        # Client should receive all events (plus welcome message)
        assert len(mock_ws.messages) >= 3
    
    def test_get_connected_clients(self, manager):
        """Test getting connected clients information."""
        # Initially no clients
        clients = manager.get_connected_clients()
        assert len(clients) == 0
    
    @pytest.mark.asyncio
    async def test_get_connected_clients_with_connections(self, manager):
        """Test getting connected clients with active connections."""
        # Connect clients
        mock_ws1 = MockWebSocket()
        client1_id = await manager.connect(mock_ws1)
        await manager.subscribe(client1_id, ["security_event"])
        
        mock_ws2 = MockWebSocket()
        client2_id = await manager.connect(mock_ws2)
        
        clients = manager.get_connected_clients()
        assert len(clients) == 2
        
        # Find client1 info
        client1_info = next(c for c in clients if c["client_id"] == client1_id)
        assert "security_event" in client1_info["subscriptions"]
        assert client1_info["user_agent"] == "test-client/1.0"
        assert "connected_at" in client1_info
    
    def test_get_statistics(self, manager):
        """Test getting WebSocket server statistics."""
        stats = manager.get_statistics()
        
        assert "total_connections" in stats
        assert "active_connections" in stats
        assert "messages_sent" in stats
        assert "messages_failed" in stats
        assert "broadcasts_sent" in stats
        assert "max_connections" in stats
        assert "queue_size" in stats
        
        assert stats["max_connections"] == manager.max_connections
        assert stats["active_connections"] == len(manager.connections)
    
    @pytest.mark.asyncio
    async def test_get_health_status(self, manager):
        """Test getting health status."""
        health = manager.get_health_status()
        
        assert "name" in health
        assert "is_running" in health
        assert "connections" in health
        assert "queue" in health
        assert "statistics" in health
        assert "health_metrics" in health
        
        assert health["is_running"] == manager.is_running
        assert health["connections"]["active"] == len(manager.connections)
        assert health["connections"]["max"] == manager.max_connections
    
    @pytest.mark.asyncio
    async def test_ping_worker(self, manager):
        """Test ping worker functionality."""
        # Connect a client
        mock_ws = MockWebSocket()
        client_id = await manager.connect(mock_ws)
        
        # Wait for ping (ping interval is 30s, but we can test the mechanism)
        # We'll manually trigger a ping by calling the internal method
        ping_message = {
            "type": "ping",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await manager._send_to_client(client_id, ping_message)
        
        # Check ping was sent
        messages = [json.loads(msg) for msg in mock_ws.messages]
        ping_messages = [msg for msg in messages if msg["type"] == "ping"]
        assert len(ping_messages) == 1
    
    @pytest.mark.asyncio
    async def test_broadcast_worker_error_handling(self, manager):
        """Test broadcast worker error handling."""
        # Connect client that will fail on send
        failing_ws = MockWebSocket(should_fail_send=True)
        client_id = await manager.connect(failing_ws)
        
        # Create event
        event = EventUpdate(
            event_type="test_event",
            data={"message": "test"}
        )
        
        # Broadcast should handle the error gracefully
        await manager.broadcast_event(event)
        await asyncio.sleep(0.2)
        
        # Client should be disconnected due to send failure
        assert len(manager.connections) == 0
    
    @pytest.mark.asyncio
    async def test_manager_shutdown_with_clients(self, manager):
        """Test manager shutdown with connected clients."""
        # Connect multiple clients
        clients = []
        for i in range(3):
            mock_ws = MockWebSocket()
            client_id = await manager.connect(mock_ws)
            clients.append((client_id, mock_ws))
        
        assert len(manager.connections) == 3
        
        # Stop manager
        await manager.stop()
        
        # All clients should be disconnected
        assert len(manager.connections) == 0
        for client_id, mock_ws in clients:
            assert mock_ws.closed


if __name__ == "__main__":
    pytest.main([__file__])