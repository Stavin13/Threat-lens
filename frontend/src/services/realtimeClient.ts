import { EventResponse } from '../types';
import websocketService, { 
  WebSocketMessage, 
  ConnectionStatus, 
  EventHandler, 
  ConnectionHandler,
  WebSocketFilter 
} from './websocket';

export interface RealtimeEventData {
  event_id: string;
  severity: number;
  category: string;
  source: string;
  message: string;
  timestamp: string;
  analysis?: {
    explanation?: string;
    recommendations?: string[];
  };
  recommendations?: string[];
}

export interface SystemStatusData {
  component: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  uptime?: number;
  metrics?: Record<string, any>;
  last_error?: string;
}

export interface ProcessingUpdateData {
  raw_log_id: string;
  stage: string;
  status: string;
  progress?: number;
  events_created?: number;
  processing_time?: number;
  error_message?: string;
}

export interface HealthCheckData {
  overall_status: string;
  components: Record<string, Record<string, any>>;
  timestamp: string;
  alerts?: string[];
}

export interface RealtimeSubscription {
  eventType: string;
  callback: (data: any) => void;
}

export interface RealtimeClientOptions {
  autoConnect?: boolean;
  reconnectAttempts?: number;
  reconnectDelay?: number;
  pingInterval?: number;
}

export type RealtimeEventType = 
  | 'security_event'
  | 'system_status'
  | 'processing_update'
  | 'health_check'
  | 'user_action';

export type RealtimeEventCallback<T = any> = (data: T, message: WebSocketMessage) => void;

/**
 * Enhanced WebSocket client for real-time updates with automatic reconnection,
 * event subscription management, and connection state handling.
 */
export class RealtimeClient {
  private subscriptions: Map<string, Set<RealtimeEventCallback>> = new Map();
  private connectionHandlers: Set<ConnectionHandler> = new Set();
  private isInitialized = false;
  private options: Required<RealtimeClientOptions>;
  private eventHandler?: EventHandler;
  private connectionHandler?: ConnectionHandler;

  constructor(options: RealtimeClientOptions = {}) {
    this.options = {
      autoConnect: true,
      reconnectAttempts: 10,
      reconnectDelay: 5000,
      pingInterval: 30000,
      ...options
    };
  }

  /**
   * Initialize the realtime client and set up event handlers
   */
  async initialize(): Promise<void> {
    if (this.isInitialized) {
      return;
    }

    // Set up event handler for all WebSocket messages
    this.eventHandler = (message: WebSocketMessage) => {
      this.handleRealtimeEvent(message);
    };

    // Set up connection status handler
    this.connectionHandler = (status: ConnectionStatus) => {
      this.notifyConnectionHandlers(status);
    };

    // Register handlers with WebSocket service
    websocketService.on('*', this.eventHandler);
    websocketService.onConnectionChange(this.connectionHandler);

    this.isInitialized = true;

    // Auto-connect if enabled
    if (this.options.autoConnect) {
      await this.connect();
    }
  }

  /**
   * Connect to the WebSocket server
   */
  async connect(): Promise<void> {
    if (!this.isInitialized) {
      await this.initialize();
    }

    return websocketService.connect();
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect(): void {
    websocketService.disconnect();
  }

  /**
   * Subscribe to a specific event type with a callback
   */
  subscribe<T = any>(eventType: RealtimeEventType, callback: RealtimeEventCallback<T>): () => void {
    const isFirstSubscription = !this.subscriptions.has(eventType) || this.subscriptions.get(eventType)!.size === 0;
    
    if (!this.subscriptions.has(eventType)) {
      this.subscriptions.set(eventType, new Set());
    }

    this.subscriptions.get(eventType)!.add(callback as RealtimeEventCallback);

    // Subscribe to the event type on the WebSocket service only if this is the first subscription
    if (isFirstSubscription && this.isConnected()) {
      websocketService.subscribe([eventType]);
    }

    // Return unsubscribe function
    return () => {
      this.unsubscribe(eventType, callback);
    };
  }

  /**
   * Unsubscribe from a specific event type
   */
  unsubscribe<T = any>(eventType: RealtimeEventType, callback: RealtimeEventCallback<T>): void {
    const callbacks = this.subscriptions.get(eventType);
    if (callbacks) {
      callbacks.delete(callback as RealtimeEventCallback);
      
      // If no more callbacks for this event type, unsubscribe from WebSocket
      if (callbacks.size === 0) {
        this.subscriptions.delete(eventType);
        if (this.isConnected()) {
          websocketService.unsubscribe([eventType]);
        }
      }
    }
  }

  /**
   * Subscribe to security events specifically
   */
  subscribeToSecurityEvents(callback: RealtimeEventCallback<RealtimeEventData>): () => void {
    return this.subscribe('security_event', callback);
  }

  /**
   * Subscribe to system status updates
   */
  subscribeToSystemStatus(callback: RealtimeEventCallback<SystemStatusData>): () => void {
    return this.subscribe('system_status', callback);
  }

  /**
   * Subscribe to processing updates
   */
  subscribeToProcessingUpdates(callback: RealtimeEventCallback<ProcessingUpdateData>): () => void {
    return this.subscribe('processing_update', callback);
  }

  /**
   * Subscribe to health check updates
   */
  subscribeToHealthChecks(callback: RealtimeEventCallback<HealthCheckData>): () => void {
    return this.subscribe('health_check', callback);
  }

  /**
   * Set event filter for the WebSocket connection
   */
  setFilter(filter: WebSocketFilter): void {
    websocketService.setFilter(filter);
  }

  /**
   * Clear event filter
   */
  clearFilter(): void {
    websocketService.clearFilter();
  }

  /**
   * Add connection status change handler
   */
  onConnectionChange(handler: ConnectionHandler): () => void {
    this.connectionHandlers.add(handler);

    // Return cleanup function
    return () => {
      this.connectionHandlers.delete(handler);
    };
  }

  /**
   * Get current connection status
   */
  getConnectionStatus(): ConnectionStatus {
    return websocketService.getStatus();
  }

  /**
   * Check if currently connected
   */
  isConnected(): boolean {
    return websocketService.isConnected();
  }

  /**
   * Send ping to server
   */
  ping(): void {
    websocketService.ping();
  }

  /**
   * Request server status
   */
  requestServerStatus(): void {
    websocketService.getServerStatus();
  }

  /**
   * Get list of active subscriptions
   */
  getActiveSubscriptions(): string[] {
    return Array.from(this.subscriptions.keys());
  }

  /**
   * Clean up resources and disconnect
   */
  destroy(): void {
    // Remove all subscriptions
    this.subscriptions.clear();
    this.connectionHandlers.clear();

    // Remove handlers from WebSocket service
    if (this.eventHandler) {
      websocketService.off('*', this.eventHandler);
    }
    if (this.connectionHandler) {
      websocketService.offConnectionChange(this.connectionHandler);
    }

    // Disconnect
    this.disconnect();
    this.isInitialized = false;
  }

  /**
   * Handle incoming realtime events and route to subscribers
   */
  private handleRealtimeEvent(message: WebSocketMessage): void {
    const { type, data } = message;
    const callbacks = this.subscriptions.get(type);

    if (callbacks && callbacks.size > 0) {
      callbacks.forEach(callback => {
        try {
          callback(data, message);
        } catch (error) {
          console.error(`Error in realtime event callback for ${type}:`, error);
        }
      });
    }
  }

  /**
   * Notify connection status handlers
   */
  private notifyConnectionHandlers(status: ConnectionStatus): void {
    this.connectionHandlers.forEach(handler => {
      try {
        handler(status);
      } catch (error) {
        console.error('Error in connection status handler:', error);
      }
    });
  }

  /**
   * Convert realtime event data to EventResponse format
   */
  static convertToEventResponse(eventData: RealtimeEventData): EventResponse {
    return {
      event: {
        id: eventData.event_id,
        timestamp: eventData.timestamp,
        source: eventData.source,
        message: eventData.message,
        category: eventData.category
      },
      analysis: {
        severity_score: eventData.severity,
        explanation: eventData.analysis?.explanation || '',
        recommendations: eventData.recommendations || eventData.analysis?.recommendations || []
      }
    };
  }
}

// Create singleton instance
const realtimeClient = new RealtimeClient();

export default realtimeClient;