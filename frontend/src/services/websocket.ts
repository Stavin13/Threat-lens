import { EventResponse } from '../types';

export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: string;
  priority?: number;
}

export interface ConnectionStatus {
  connected: boolean;
  connecting: boolean;
  error: string | null;
  lastConnected: Date | null;
  reconnectAttempts: number;
}

export interface WebSocketSubscription {
  event_types: string[];
  replace_existing?: boolean;
}

export interface WebSocketFilter {
  event_types?: string[];
  categories?: string[];
  min_priority?: number;
  max_priority?: number;
  sources?: string[];
}

export type EventHandler = (event: WebSocketMessage) => void;
export type ConnectionHandler = (status: ConnectionStatus) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectInterval: number = 5000; // 5 seconds
  private maxReconnectAttempts: number = 10;
  private reconnectAttempts: number = 0;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private pingTimer: NodeJS.Timeout | null = null;
  private pingInterval: number = 30000; // 30 seconds
  
  private eventHandlers: Map<string, EventHandler[]> = new Map();
  private connectionHandlers: ConnectionHandler[] = [];
  
  private status: ConnectionStatus = {
    connected: false,
    connecting: false,
    error: null,
    lastConnected: null,
    reconnectAttempts: 0
  };

  private subscriptions: Set<string> = new Set();
  private currentFilter: WebSocketFilter | null = null;

  constructor(baseUrl?: string) {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = baseUrl || window.location.host;
    this.url = `${wsProtocol}//${wsHost}/ws`;
  }

  /**
   * Connect to WebSocket server
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      this.updateStatus({ connecting: true, error: null });

      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          this.updateStatus({
            connected: true,
            connecting: false,
            error: null,
            lastConnected: new Date(),
            reconnectAttempts: 0
          });

          // Start ping timer
          this.startPingTimer();

          // Restore subscriptions and filters
          this.restoreSubscriptions();

          resolve();
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event.data);
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket disconnected:', event.code, event.reason);
          this.updateStatus({
            connected: false,
            connecting: false,
            error: event.reason || 'Connection closed'
          });

          this.stopPingTimer();

          // Attempt reconnection if not a clean close
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect();
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.updateStatus({
            connected: false,
            connecting: false,
            error: 'Connection error'
          });
          reject(new Error('WebSocket connection failed'));
        };

      } catch (error) {
        this.updateStatus({
          connected: false,
          connecting: false,
          error: 'Failed to create WebSocket connection'
        });
        reject(error);
      }
    });
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.stopPingTimer();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.updateStatus({
      connected: false,
      connecting: false,
      error: null,
      reconnectAttempts: 0
    });
  }

  /**
   * Subscribe to event types
   */
  subscribe(eventTypes: string[], replaceExisting: boolean = false): void {
    if (replaceExisting) {
      this.subscriptions.clear();
    }
    
    eventTypes.forEach(type => this.subscriptions.add(type));

    if (this.isConnected()) {
      this.sendMessage({
        type: 'subscribe',
        data: {
          event_types: eventTypes,
          replace_existing: replaceExisting
        }
      });
    }
  }

  /**
   * Unsubscribe from event types
   */
  unsubscribe(eventTypes: string[]): void {
    eventTypes.forEach(type => this.subscriptions.delete(type));

    if (this.isConnected()) {
      this.sendMessage({
        type: 'unsubscribe',
        data: {
          event_types: eventTypes
        }
      });
    }
  }

  /**
   * Set event filter
   */
  setFilter(filter: WebSocketFilter): void {
    this.currentFilter = filter;

    if (this.isConnected()) {
      this.sendMessage({
        type: 'set_filter',
        data: filter
      });
    }
  }

  /**
   * Clear event filter
   */
  clearFilter(): void {
    this.currentFilter = null;

    if (this.isConnected()) {
      this.sendMessage({
        type: 'clear_filter',
        data: {}
      });
    }
  }

  /**
   * Add event handler
   */
  on(eventType: string, handler: EventHandler): void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, []);
    }
    this.eventHandlers.get(eventType)!.push(handler);
  }

  /**
   * Remove event handler
   */
  off(eventType: string, handler: EventHandler): void {
    const handlers = this.eventHandlers.get(eventType);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  }

  /**
   * Add connection status handler
   */
  onConnectionChange(handler: ConnectionHandler): void {
    this.connectionHandlers.push(handler);
  }

  /**
   * Remove connection status handler
   */
  offConnectionChange(handler: ConnectionHandler): void {
    const index = this.connectionHandlers.indexOf(handler);
    if (index > -1) {
      this.connectionHandlers.splice(index, 1);
    }
  }

  /**
   * Get current connection status
   */
  getStatus(): ConnectionStatus {
    return { ...this.status };
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Send ping to server
   */
  ping(): void {
    if (this.isConnected()) {
      this.sendMessage({
        type: 'ping',
        data: {
          timestamp: new Date().toISOString()
        }
      });
    }
  }

  /**
   * Get server status
   */
  getServerStatus(): void {
    if (this.isConnected()) {
      this.sendMessage({
        type: 'get_status',
        data: {}
      });
    }
  }

  private sendMessage(message: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  private handleMessage(data: string): void {
    try {
      const message: WebSocketMessage = JSON.parse(data);
      
      // Handle system messages
      switch (message.type) {
        case 'connection_established':
          console.log('WebSocket connection established:', message.data);
          break;
        case 'pong':
          // Handle ping response
          break;
        case 'error':
          console.error('WebSocket server error:', message.data);
          this.updateStatus({
            ...this.status,
            error: message.data.error || 'Server error'
          });
          break;
        case 'subscription_updated':
          console.log('Subscription updated:', message.data);
          break;
        case 'filter_updated':
          console.log('Filter updated:', message.data);
          break;
        default:
          // Handle custom event types
          this.notifyEventHandlers(message.type, message);
          break;
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  private notifyEventHandlers(eventType: string, message: WebSocketMessage): void {
    const handlers = this.eventHandlers.get(eventType);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(message);
        } catch (error) {
          console.error('Error in event handler:', error);
        }
      });
    }

    // Also notify wildcard handlers
    const wildcardHandlers = this.eventHandlers.get('*');
    if (wildcardHandlers) {
      wildcardHandlers.forEach(handler => {
        try {
          handler(message);
        } catch (error) {
          console.error('Error in wildcard event handler:', error);
        }
      });
    }
  }

  private updateStatus(updates: Partial<ConnectionStatus>): void {
    this.status = { ...this.status, ...updates };
    this.connectionHandlers.forEach(handler => {
      try {
        handler(this.status);
      } catch (error) {
        console.error('Error in connection handler:', error);
      }
    });
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1), 30000);

    console.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);

    this.reconnectTimer = setTimeout(() => {
      console.log(`Reconnect attempt ${this.reconnectAttempts}`);
      this.updateStatus({ reconnectAttempts: this.reconnectAttempts });
      this.connect().catch(error => {
        console.error('Reconnect failed:', error);
      });
    }, delay);
  }

  private startPingTimer(): void {
    this.stopPingTimer();
    this.pingTimer = setInterval(() => {
      this.ping();
    }, this.pingInterval);
  }

  private stopPingTimer(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private restoreSubscriptions(): void {
    if (this.subscriptions.size > 0) {
      this.subscribe(Array.from(this.subscriptions), true);
    }

    if (this.currentFilter) {
      this.setFilter(this.currentFilter);
    }
  }
}

// Create singleton instance
const websocketService = new WebSocketService();

export default websocketService;