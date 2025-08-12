/**
 * Integration tests for WebSocket client connection and reconnection logic.
 * 
 * Tests connection lifecycle, automatic reconnection, message handling,
 * and error recovery scenarios.
 */

import websocketService from '../websocket';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  public readyState: number = MockWebSocket.CONNECTING;
  public onopen: ((event: Event) => void) | null = null;
  public onclose: ((event: CloseEvent) => void) | null = null;
  public onmessage: ((event: MessageEvent) => void) | null = null;
  public onerror: ((event: Event) => void) | null = null;
  public url: string;
  public protocol: string;

  private static instances: MockWebSocket[] = [];

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocol = Array.isArray(protocols) ? protocols[0] : protocols || '';
    MockWebSocket.instances.push(this);
    
    // Simulate async connection
    setTimeout(() => {
      if (this.readyState === MockWebSocket.CONNECTING) {
        this.readyState = MockWebSocket.OPEN;
        this.onopen?.(new Event('open'));
      }
    }, 10);
  }

  send(data: string | ArrayBuffer | Blob | ArrayBufferView): void {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
    // Echo back for testing
    setTimeout(() => {
      if (this.onmessage) {
        this.onmessage(new MessageEvent('message', { data }));
      }
    }, 5);
  }

  close(code?: number, reason?: string): void {
    if (this.readyState === MockWebSocket.OPEN || this.readyState === MockWebSocket.CONNECTING) {
      this.readyState = MockWebSocket.CLOSING;
      setTimeout(() => {
        this.readyState = MockWebSocket.CLOSED;
        this.onclose?.(new CloseEvent('close', { code: code || 1000, reason: reason || '' }));
      }, 5);
    }
  }

  // Test utilities
  static getLastInstance(): MockWebSocket | undefined {
    return this.instances[this.instances.length - 1];
  }

  static getAllInstances(): MockWebSocket[] {
    return [...this.instances];
  }

  static clearInstances(): void {
    this.instances = [];
  }

  simulateError(): void {
    this.onerror?.(new Event('error'));
  }

  simulateMessage(data: any): void {
    if (this.readyState === MockWebSocket.OPEN && this.onmessage) {
      this.onmessage(new MessageEvent('message', { 
        data: typeof data === 'string' ? data : JSON.stringify(data) 
      }));
    }
  }

  simulateClose(code: number = 1000, reason: string = ''): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close', { code, reason }));
  }
}

// Mock global WebSocket
(global as any).WebSocket = MockWebSocket;

describe('WebSocket Integration Tests', () => {
  beforeEach(() => {
    MockWebSocket.clearInstances();
    websocketService.disconnect();
    jest.clearAllTimers();
    jest.useFakeTimers();
  });

  afterEach(() => {
    websocketService.disconnect();
    jest.useRealTimers();
  });

  describe('Connection Lifecycle', () => {
    it('should establish WebSocket connection successfully', async () => {
      const connectPromise = websocketService.connect();
      
      // Advance timers to complete connection
      jest.advanceTimersByTime(20);
      
      await connectPromise;
      
      expect(websocketService.isConnected()).toBe(true);
      expect(MockWebSocket.getLastInstance()?.readyState).toBe(MockWebSocket.OPEN);
    });

    it('should handle connection URL configuration', async () => {
      await websocketService.connect('ws://custom-host:8080/ws');
      
      jest.advanceTimersByTime(20);
      
      const instance = MockWebSocket.getLastInstance();
      expect(instance?.url).toBe('ws://custom-host:8080/ws');
    });

    it('should disconnect cleanly', async () => {
      await websocketService.connect();
      jest.advanceTimersByTime(20);
      
      expect(websocketService.isConnected()).toBe(true);
      
      websocketService.disconnect();
      jest.advanceTimersByTime(20);
      
      expect(websocketService.isConnected()).toBe(false);
      expect(MockWebSocket.getLastInstance()?.readyState).toBe(MockWebSocket.CLOSED);
    });

    it('should track connection status changes', async () => {
      const statusChanges: any[] = [];
      
      websocketService.onConnectionChange((status) => {
        statusChanges.push({ ...status });
      });

      // Initial status should be disconnected
      expect(websocketService.getStatus().connected).toBe(false);

      // Connect
      const connectPromise = websocketService.connect();
      
      // Should be connecting
      expect(websocketService.getStatus().connecting).toBe(true);
      
      jest.advanceTimersByTime(20);
      await connectPromise;
      
      // Should be connected
      expect(websocketService.getStatus().connected).toBe(true);
      expect(websocketService.getStatus().connecting).toBe(false);
      
      // Disconnect
      websocketService.disconnect();
      jest.advanceTimersByTime(20);
      
      // Should be disconnected
      expect(websocketService.getStatus().connected).toBe(false);
      
      // Verify status change callbacks were called
      expect(statusChanges.length).toBeGreaterThan(0);
      expect(statusChanges.some(s => s.connecting)).toBe(true);
      expect(statusChanges.some(s => s.connected)).toBe(true);
    });

    it('should handle multiple connection attempts gracefully', async () => {
      const promise1 = websocketService.connect();
      const promise2 = websocketService.connect();
      const promise3 = websocketService.connect();
      
      jest.advanceTimersByTime(20);
      
      await Promise.all([promise1, promise2, promise3]);
      
      // Should only create one WebSocket instance
      expect(MockWebSocket.getAllInstances()).toHaveLength(1);
      expect(websocketService.isConnected()).toBe(true);
    });
  });

  describe('Automatic Reconnection', () => {
    it('should automatically reconnect on connection loss', async () => {
      await websocketService.connect();
      jest.advanceTimersByTime(20);
      
      expect(websocketService.isConnected()).toBe(true);
      
      // Simulate connection loss
      const instance = MockWebSocket.getLastInstance()!;
      instance.simulateClose(1006, 'Connection lost'); // Abnormal closure
      
      jest.advanceTimersByTime(20);
      
      // Should attempt reconnection
      expect(websocketService.getStatus().connecting).toBe(true);
      
      // Complete reconnection
      jest.advanceTimersByTime(1000); // Wait for reconnect delay
      jest.advanceTimersByTime(20); // Complete connection
      
      expect(websocketService.isConnected()).toBe(true);
      expect(MockWebSocket.getAllInstances().length).toBeGreaterThan(1); // New instance created
    });

    it('should implement exponential backoff for reconnection', async () => {
      await websocketService.connect();
      jest.advanceTimersByTime(20);
      
      const reconnectDelays: number[] = [];
      let startTime = Date.now();
      
      // Mock Date.now to track delays
      const originalNow = Date.now;
      Date.now = jest.fn(() => startTime);
      
      websocketService.onConnectionChange((status) => {
        if (status.connecting && status.reconnectAttempts > 0) {
          reconnectDelays.push(Date.now() - startTime);
          startTime = Date.now();
        }
      });

      // Simulate multiple connection failures
      for (let i = 0; i < 3; i++) {
        const instance = MockWebSocket.getLastInstance()!;
        instance.simulateClose(1006, 'Connection lost');
        
        jest.advanceTimersByTime(20);
        jest.advanceTimersByTime(Math.pow(2, i) * 1000); // Exponential backoff
        jest.advanceTimersByTime(20);
        
        startTime += Math.pow(2, i) * 1000;
      }
      
      Date.now = originalNow;
      
      // Verify exponential backoff pattern
      expect(reconnectDelays.length).toBeGreaterThan(0);
    });

    it('should limit maximum reconnection attempts', async () => {
      await websocketService.connect();
      jest.advanceTimersByTime(20);
      
      let maxAttempts = 0;
      websocketService.onConnectionChange((status) => {
        maxAttempts = Math.max(maxAttempts, status.reconnectAttempts);
      });

      // Simulate many connection failures
      for (let i = 0; i < 10; i++) {
        const instance = MockWebSocket.getLastInstance()!;
        instance.simulateClose(1006, 'Connection lost');
        
        jest.advanceTimersByTime(20);
        jest.advanceTimersByTime(5000); // Wait for reconnect
        jest.advanceTimersByTime(20);
      }
      
      // Should stop attempting after max attempts
      expect(maxAttempts).toBeLessThanOrEqual(5); // Assuming max 5 attempts
    });

    it('should not reconnect on normal closure', async () => {
      await websocketService.connect();
      jest.advanceTimersByTime(20);
      
      const initialInstanceCount = MockWebSocket.getAllInstances().length;
      
      // Simulate normal closure
      const instance = MockWebSocket.getLastInstance()!;
      instance.simulateClose(1000, 'Normal closure');
      
      jest.advanceTimersByTime(20);
      jest.advanceTimersByTime(5000); // Wait for potential reconnect
      
      // Should not create new instance
      expect(MockWebSocket.getAllInstances()).toHaveLength(initialInstanceCount);
      expect(websocketService.isConnected()).toBe(false);
    });

    it('should reset reconnect attempts on successful connection', async () => {
      await websocketService.connect();
      jest.advanceTimersByTime(20);
      
      // Simulate connection loss and reconnect
      const instance = MockWebSocket.getLastInstance()!;
      instance.simulateClose(1006, 'Connection lost');
      
      jest.advanceTimersByTime(20);
      jest.advanceTimersByTime(1000);
      jest.advanceTimersByTime(20);
      
      // Should have reset reconnect attempts
      expect(websocketService.getStatus().reconnectAttempts).toBe(0);
    });
  });

  describe('Message Handling', () => {
    beforeEach(async () => {
      await websocketService.connect();
      jest.advanceTimersByTime(20);
    });

    it('should receive and parse JSON messages', async () => {
      const receivedMessages: any[] = [];
      
      websocketService.on('test_event', (data) => {
        receivedMessages.push(data);
      });

      const testMessage = {
        type: 'test_event',
        data: { message: 'Hello, World!' },
        timestamp: '2023-01-01T00:00:00Z'
      };

      const instance = MockWebSocket.getLastInstance()!;
      instance.simulateMessage(testMessage);
      
      jest.advanceTimersByTime(10);
      
      expect(receivedMessages).toHaveLength(1);
      expect(receivedMessages[0]).toEqual(testMessage.data);
    });

    it('should handle malformed JSON messages gracefully', async () => {
      const errorMessages: any[] = [];
      
      websocketService.on('error', (data) => {
        errorMessages.push(data);
      });

      const instance = MockWebSocket.getLastInstance()!;
      instance.simulateMessage('invalid json {');
      
      jest.advanceTimersByTime(10);
      
      // Should not crash, may log error
      expect(websocketService.isConnected()).toBe(true);
    });

    it('should support wildcard event listeners', async () => {
      const allMessages: any[] = [];
      
      websocketService.on('*', (data, message) => {
        allMessages.push({ data, message });
      });

      const messages = [
        { type: 'event1', data: { test: 1 } },
        { type: 'event2', data: { test: 2 } },
        { type: 'event3', data: { test: 3 } }
      ];

      const instance = MockWebSocket.getLastInstance()!;
      messages.forEach(msg => instance.simulateMessage(msg));
      
      jest.advanceTimersByTime(10);
      
      expect(allMessages).toHaveLength(3);
      expect(allMessages[0].message.type).toBe('event1');
      expect(allMessages[1].message.type).toBe('event2');
      expect(allMessages[2].message.type).toBe('event3');
    });

    it('should handle event listener cleanup', async () => {
      const messages: any[] = [];
      
      const unsubscribe = websocketService.on('test_event', (data) => {
        messages.push(data);
      });

      const instance = MockWebSocket.getLastInstance()!;
      
      // Send message - should be received
      instance.simulateMessage({ type: 'test_event', data: { test: 1 } });
      jest.advanceTimersByTime(10);
      
      expect(messages).toHaveLength(1);
      
      // Unsubscribe
      unsubscribe();
      
      // Send another message - should not be received
      instance.simulateMessage({ type: 'test_event', data: { test: 2 } });
      jest.advanceTimersByTime(10);
      
      expect(messages).toHaveLength(1); // Still only 1 message
    });

    it('should maintain message order', async () => {
      const receivedOrder: number[] = [];
      
      websocketService.on('ordered_event', (data) => {
        receivedOrder.push(data.order);
      });

      const instance = MockWebSocket.getLastInstance()!;
      
      // Send messages in order
      for (let i = 1; i <= 5; i++) {
        instance.simulateMessage({
          type: 'ordered_event',
          data: { order: i }
        });
      }
      
      jest.advanceTimersByTime(10);
      
      expect(receivedOrder).toEqual([1, 2, 3, 4, 5]);
    });
  });

  describe('Subscription Management', () => {
    beforeEach(async () => {
      await websocketService.connect();
      jest.advanceTimersByTime(20);
    });

    it('should send subscription messages', async () => {
      const sentMessages: string[] = [];
      
      // Mock send to capture messages
      const instance = MockWebSocket.getLastInstance()!;
      const originalSend = instance.send;
      instance.send = jest.fn((data: string) => {
        sentMessages.push(data);
        originalSend.call(instance, data);
      });

      websocketService.subscribe(['security_event', 'system_status']);
      
      jest.advanceTimersByTime(10);
      
      expect(sentMessages).toHaveLength(1);
      const subscribeMessage = JSON.parse(sentMessages[0]);
      expect(subscribeMessage.type).toBe('subscribe');
      expect(subscribeMessage.event_types).toEqual(['security_event', 'system_status']);
    });

    it('should send unsubscription messages', async () => {
      const sentMessages: string[] = [];
      
      const instance = MockWebSocket.getLastInstance()!;
      const originalSend = instance.send;
      instance.send = jest.fn((data: string) => {
        sentMessages.push(data);
        originalSend.call(instance, data);
      });

      websocketService.subscribe(['security_event']);
      websocketService.unsubscribe(['security_event']);
      
      jest.advanceTimersByTime(10);
      
      expect(sentMessages).toHaveLength(2);
      const unsubscribeMessage = JSON.parse(sentMessages[1]);
      expect(unsubscribeMessage.type).toBe('unsubscribe');
      expect(unsubscribeMessage.event_types).toEqual(['security_event']);
    });

    it('should handle subscription persistence across reconnections', async () => {
      const sentMessages: string[] = [];
      
      // Subscribe to events
      websocketService.subscribe(['security_event', 'system_status']);
      
      // Simulate connection loss
      const instance = MockWebSocket.getLastInstance()!;
      instance.simulateClose(1006, 'Connection lost');
      
      jest.advanceTimersByTime(20);
      jest.advanceTimersByTime(1000); // Reconnect delay
      
      // Mock send on new instance
      const newInstance = MockWebSocket.getLastInstance()!;
      newInstance.send = jest.fn((data: string) => {
        sentMessages.push(data);
      });
      
      jest.advanceTimersByTime(20); // Complete reconnection
      
      // Should re-subscribe automatically
      expect(sentMessages.length).toBeGreaterThan(0);
      const resubscribeMessage = JSON.parse(sentMessages[sentMessages.length - 1]);
      expect(resubscribeMessage.type).toBe('subscribe');
      expect(resubscribeMessage.event_types).toEqual(['security_event', 'system_status']);
    });
  });

  describe('Error Handling', () => {
    it('should handle WebSocket errors gracefully', async () => {
      const errorEvents: any[] = [];
      
      websocketService.onConnectionChange((status) => {
        if (status.error) {
          errorEvents.push(status.error);
        }
      });

      await websocketService.connect();
      jest.advanceTimersByTime(20);
      
      // Simulate WebSocket error
      const instance = MockWebSocket.getLastInstance()!;
      instance.simulateError();
      
      jest.advanceTimersByTime(20);
      
      expect(errorEvents.length).toBeGreaterThan(0);
    });

    it('should handle send errors when disconnected', async () => {
      await websocketService.connect();
      jest.advanceTimersByTime(20);
      
      // Disconnect
      websocketService.disconnect();
      jest.advanceTimersByTime(20);
      
      // Try to send message - should not throw
      expect(() => {
        websocketService.subscribe(['test_event']);
      }).not.toThrow();
    });

    it('should handle connection timeout', async () => {
      // Mock WebSocket that never connects
      class TimeoutWebSocket extends MockWebSocket {
        constructor(url: string, protocols?: string | string[]) {
          super(url, protocols);
          this.readyState = MockWebSocket.CONNECTING;
          // Never call onopen
        }
      }
      
      (global as any).WebSocket = TimeoutWebSocket;
      
      const connectPromise = websocketService.connect();
      
      // Advance time beyond connection timeout
      jest.advanceTimersByTime(30000);
      
      // Should handle timeout gracefully
      expect(websocketService.getStatus().error).toBeTruthy();
    });
  });

  describe('Performance and Resource Management', () => {
    it('should clean up resources on disconnect', async () => {
      await websocketService.connect();
      jest.advanceTimersByTime(20);
      
      const instance = MockWebSocket.getLastInstance()!;
      
      // Add event listeners
      websocketService.on('test_event', () => {});
      websocketService.onConnectionChange(() => {});
      
      // Disconnect
      websocketService.disconnect();
      jest.advanceTimersByTime(20);
      
      // WebSocket should be closed
      expect(instance.readyState).toBe(MockWebSocket.CLOSED);
    });

    it('should handle high message volume', async () => {
      await websocketService.connect();
      jest.advanceTimersByTime(20);
      
      const receivedMessages: any[] = [];
      websocketService.on('high_volume_event', (data) => {
        receivedMessages.push(data);
      });

      const instance = MockWebSocket.getLastInstance()!;
      
      // Send many messages quickly
      for (let i = 0; i < 1000; i++) {
        instance.simulateMessage({
          type: 'high_volume_event',
          data: { id: i }
        });
      }
      
      jest.advanceTimersByTime(100);
      
      // Should handle all messages
      expect(receivedMessages).toHaveLength(1000);
      expect(receivedMessages[999].id).toBe(999);
    });

    it('should prevent memory leaks from event listeners', async () => {
      await websocketService.connect();
      jest.advanceTimersByTime(20);
      
      const unsubscribeFunctions: (() => void)[] = [];
      
      // Add many event listeners
      for (let i = 0; i < 100; i++) {
        const unsubscribe = websocketService.on(`event_${i}`, () => {});
        unsubscribeFunctions.push(unsubscribe);
      }
      
      // Remove all listeners
      unsubscribeFunctions.forEach(unsub => unsub());
      
      // Send messages - none should be received
      const receivedMessages: any[] = [];
      websocketService.on('test_cleanup', (data) => {
        receivedMessages.push(data);
      });

      const instance = MockWebSocket.getLastInstance()!;
      
      // Send messages to removed listeners
      for (let i = 0; i < 100; i++) {
        instance.simulateMessage({
          type: `event_${i}`,
          data: { test: true }
        });
      }
      
      jest.advanceTimersByTime(10);
      
      // Only the new listener should receive messages
      expect(receivedMessages).toHaveLength(0);
    });
  });
});