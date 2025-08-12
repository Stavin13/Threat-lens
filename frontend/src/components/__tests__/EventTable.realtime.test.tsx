import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import EventTable from '../EventTable';
import { api } from '../../services/api';
import * as useWebSocketHook from '../../hooks/useWebSocket';
import * as useRealtimeClientHook from '../../hooks/useRealtimeClient';

// Mock the API
jest.mock('../../services/api', () => ({
  api: {
    getEvents: jest.fn(),
    getEvent: jest.fn()
  }
}));

// Mock the hooks
jest.mock('../../hooks/useWebSocket');
jest.mock('../../hooks/useRealtimeClient');

const mockApi = api as jest.Mocked<typeof api>;
const mockUseSecurityEvents = useWebSocketHook.useSecurityEvents as jest.MockedFunction<typeof useWebSocketHook.useSecurityEvents>;
const mockUseRealtimeClient = useRealtimeClientHook.useRealtimeClient as jest.MockedFunction<typeof useRealtimeClientHook.useRealtimeClient>;

describe('EventTable Real-time Features', () => {
  const mockEvents = [
    {
      event: {
        id: 'event-1',
        timestamp: '2023-01-01T00:00:00Z',
        source: 'auth.log',
        message: 'Failed login attempt',
        category: 'authentication'
      },
      analysis: {
        severity_score: 8,
        explanation: 'Multiple failed login attempts detected',
        recommendations: ['Enable account lockout']
      }
    },
    {
      event: {
        id: 'event-2',
        timestamp: '2023-01-01T00:01:00Z',
        source: 'system.log',
        message: 'System event',
        category: 'system'
      },
      analysis: {
        severity_score: 3,
        explanation: 'Normal system operation',
        recommendations: []
      }
    }
  ];

  beforeEach(() => {
    jest.clearAllMocks();

    // Mock API responses
    mockApi.getEvents.mockResolvedValue(mockEvents);
    mockApi.getEvent.mockResolvedValue(mockEvents[0]);

    // Mock useSecurityEvents hook
    mockUseSecurityEvents.mockReturnValue({
      events: mockEvents,
      securityEvents: mockEvents,
      optimisticEvents: [],
      addOptimisticEvent: jest.fn(),
      removeOptimisticEvent: jest.fn(),
      connectionStatus: {
        connected: true,
        connecting: false,
        error: null,
        lastConnected: new Date(),
        reconnectAttempts: 0
      },
      isConnected: true,
      connect: jest.fn(),
      disconnect: jest.fn()
    });

    // Mock useRealtimeClient hook
    mockUseRealtimeClient.mockReturnValue({
      connectionStatus: {
        connected: true,
        connecting: false,
        error: null,
        lastConnected: new Date(),
        reconnectAttempts: 0
      },
      isConnected: true,
      isConnecting: false,
      connect: jest.fn(),
      disconnect: jest.fn(),
      subscribe: jest.fn(),
      unsubscribe: jest.fn(),
      subscribeToSecurityEvents: jest.fn(),
      subscribeToSystemStatus: jest.fn(),
      subscribeToProcessingUpdates: jest.fn(),
      subscribeToHealthChecks: jest.fn(),
      ping: jest.fn(),
      requestServerStatus: jest.fn(),
      getActiveSubscriptions: jest.fn(() => []),
      lastSecurityEvent: null,
      lastSystemStatus: null,
      lastProcessingUpdate: null,
      lastHealthCheck: null,
      recentSecurityEvents: [],
      clearRecentEvents: jest.fn()
    });
  });

  it('should display real-time connection status when enabled', async () => {
    render(<EventTable realTimeEnabled={true} />);

    await waitFor(() => {
      expect(screen.getByText('Live Updates')).toBeInTheDocument();
    });

    // Should show connected indicator
    const liveIndicator = screen.getByText('Live Updates');
    expect(liveIndicator).toHaveClass('text-green-600');
  });

  it('should show disconnected status when real-time is unavailable', async () => {
    // Mock disconnected state
    mockUseSecurityEvents.mockReturnValue({
      events: mockEvents,
      securityEvents: mockEvents,
      optimisticEvents: [],
      addOptimisticEvent: jest.fn(),
      removeOptimisticEvent: jest.fn(),
      connectionStatus: {
        connected: false,
        connecting: false,
        error: 'Connection failed',
        lastConnected: null,
        reconnectAttempts: 3
      },
      isConnected: false,
      connect: jest.fn(),
      disconnect: jest.fn()
    });

    render(<EventTable realTimeEnabled={true} />);

    await waitFor(() => {
      expect(screen.getByText('Disconnected')).toBeInTheDocument();
    });

    // Should show disconnected indicator
    const disconnectedIndicator = screen.getByText('Disconnected');
    expect(disconnectedIndicator).toHaveClass('text-red-600');
  });

  it('should display auto-refresh indicator when enabled', async () => {
    render(<EventTable autoRefresh={true} />);

    await waitFor(() => {
      expect(screen.getByText('Auto-refresh')).toBeInTheDocument();
    });

    // Should show auto-refresh indicator
    const autoRefreshIndicator = screen.getByText('Auto-refresh');
    expect(autoRefreshIndicator).toHaveClass('text-blue-600');
  });

  it('should show processing status column when enabled', async () => {
    render(<EventTable showProcessingStatus={true} />);

    await waitFor(() => {
      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByText('Processing Monitor')).toBeInTheDocument();
    });

    // Should show complete status for events
    expect(screen.getAllByText('Complete')).toHaveLength(2);
  });

  it('should highlight new events', async () => {
    const { rerender } = render(<EventTable realTimeEnabled={true} />);

    // Add a new event
    const newEvent = {
      event: {
        id: 'event-3',
        timestamp: '2023-01-01T00:02:00Z',
        source: 'new.log',
        message: 'New event',
        category: 'security'
      },
      analysis: {
        severity_score: 6,
        explanation: 'New security event',
        recommendations: []
      }
    };

    const updatedEvents = [...mockEvents, newEvent];

    mockUseSecurityEvents.mockReturnValue({
      events: updatedEvents,
      securityEvents: updatedEvents,
      optimisticEvents: [],
      addOptimisticEvent: jest.fn(),
      removeOptimisticEvent: jest.fn(),
      connectionStatus: {
        connected: true,
        connecting: false,
        error: null,
        lastConnected: new Date(),
        reconnectAttempts: 0
      },
      isConnected: true,
      connect: jest.fn(),
      disconnect: jest.fn()
    });

    rerender(<EventTable realTimeEnabled={true} />);

    await waitFor(() => {
      expect(screen.getByText('1 new')).toBeInTheDocument();
      expect(screen.getByText('NEW')).toBeInTheDocument();
    });
  });

  it('should handle processing updates', async () => {
    const mockOnProcessingUpdate = jest.fn();

    mockUseRealtimeClient.mockImplementation((options) => {
      // Simulate processing update
      if (options?.onProcessingUpdate) {
        setTimeout(() => {
          options.onProcessingUpdate({
            raw_log_id: 'event-1',
            stage: 'analysis',
            status: 'processing',
            progress: 0.5,
            events_created: 0,
            processing_time: 1.5
          });
        }, 0);
      }

      return {
        connectionStatus: {
          connected: true,
          connecting: false,
          error: null,
          lastConnected: new Date(),
          reconnectAttempts: 0
        },
        isConnected: true,
        isConnecting: false,
        connect: jest.fn(),
        disconnect: jest.fn(),
        subscribe: jest.fn(),
        unsubscribe: jest.fn(),
        subscribeToSecurityEvents: jest.fn(),
        subscribeToSystemStatus: jest.fn(),
        subscribeToProcessingUpdates: jest.fn(),
        subscribeToHealthChecks: jest.fn(),
        ping: jest.fn(),
        requestServerStatus: jest.fn(),
        getActiveSubscriptions: jest.fn(() => []),
        lastSecurityEvent: null,
        lastSystemStatus: null,
        lastProcessingUpdate: null,
        lastHealthCheck: null,
        recentSecurityEvents: [],
        clearRecentEvents: jest.fn()
      };
    });

    render(<EventTable showProcessingStatus={true} />);

    await waitFor(() => {
      expect(screen.getByText('Processing Monitor')).toBeInTheDocument();
    });
  });

  it('should display updated timestamp', async () => {
    render(<EventTable realTimeEnabled={true} />);

    await waitFor(() => {
      expect(screen.getByText(/Updated:/)).toBeInTheDocument();
    });

    // Should show a timestamp
    const timestampElement = screen.getByText(/Updated:/);
    expect(timestampElement).toBeInTheDocument();
  });

  it('should handle event selection', async () => {
    const mockOnEventSelect = jest.fn();
    
    render(<EventTable onEventSelect={mockOnEventSelect} />);

    await waitFor(() => {
      expect(screen.getAllByText('View Details')).toHaveLength(2);
    });

    // Click on first event's view details button (events are sorted by timestamp desc, so event-2 comes first)
    fireEvent.click(screen.getAllByText('View Details')[0]);

    expect(mockOnEventSelect).toHaveBeenCalledWith('event-2');
  });

  it('should show connection warning in empty state when disconnected', async () => {
    // Mock disconnected state with no events
    mockUseSecurityEvents.mockReturnValue({
      events: [],
      securityEvents: [],
      optimisticEvents: [],
      addOptimisticEvent: jest.fn(),
      removeOptimisticEvent: jest.fn(),
      connectionStatus: {
        connected: false,
        connecting: false,
        error: 'Connection failed',
        lastConnected: null,
        reconnectAttempts: 3
      },
      isConnected: false,
      connect: jest.fn(),
      disconnect: jest.fn()
    });

    render(<EventTable realTimeEnabled={true} />);

    await waitFor(() => {
      expect(screen.getByText('No Events Found')).toBeInTheDocument();
      expect(screen.getByText(/Real-time connection unavailable/)).toBeInTheDocument();
    });
  });

  it('should use prop events when provided', async () => {
    const propEvents = [mockEvents[0]]; // Only first event

    render(<EventTable events={propEvents} />);

    await waitFor(() => {
      expect(screen.getByText('Security Events (1)')).toBeInTheDocument();
      expect(screen.getByText('Failed login attempt')).toBeInTheDocument();
      expect(screen.queryByText('System event')).not.toBeInTheDocument();
    });

    // Should not call API when prop events are provided
    expect(mockApi.getEvents).not.toHaveBeenCalled();
  });

  it('should handle sorting with real-time events', async () => {
    render(<EventTable realTimeEnabled={true} />);

    await waitFor(() => {
      expect(screen.getByText('Timestamp')).toBeInTheDocument();
    });

    // Click on timestamp header to sort
    fireEvent.click(screen.getByText('Timestamp'));

    // Events should still be displayed
    expect(screen.getByText('Failed login attempt')).toBeInTheDocument();
    expect(screen.getByText('System event')).toBeInTheDocument();
  });
});