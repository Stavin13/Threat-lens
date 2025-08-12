import { renderHook, act } from '@testing-library/react';
import { useRealtimeClient, useSecurityEvents } from '../useRealtimeClient';
import realtimeClient from '../../services/realtimeClient';

// Mock the realtime client
jest.mock('../../services/realtimeClient', () => ({
  __esModule: true,
  default: {
    initialize: jest.fn(),
    connect: jest.fn(),
    disconnect: jest.fn(),
    subscribe: jest.fn(),
    unsubscribe: jest.fn(),
    subscribeToSecurityEvents: jest.fn(),
    subscribeToSystemStatus: jest.fn(),
    subscribeToProcessingUpdates: jest.fn(),
    subscribeToHealthChecks: jest.fn(),
    onConnectionChange: jest.fn(),
    getConnectionStatus: jest.fn(),
    isConnected: jest.fn(),
    ping: jest.fn(),
    requestServerStatus: jest.fn(),
    getActiveSubscriptions: jest.fn(),
    destroy: jest.fn()
  },
  RealtimeClient: {
    convertToEventResponse: jest.fn()
  }
}));

describe('useRealtimeClient', () => {
  const mockRealtimeClient = realtimeClient as jest.Mocked<typeof realtimeClient>;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock default return values
    mockRealtimeClient.initialize.mockResolvedValue();
    mockRealtimeClient.connect.mockResolvedValue();
    mockRealtimeClient.getConnectionStatus.mockReturnValue({
      connected: false,
      connecting: false,
      error: null,
      lastConnected: null,
      reconnectAttempts: 0
    });
    mockRealtimeClient.isConnected.mockReturnValue(false);
    mockRealtimeClient.getActiveSubscriptions.mockReturnValue([]);
    
    // Mock subscription functions to return unsubscribe functions
    const mockUnsubscribe = jest.fn();
    mockRealtimeClient.subscribeToSecurityEvents.mockReturnValue(mockUnsubscribe);
    mockRealtimeClient.subscribeToSystemStatus.mockReturnValue(mockUnsubscribe);
    mockRealtimeClient.subscribeToProcessingUpdates.mockReturnValue(mockUnsubscribe);
    mockRealtimeClient.subscribeToHealthChecks.mockReturnValue(mockUnsubscribe);
    mockRealtimeClient.subscribe.mockReturnValue(mockUnsubscribe);
    mockRealtimeClient.onConnectionChange.mockReturnValue(mockUnsubscribe);
  });

  it('should initialize the realtime client on mount', async () => {
    renderHook(() => useRealtimeClient());
    
    // Wait for initialization
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    
    expect(mockRealtimeClient.initialize).toHaveBeenCalled();
  });

  it('should set up connection status monitoring', async () => {
    renderHook(() => useRealtimeClient());
    
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    
    expect(mockRealtimeClient.onConnectionChange).toHaveBeenCalledWith(expect.any(Function));
  });

  it('should subscribe to default event types', async () => {
    renderHook(() => useRealtimeClient());
    
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    
    expect(mockRealtimeClient.subscribeToSecurityEvents).toHaveBeenCalled();
    expect(mockRealtimeClient.subscribeToSystemStatus).toHaveBeenCalled();
    expect(mockRealtimeClient.subscribeToProcessingUpdates).toHaveBeenCalled();
    expect(mockRealtimeClient.subscribeToHealthChecks).toHaveBeenCalled();
  });

  it('should handle security event callbacks', async () => {
    const onSecurityEvent = jest.fn();
    
    renderHook(() => useRealtimeClient({ onSecurityEvent }));
    
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    
    // Get the callback passed to subscribeToSecurityEvents
    const securityEventCallback = mockRealtimeClient.subscribeToSecurityEvents.mock.calls[0][0];
    
    const eventData = {
      event_id: 'test-123',
      severity: 8,
      category: 'authentication',
      source: 'auth.log',
      message: 'Failed login attempt',
      timestamp: '2023-01-01T00:00:00Z'
    };
    
    act(() => {
      securityEventCallback(eventData);
    });
    
    expect(onSecurityEvent).toHaveBeenCalledWith(eventData);
  });

  it('should update connection status when it changes', async () => {
    const { result } = renderHook(() => useRealtimeClient());
    
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    
    // Get the connection change callback
    const connectionChangeCallback = mockRealtimeClient.onConnectionChange.mock.calls[0][0];
    
    const newStatus = {
      connected: true,
      connecting: false,
      error: null,
      lastConnected: new Date(),
      reconnectAttempts: 0
    };
    
    act(() => {
      connectionChangeCallback(newStatus);
    });
    
    expect(result.current.connectionStatus).toEqual(newStatus);
    expect(result.current.isConnected).toBe(true);
  });

  it('should provide connect and disconnect functions', async () => {
    const { result } = renderHook(() => useRealtimeClient());
    
    await act(async () => {
      await result.current.connect();
    });
    
    expect(mockRealtimeClient.connect).toHaveBeenCalled();
    
    act(() => {
      result.current.disconnect();
    });
    
    expect(mockRealtimeClient.disconnect).toHaveBeenCalled();
  });

  it('should provide subscription functions', async () => {
    const { result } = renderHook(() => useRealtimeClient());
    
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    
    const callback = jest.fn();
    
    act(() => {
      result.current.subscribe('security_event', callback);
    });
    
    expect(mockRealtimeClient.subscribe).toHaveBeenCalledWith('security_event', callback);
  });

  it('should provide utility functions', async () => {
    const { result } = renderHook(() => useRealtimeClient());
    
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    
    act(() => {
      result.current.ping();
    });
    expect(mockRealtimeClient.ping).toHaveBeenCalled();
    
    act(() => {
      result.current.requestServerStatus();
    });
    expect(mockRealtimeClient.requestServerStatus).toHaveBeenCalled();
    
    act(() => {
      result.current.getActiveSubscriptions();
    });
    expect(mockRealtimeClient.getActiveSubscriptions).toHaveBeenCalled();
  });

  it('should track recent security events', async () => {
    const { result } = renderHook(() => useRealtimeClient());
    
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    
    // Get the security event callback
    const securityEventCallback = mockRealtimeClient.subscribeToSecurityEvents.mock.calls[0][0];
    
    const eventData1 = {
      event_id: 'test-1',
      severity: 8,
      category: 'authentication',
      source: 'auth.log',
      message: 'Event 1',
      timestamp: '2023-01-01T00:00:00Z'
    };
    
    const eventData2 = {
      event_id: 'test-2',
      severity: 6,
      category: 'system',
      source: 'system.log',
      message: 'Event 2',
      timestamp: '2023-01-01T00:01:00Z'
    };
    
    act(() => {
      securityEventCallback(eventData1);
      securityEventCallback(eventData2);
    });
    
    expect(result.current.recentSecurityEvents).toHaveLength(2);
    expect(result.current.recentSecurityEvents[0]).toEqual(eventData2); // Most recent first
    expect(result.current.recentSecurityEvents[1]).toEqual(eventData1);
    expect(result.current.lastSecurityEvent).toEqual(eventData2);
  });

  it('should clear recent events', async () => {
    const { result } = renderHook(() => useRealtimeClient());
    
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    
    // Add an event first
    const securityEventCallback = mockRealtimeClient.subscribeToSecurityEvents.mock.calls[0][0];
    
    act(() => {
      securityEventCallback({
        event_id: 'test-1',
        severity: 8,
        category: 'authentication',
        source: 'auth.log',
        message: 'Event 1',
        timestamp: '2023-01-01T00:00:00Z'
      });
    });
    
    expect(result.current.recentSecurityEvents).toHaveLength(1);
    
    act(() => {
      result.current.clearRecentEvents();
    });
    
    expect(result.current.recentSecurityEvents).toHaveLength(0);
  });

  it('should clean up subscriptions on unmount', async () => {
    const { unmount } = renderHook(() => useRealtimeClient());
    
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    
    // Get all the unsubscribe functions that were returned
    const unsubscribeFunctions = [
      mockRealtimeClient.subscribeToSecurityEvents.mock.results[0].value,
      mockRealtimeClient.subscribeToSystemStatus.mock.results[0].value,
      mockRealtimeClient.subscribeToProcessingUpdates.mock.results[0].value,
      mockRealtimeClient.subscribeToHealthChecks.mock.results[0].value,
      mockRealtimeClient.onConnectionChange.mock.results[0].value
    ];
    
    unmount();
    
    // All unsubscribe functions should have been called
    unsubscribeFunctions.forEach(unsubscribe => {
      expect(unsubscribe).toHaveBeenCalled();
    });
  });
});

describe('useSecurityEvents', () => {
  const mockRealtimeClient = realtimeClient as jest.Mocked<typeof realtimeClient>;
  const { RealtimeClient } = require('../../services/realtimeClient');

  beforeEach(() => {
    jest.clearAllMocks();
    
    mockRealtimeClient.initialize.mockResolvedValue();
    mockRealtimeClient.getConnectionStatus.mockReturnValue({
      connected: false,
      connecting: false,
      error: null,
      lastConnected: null,
      reconnectAttempts: 0
    });
    mockRealtimeClient.isConnected.mockReturnValue(false);
    
    const mockUnsubscribe = jest.fn();
    mockRealtimeClient.subscribeToSecurityEvents.mockReturnValue(mockUnsubscribe);
    mockRealtimeClient.onConnectionChange.mockReturnValue(mockUnsubscribe);
    
    // Mock the conversion function
    RealtimeClient.convertToEventResponse.mockImplementation((data: any) => ({
      event: {
        id: data.event_id,
        timestamp: data.timestamp,
        source: data.source,
        message: data.message,
        category: data.category
      },
      analysis: {
        severity_score: data.severity,
        explanation: data.analysis?.explanation || '',
        recommendations: data.recommendations || data.analysis?.recommendations || []
      }
    }));
  });

  it('should initialize and set up security event subscription', async () => {
    const { result } = renderHook(() => useSecurityEvents());
    
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    
    expect(mockRealtimeClient.subscribeToSecurityEvents).toHaveBeenCalled();
    expect(result.current.events).toEqual([]);
    expect(result.current.securityEvents).toEqual([]);
    expect(result.current.optimisticEvents).toEqual([]);
  });

  it('should provide connection status and control functions', async () => {
    const { result } = renderHook(() => useSecurityEvents());
    
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    
    expect(result.current.connectionStatus).toBeDefined();
    expect(result.current.isConnected).toBe(false);
    expect(typeof result.current.connect).toBe('function');
    expect(typeof result.current.disconnect).toBe('function');
    expect(typeof result.current.addOptimisticEvent).toBe('function');
    expect(typeof result.current.removeOptimisticEvent).toBe('function');
  });
});