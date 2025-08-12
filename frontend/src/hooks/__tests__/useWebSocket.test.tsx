import React from 'react';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useWebSocket, useSecurityEvents } from '../useWebSocket';
import websocketService from '../../services/websocket';

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

  simulateMessage(data: any) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }
}

// Replace global WebSocket with mock
(global as any).WebSocket = MockWebSocket;

describe('useWebSocket Hook', () => {
  let mockWebSocket: MockWebSocket;

  beforeEach(() => {
    websocketService.disconnect();
    
    (global as any).WebSocket = jest.fn().mockImplementation((url: string) => {
      mockWebSocket = new MockWebSocket(url);
      return mockWebSocket;
    });
  });

  afterEach(() => {
    websocketService.disconnect();
  });

  describe('Basic Functionality', () => {
    test('should connect automatically by default', async () => {
      const { result } = renderHook(() => useWebSocket());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      expect(result.current.status.connected).toBe(true);
    });

    test('should not auto-connect when disabled', () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));

      expect(result.current.status.connecting).toBe(false);
      expect(result.current.isConnected).toBe(false);
    });

    test('should allow manual connection', async () => {
      const { result } = renderHook(() => useWebSocket({ autoConnect: false }));

      expect(result.current.isConnected).toBe(false);

      await act(async () => {
        await result.current.connect();
      });

      expect(result.current.isConnected).toBe(true);
    });

    test('should allow disconnection', async () => {
      const { result } = renderHook(() => useWebSocket());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      act(() => {
        result.current.disconnect();
      });

      expect(result.current.isConnected).toBe(false);
    });
  });

  describe('Event Handling', () => {
    test('should receive and store events', async () => {
      const onEvent = jest.fn();
      const { result } = renderHook(() => useWebSocket({ onEvent }));

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const testMessage = {
        type: 'test_event',
        data: { test: 'data' },
        timestamp: new Date().toISOString()
      };

      act(() => {
        mockWebSocket.simulateMessage(testMessage);
      });

      await waitFor(() => {
        expect(result.current.lastMessage).toEqual(testMessage);
        expect(result.current.events).toHaveLength(1);
        expect(onEvent).toHaveBeenCalledWith('test_event', testMessage);
      });
    });

    test('should limit stored events to 100', async () => {
      const { result } = renderHook(() => useWebSocket());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Send 150 events
      act(() => {
        for (let i = 0; i < 150; i++) {
          mockWebSocket.simulateMessage({
            type: 'test_event',
            data: { index: i },
            timestamp: new Date().toISOString()
          });
        }
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(100);
        // Should keep the most recent events
        expect(result.current.events[99].data.index).toBe(149);
      });
    });

    test('should clear events when requested', async () => {
      const { result } = renderHook(() => useWebSocket());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      act(() => {
        mockWebSocket.simulateMessage({
          type: 'test_event',
          data: {},
          timestamp: new Date().toISOString()
        });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
      });

      act(() => {
        result.current.clearEvents();
      });

      expect(result.current.events).toHaveLength(0);
    });
  });

  describe('Subscription Management', () => {
    test('should subscribe to initial event types', async () => {
      const { result } = renderHook(() => 
        useWebSocket({ subscriptions: ['security_event', 'system_status'] })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Should have sent subscription message
      const subscribeMessage = mockWebSocket.sentMessages.find(msg => {
        const parsed = JSON.parse(msg);
        return parsed.type === 'subscribe';
      });

      expect(subscribeMessage).toBeTruthy();
    });

    test('should allow dynamic subscription changes', async () => {
      const { result } = renderHook(() => useWebSocket());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      act(() => {
        result.current.subscribe(['new_event_type']);
      });

      const subscribeMessage = JSON.parse(mockWebSocket.sentMessages[mockWebSocket.sentMessages.length - 1]);
      expect(subscribeMessage.type).toBe('subscribe');
      expect(subscribeMessage.data.event_types).toEqual(['new_event_type']);
    });

    test('should allow unsubscription', async () => {
      const { result } = renderHook(() => useWebSocket());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      act(() => {
        result.current.unsubscribe(['unwanted_event']);
      });

      const unsubscribeMessage = JSON.parse(mockWebSocket.sentMessages[mockWebSocket.sentMessages.length - 1]);
      expect(unsubscribeMessage.type).toBe('unsubscribe');
      expect(unsubscribeMessage.data.event_types).toEqual(['unwanted_event']);
    });
  });

  describe('Filter Management', () => {
    test('should set initial filter', async () => {
      const filter = {
        event_types: ['security_event'],
        min_priority: 5
      };

      const { result } = renderHook(() => useWebSocket({ filter }));

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const filterMessage = mockWebSocket.sentMessages.find(msg => {
        const parsed = JSON.parse(msg);
        return parsed.type === 'set_filter';
      });

      expect(filterMessage).toBeTruthy();
    });

    test('should allow dynamic filter changes', async () => {
      const { result } = renderHook(() => useWebSocket());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const newFilter = {
        categories: ['security'],
        max_priority: 8
      };

      act(() => {
        result.current.setFilter(newFilter);
      });

      const filterMessage = JSON.parse(mockWebSocket.sentMessages[mockWebSocket.sentMessages.length - 1]);
      expect(filterMessage.type).toBe('set_filter');
      expect(filterMessage.data).toEqual(newFilter);
    });

    test('should allow filter clearing', async () => {
      const { result } = renderHook(() => useWebSocket());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      act(() => {
        result.current.clearFilter();
      });

      const clearMessage = JSON.parse(mockWebSocket.sentMessages[mockWebSocket.sentMessages.length - 1]);
      expect(clearMessage.type).toBe('clear_filter');
    });
  });
});

describe('useSecurityEvents Hook', () => {
  let mockWebSocket: MockWebSocket;

  beforeEach(() => {
    websocketService.disconnect();
    
    (global as any).WebSocket = jest.fn().mockImplementation((url: string) => {
      mockWebSocket = new MockWebSocket(url);
      return mockWebSocket;
    });
  });

  afterEach(() => {
    websocketService.disconnect();
  });

  test('should automatically subscribe to security events', async () => {
    const { result } = renderHook(() => useSecurityEvents());

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const subscribeMessage = mockWebSocket.sentMessages.find(msg => {
      const parsed = JSON.parse(msg);
      return parsed.type === 'subscribe' && 
             parsed.data.event_types.includes('security_event');
    });

    expect(subscribeMessage).toBeTruthy();
  });

  test('should convert WebSocket messages to EventResponse format', async () => {
    const { result } = renderHook(() => useSecurityEvents());

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const securityEventMessage = {
      type: 'security_event',
      data: {
        event_id: 'test-event-1',
        severity: 8,
        category: 'security',
        source: 'test-source',
        message: 'Test security event',
        timestamp: new Date().toISOString(),
        analysis: {
          explanation: 'This is a test security event'
        },
        recommendations: ['Review system logs']
      },
      timestamp: new Date().toISOString()
    };

    act(() => {
      mockWebSocket.simulateMessage(securityEventMessage);
    });

    await waitFor(() => {
      expect(result.current.events).toHaveLength(1);
      
      const event = result.current.events[0];
      expect(event.event.id).toBe('test-event-1');
      expect(event.analysis.severity_score).toBe(8);
      expect(event.analysis.explanation).toBe('This is a test security event');
      expect(event.analysis.recommendations).toEqual(['Review system logs']);
    });
  });

  test('should handle optimistic updates', async () => {
    const { result } = renderHook(() => useSecurityEvents());

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const optimisticEvent = {
      event: {
        id: 'optimistic-1',
        timestamp: new Date().toISOString(),
        source: 'test',
        message: 'Optimistic event',
        category: 'test'
      },
      analysis: {
        severity_score: 5,
        explanation: 'Optimistic explanation',
        recommendations: []
      }
    };

    act(() => {
      result.current.addOptimisticEvent(optimisticEvent);
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.optimisticEvents).toHaveLength(1);

    // Simulate real event arriving
    act(() => {
      mockWebSocket.simulateMessage({
        type: 'security_event',
        data: {
          event_id: 'optimistic-1',
          severity: 6, // Different severity
          category: 'test',
          source: 'test',
          message: 'Optimistic event',
          timestamp: new Date().toISOString(),
          analysis: {
            explanation: 'Real explanation'
          }
        },
        timestamp: new Date().toISOString()
      });
    });

    await waitFor(() => {
      // Should have removed optimistic event and added real event
      expect(result.current.optimisticEvents).toHaveLength(0);
      expect(result.current.securityEvents).toHaveLength(1);
      expect(result.current.events).toHaveLength(1);
      
      // Should use real event data
      const event = result.current.events[0];
      expect(event.analysis.severity_score).toBe(6);
      expect(event.analysis.explanation).toBe('Real explanation');
    });
  });

  test('should prevent duplicate events', async () => {
    const { result } = renderHook(() => useSecurityEvents());

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const eventMessage = {
      type: 'security_event',
      data: {
        event_id: 'duplicate-test',
        severity: 5,
        category: 'test',
        source: 'test',
        message: 'Duplicate test',
        timestamp: new Date().toISOString()
      },
      timestamp: new Date().toISOString()
    };

    // Send same event twice
    act(() => {
      mockWebSocket.simulateMessage(eventMessage);
      mockWebSocket.simulateMessage(eventMessage);
    });

    await waitFor(() => {
      // Should only have one event
      expect(result.current.events).toHaveLength(1);
    });
  });

  test('should limit events to 1000', async () => {
    const { result } = renderHook(() => useSecurityEvents());

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    // Send 1100 events
    act(() => {
      for (let i = 0; i < 1100; i++) {
        mockWebSocket.simulateMessage({
          type: 'security_event',
          data: {
            event_id: `event-${i}`,
            severity: 5,
            category: 'test',
            source: 'test',
            message: `Event ${i}`,
            timestamp: new Date().toISOString()
          },
          timestamp: new Date().toISOString()
        });
      }
    });

    await waitFor(() => {
      // Should limit to 1000 events
      expect(result.current.events).toHaveLength(1000);
      
      // Should keep the most recent events
      const firstEvent = result.current.events[0];
      expect(firstEvent.event.id).toBe('event-1099');
    });
  });

  test('should handle malformed security events gracefully', async () => {
    const { result } = renderHook(() => useSecurityEvents());

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    // Send malformed security event
    act(() => {
      mockWebSocket.simulateMessage({
        type: 'security_event',
        data: {
          // Missing required fields
          severity: 5
        },
        timestamp: new Date().toISOString()
      });
    });

    // Should not crash and should not add the malformed event
    expect(result.current.events).toHaveLength(0);
  });
});