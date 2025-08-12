/**
 * Comprehensive tests for real-time frontend components.
 * 
 * Tests WebSocket client connection/reconnection, real-time dashboard updates,
 * event streaming, and configuration UI validation.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Dashboard from '../Dashboard';
import Events from '../Events';
import Configuration from '../Configuration';
import LogSourceManager from '../LogSourceManager';
import NotificationManager from '../NotificationManager';
import SystemMonitoring from '../SystemMonitoring';
import ConnectionStatus from '../ConnectionStatus';
import { api } from '../../services/api';
import * as useWebSocketHook from '../../hooks/useWebSocket';
import * as useRealtimeClientHook from '../../hooks/useRealtimeClient';

// Mock the API
jest.mock('../../services/api', () => ({
  api: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
    getEvents: jest.fn(),
    getHealth: jest.fn(),
    getSystemMetrics: jest.fn()
  }
}));

// Mock the hooks
jest.mock('../../hooks/useWebSocket');
jest.mock('../../hooks/useRealtimeClient');

const mockApi = api as jest.Mocked<typeof api>;
const mockUseSecurityEvents = useWebSocketHook.useSecurityEvents as jest.MockedFunction<typeof useWebSocketHook.useSecurityEvents>;
const mockUseRealtimeClient = useRealtimeClientHook.useRealtimeClient as jest.MockedFunction<typeof useRealtimeClientHook.useRealtimeClient>;

describe('Real-time Frontend Components', () => {
  const mockEvents = [
    {
      event: {
        id: 'event-1',
        timestamp: '2023-01-01T00:00:00Z',
        source: 'auth.log',
        message: 'Failed login attempt for user admin',
        category: 'authentication'
      },
      analysis: {
        severity_score: 8,
        explanation: 'Multiple failed login attempts detected from suspicious IP',
        recommendations: ['Enable account lockout', 'Review access logs', 'Consider IP blocking']
      }
    },
    {
      event: {
        id: 'event-2',
        timestamp: '2023-01-01T00:01:00Z',
        source: 'system.log',
        message: 'System startup completed',
        category: 'system'
      },
      analysis: {
        severity_score: 2,
        explanation: 'Normal system startup sequence',
        recommendations: []
      }
    }
  ];

  const mockHealthData = {
    overall_status: 'healthy',
    timestamp: '2023-01-01T00:00:00Z',
    uptime_seconds: 3600,
    monitoring_active: true,
    component_health: {
      database: { status: 'healthy', message: 'Operating normally', last_check: '2023-01-01T00:00:00Z' },
      websocket: { status: 'healthy', message: 'Connected', last_check: '2023-01-01T00:00:00Z' },
      file_monitor: { status: 'healthy', message: '3 sources active', last_check: '2023-01-01T00:00:00Z' },
      queue_processor: { status: 'healthy', message: 'Processing normally', last_check: '2023-01-01T00:00:00Z' }
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
    realtime_metrics: {
      events_per_second: 12.5,
      queue_size: 45,
      active_sources: 3,
      errors_per_minute: 0.2,
      websocket_connections: 5,
      processing_latency_ms: 150
    }
  };

  const mockConnectionStatus = {
    connected: true,
    connecting: false,
    error: null,
    lastConnected: new Date('2023-01-01T00:00:00Z'),
    reconnectAttempts: 0
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();

    // Mock API responses
    mockApi.get.mockResolvedValue({ data: mockHealthData });
    mockApi.getEvents.mockResolvedValue({ data: { events: mockEvents } });
    mockApi.getHealth.mockResolvedValue({ data: mockHealthData });
    mockApi.getSystemMetrics.mockResolvedValue({ data: mockHealthData.system_metrics });

    // Default mock for useSecurityEvents
    mockUseSecurityEvents.mockReturnValue({
      events: mockEvents,
      securityEvents: mockEvents,
      optimisticEvents: [],
      addOptimisticEvent: jest.fn(),
      removeOptimisticEvent: jest.fn(),
      connectionStatus: mockConnectionStatus,
      isConnected: true,
      connect: jest.fn(),
      disconnect: jest.fn()
    });

    // Default mock for useRealtimeClient
    mockUseRealtimeClient.mockReturnValue({
      connectionStatus: mockConnectionStatus,
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
      getActiveSubscriptions: jest.fn(() => ['security_event', 'system_status']),
      lastSecurityEvent: null,
      lastSystemStatus: null,
      lastProcessingUpdate: null,
      lastHealthCheck: null,
      recentSecurityEvents: [],
      clearRecentEvents: jest.fn()
    });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('WebSocket Connection Management', () => {
    it('should display connection status correctly when connected', async () => {
      render(<ConnectionStatus />);

      await waitFor(() => {
        expect(screen.getByText('Connected')).toBeInTheDocument();
        expect(screen.getByText(/Connected since/)).toBeInTheDocument();
        expect(screen.queryByText('Disconnected')).not.toBeInTheDocument();
      });
    });

    it('should display disconnected status with error message', async () => {
      const disconnectedStatus = {
        connected: false,
        connecting: false,
        error: 'WebSocket connection failed',
        lastConnected: null,
        reconnectAttempts: 3
      };

      mockUseRealtimeClient.mockReturnValue({
        ...mockUseRealtimeClient(),
        connectionStatus: disconnectedStatus,
        isConnected: false
      });

      render(<ConnectionStatus />);

      await waitFor(() => {
        expect(screen.getByText('Disconnected')).toBeInTheDocument();
        expect(screen.getByText('WebSocket connection failed')).toBeInTheDocument();
        expect(screen.getByText('Reconnect attempts: 3')).toBeInTheDocument();
      });
    });

    it('should show connecting status during connection attempts', async () => {
      const connectingStatus = {
        connected: false,
        connecting: true,
        error: null,
        lastConnected: null,
        reconnectAttempts: 1
      };

      mockUseRealtimeClient.mockReturnValue({
        ...mockUseRealtimeClient(),
        connectionStatus: connectingStatus,
        isConnected: false,
        isConnecting: true
      });

      render(<ConnectionStatus />);

      await waitFor(() => {
        expect(screen.getByText('Connecting...')).toBeInTheDocument();
        expect(screen.getByText('Reconnect attempts: 1')).toBeInTheDocument();
      });
    });

    it('should handle manual connect/disconnect actions', async () => {
      const mockConnect = jest.fn();
      const mockDisconnect = jest.fn();

      mockUseRealtimeClient.mockReturnValue({
        ...mockUseRealtimeClient(),
        connect: mockConnect,
        disconnect: mockDisconnect,
        isConnected: false
      });

      render(<ConnectionStatus />);

      const connectButton = screen.getByRole('button', { name: /connect/i });
      fireEvent.click(connectButton);

      expect(mockConnect).toHaveBeenCalled();

      // Simulate connected state
      mockUseRealtimeClient.mockReturnValue({
        ...mockUseRealtimeClient(),
        connect: mockConnect,
        disconnect: mockDisconnect,
        isConnected: true
      });

      render(<ConnectionStatus />);

      const disconnectButton = screen.getByRole('button', { name: /disconnect/i });
      fireEvent.click(disconnectButton);

      expect(mockDisconnect).toHaveBeenCalled();
    });

    it('should display active subscriptions', async () => {
      mockUseRealtimeClient.mockReturnValue({
        ...mockUseRealtimeClient(),
        getActiveSubscriptions: jest.fn(() => ['security_event', 'system_status', 'processing_update'])
      });

      render(<ConnectionStatus />);

      await waitFor(() => {
        expect(screen.getByText('Active Subscriptions:')).toBeInTheDocument();
        expect(screen.getByText('security_event')).toBeInTheDocument();
        expect(screen.getByText('system_status')).toBeInTheDocument();
        expect(screen.getByText('processing_update')).toBeInTheDocument();
      });
    });
  });

  describe('Real-time Dashboard Updates', () => {
    it('should display real-time event counters with live updates', async () => {
      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('Total Events')).toBeInTheDocument();
        expect(screen.getByText('2')).toBeInTheDocument(); // Total events
        expect(screen.getByText('High Severity')).toBeInTheDocument();
        expect(screen.getByText('1')).toBeInTheDocument(); // High severity events
      });

      // Simulate new event arrival
      const newEvent = {
        event: {
          id: 'event-3',
          timestamp: new Date().toISOString(),
          source: 'security.log',
          message: 'New security event',
          category: 'security'
        },
        analysis: {
          severity_score: 9,
          explanation: 'Critical security event',
          recommendations: ['Immediate action required']
        }
      };

      act(() => {
        mockUseSecurityEvents.mockReturnValue({
          ...mockUseSecurityEvents(),
          events: [...mockEvents, newEvent],
          securityEvents: [...mockEvents, newEvent]
        });
      });

      // Re-render to simulate state update
      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('3')).toBeInTheDocument(); // Updated total
        expect(screen.getByText('2')).toBeInTheDocument(); // Updated high severity count
      });
    });

    it('should show real-time processing metrics', async () => {
      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('Real-time Processing Metrics')).toBeInTheDocument();
        expect(screen.getByText('12.5')).toBeInTheDocument(); // Events/sec
        expect(screen.getByText('45')).toBeInTheDocument(); // Queue size
        expect(screen.getByText('3')).toBeInTheDocument(); // Active sources
        expect(screen.getByText('0.2')).toBeInTheDocument(); // Errors/min
      });
    });

    it('should update metrics when new data arrives', async () => {
      const { rerender } = render(<Dashboard />);

      // Initial metrics
      await waitFor(() => {
        expect(screen.getByText('12.5')).toBeInTheDocument();
      });

      // Update health data with new metrics
      const updatedHealthData = {
        ...mockHealthData,
        realtime_metrics: {
          ...mockHealthData.realtime_metrics,
          events_per_second: 25.0,
          queue_size: 120,
          active_sources: 5
        }
      };

      mockApi.get.mockResolvedValue({ data: updatedHealthData });

      // Trigger re-render
      rerender(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('25')).toBeInTheDocument(); // Updated events/sec
        expect(screen.getByText('120')).toBeInTheDocument(); // Updated queue size
        expect(screen.getByText('5')).toBeInTheDocument(); // Updated active sources
      });
    });

    it('should display live indicators when connected', async () => {
      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('Live')).toBeInTheDocument();
        expect(screen.getByText('Real-time monitoring active')).toBeInTheDocument();
      });
    });

    it('should show warning indicators when disconnected', async () => {
      mockUseRealtimeClient.mockReturnValue({
        ...mockUseRealtimeClient(),
        isConnected: false,
        connectionStatus: {
          ...mockConnectionStatus,
          connected: false,
          error: 'Connection lost'
        }
      });

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('Real-time updates unavailable')).toBeInTheDocument();
        expect(screen.getByText(/Connection lost/)).toBeInTheDocument();
      });
    });
  });

  describe('Real-time Event Streaming', () => {
    it('should display events in real-time table', async () => {
      render(<Events />);

      await waitFor(() => {
        expect(screen.getByText('Failed login attempt for user admin')).toBeInTheDocument();
        expect(screen.getByText('System startup completed')).toBeInTheDocument();
        expect(screen.getByText('authentication')).toBeInTheDocument();
        expect(screen.getByText('system')).toBeInTheDocument();
      });
    });

    it('should update table when new events arrive', async () => {
      const { rerender } = render(<Events />);

      // Initial events
      await waitFor(() => {
        expect(screen.getAllByRole('row')).toHaveLength(3); // Header + 2 events
      });

      // Add new event
      const newEvent = {
        event: {
          id: 'event-3',
          timestamp: new Date().toISOString(),
          source: 'network.log',
          message: 'Suspicious network activity detected',
          category: 'network'
        },
        analysis: {
          severity_score: 7,
          explanation: 'Unusual traffic pattern detected',
          recommendations: ['Monitor network traffic', 'Check firewall logs']
        }
      };

      mockUseSecurityEvents.mockReturnValue({
        ...mockUseSecurityEvents(),
        events: [...mockEvents, newEvent],
        securityEvents: [...mockEvents, newEvent]
      });

      rerender(<Events />);

      await waitFor(() => {
        expect(screen.getAllByRole('row')).toHaveLength(4); // Header + 3 events
        expect(screen.getByText('Suspicious network activity detected')).toBeInTheDocument();
        expect(screen.getByText('network')).toBeInTheDocument();
      });
    });

    it('should handle optimistic updates', async () => {
      const mockAddOptimistic = jest.fn();
      const mockRemoveOptimistic = jest.fn();

      const optimisticEvent = {
        event: {
          id: 'temp-1',
          timestamp: new Date().toISOString(),
          source: 'processing',
          message: 'Processing new log entry...',
          category: 'system'
        },
        analysis: {
          severity_score: 1,
          explanation: 'Processing in progress',
          recommendations: []
        }
      };

      mockUseSecurityEvents.mockReturnValue({
        ...mockUseSecurityEvents(),
        optimisticEvents: [optimisticEvent],
        addOptimisticEvent: mockAddOptimistic,
        removeOptimisticEvent: mockRemoveOptimistic
      });

      render(<Events />);

      await waitFor(() => {
        expect(screen.getByText('Processing new log entry...')).toBeInTheDocument();
        expect(screen.getByText(/Processing in progress/)).toBeInTheDocument();
      });
    });

    it('should show real-time processing status indicators', async () => {
      render(<Events />);

      await waitFor(() => {
        // Should show live indicator
        expect(screen.getByText('Live Updates')).toBeInTheDocument();
        
        // Should show event timestamps
        expect(screen.getByText(/2023-01-01/)).toBeInTheDocument();
      });
    });

    it('should handle event filtering in real-time', async () => {
      render(<Events />);

      // Filter by category
      const categoryFilter = screen.getByLabelText(/category/i);
      await userEvent.selectOptions(categoryFilter, 'authentication');

      await waitFor(() => {
        expect(screen.getByText('Failed login attempt for user admin')).toBeInTheDocument();
        expect(screen.queryByText('System startup completed')).not.toBeInTheDocument();
      });
    });

    it('should display severity indicators correctly', async () => {
      render(<Events />);

      await waitFor(() => {
        // High severity event should have appropriate styling
        const highSeverityRow = screen.getByText('Failed login attempt for user admin').closest('tr');
        expect(highSeverityRow).toHaveClass('severity-high');
        
        // Low severity event should have appropriate styling
        const lowSeverityRow = screen.getByText('System startup completed').closest('tr');
        expect(lowSeverityRow).toHaveClass('severity-low');
      });
    });
  });

  describe('Configuration UI Testing', () => {
    const mockLogSources = [
      {
        id: 1,
        source_name: 'auth_logs',
        path: '/var/log/auth.log',
        source_type: 'file',
        enabled: true,
        status: 'active',
        last_monitored: '2023-01-01T00:00:00Z'
      },
      {
        id: 2,
        source_name: 'system_logs',
        path: '/var/log/system',
        source_type: 'directory',
        enabled: false,
        status: 'inactive',
        last_monitored: null
      }
    ];

    const mockNotificationRules = [
      {
        id: 1,
        rule_name: 'High Severity Alerts',
        enabled: true,
        min_severity: 7,
        max_severity: 10,
        channels: ['email', 'webhook'],
        email_recipients: ['admin@example.com'],
        webhook_url: 'https://hooks.example.com/webhook'
      }
    ];

    beforeEach(() => {
      mockApi.get.mockImplementation((url) => {
        if (url.includes('/log-sources')) {
          return Promise.resolve({ data: { sources: mockLogSources } });
        }
        if (url.includes('/notification-rules')) {
          return Promise.resolve({ data: { rules: mockNotificationRules } });
        }
        return Promise.resolve({ data: mockHealthData });
      });
    });

    it('should validate log source configuration', async () => {
      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByText('Log Source Management')).toBeInTheDocument();
      });

      // Click add new source
      const addButton = screen.getByRole('button', { name: /add.*source/i });
      fireEvent.click(addButton);

      // Fill in form with invalid data
      const nameInput = screen.getByLabelText(/source name/i);
      const pathInput = screen.getByLabelText(/path/i);

      await userEvent.type(nameInput, ''); // Empty name
      await userEvent.type(pathInput, 'invalid-path'); // Invalid path

      const saveButton = screen.getByRole('button', { name: /save/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/source name is required/i)).toBeInTheDocument();
        expect(screen.getByText(/invalid path format/i)).toBeInTheDocument();
      });
    });

    it('should validate notification rule configuration', async () => {
      render(<NotificationManager />);

      await waitFor(() => {
        expect(screen.getByText('Notification Rules')).toBeInTheDocument();
      });

      // Click add new rule
      const addButton = screen.getByRole('button', { name: /add.*rule/i });
      fireEvent.click(addButton);

      // Fill in form with invalid data
      const nameInput = screen.getByLabelText(/rule name/i);
      const minSeverityInput = screen.getByLabelText(/minimum severity/i);
      const maxSeverityInput = screen.getByLabelText(/maximum severity/i);
      const emailInput = screen.getByLabelText(/email recipients/i);

      await userEvent.type(nameInput, ''); // Empty name
      await userEvent.type(minSeverityInput, '8');
      await userEvent.type(maxSeverityInput, '5'); // Max < Min
      await userEvent.type(emailInput, 'invalid-email'); // Invalid email

      const saveButton = screen.getByRole('button', { name: /save/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/rule name is required/i)).toBeInTheDocument();
        expect(screen.getByText(/maximum severity must be greater than minimum/i)).toBeInTheDocument();
        expect(screen.getByText(/invalid email format/i)).toBeInTheDocument();
      });
    });

    it('should test notification delivery', async () => {
      mockApi.post.mockResolvedValue({ data: { success: true, message: 'Test notification sent' } });

      render(<NotificationManager />);

      await waitFor(() => {
        expect(screen.getByText('High Severity Alerts')).toBeInTheDocument();
      });

      // Click test button for the rule
      const testButton = screen.getByRole('button', { name: /test/i });
      fireEvent.click(testButton);

      await waitFor(() => {
        expect(screen.getByText('Test notification sent')).toBeInTheDocument();
      });

      expect(mockApi.post).toHaveBeenCalledWith('/api/notifications/test', expect.any(Object));
    });

    it('should show real-time status updates for log sources', async () => {
      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByText('auth_logs')).toBeInTheDocument();
        expect(screen.getByText('active')).toBeInTheDocument();
        expect(screen.getByText('system_logs')).toBeInTheDocument();
        expect(screen.getByText('inactive')).toBeInTheDocument();
      });

      // Simulate status update via WebSocket
      const statusUpdate = {
        source_name: 'auth_logs',
        status: 'error',
        error_message: 'Permission denied',
        last_monitored: new Date().toISOString()
      };

      // Mock the system status callback
      const mockSystemStatusCallback = mockUseRealtimeClient().subscribeToSystemStatus;
      act(() => {
        if (mockSystemStatusCallback.mock && mockSystemStatusCallback.mock.calls.length > 0) {
          const callback = mockSystemStatusCallback.mock.calls[0][0];
          callback(statusUpdate);
        }
      });

      await waitFor(() => {
        expect(screen.getByText('error')).toBeInTheDocument();
        expect(screen.getByText('Permission denied')).toBeInTheDocument();
      });
    });

    it('should handle configuration save errors gracefully', async () => {
      mockApi.post.mockRejectedValue(new Error('Network error'));

      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByText('Log Source Management')).toBeInTheDocument();
      });

      const addButton = screen.getByRole('button', { name: /add.*source/i });
      fireEvent.click(addButton);

      // Fill in valid form data
      const nameInput = screen.getByLabelText(/source name/i);
      const pathInput = screen.getByLabelText(/path/i);

      await userEvent.type(nameInput, 'test_source');
      await userEvent.type(pathInput, '/var/log/test.log');

      const saveButton = screen.getByRole('button', { name: /save/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/failed to save configuration/i)).toBeInTheDocument();
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
    });
  });

  describe('System Monitoring Real-time Updates', () => {
    it('should display real-time system metrics', async () => {
      render(<SystemMonitoring />);

      await waitFor(() => {
        expect(screen.getByText('System Monitoring')).toBeInTheDocument();
        expect(screen.getByText('25.5%')).toBeInTheDocument(); // CPU usage
        expect(screen.getByText('60.2%')).toBeInTheDocument(); // Memory usage
        expect(screen.getByText('45.0%')).toBeInTheDocument(); // Disk usage
      });
    });

    it('should update metrics in real-time', async () => {
      const { rerender } = render(<SystemMonitoring />);

      // Initial metrics
      await waitFor(() => {
        expect(screen.getByText('25.5%')).toBeInTheDocument();
      });

      // Simulate metric update
      const updatedMetrics = {
        ...mockHealthData.system_metrics,
        cpu_percent: 45.8,
        memory_percent: 72.1
      };

      mockApi.getSystemMetrics.mockResolvedValue({ data: updatedMetrics });

      // Advance timers to trigger update
      act(() => {
        jest.advanceTimersByTime(5000);
      });

      rerender(<SystemMonitoring />);

      await waitFor(() => {
        expect(screen.getByText('45.8%')).toBeInTheDocument();
        expect(screen.getByText('72.1%')).toBeInTheDocument();
      });
    });

    it('should show component health status', async () => {
      render(<SystemMonitoring />);

      await waitFor(() => {
        expect(screen.getByText('Database')).toBeInTheDocument();
        expect(screen.getByText('Operating normally')).toBeInTheDocument();
        expect(screen.getByText('WebSocket')).toBeInTheDocument();
        expect(screen.getByText('Connected')).toBeInTheDocument();
        expect(screen.getByText('File Monitor')).toBeInTheDocument();
        expect(screen.getByText('3 sources active')).toBeInTheDocument();
      });
    });

    it('should highlight unhealthy components', async () => {
      const unhealthyData = {
        ...mockHealthData,
        component_health: {
          ...mockHealthData.component_health,
          database: {
            status: 'degraded',
            message: 'High connection count',
            last_check: '2023-01-01T00:00:00Z'
          },
          file_monitor: {
            status: 'error',
            message: 'Permission denied on /var/log/secure.log',
            last_check: '2023-01-01T00:00:00Z'
          }
        }
      };

      mockApi.get.mockResolvedValue({ data: unhealthyData });

      render(<SystemMonitoring />);

      await waitFor(() => {
        expect(screen.getByText('degraded')).toBeInTheDocument();
        expect(screen.getByText('High connection count')).toBeInTheDocument();
        expect(screen.getByText('error')).toBeInTheDocument();
        expect(screen.getByText('Permission denied on /var/log/secure.log')).toBeInTheDocument();
      });

      // Check for warning styling
      const degradedComponent = screen.getByText('degraded').closest('.component-status');
      const errorComponent = screen.getByText('error').closest('.component-status');
      
      expect(degradedComponent).toHaveClass('status-degraded');
      expect(errorComponent).toHaveClass('status-error');
    });

    it('should show real-time processing queue status', async () => {
      render(<SystemMonitoring />);

      await waitFor(() => {
        expect(screen.getByText('Processing Queue')).toBeInTheDocument();
        expect(screen.getByText('45')).toBeInTheDocument(); // Queue size
        expect(screen.getByText('12.5/sec')).toBeInTheDocument(); // Processing rate
        expect(screen.getByText('150ms')).toBeInTheDocument(); // Latency
      });
    });
  });

  describe('Error Handling and Recovery', () => {
    it('should handle WebSocket reconnection gracefully', async () => {
      const mockConnect = jest.fn();
      
      // Start with disconnected state
      mockUseRealtimeClient.mockReturnValue({
        ...mockUseRealtimeClient(),
        isConnected: false,
        connectionStatus: {
          connected: false,
          connecting: false,
          error: 'Connection lost',
          lastConnected: new Date('2023-01-01T00:00:00Z'),
          reconnectAttempts: 2
        },
        connect: mockConnect
      });

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('Real-time updates unavailable')).toBeInTheDocument();
        expect(screen.getByText(/Connection lost/)).toBeInTheDocument();
      });

      // Click reconnect button
      const reconnectButton = screen.getByRole('button', { name: /reconnect/i });
      fireEvent.click(reconnectButton);

      expect(mockConnect).toHaveBeenCalled();

      // Simulate successful reconnection
      mockUseRealtimeClient.mockReturnValue({
        ...mockUseRealtimeClient(),
        isConnected: true,
        connectionStatus: {
          connected: true,
          connecting: false,
          error: null,
          lastConnected: new Date(),
          reconnectAttempts: 0
        }
      });

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('Real-time monitoring active')).toBeInTheDocument();
        expect(screen.queryByText('Real-time updates unavailable')).not.toBeInTheDocument();
      });
    });

    it('should show fallback data when real-time updates fail', async () => {
      mockUseRealtimeClient.mockReturnValue({
        ...mockUseRealtimeClient(),
        isConnected: false
      });

      // Mock API to return cached data
      mockApi.getEvents.mockResolvedValue({ 
        data: { 
          events: mockEvents,
          cached: true,
          last_updated: '2023-01-01T00:00:00Z'
        } 
      });

      render(<Events />);

      await waitFor(() => {
        expect(screen.getByText('Failed login attempt for user admin')).toBeInTheDocument();
        expect(screen.getByText(/Showing cached data/)).toBeInTheDocument();
        expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
      });
    });

    it('should handle API errors gracefully', async () => {
      mockApi.get.mockRejectedValue(new Error('API Error'));

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText(/Unable to load dashboard data/)).toBeInTheDocument();
        expect(screen.getByText(/API Error/)).toBeInTheDocument();
      });

      // Should show retry button
      const retryButton = screen.getByRole('button', { name: /retry/i });
      expect(retryButton).toBeInTheDocument();

      // Mock successful retry
      mockApi.get.mockResolvedValue({ data: mockHealthData });
      fireEvent.click(retryButton);

      await waitFor(() => {
        expect(screen.getByText('Total Events')).toBeInTheDocument();
        expect(screen.queryByText(/Unable to load dashboard data/)).not.toBeInTheDocument();
      });
    });

    it('should handle partial data loading', async () => {
      // Mock partial API failure
      mockApi.get.mockImplementation((url) => {
        if (url.includes('/health')) {
          return Promise.reject(new Error('Health API unavailable'));
        }
        return Promise.resolve({ data: mockEvents });
      });

      render(<Dashboard />);

      await waitFor(() => {
        // Events should still load
        expect(screen.getByText('Total Events')).toBeInTheDocument();
        
        // Health section should show error
        expect(screen.getByText(/Health data unavailable/)).toBeInTheDocument();
      });
    });
  });
});