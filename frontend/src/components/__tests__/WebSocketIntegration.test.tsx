import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Dashboard from '../Dashboard';
import Events from '../Events';
import websocketService from '../../services/websocket';
import { api } from '../../services/api';

// Mock the API
jest.mock('../../services/api');
const mockApi = api as jest.Mocked<typeof api>;

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
    // Mock send - could be used to verify messages sent to server
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
}

// Replace global WebSocket with mock
(global as any).WebSocket = MockWebSocket;

describe('WebSocket Integration Tests', () => {
  let mockWebSocket: MockWebSocket;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock API responses
    mockApi.get.mockImplementation((url) => {
      if (url === '/api/health/') {
        return Promise.resolve({
          data: {
            overall_status: 'healthy',
            timestamp: new Date().toISOString(),
            uptime_seconds: 3600,
            monitoring_active: true,
            component_health: {},
            component_metrics: {}
          }
        });
      }
      return Promise.resolve({ data: {} });
    });

    mockApi.getEvents.mockResolvedValue([]);

    // Intercept WebSocket creation
    const originalWebSocket = (global as any).WebSocket;
    (global as any).WebSocket = jest.fn().mockImplementation((url: string) => {
      mockWebSocket = new MockWebSocket(url);
      return mockWebSocket;
    });
  });

  afterEach(() => {
    // Clean up WebSocket connections
    websocketService.disconnect();
  });

  describe('Dashboard Real-time Updates', () => {
    test('should show connection status indicator', async () => {
      render(<Dashboard />);

      // Initially should show connecting or connected status
      await waitFor(() => {
        expect(screen.getByText(/connected|connecting/i)).toBeInTheDocument();
      });
    });

    test('should display real-time security events', async () => {
      render(<Dashboard />);

      // Wait for WebSocket connection
      await waitFor(() => {
        expect(mockWebSocket.readyState).toBe(MockWebSocket.OPEN);
      });

      // Simulate receiving a security event
      act(() => {
        mockWebSocket.simulateMessage({
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
          timestamp: new Date().toISOString(),
          priority: 8
        });
      });

      // Should display the event in the dashboard
      await waitFor(() => {
        expect(screen.getByText('Test security event')).toBeInTheDocument();
        expect(screen.getByText('Severity 8')).toBeInTheDocument();
      });
    });

    test('should show disconnection warning when WebSocket fails', async () => {
      render(<Dashboard />);

      // Wait for initial connection
      await waitFor(() => {
        expect(mockWebSocket.readyState).toBe(MockWebSocket.OPEN);
      });

      // Simulate connection loss
      act(() => {
        mockWebSocket.close(1006, 'Connection lost');
      });

      // Should show disconnection warning
      await waitFor(() => {
        expect(screen.getByText(/real-time updates unavailable/i)).toBeInTheDocument();
      });
    });

    test('should allow manual reconnection', async () => {
      render(<Dashboard />);

      // Wait for initial connection
      await waitFor(() => {
        expect(mockWebSocket.readyState).toBe(MockWebSocket.OPEN);
      });

      // Simulate connection loss
      act(() => {
        mockWebSocket.close(1006, 'Connection lost');
      });

      // Should show reconnect button
      await waitFor(() => {
        expect(screen.getByText('Reconnect')).toBeInTheDocument();
      });

      // Click reconnect button
      const user = userEvent.setup();
      await user.click(screen.getByText('Reconnect'));

      // Should attempt to reconnect
      await waitFor(() => {
        expect((global as any).WebSocket).toHaveBeenCalledTimes(2);
      });
    });

    test('should update last update timestamp when events arrive', async () => {
      render(<Dashboard />);

      // Wait for WebSocket connection
      await waitFor(() => {
        expect(mockWebSocket.readyState).toBe(MockWebSocket.OPEN);
      });

      const initialTime = screen.getByText(/last updated:/i).textContent;

      // Wait a moment and simulate an event
      await new Promise(resolve => setTimeout(resolve, 100));

      act(() => {
        mockWebSocket.simulateMessage({
          type: 'security_event',
          data: {
            event_id: 'test-event-2',
            severity: 5,
            category: 'system',
            source: 'test-source',
            message: 'Another test event',
            timestamp: new Date().toISOString()
          },
          timestamp: new Date().toISOString(),
          priority: 5
        });
      });

      // Should update the timestamp
      await waitFor(() => {
        const newTime = screen.getByText(/last updated:/i).textContent;
        expect(newTime).not.toBe(initialTime);
      });
    });
  });

  describe('Events Page Real-time Updates', () => {
    test('should show live indicator when connected', async () => {
      render(<Events />);

      // Wait for WebSocket connection
      await waitFor(() => {
        expect(mockWebSocket.readyState).toBe(MockWebSocket.OPEN);
      });

      // Should show live updates indicator
      await waitFor(() => {
        expect(screen.getByText('Live Updates')).toBeInTheDocument();
      });
    });

    test('should update event table in real-time', async () => {
      render(<Events />);

      // Wait for WebSocket connection
      await waitFor(() => {
        expect(mockWebSocket.readyState).toBe(MockWebSocket.OPEN);
      });

      // Initially should show no events
      expect(screen.getByText('0 events')).toBeInTheDocument();

      // Simulate receiving an event
      act(() => {
        mockWebSocket.simulateMessage({
          type: 'security_event',
          data: {
            event_id: 'table-event-1',
            severity: 7,
            category: 'authentication',
            source: 'auth-service',
            message: 'Failed login attempt',
            timestamp: new Date().toISOString(),
            analysis: {
              explanation: 'Multiple failed login attempts detected'
            },
            recommendations: ['Check user credentials', 'Review access logs']
          },
          timestamp: new Date().toISOString(),
          priority: 7
        });
      });

      // Should update event count and show event in table
      await waitFor(() => {
        expect(screen.getByText('1 event')).toBeInTheDocument();
        expect(screen.getByText('Failed login attempt')).toBeInTheDocument();
        expect(screen.getByText('auth-service')).toBeInTheDocument();
      });
    });

    test('should handle multiple rapid events without issues', async () => {
      render(<Events />);

      // Wait for WebSocket connection
      await waitFor(() => {
        expect(mockWebSocket.readyState).toBe(MockWebSocket.OPEN);
      });

      // Simulate multiple rapid events
      act(() => {
        for (let i = 1; i <= 5; i++) {
          mockWebSocket.simulateMessage({
            type: 'security_event',
            data: {
              event_id: `rapid-event-${i}`,
              severity: i + 3,
              category: 'system',
              source: `source-${i}`,
              message: `Rapid event ${i}`,
              timestamp: new Date().toISOString(),
              analysis: {
                explanation: `Analysis for event ${i}`
              }
            },
            timestamp: new Date().toISOString(),
            priority: i + 3
          });
        }
      });

      // Should handle all events
      await waitFor(() => {
        expect(screen.getByText('5 events')).toBeInTheDocument();
        expect(screen.getByText('Rapid event 1')).toBeInTheDocument();
        expect(screen.getByText('Rapid event 5')).toBeInTheDocument();
      });
    });
  });

  describe('WebSocket Service', () => {
    test('should handle connection establishment', async () => {
      const connectionHandler = jest.fn();
      websocketService.onConnectionChange(connectionHandler);

      await websocketService.connect();

      expect(connectionHandler).toHaveBeenCalledWith(
        expect.objectContaining({
          connected: true,
          connecting: false,
          error: null
        })
      );
    });

    test('should handle subscription management', async () => {
      await websocketService.connect();

      // Should be able to subscribe to events
      websocketService.subscribe(['security_event', 'system_status']);

      // Should be able to unsubscribe
      websocketService.unsubscribe(['system_status']);

      // No errors should occur
      expect(mockWebSocket.readyState).toBe(MockWebSocket.OPEN);
    });

    test('should handle filter management', async () => {
      await websocketService.connect();

      // Should be able to set filters
      websocketService.setFilter({
        event_types: ['security_event'],
        min_priority: 5,
        categories: ['security', 'authentication']
      });

      // Should be able to clear filters
      websocketService.clearFilter();

      // No errors should occur
      expect(mockWebSocket.readyState).toBe(MockWebSocket.OPEN);
    });

    test('should handle ping/pong', async () => {
      await websocketService.connect();

      // Should be able to send ping
      websocketService.ping();

      // Simulate pong response
      act(() => {
        mockWebSocket.simulateMessage({
          type: 'pong',
          data: {
            timestamp: new Date().toISOString()
          }
        });
      });

      // No errors should occur
      expect(mockWebSocket.readyState).toBe(MockWebSocket.OPEN);
    });

    test('should handle reconnection attempts', async () => {
      await websocketService.connect();

      // Simulate connection loss
      act(() => {
        mockWebSocket.close(1006, 'Connection lost');
      });

      // Should attempt to reconnect
      await waitFor(() => {
        expect((global as any).WebSocket).toHaveBeenCalledTimes(2);
      }, { timeout: 10000 });
    });
  });

  describe('Optimistic Updates', () => {
    test('should handle optimistic event updates', async () => {
      render(<Dashboard />);

      // Wait for WebSocket connection
      await waitFor(() => {
        expect(mockWebSocket.readyState).toBe(MockWebSocket.OPEN);
      });

      // Simulate a processing update (optimistic)
      act(() => {
        mockWebSocket.simulateMessage({
          type: 'processing_update',
          data: {
            raw_log_id: 'log-123',
            stage: 'parsing',
            status: 'in_progress',
            progress: 0.5
          },
          timestamp: new Date().toISOString(),
          priority: 3
        });
      });

      // Then simulate the actual security event
      act(() => {
        mockWebSocket.simulateMessage({
          type: 'security_event',
          data: {
            event_id: 'optimistic-event-1',
            severity: 6,
            category: 'network',
            source: 'firewall',
            message: 'Suspicious network activity',
            timestamp: new Date().toISOString(),
            analysis: {
              explanation: 'Unusual traffic pattern detected'
            }
          },
          timestamp: new Date().toISOString(),
          priority: 6
        });
      });

      // Should show the final event
      await waitFor(() => {
        expect(screen.getByText('Suspicious network activity')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    test('should handle malformed WebSocket messages', async () => {
      render(<Dashboard />);

      // Wait for WebSocket connection
      await waitFor(() => {
        expect(mockWebSocket.readyState).toBe(MockWebSocket.OPEN);
      });

      // Simulate malformed message
      act(() => {
        if (mockWebSocket.onmessage) {
          mockWebSocket.onmessage(new MessageEvent('message', { data: 'invalid json' }));
        }
      });

      // Should not crash the application
      expect(screen.getByText('Security Dashboard')).toBeInTheDocument();
    });

    test('should handle WebSocket errors gracefully', async () => {
      render(<Dashboard />);

      // Simulate WebSocket error
      act(() => {
        if (mockWebSocket.onerror) {
          mockWebSocket.onerror(new Event('error'));
        }
      });

      // Should show error state
      await waitFor(() => {
        expect(screen.getByText(/real-time updates unavailable/i)).toBeInTheDocument();
      });
    });
  });
});