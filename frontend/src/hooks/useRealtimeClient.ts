import { useState, useEffect, useCallback, useRef } from 'react';
import realtimeClient, { 
  RealtimeClient, 
  RealtimeEventType, 
  RealtimeEventCallback,
  RealtimeEventData,
  SystemStatusData,
  ProcessingUpdateData,
  HealthCheckData
} from '../services/realtimeClient';
import { ConnectionStatus } from '../services/websocket';
import { EventResponse } from '../types';

export interface UseRealtimeClientOptions {
  autoConnect?: boolean;
  subscriptions?: RealtimeEventType[];
  onSecurityEvent?: (data: RealtimeEventData) => void;
  onSystemStatus?: (data: SystemStatusData) => void;
  onProcessingUpdate?: (data: ProcessingUpdateData) => void;
  onHealthCheck?: (data: HealthCheckData) => void;
}

export interface UseRealtimeClientReturn {
  // Connection state
  connectionStatus: ConnectionStatus;
  isConnected: boolean;
  isConnecting: boolean;
  
  // Connection control
  connect: () => Promise<void>;
  disconnect: () => void;
  
  // Event subscription
  subscribe: <T = any>(eventType: RealtimeEventType, callback: RealtimeEventCallback<T>) => () => void;
  unsubscribe: <T = any>(eventType: RealtimeEventType, callback: RealtimeEventCallback<T>) => void;
  
  // Specialized subscriptions
  subscribeToSecurityEvents: (callback: RealtimeEventCallback<RealtimeEventData>) => () => void;
  subscribeToSystemStatus: (callback: RealtimeEventCallback<SystemStatusData>) => () => void;
  subscribeToProcessingUpdates: (callback: RealtimeEventCallback<ProcessingUpdateData>) => () => void;
  subscribeToHealthChecks: (callback: RealtimeEventCallback<HealthCheckData>) => () => void;
  
  // Utility functions
  ping: () => void;
  requestServerStatus: () => void;
  getActiveSubscriptions: () => string[];
  
  // Event data
  lastSecurityEvent: RealtimeEventData | null;
  lastSystemStatus: SystemStatusData | null;
  lastProcessingUpdate: ProcessingUpdateData | null;
  lastHealthCheck: HealthCheckData | null;
  
  // Event collections
  recentSecurityEvents: RealtimeEventData[];
  clearRecentEvents: () => void;
}

/**
 * React hook for using the RealtimeClient with automatic lifecycle management
 */
export const useRealtimeClient = (options: UseRealtimeClientOptions = {}): UseRealtimeClientReturn => {
  const {
    autoConnect = true,
    subscriptions = [],
    onSecurityEvent,
    onSystemStatus,
    onProcessingUpdate,
    onHealthCheck
  } = options;

  // State
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>(
    realtimeClient.getConnectionStatus()
  );
  const [lastSecurityEvent, setLastSecurityEvent] = useState<RealtimeEventData | null>(null);
  const [lastSystemStatus, setLastSystemStatus] = useState<SystemStatusData | null>(null);
  const [lastProcessingUpdate, setLastProcessingUpdate] = useState<ProcessingUpdateData | null>(null);
  const [lastHealthCheck, setLastHealthCheck] = useState<HealthCheckData | null>(null);
  const [recentSecurityEvents, setRecentSecurityEvents] = useState<RealtimeEventData[]>([]);

  // Refs for stable callbacks
  const callbackRefs = useRef({
    onSecurityEvent,
    onSystemStatus,
    onProcessingUpdate,
    onHealthCheck
  });

  // Update callback refs when they change
  useEffect(() => {
    callbackRefs.current = {
      onSecurityEvent,
      onSystemStatus,
      onProcessingUpdate,
      onHealthCheck
    };
  }, [onSecurityEvent, onSystemStatus, onProcessingUpdate, onHealthCheck]);

  // Initialize client and set up connection status monitoring
  useEffect(() => {
    let mounted = true;

    const initializeClient = async () => {
      try {
        await realtimeClient.initialize();
        
        if (mounted) {
          // Set up connection status monitoring
          const unsubscribeConnection = realtimeClient.onConnectionChange((status) => {
            if (mounted) {
              setConnectionStatus(status);
            }
          });

          // Clean up on unmount
          return () => {
            unsubscribeConnection();
          };
        }
      } catch (error) {
        console.error('Failed to initialize realtime client:', error);
      }
    };

    const cleanup = initializeClient();

    return () => {
      mounted = false;
      cleanup?.then(cleanupFn => cleanupFn?.());
    };
  }, []);

  // Set up event handlers
  useEffect(() => {
    const unsubscribeFunctions: (() => void)[] = [];

    // Security events handler
    const securityEventHandler = (data: RealtimeEventData) => {
      setLastSecurityEvent(data);
      setRecentSecurityEvents(prev => {
        const updated = [data, ...prev.slice(0, 99)]; // Keep last 100 events
        return updated;
      });
      
      if (callbackRefs.current.onSecurityEvent) {
        callbackRefs.current.onSecurityEvent(data);
      }
    };

    // System status handler
    const systemStatusHandler = (data: SystemStatusData) => {
      setLastSystemStatus(data);
      
      if (callbackRefs.current.onSystemStatus) {
        callbackRefs.current.onSystemStatus(data);
      }
    };

    // Processing update handler
    const processingUpdateHandler = (data: ProcessingUpdateData) => {
      setLastProcessingUpdate(data);
      
      if (callbackRefs.current.onProcessingUpdate) {
        callbackRefs.current.onProcessingUpdate(data);
      }
    };

    // Health check handler
    const healthCheckHandler = (data: HealthCheckData) => {
      setLastHealthCheck(data);
      
      if (callbackRefs.current.onHealthCheck) {
        callbackRefs.current.onHealthCheck(data);
      }
    };

    // Subscribe to events
    unsubscribeFunctions.push(
      realtimeClient.subscribeToSecurityEvents(securityEventHandler),
      realtimeClient.subscribeToSystemStatus(systemStatusHandler),
      realtimeClient.subscribeToProcessingUpdates(processingUpdateHandler),
      realtimeClient.subscribeToHealthChecks(healthCheckHandler)
    );

    // Subscribe to additional event types if specified
    subscriptions.forEach(eventType => {
      if (!['security_event', 'system_status', 'processing_update', 'health_check'].includes(eventType)) {
        unsubscribeFunctions.push(
          realtimeClient.subscribe(eventType, (data) => {
            console.log(`Received ${eventType} event:`, data);
          })
        );
      }
    });

    // Cleanup subscriptions on unmount
    return () => {
      unsubscribeFunctions.forEach(unsubscribe => {
        if (typeof unsubscribe === 'function') {
          unsubscribe();
        }
      });
    };
  }, [subscriptions]);

  // Connection control functions
  const connect = useCallback(async () => {
    try {
      await realtimeClient.connect();
    } catch (error) {
      console.error('Failed to connect to realtime server:', error);
      throw error;
    }
  }, []);

  const disconnect = useCallback(() => {
    realtimeClient.disconnect();
  }, []);

  // Event subscription functions
  const subscribe = useCallback(<T = any>(
    eventType: RealtimeEventType, 
    callback: RealtimeEventCallback<T>
  ) => {
    return realtimeClient.subscribe(eventType, callback);
  }, []);

  const unsubscribe = useCallback(<T = any>(
    eventType: RealtimeEventType, 
    callback: RealtimeEventCallback<T>
  ) => {
    realtimeClient.unsubscribe(eventType, callback);
  }, []);

  // Specialized subscription functions
  const subscribeToSecurityEvents = useCallback((callback: RealtimeEventCallback<RealtimeEventData>) => {
    return realtimeClient.subscribeToSecurityEvents(callback);
  }, []);

  const subscribeToSystemStatus = useCallback((callback: RealtimeEventCallback<SystemStatusData>) => {
    return realtimeClient.subscribeToSystemStatus(callback);
  }, []);

  const subscribeToProcessingUpdates = useCallback((callback: RealtimeEventCallback<ProcessingUpdateData>) => {
    return realtimeClient.subscribeToProcessingUpdates(callback);
  }, []);

  const subscribeToHealthChecks = useCallback((callback: RealtimeEventCallback<HealthCheckData>) => {
    return realtimeClient.subscribeToHealthChecks(callback);
  }, []);

  // Utility functions
  const ping = useCallback(() => {
    realtimeClient.ping();
  }, []);

  const requestServerStatus = useCallback(() => {
    realtimeClient.requestServerStatus();
  }, []);

  const getActiveSubscriptions = useCallback(() => {
    return realtimeClient.getActiveSubscriptions();
  }, []);

  const clearRecentEvents = useCallback(() => {
    setRecentSecurityEvents([]);
  }, []);

  // Derived state
  const isConnected = connectionStatus.connected;
  const isConnecting = connectionStatus.connecting;

  return {
    // Connection state
    connectionStatus,
    isConnected,
    isConnecting,
    
    // Connection control
    connect,
    disconnect,
    
    // Event subscription
    subscribe,
    unsubscribe,
    
    // Specialized subscriptions
    subscribeToSecurityEvents,
    subscribeToSystemStatus,
    subscribeToProcessingUpdates,
    subscribeToHealthChecks,
    
    // Utility functions
    ping,
    requestServerStatus,
    getActiveSubscriptions,
    
    // Event data
    lastSecurityEvent,
    lastSystemStatus,
    lastProcessingUpdate,
    lastHealthCheck,
    
    // Event collections
    recentSecurityEvents,
    clearRecentEvents
  };
};

/**
 * Hook specifically for security events with EventResponse conversion
 */
export const useSecurityEvents = () => {
  const [securityEvents, setSecurityEvents] = useState<EventResponse[]>([]);
  const [optimisticEvents, setOptimisticEvents] = useState<EventResponse[]>([]);

  const { 
    connectionStatus, 
    isConnected, 
    connect, 
    disconnect,
    subscribeToSecurityEvents 
  } = useRealtimeClient();

  // Handle security events and convert to EventResponse format
  useEffect(() => {
    const unsubscribe = subscribeToSecurityEvents((data: RealtimeEventData) => {
      try {
        const eventResponse = RealtimeClient.convertToEventResponse(data);
        
        setSecurityEvents(prev => {
          // Check if event already exists (avoid duplicates)
          const exists = prev.some(e => e.event.id === eventResponse.event.id);
          if (exists) {
            return prev;
          }
          
          // Add new event and keep sorted by timestamp (newest first)
          const updated = [eventResponse, ...prev];
          return updated.slice(0, 1000); // Keep last 1000 events
        });

        // Remove from optimistic events if it exists
        setOptimisticEvents(prev => 
          prev.filter(e => e.event.id !== eventResponse.event.id)
        );

      } catch (error) {
        console.error('Error processing security event:', error);
      }
    });

    return unsubscribe;
  }, [subscribeToSecurityEvents]);

  const addOptimisticEvent = useCallback((event: EventResponse) => {
    setOptimisticEvents(prev => [event, ...prev]);
  }, []);

  const removeOptimisticEvent = useCallback((eventId: string) => {
    setOptimisticEvents(prev => prev.filter(e => e.event.id !== eventId));
  }, []);

  // Combine real and optimistic events
  const allEvents = [...optimisticEvents, ...securityEvents];

  return {
    events: allEvents,
    securityEvents,
    optimisticEvents,
    addOptimisticEvent,
    removeOptimisticEvent,
    connectionStatus,
    isConnected,
    connect,
    disconnect
  };
};

export default useRealtimeClient;