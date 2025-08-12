import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import Dashboard from '../Dashboard';
import { api } from '../../services/api';
import * as useWebSocketHook from '../../hooks/useWebSocket';
import * as useRealtimeClientHook from '../../hooks/useRealtimeClient';

// Mock the API
jest.mock('../../services/api', () => ({
  api: {
    get: jest.fn(),
    getEvents: jest.fn()
  }
}));

// Mock the hooks
jest.mock('../../hooks/useWebSocket');
jest.mock('../../hooks/useRealtimeClient');

const mockApi = api as jest.Mocked<typeof api>;
const mockUseSecurityEvents = useWebSocketHook.useSecurityEvents as jest.MockedFunction<typeof useWebSocketHook.useSecurityEvents>;
const mockUseRealtimeClient = useRealtimeClientHook.useRealtimeClient as jest.MockedFunction<typeof useRealtimeClientHook.useRealtimeClient>;

describe('Dashboard Real-time Features', () => {
  const mockHealthData = {
    overall_status: 'healthy',
    timestamp: '2023-01-01T00:00:00Z',
    uptime_seconds: 3600,
    monitoring_active: true,
    component_health: {
      database: {
        status: 'healthy',
        message: 'Operating normally',
        last_check: '2023-01-01T00:00:00Z'
      },
      websocket: {
        status: 'healthy',
        message: 'Connected',
        last_check: '2023-01-01T00:00:00Z'
      }
    },
    system_metrics: {
      cpu_percent: 25.5,
      memory_percent: 60.2,
      memory_used_mb: 1024,
      memory_total_mb: 2048,
      disk_percent: 45.0,
      disk_used_gb: 45.0,
      disk_total_gb: 100.0,
      load_average: [1.2, 1.1, 1.0],
      timestamp: '2023-01-01T00:00:00Z'
    },
    component_metrics: {}
  };

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
    mockApi.get.mockResolvedValue({ data: mockHealthData });
    mockApi.getEvents.mockResolvedValue({ data: { events: [] } });

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

  it('should render real-time event counters', async () => {
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Total Events')).toBeInTheDocument();
      expect(screen.getByText('High Severity')).toBeInTheDocument();
      expect(screen.getByText('Medium Severity')).toBeInTheDocument();
      expect(screen.getByText('Low Severity')).toBeInTheDocument();
      expect(screen.getByText('Last Hour')).toBeInTheDocument();
    });

    // Check event counts are displayed
    expect(screen.getByText('2')).toBeInTheDocument(); // Total events
    expect(screen.getByText('1')).toBeInTheDocument(); // High severity (score >= 7)
  });

  it('should show real-time processing metrics', async () => {
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Real-time Processing Metrics')).toBeInTheDocument();
      expect(screen.getByText('Events/sec')).toBeInTheDocument();
      expect(screen.getByText('Queue Size')).toBeInTheDocument();
      expect(screen.getByText('Active Sources')).toBeInTheDocument();
      expect(screen.getByText('Errors/min')).toBeInTheDocument();
    });
  });

  it('should display live connection indicators when connected', async () => {
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Real-time monitoring active')).toBeInTheDocument();
      expect(screen.getByText('Live Updates')).toBeInTheDocument();
      expect(screen.getByText('Live')).toBeInTheDocument();
    });
  });

  it('should show warning when connections are not available', async () => {
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

    mockUseRealtimeClient.mockReturnValue({
      connectionStatus: {
        connected: false,
        connecting: false,
        error: null,
        lastConnected: null,
        reconnectAttempts: 0
      },
      isConnected: false,
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

    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Real-time updates unavailable')).toBeInTheDocument();
      expect(screen.getByText(/Security events: Real-time updates not available/)).toBeInTheDocument();
      expect(screen.getByText(/System status: Real-time updates not available/)).toBeInTheDocument();
    });
  });

  it('should calculate event counts correctly', async () => {
    const eventsWithVariedSeverity = [
      {
        event: { id: '1', timestamp: '2023-01-01T00:00:00Z', source: 'test', message: 'test', category: 'test' },
        analysis: { severity_score: 9, explanation: '', recommendations: [] }
      },
      {
        event: { id: '2', timestamp: '2023-01-01T00:00:00Z', source: 'test', message: 'test', category: 'test' },
        analysis: { severity_score: 5, explanation: '', recommendations: [] }
      },
      {
        event: { id: '3', timestamp: '2023-01-01T00:00:00Z', source: 'test', message: 'test', category: 'test' },
        analysis: { severity_score: 2, explanation: '', recommendations: [] }
      }
    ];

    mockUseSecurityEvents.mockReturnValue({
      events: eventsWithVariedSeverity,
      securityEvents: eventsWithVariedSeverity,
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

    render(<Dashboard />);

    await waitFor(() => {
      // Should show 1 high severity (score >= 7)
      const highSeverityElements = screen.getAllByText('1');
      expect(highSeverityElements.length).toBeGreaterThan(0);
      
      // Should show 1 medium severity (4 <= score < 7)
      // Should show 1 low severity (score < 4)
      // Should show 3 total events
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  it('should handle system status updates', async () => {
    const mockSystemStatusCallback = jest.fn();
    
    mockUseRealtimeClient.mockImplementation((options) => {
      // Call the onSystemStatus callback if provided
      if (options?.onSystemStatus) {
        setTimeout(() => {
          options.onSystemStatus({
            component: 'test_component',
            status: 'degraded',
            uptime: 3600,
            metrics: {},
            last_error: 'Test error'
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

    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Real-time Processing Metrics')).toBeInTheDocument();
    });
  });
});