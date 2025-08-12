"""
Tests for WebSocket server functionality.
"""

import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

from app.realtime.websocket_server import WebSocketManager, EventUpdate, ClientConnection
from app.realtime.event_broadcaster import EventBroadcaster, EventFilter
from app.realtime.websocket_api import WebSocketAPI, MessageType, SubscriptionRequest
from app.realtime.exceptions import WebSocketError


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.messages = []
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.headers = {"user-agent": "test-client"}
    
    async def accept(self):
        """Mock accept method."""
        pass
    
    async def send_text(self, message: str):
        """Mock send_text method."""
        if self.closed:
            raise Exception("WebSocket is closed")
        self.messages.append(message)
    
    async def receive_text(self):
        """Mock receive_text method."""
        if self.closed:
            raise Exception("WebSocket is closed")
        # Return a test message
        return json.dumps({
            "type": "ping",
            "data": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    async def close(self, code=None, reason=None):
        """Mock close method."""
        self.closed = True
        self.close_code = code
        self.close_reason = reason


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket."""
    return MockWebSocket()


@pytest.fixture
async def websocket_manager():
    """Create a WebSocket manager for testing."""
    manager = WebSocketManager(max_connections=10)
    await manager.start()
    try:
        yield manager
    finally:
        await manager.stop()


@pytest.fixture
async def event_broadcaster():
    """Create an event broadcaster for testing."""
    # Create a simple websocket manager for the broadcaster
    ws_manager = WebSocketManager(max_connections=10)
    await ws_manager.start()
    
    broadcaster = EventBroadcaster(ws_manager, max_queue_size=100)
    await broadcaster.start()
    
    try:
        yield broadcaster
    finally:
        await broadcaster.stop()
        await ws_manager.stop()


@pytest.fixture
async def websocket_api():
    """Create a WebSocket API for testing."""
    # Create components
    ws_manager = WebSocketManager(max_connections=10)
    await ws_manager.start()
    
    broadcaster = EventBroadcaster(ws_manager, max_queue_size=100)
    await broadcaster.start()
    
    api = WebSocketAPI(ws_manager, broadcaster)
    
    try:
        yield api
    finally:
        await broadcaster.stop()
        await ws_manager.stop()


class TestWebSocketManager:
    """Test WebSocket manager functionality."""
    
    @pytest.mark.asyncio
    async def test_websocket_manager_lifecycle(self):
        """Test WebSocket manager start/stop lifecycle."""
        manager = WebSocketManager(max_connections=5)
        
        # Test initial state
        assert not manager.is_running
        assert len(manager.connections) == 0
        
        # Test start
        await manager.start()
        assert manager.is_running
        
        # Test stop
        await manager.stop()
        assert not manager.is_running
    
    @pytest.mark.asyncio
    async def test_client_connection(self, websocket_manager, mock_websocket):
        """Test client connection and disconnection."""
        # Test connection
        client_id = await websocket_manager.connect(mock_websocket)
        
        assert client_id is not None
        assert len(websocket_manager.connections) == 1
        assert client_id in websocket_manager.connections
        
        # Verify welcome message was sent
        assert len(mock_websocket.messages) == 1
        welcome_msg = json.loads(mock_websocket.messages[0])
        assert welcome_msg["type"] == "connection_established"
        assert welcome_msg["client_id"] == client_id
        
        # Test disconnection
        await websocket_manager.disconnect(client_id)
        assert len(websocket_manager.connections) == 0
        assert client_id not in websocket_manager.connections
    
    @pytest.mark.asyncio
    async def test_connection_limit(self, mock_websocket):
        """Test connection limit enforcement."""
        manager = WebSocketManager(max_connections=2)
        await manager.start()
        
        try:
            # Connect up to limit
            client1 = await manager.connect(MockWebSocket())
            client2 = await manager.connect(MockWebSocket())
            
            assert len(manager.connections) == 2
            
            # Try to exceed limit
            with pytest.raises(WebSocketError):
                await manager.connect(MockWebSocket())
            
        finally:
            await manager.stop()
    
    @pytest.mark.asyncio
    async def test_subscription_management(self, websocket_manager, mock_websocket):
        """Test client subscription management."""
        client_id = await websocket_manager.connect(mock_websocket)
        
        # Test subscription
        event_types = ["security_event", "system_status"]
        success = await websocket_manager.subscribe(client_id, event_types)
        assert success
        
        # Verify subscription confirmation was sent
        assert len(mock_websocket.messages) >= 2  # Welcome + subscription
        sub_msg = json.loads(mock_websocket.messages[-1])
        assert sub_msg["type"] == "subscription_updated"
        assert set(sub_msg["subscriptions"]) == set(event_types)
        
        # Test unsubscription
        success = await websocket_manager.unsubscribe(client_id, ["security_event"])
        assert success
        
        # Verify unsubscription confirmation
        unsub_msg = json.loads(mock_websocket.messages[-1])
        assert unsub_msg["type"] == "subscription_updated"
        assert "system_status" in unsub_msg["subscriptions"]
        assert "security_event" not in unsub_msg["subscriptions"]
    
    @pytest.mark.asyncio
    async def test_message_sending(self, websocket_manager, mock_websocket):
        """Test sending messages to clients."""
        client_id = await websocket_manager.connect(mock_websocket)
        
        # Send test message
        test_message = {
            "type": "test_event",
            "data": {"message": "Hello, World!"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        success = await websocket_manager.send_to_client(client_id, test_message)
        assert success
        
        # Verify message was sent
        assert len(mock_websocket.messages) >= 2  # Welcome + test message
        sent_msg = json.loads(mock_websocket.messages[-1])
        assert sent_msg["type"] == "test_event"
        assert sent_msg["data"]["message"] == "Hello, World!"
    
    @pytest.mark.asyncio
    async def test_broadcast_event(self, websocket_manager):
        """Test event broadcasting."""
        # Connect multiple clients
        clients = []
        for i in range(3):
            mock_ws = MockWebSocket()
            client_id = await websocket_manager.connect(mock_ws)
            clients.append((client_id, mock_ws))
        
        # Create test event
        event = EventUpdate(
            event_type="test_broadcast",
            data={"message": "Broadcast test"},
            priority=5
        )
        
        # Broadcast event
        result = await websocket_manager.broadcast_event(event)
        assert result == 3  # Number of connected clients
        
        # Wait for broadcast processing
        await asyncio.sleep(0.1)
        
        # Verify all clients received the event
        for client_id, mock_ws in clients:
            # Should have welcome message + broadcast message
            assert len(mock_ws.messages) >= 2


class TestEventBroadcaster:
    """Test event broadcaster functionality."""
    
    @pytest.mark.asyncio
    async def test_broadcaster_lifecycle(self, websocket_manager):
        """Test event broadcaster start/stop lifecycle."""
        broadcaster = EventBroadcaster(websocket_manager, max_queue_size=50)
        
        # Test initial state
        assert not broadcaster.is_running
        
        # Test start
        await broadcaster.start()
        assert broadcaster.is_running
        
        # Test stop
        await broadcaster.stop()
        assert not broadcaster.is_running
    
    @pytest.mark.asyncio
    async def test_client_filtering(self, event_broadcaster):
        """Test client event filtering."""
        client_id = "test_client"
        
        # Add event filter
        event_filter = EventFilter(
            event_types={"security_event"},
            min_priority=5
        )
        event_broadcaster.add_client_filter(client_id, event_filter)
        
        # Test event that should match filter
        matching_event = EventUpdate(
            event_type="security_event",
            data={"severity": 8},
            priority=8
        )
        
        should_receive = event_broadcaster._client_should_receive_event(client_id, matching_event)
        assert should_receive
        
        # Test event that should not match filter
        non_matching_event = EventUpdate(
            event_type="system_status",
            data={"status": "healthy"},
            priority=3
        )
        
        should_receive = event_broadcaster._client_should_receive_event(client_id, non_matching_event)
        assert not should_receive
    
    @pytest.mark.asyncio
    async def test_subscription_management(self, event_broadcaster):
        """Test client subscription management."""
        client_id = "test_client"
        
        # Subscribe to event types
        event_types = ["security_event", "processing_update"]
        event_broadcaster.subscribe_client(client_id, event_types)
        
        assert client_id in event_broadcaster.client_subscriptions
        assert event_broadcaster.client_subscriptions[client_id] == set(event_types)
        
        # Unsubscribe from one event type
        event_broadcaster.unsubscribe_client(client_id, ["security_event"])
        assert event_broadcaster.client_subscriptions[client_id] == {"processing_update"}
    
    @pytest.mark.asyncio
    async def test_message_queuing(self, event_broadcaster):
        """Test message queuing for disconnected clients."""
        client_id = "disconnected_client"
        
        # Create test event
        event = EventUpdate(
            event_type="test_event",
            data={"message": "Queued message"},
            priority=5
        )
        
        # Queue message for disconnected client
        await event_broadcaster._queue_message(client_id, event)
        
        # Verify message was queued
        assert client_id in event_broadcaster.message_queue
        assert len(event_broadcaster.message_queue[client_id]) == 1
        
        queued_msg = event_broadcaster.message_queue[client_id][0]
        assert queued_msg.client_id == client_id
        assert queued_msg.event.event_type == "test_event"


class TestWebSocketAPI:
    """Test WebSocket API functionality."""
    
    @pytest.mark.asyncio
    async def test_message_handling(self, websocket_api):
        """Test WebSocket message handling."""
        # This is a basic test - full message handling would require
        # more complex mocking of WebSocket connections
        
        # Test event creation
        from app.realtime.websocket_api import SecurityEventData
        
        security_data = SecurityEventData(
            event_id="test_event_123",
            severity=8,
            category="authentication",
            source="auth_service",
            message="Failed login attempt",
            timestamp=datetime.now(timezone.utc)
        )
        
        event = websocket_api.create_security_event(security_data)
        
        assert event.event_type == MessageType.SECURITY_EVENT
        assert event.priority == 8
        assert event.data["event_id"] == "test_event_123"
        assert event.data["severity"] == 8
    
    def test_connection_info(self, websocket_api):
        """Test getting connection information."""
        info = websocket_api.get_connection_info()
        
        assert "active_connections" in info
        assert "websocket_manager_stats" in info
        assert "broadcaster_stats" in info
        assert "connected_clients" in info
        
        # Should start with 0 connections
        assert info["active_connections"] == 0


if __name__ == "__main__":
    pytest.main([__file__])