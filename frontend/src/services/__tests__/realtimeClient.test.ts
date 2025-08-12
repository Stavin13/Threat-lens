import { RealtimeClient } from '../realtimeClient';
import websocketService from '../websocket';

// Mock the websocket service
jest.mock('../websocket', () => ({
  __esModule: true,
  default: {
    connect: jest.fn(),
    disconnect: jest.fn(),
    on: jest.fn(),
    off: jest.fn(),
    onConnectionChange: jest.fn(),
    offConnectionChange: jest.fn(),
    subscribe: jest.fn(),
    unsubscribe: jest.fn(),
    setFilter: jest.fn(),
    clearFilter: jest.fn(),
    isConnected: jest.fn(),
    getStatus: jest.fn(),
    ping: jest.fn(),
    getServerStatus: jest.fn()
  }
}));

describe('RealtimeClient', () => {
  let client: RealtimeClient;
  const mockWebsocketService = websocketService as jest.Mocked<typeof websocketService>;

  beforeEach(() => {
    jest.clearAllMocks();
    client = new RealtimeClient({ autoConnect: false });
    
    // Mock default connection status
    mockWebsocketService.getStatus.mockReturnValue({
      connected: false,
      connecting: false,
      error: null,
      lastConnected: null,
      reconnectAttempts: 0
    });
  });

  afterEach(() => {
    client.destroy();
  });

  describe('initialization', () => {
    it('should initialize without auto-connecting', async () => {
      await client.initialize();
      
      expect(mockWebsocketService.on).toHaveBeenCalledWith('*', expect.any(Function));
      expect(mockWebsocketService.onConnectionChange).toHaveBeenCalledWith(expect.any(Function));
      expect(mockWebsocketService.connect).not.toHaveBeenCalled();
    });

    it('should auto-connect when enabled', async () => {
      const autoConnectClient = new RealtimeClient({ autoConnect: true });
      mockWebsocketService.connect.mockResolvedValue();
      
      await autoConnectClient.initialize();
      
      expect(mockWebsocketService.connect).toHaveBeenCalled();
      
      autoConnectClient.destroy();
    });

    it('should not initialize twice', async () => {
      await client.initialize();
      await client.initialize();
      
      expect(mockWebsocketService.on).toHaveBeenCalledTimes(1);
    });
  });

  describe('connection management', () => {
    beforeEach(async () => {
      await client.initialize();
    });

    it('should connect to websocket service', async () => {
      mockWebsocketService.connect.mockResolvedValue();
      
      await client.connect();
      
      expect(mockWebsocketService.connect).toHaveBeenCalled();
    });

    it('should disconnect from websocket service', () => {
      client.disconnect();
      
      expect(mockWebsocketService.disconnect).toHaveBeenCalled();
    });

    it('should return connection status', () => {
      const mockStatus = {
        connected: true,
        connecting: false,
        error: null,
        lastConnected: new Date(),
        reconnectAttempts: 0
      };
      mockWebsocketService.getStatus.mockReturnValue(mockStatus);
      
      const status = client.getConnectionStatus();
      
      expect(status).toEqual(mockStatus);
    });

    it('should check if connected', () => {
      mockWebsocketService.isConnected.mockReturnValue(true);
      
      const isConnected = client.isConnected();
      
      expect(isConnected).toBe(true);
      expect(mockWebsocketService.isConnected).toHaveBeenCalled();
    });
  });

  describe('event subscription', () => {
    beforeEach(async () => {
      await client.initialize();
      mockWebsocketService.isConnected.mockReturnValue(true);
    });

    it('should subscribe to security events', () => {
      const callback = jest.fn();
      
      const unsubscribe = client.subscribeToSecurityEvents(callback);
      
      expect(mockWebsocketService.subscribe).toHaveBeenCalledWith(['security_event']);
      expect(typeof unsubscribe).toBe('function');
    });

    it('should subscribe to system status events', () => {
      const callback = jest.fn();
      
      client.subscribeToSystemStatus(callback);
      
      expect(mockWebsocketService.subscribe).toHaveBeenCalledWith(['system_status']);
    });

    it('should subscribe to processing updates', () => {
      const callback = jest.fn();
      
      client.subscribeToProcessingUpdates(callback);
      
      expect(mockWebsocketService.subscribe).toHaveBeenCalledWith(['processing_update']);
    });

    it('should subscribe to health checks', () => {
      const callback = jest.fn();
      
      client.subscribeToHealthChecks(callback);
      
      expect(mockWebsocketService.subscribe).toHaveBeenCalledWith(['health_check']);
    });

    it('should unsubscribe from events', () => {
      const callback = jest.fn();
      
      const unsubscribe = client.subscribe('security_event', callback);
      unsubscribe();
      
      expect(mockWebsocketService.unsubscribe).toHaveBeenCalledWith(['security_event']);
    });

    it('should handle multiple callbacks for same event type', () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();
      
      client.subscribe('security_event', callback1);
      client.subscribe('security_event', callback2);
      
      // Should only subscribe once to websocket service
      expect(mockWebsocketService.subscribe).toHaveBeenCalledTimes(1);
    });

    it('should get active subscriptions', () => {
      client.subscribe('security_event', jest.fn());
      client.subscribe('system_status', jest.fn());
      
      const subscriptions = client.getActiveSubscriptions();
      
      expect(subscriptions).toContain('security_event');
      expect(subscriptions).toContain('system_status');
    });
  });

  describe('event handling', () => {
    let eventHandler: (message: any) => void;

    beforeEach(async () => {
      await client.initialize();
      
      // Capture the event handler passed to websocket service
      const onCall = mockWebsocketService.on.mock.calls.find(call => call[0] === '*');
      eventHandler = onCall?.[1];
    });

    it('should route security events to subscribers', () => {
      const callback = jest.fn();
      client.subscribeToSecurityEvents(callback);
      
      const eventData = {
        event_id: 'test-123',
        severity: 8,
        category: 'authentication',
        source: 'auth.log',
        message: 'Failed login attempt',
        timestamp: '2023-01-01T00:00:00Z'
      };

      const message = {
        type: 'security_event',
        data: eventData,
        timestamp: '2023-01-01T00:00:00Z',
        priority: 8
      };

      eventHandler(message);
      
      expect(callback).toHaveBeenCalledWith(eventData, message);
    });

    it('should handle multiple subscribers for same event', () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();
      
      client.subscribe('security_event', callback1);
      client.subscribe('security_event', callback2);
      
      const message = {
        type: 'security_event',
        data: { test: 'data' },
        timestamp: '2023-01-01T00:00:00Z',
        priority: 5
      };

      eventHandler(message);
      
      expect(callback1).toHaveBeenCalledWith({ test: 'data' }, message);
      expect(callback2).toHaveBeenCalledWith({ test: 'data' }, message);
    });

    it('should handle callback errors gracefully', () => {
      const errorCallback = jest.fn().mockImplementation(() => {
        throw new Error('Callback error');
      });
      const goodCallback = jest.fn();
      
      client.subscribe('security_event', errorCallback);
      client.subscribe('security_event', goodCallback);
      
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      const message = {
        type: 'security_event',
        data: { test: 'data' },
        timestamp: '2023-01-01T00:00:00Z',
        priority: 5
      };

      eventHandler(message);
      
      expect(errorCallback).toHaveBeenCalled();
      expect(goodCallback).toHaveBeenCalled();
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Error in realtime event callback'),
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('filtering', () => {
    beforeEach(async () => {
      await client.initialize();
    });

    it('should set event filter', () => {
      const filter = {
        event_types: ['security_event'],
        min_priority: 5
      };
      
      client.setFilter(filter);
      
      expect(mockWebsocketService.setFilter).toHaveBeenCalledWith(filter);
    });

    it('should clear event filter', () => {
      client.clearFilter();
      
      expect(mockWebsocketService.clearFilter).toHaveBeenCalled();
    });
  });

  describe('utility functions', () => {
    beforeEach(async () => {
      await client.initialize();
    });

    it('should send ping', () => {
      client.ping();
      
      expect(mockWebsocketService.ping).toHaveBeenCalled();
    });

    it('should request server status', () => {
      client.requestServerStatus();
      
      expect(mockWebsocketService.getServerStatus).toHaveBeenCalled();
    });
  });

  describe('cleanup', () => {
    it('should clean up resources on destroy', async () => {
      await client.initialize();
      
      client.destroy();
      
      expect(mockWebsocketService.off).toHaveBeenCalledWith('*', expect.any(Function));
      expect(mockWebsocketService.offConnectionChange).toHaveBeenCalledWith(expect.any(Function));
      expect(mockWebsocketService.disconnect).toHaveBeenCalled();
    });
  });

  describe('data conversion', () => {
    it('should convert realtime event data to EventResponse format', () => {
      const realtimeData = {
        event_id: 'test-123',
        severity: 8,
        category: 'authentication',
        source: 'auth.log',
        message: 'Failed login attempt',
        timestamp: '2023-01-01T00:00:00Z',
        analysis: {
          explanation: 'Multiple failed attempts detected',
          recommendations: ['Enable account lockout', 'Review access logs']
        }
      };

      const eventResponse = RealtimeClient.convertToEventResponse(realtimeData);

      expect(eventResponse).toEqual({
        event: {
          id: 'test-123',
          timestamp: '2023-01-01T00:00:00Z',
          source: 'auth.log',
          message: 'Failed login attempt',
          category: 'authentication'
        },
        analysis: {
          severity_score: 8,
          explanation: 'Multiple failed attempts detected',
          recommendations: ['Enable account lockout', 'Review access logs']
        }
      });
    });

    it('should handle missing analysis data', () => {
      const realtimeData = {
        event_id: 'test-123',
        severity: 5,
        category: 'system',
        source: 'system.log',
        message: 'System event',
        timestamp: '2023-01-01T00:00:00Z'
      };

      const eventResponse = RealtimeClient.convertToEventResponse(realtimeData);

      expect(eventResponse.analysis).toEqual({
        severity_score: 5,
        explanation: '',
        recommendations: []
      });
    });
  });
});