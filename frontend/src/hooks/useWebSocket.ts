import { useState, useEffect, useCallback, useRef } from 'react';
import websocketService, { 
  ConnectionStatus, 
  WebSocketMessage, 
  EventHandler, 
  ConnectionHandler,
  WebSocketFilter 
} from '../services/websocket';
import { EventResponse } from '../types';

export interface UseWebSocketOptions {
  autoConnect?: boolean;
  subscriptions?: string[];
  filter?: WebSocketFilter;
  onEvent?: (eventType: string, message: WebSocketMessage) => void;
}

export interface UseWebSocketReturn {
  status: ConnectionStatus;
  connect: () => Promise<void>;
  disconnect: () => void;
  subscribe: (eventTypes: string[], replaceExisting?: boolean) => void;
  unsubscribe: (eventTypes: string[]) => void;
  setFilter: (filter: WebSocketFilter) => void;
  clearFilter: () => void;
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
  events: WebSocketMessage[];
  clearEvents: () => void;
}

export const useWebSocket = (options: UseWebSocketOptions = {}): UseWebSocketReturn => {
  const {
    autoConnect = true,
    subscriptions = [],
    filter,
    onEvent
  } = options;

  const [status, setStatus] = useState<ConnectionStatus>(websocketService.getStatus());
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [events, setEvents] = useState<WebSocketMessage[]>([]);
  
  const eventHandlerRef = useRef<EventHandler | undefined>(undefined);
  const connectionHandlerRef = useRef<ConnectionHandler | undefined>(undefined);
  const onEventRef = useRef(onEvent);

  // Update onEvent ref when it changes
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  // Connection status handler
  useEffect(() => {
    const handler: ConnectionHandler = (newStatus) => {
      setStatus(newStatus);
    };

    connectionHandlerRef.current = handler;
    websocketService.onConnectionChange(handler);

    return () => {
      if (connectionHandlerRef.current) {
        websocketService.offConnectionChange(connectionHandlerRef.current);
      }
    };
  }, []);

  // Event handler
  useEffect(() => {
    const handler: EventHandler = (message) => {
      setLastMessage(message);
      setEvents(prev => [...prev.slice(-99), message]); // Keep last 100 events
      
      if (onEventRef.current) {
        onEventRef.current(message.type, message);
      }
    };

    eventHandlerRef.current = handler;
    websocketService.on('*', handler); // Listen to all events

    return () => {
      if (eventHandlerRef.current) {
        websocketService.off('*', eventHandlerRef.current);
      }
    };
  }, []);

  // Auto-connect
  useEffect(() => {
    if (autoConnect && !status.connected && !status.connecting) {
      websocketService.connect().catch(error => {
        console.error('Auto-connect failed:', error);
      });
    }
  }, [autoConnect, status.connected, status.connecting]);

  // Initial subscriptions
  useEffect(() => {
    if (subscriptions.length > 0 && status.connected) {
      websocketService.subscribe(subscriptions, true);
    }
  }, [subscriptions, status.connected]);

  // Initial filter
  useEffect(() => {
    if (filter && status.connected) {
      websocketService.setFilter(filter);
    }
  }, [filter, status.connected]);

  const connect = useCallback(async () => {
    return websocketService.connect();
  }, []);

  const disconnect = useCallback(() => {
    websocketService.disconnect();
  }, []);

  const subscribe = useCallback((eventTypes: string[], replaceExisting = false) => {
    websocketService.subscribe(eventTypes, replaceExisting);
  }, []);

  const unsubscribe = useCallback((eventTypes: string[]) => {
    websocketService.unsubscribe(eventTypes);
  }, []);

  const setFilter = useCallback((filter: WebSocketFilter) => {
    websocketService.setFilter(filter);
  }, []);

  const clearFilter = useCallback(() => {
    websocketService.clearFilter();
  }, []);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  return {
    status,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    setFilter,
    clearFilter,
    isConnected: status.connected,
    lastMessage,
    events,
    clearEvents
  };
};

// Hook for security events specifically
export const useSecurityEvents = () => {
  const [securityEvents, setSecurityEvents] = useState<EventResponse[]>([]);
  const [optimisticEvents, setOptimisticEvents] = useState<EventResponse[]>([]);

  const handleSecurityEvent = useCallback((eventType: string, message: WebSocketMessage) => {
    if (eventType === 'security_event' && message.data) {
      try {
        // Validate required fields
        if (!message.data.event_id || !message.data.timestamp || !message.data.source || 
            !message.data.message || !message.data.category || typeof message.data.severity !== 'number') {
          console.warn('Malformed security event:', message.data);
          return;
        }

        // Convert WebSocket message to EventResponse format
        const eventResponse: EventResponse = {
          event: {
            id: message.data.event_id,
            timestamp: message.data.timestamp,
            source: message.data.source,
            message: message.data.message,
            category: message.data.category
          },
          analysis: {
            severity_score: message.data.severity,
            explanation: message.data.analysis?.explanation || message.data.explanation || '',
            recommendations: message.data.recommendations || []
          }
        };

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
    }
  }, []);

  const { status, isConnected, ...websocket } = useWebSocket({
    subscriptions: ['security_event', 'processing_update'],
    onEvent: handleSecurityEvent
  });

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
    connectionStatus: status,
    isConnected,
    connect: websocket.connect,
    disconnect: websocket.disconnect,
    subscribe: websocket.subscribe,
    unsubscribe: websocket.unsubscribe
  };
};

export default useWebSocket;