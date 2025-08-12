import websocketService, { WebSocketMessage, ConnectionStatus } from '../websocket';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  sentMessages: string[] = [];

  constructor(public url: string) {
    // Simulate connection after a short delay
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 10);
  }

  send(data: string) {
    this.sentMessages.push(data);
  }

  close(code?: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code: code || 1000, reason }));
    }
  }

  // Helper method to simulate receiving messages
  simulateMessage(data: any) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }

  // Helper method to simulate errors
  simulateError() {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }
}

// Replace global WebSocket with mock
(global as any).WebSocket = MockWebSocket;

describe('WebSocket Service', () => {
  let mockWebSocket: MockWebSocket;

  beforeEach(() => {
    // Reset the service
    websocketService.disconnect();
    
    // Intercept WebSocket creation
    const originalWebSocket = (global as any).WebSocket;
    (global as any).WebSocket = jest.fn().mockImplementation((url: string) => {
      mockWebSocket = new MockWebSocket(url);
      return mockWebSocket;
    });
  });

  afterEach(() => {
    websocketService.disconnect();
  });

  describe('Connection Management', () => {
    test('should connect successfully', async () => {
      const promise = websocketService.connect();

      // Wait for connection to establish
      await promise;

      expect(websocketService.isConnected()).toBe(true);
      expect(websocketService.getStatus().connected).toBe(true);
    });

    test('should handle connection failure', async () => {
      const connectPromise = websocketService.connect();

      // Simulate connection error
      setTimeout(() => {
        mockWebSocket.simulateError();
      }, 5);

      await expect(connectPromise).rejects.toThrow('WebSocket connection failed');
      expect(websocketService.isConnected()).toBe(false);
    });

    test('should disconnect cleanly', async () => {
      await websocketService.connect();
      expect(websocketService.isConnected()).toBe(true);

      websocketService.disconnect();
      expect(websocketService.isConnected()).toBe(false);
    });

    test('should handle reconnection attempts', async () => {
      await websocketService.connect();

      // Simulate unexpected disconnection
      mockWebSocket.close(1006, 'Connection lost');

      // Should attempt to reconnect
      await new Promise(resolve => setTimeout(resolve, 100));
      expect((global as any).WebSocket).toHaveBeenCalledTimes(2);
    });

    test('should not exceed max reconnection attempts', async () => {
      await websocketService.connect();

      // Simulate multiple connection failures
      for (let i = 0; i < 12; i++) {
        mockWebSocket.close(1006, 'Connection lost');
        await new Promise(resolve => setTimeout(resolve, 10));
      }

      // Should not exceed max attempts (10)
      expect((global as any).WebSocket).toHaveBeenCalledTimes(11); // Initial + 10 retries
    });
  });

  describe('Event Handling', () => {
    beforeEach(async () => {
      await websocketService.connect();
    });

    test('should handle incoming messages', (done) => {
      const testMessage: WebSocketMessage = {
        type: 'test_event',
        data: { test: 'data' },
        timestamp: new Date().toISOString()
      };

      websocketService.on('test_event', (message) => {
        expect(message.type).toBe('test_event');
        expect(message.data.test).toBe('data');
        done();
      });

      mockWebSocket.simulateMessage(testMessage);
    });

    test('should handle wildcard event listeners', (done) => {
      const testMessage: WebSocketMessage = {
        type: 'any_event',
        data: { test: 'wildcard' },
        timestamp: new Date().toISOString()
      };

      websocketService.on('*', (message) => {
        expect(message.type).toBe('any_event');
        expect(message.data.test).toBe('wildcard');
        done();
      });

      mockWebSocket.simulateMessage(testMessage);
    });

    test('should remove event listeners', async () => {
      const handler = jest.fn();
      
      websocketService.on('test_event', handler);
      websocketService.off('test_event', handler);

      mockWebSocket.simulateMessage({
        type: 'test_event',
        data: {},
        timestamp: new Date().toISOString()
      });

      // Wait a bit to ensure handler is not called
      await new Promise(resolve => setTimeout(resolve, 10));
      expect(handler).not.toHaveBeenCalled();
    });

    test('should handle connection status changes', (done) => {
      let callCount = 0;
      
      websocketService.onConnectionChange((status: ConnectionStatus) => {
        callCount++;
        if (callCount === 2) { // Second call should be disconnection
          expect(status.connected).toBe(false);
          expect(status.error).toBeTruthy();
          done();
        }
      });

      // Simulate disconnection
      mockWebSocket.close(1006, 'Test disconnection');
    });
  });

  describe('Subscription Management', () => {
    beforeEach(async () => {
      await websocketService.connect();
    });

    test('should send subscription messages', () => {
      websocketService.subscribe(['security_event', 'system_status']);

      const sentMessage = JSON.parse(mockWebSocket.sentMessages[0]);
      expect(sentMessage.type).toBe('subscribe');
      expect(sentMessage.data.event_types).toEqual(['security_event', 'system_status']);
    });

    test('should send unsubscription messages', () => {
      websocketService.unsubscribe(['security_event']);

      const sentMessage = JSON.parse(mockWebSocket.sentMessages[0]);
      expect(sentMessage.type).toBe('unsubscribe');
      expect(sentMessage.data.event_types).toEqual(['security_event']);
    });

    test('should restore subscriptions on reconnect', async () => {
      // Subscribe to events
      websocketService.subscribe(['security_event']);
      
      // Clear sent messages
      mockWebSocket.sentMessages = [];

      // Simulate disconnection and reconnection
      mockWebSocket.close(1006, 'Connection lost');
      
      // Wait for reconnection
      await new Promise(resolve => setTimeout(resolve, 100));

      // Should restore subscriptions
      const restoreMessage = mockWebSocket.sentMessages.find(msg => {
        const parsed = JSON.parse(msg);
        return parsed.type === 'subscribe';
      });
      
      expect(restoreMessage).toBeTruthy();
    });
  });

  describe('Filter Management', () => {
    beforeEach(async () => {
      await websocketService.connect();
    });

    test('should send filter messages', () => {
      const filter = {
        event_types: ['security_event'],
        min_priority: 5,
        categories: ['security']
      };

      websocketService.setFilter(filter);

      const sentMessage = JSON.parse(mockWebSocket.sentMessages[0]);
      expect(sentMessage.type).toBe('set_filter');
      expect(sentMessage.data).toEqual(filter);
    });

    test('should send clear filter messages', () => {
      websocketService.clearFilter();

      const sentMessage = JSON.parse(mockWebSocket.sentMessages[0]);
      expect(sentMessage.type).toBe('clear_filter');
    });

    test('should restore filters on reconnect', async () => {
      const filter = { event_types: ['security_event'] };
      
      // Set filter
      websocketService.setFilter(filter);
      
      // Clear sent messages
      mockWebSocket.sentMessages = [];

      // Simulate disconnection and reconnection
      mockWebSocket.close(1006, 'Connection lost');
      
      // Wait for reconnection
      await new Promise(resolve => setTimeout(resolve, 100));

      // Should restore filter
      const restoreMessage = mockWebSocket.sentMessages.find(msg => {
        const parsed = JSON.parse(msg);
        return parsed.type === 'set_filter';
      });
      
      expect(restoreMessage).toBeTruthy();
    });
  });

  describe('Ping/Pong', () => {
    beforeEach(async () => {
      await websocketService.connect();
    });

    test('should send ping messages', () => {
      websocketService.ping();

      const sentMessage = JSON.parse(mockWebSocket.sentMessages[0]);
      expect(sentMessage.type).toBe('ping');
      expect(sentMessage.data.timestamp).toBeTruthy();
    });

    test('should handle pong responses', (done) => {
      websocketService.on('pong', (message) => {
        expect(message.type).toBe('pong');
        done();
      });

      mockWebSocket.simulateMessage({
        type: 'pong',
        data: { timestamp: new Date().toISOString() },
        timestamp: new Date().toISOString()
      });
    });
  });

  describe('Error Handling', () => {
    beforeEach(async () => {
      await websocketService.connect();
    });

    test('should handle malformed JSON messages', () => {
      // Should not throw error
      expect(() => {
        if (mockWebSocket.onmessage) {
          mockWebSocket.onmessage(new MessageEvent('message', { data: 'invalid json' }));
        }
      }).not.toThrow();
    });

    test('should handle server error messages', (done) => {
      websocketService.onConnectionChange((status) => {
        if (status.error) {
          expect(status.error).toBe('Server error occurred');
          done();
        }
      });

      mockWebSocket.simulateMessage({
        type: 'error',
        data: { error: 'Server error occurred' },
        timestamp: new Date().toISOString()
      });
    });

    test('should handle event handler errors gracefully', () => {
      const faultyHandler = () => {
        throw new Error('Handler error');
      };

      websocketService.on('test_event', faultyHandler);

      // Should not crash the service
      expect(() => {
        mockWebSocket.simulateMessage({
          type: 'test_event',
          data: {},
          timestamp: new Date().toISOString()
        });
      }).not.toThrow();
    });
  });

  describe('Status Reporting', () => {
    test('should report correct connection status', async () => {
      // Initially disconnected
      expect(websocketService.getStatus().connected).toBe(false);

      // After connection
      await websocketService.connect();
      expect(websocketService.getStatus().connected).toBe(true);
      expect(websocketService.getStatus().lastConnected).toBeTruthy();

      // After disconnection
      websocketService.disconnect();
      expect(websocketService.getStatus().connected).toBe(false);
    });

    test('should track reconnection attempts', async () => {
      await websocketService.connect();

      // Simulate connection loss
      mockWebSocket.close(1006, 'Connection lost');

      // Wait for reconnection attempt
      await new Promise(resolve => setTimeout(resolve, 100));

      const status = websocketService.getStatus();
      expect(status.reconnectAttempts).toBeGreaterThan(0);
    });
  });
});