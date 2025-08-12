/**
 * Tests for configuration UI validation and real-time updates.
 * 
 * Tests form validation, real-time status updates, error handling,
 * and user interaction flows for configuration components.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LogSourceManager from '../LogSourceManager';
import NotificationManager from '../NotificationManager';
import Configuration from '../Configuration';
import { api } from '../../services/api';
import * as useRealtimeClientHook from '../../hooks/useRealtimeClient';

// Mock the API
jest.mock('../../services/api', () => ({
  api: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn()
  }
}));

// Mock the realtime client hook
jest.mock('../../hooks/useRealtimeClient');

const mockApi = api as jest.Mocked<typeof api>;
const mockUseRealtimeClient = useRealtimeClientHook.useRealtimeClient as jest.MockedFunction<typeof useRealtimeClientHook.useRealtimeClient>;

describe('Configuration UI Validation', () => {
  const mockLogSources = [
    {
      id: 1,
      source_name: 'auth_logs',
      path: '/var/log/auth.log',
      source_type: 'file',
      enabled: true,
      status: 'active',
      last_monitored: '2023-01-01T00:00:00Z',
      file_size: 1024000,
      error_message: null
    },
    {
      id: 2,
      source_name: 'system_directory',
      path: '/var/log/system',
      source_type: 'directory',
      enabled: false,
      status: 'inactive',
      last_monitored: null,
      file_size: null,
      error_message: null
    },
    {
      id: 3,
      source_name: 'error_source',
      path: '/var/log/secure.log',
      source_type: 'file',
      enabled: true,
      status: 'error',
      last_monitored: '2023-01-01T00:00:00Z',
      file_size: null,
      error_message: 'Permission denied'
    }
  ];

  const mockNotificationRules = [
    {
      id: 1,
      rule_name: 'High Severity Alerts',
      enabled: true,
      min_severity: 7,
      max_severity: 10,
      categories: ['authentication', 'security'],
      channels: ['email', 'webhook'],
      email_recipients: ['admin@example.com', 'security@example.com'],
      webhook_url: 'https://hooks.example.com/security',
      throttle_minutes: 15
    },
    {
      id: 2,
      rule_name: 'System Notifications',
      enabled: false,
      min_severity: 1,
      max_severity: 5,
      categories: ['system'],
      channels: ['email'],
      email_recipients: ['ops@example.com'],
      webhook_url: null,
      throttle_minutes: 60
    }
  ];

  beforeEach(() => {
    jest.clearAllMocks();

    // Mock API responses
    mockApi.get.mockImplementation((url) => {
      if (url.includes('/log-sources')) {
        return Promise.resolve({ data: { sources: mockLogSources } });
      }
      if (url.includes('/notification-rules')) {
        return Promise.resolve({ data: { rules: mockNotificationRules } });
      }
      if (url.includes('/config')) {
        return Promise.resolve({ 
          data: { 
            log_sources: mockLogSources,
            notification_rules: mockNotificationRules,
            system_settings: {
              max_queue_size: 10000,
              batch_size: 100,
              health_check_interval: 30
            }
          } 
        });
      }
      return Promise.resolve({ data: {} });
    });

    // Mock successful save operations
    mockApi.post.mockResolvedValue({ data: { success: true, id: 999 } });
    mockApi.put.mockResolvedValue({ data: { success: true } });
    mockApi.delete.mockResolvedValue({ data: { success: true } });

    // Mock realtime client
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

  describe('Log Source Configuration', () => {
    it('should display existing log sources with status', async () => {
      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByText('Log Source Management')).toBeInTheDocument();
        expect(screen.getByText('auth_logs')).toBeInTheDocument();
        expect(screen.getByText('system_directory')).toBeInTheDocument();
        expect(screen.getByText('error_source')).toBeInTheDocument();
      });

      // Check status indicators
      expect(screen.getByText('active')).toBeInTheDocument();
      expect(screen.getByText('inactive')).toBeInTheDocument();
      expect(screen.getByText('error')).toBeInTheDocument();
      expect(screen.getByText('Permission denied')).toBeInTheDocument();
    });

    it('should validate required fields when adding new source', async () => {
      const user = userEvent.setup();
      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByText('Log Source Management')).toBeInTheDocument();
      });

      // Click add new source
      const addButton = screen.getByRole('button', { name: /add.*source/i });
      await user.click(addButton);

      // Try to save without filling required fields
      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/source name is required/i)).toBeInTheDocument();
        expect(screen.getByText(/path is required/i)).toBeInTheDocument();
      });

      // API should not have been called
      expect(mockApi.post).not.toHaveBeenCalled();
    });

    it('should validate source name format', async () => {
      const user = userEvent.setup();
      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add.*source/i })).toBeInTheDocument();
      });

      const addButton = screen.getByRole('button', { name: /add.*source/i });
      await user.click(addButton);

      // Enter invalid source name
      const nameInput = screen.getByLabelText(/source name/i);
      await user.type(nameInput, 'invalid@name!');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/source name can only contain letters, numbers, spaces, hyphens, and underscores/i)).toBeInTheDocument();
      });
    });

    it('should validate file path format', async () => {
      const user = userEvent.setup();
      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add.*source/i })).toBeInTheDocument();
      });

      const addButton = screen.getByRole('button', { name: /add.*source/i });
      await user.click(addButton);

      // Fill in valid name
      const nameInput = screen.getByLabelText(/source name/i);
      await user.type(nameInput, 'test_source');

      // Enter invalid path
      const pathInput = screen.getByLabelText(/path/i);
      await user.type(pathInput, '../../../etc/passwd'); // Directory traversal attempt

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid path format/i)).toBeInTheDocument();
      });
    });

    it('should validate file pattern for directory sources', async () => {
      const user = userEvent.setup();
      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add.*source/i })).toBeInTheDocument();
      });

      const addButton = screen.getByRole('button', { name: /add.*source/i });
      await user.click(addButton);

      // Fill in basic info
      const nameInput = screen.getByLabelText(/source name/i);
      await user.type(nameInput, 'test_directory');

      const pathInput = screen.getByLabelText(/path/i);
      await user.type(pathInput, '/var/log/test');

      // Select directory type
      const typeSelect = screen.getByLabelText(/source type/i);
      await user.selectOptions(typeSelect, 'directory');

      // Enter invalid file pattern
      const patternInput = screen.getByLabelText(/file pattern/i);
      await user.type(patternInput, '../*.log'); // Invalid pattern with directory traversal

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/file pattern cannot contain/i)).toBeInTheDocument();
      });
    });

    it('should successfully save valid log source', async () => {
      const user = userEvent.setup();
      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add.*source/i })).toBeInTheDocument();
      });

      const addButton = screen.getByRole('button', { name: /add.*source/i });
      await user.click(addButton);

      // Fill in valid data
      const nameInput = screen.getByLabelText(/source name/i);
      await user.type(nameInput, 'new_test_source');

      const pathInput = screen.getByLabelText(/path/i);
      await user.type(pathInput, '/var/log/test.log');

      const descriptionInput = screen.getByLabelText(/description/i);
      await user.type(descriptionInput, 'Test log source for validation');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockApi.post).toHaveBeenCalledWith('/api/log-sources', {
          source_name: 'new_test_source',
          path: '/var/log/test.log',
          source_type: 'file',
          enabled: true,
          description: 'Test log source for validation',
          recursive: false,
          file_pattern: '',
          polling_interval: 1.0,
          priority: 5
        });
      });

      expect(screen.getByText(/source saved successfully/i)).toBeInTheDocument();
    });

    it('should handle duplicate source names', async () => {
      const user = userEvent.setup();
      
      // Mock API to return conflict error
      mockApi.post.mockRejectedValueOnce({
        response: {
          status: 409,
          data: { error: 'Source name already exists' }
        }
      });

      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add.*source/i })).toBeInTheDocument();
      });

      const addButton = screen.getByRole('button', { name: /add.*source/i });
      await user.click(addButton);

      // Use existing source name
      const nameInput = screen.getByLabelText(/source name/i);
      await user.type(nameInput, 'auth_logs');

      const pathInput = screen.getByLabelText(/path/i);
      await user.type(pathInput, '/var/log/duplicate.log');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/source name already exists/i)).toBeInTheDocument();
      });
    });

    it('should update source status in real-time', async () => {
      const mockSubscribeToSystemStatus = jest.fn();
      
      mockUseRealtimeClient.mockReturnValue({
        ...mockUseRealtimeClient(),
        subscribeToSystemStatus: mockSubscribeToSystemStatus
      });

      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByText('auth_logs')).toBeInTheDocument();
        expect(screen.getByText('active')).toBeInTheDocument();
      });

      // Simulate real-time status update
      const statusCallback = mockSubscribeToSystemStatus.mock.calls[0]?.[0];
      if (statusCallback) {
        statusCallback({
          component: 'file_monitor',
          source_name: 'auth_logs',
          status: 'error',
          error_message: 'File not found',
          last_monitored: new Date().toISOString()
        });
      }

      await waitFor(() => {
        expect(screen.getByText('error')).toBeInTheDocument();
        expect(screen.getByText('File not found')).toBeInTheDocument();
      });
    });

    it('should test log source connectivity', async () => {
      const user = userEvent.setup();
      
      mockApi.post.mockImplementation((url) => {
        if (url.includes('/test')) {
          return Promise.resolve({ 
            data: { 
              success: true, 
              readable: true,
              file_size: 2048,
              last_modified: '2023-01-01T00:00:00Z'
            } 
          });
        }
        return Promise.resolve({ data: { success: true } });
      });

      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByText('auth_logs')).toBeInTheDocument();
      });

      // Find and click test button for auth_logs
      const authLogsRow = screen.getByText('auth_logs').closest('tr');
      const testButton = within(authLogsRow!).getByRole('button', { name: /test/i });
      await user.click(testButton);

      await waitFor(() => {
        expect(mockApi.post).toHaveBeenCalledWith('/api/log-sources/1/test');
        expect(screen.getByText(/test successful/i)).toBeInTheDocument();
        expect(screen.getByText(/file size: 2048 bytes/i)).toBeInTheDocument();
      });
    });
  });

  describe('Notification Rule Configuration', () => {
    it('should display existing notification rules', async () => {
      render(<NotificationManager />);

      await waitFor(() => {
        expect(screen.getByText('Notification Rules')).toBeInTheDocument();
        expect(screen.getByText('High Severity Alerts')).toBeInTheDocument();
        expect(screen.getByText('System Notifications')).toBeInTheDocument();
      });

      // Check enabled/disabled status
      expect(screen.getByText('Enabled')).toBeInTheDocument();
      expect(screen.getByText('Disabled')).toBeInTheDocument();
    });

    it('should validate severity range', async () => {
      const user = userEvent.setup();
      render(<NotificationManager />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add.*rule/i })).toBeInTheDocument();
      });

      const addButton = screen.getByRole('button', { name: /add.*rule/i });
      await user.click(addButton);

      // Fill in basic info
      const nameInput = screen.getByLabelText(/rule name/i);
      await user.type(nameInput, 'Test Rule');

      // Set invalid severity range (max < min)
      const minSeverityInput = screen.getByLabelText(/minimum severity/i);
      await user.clear(minSeverityInput);
      await user.type(minSeverityInput, '8');

      const maxSeverityInput = screen.getByLabelText(/maximum severity/i);
      await user.clear(maxSeverityInput);
      await user.type(maxSeverityInput, '5');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/maximum severity must be greater than or equal to minimum severity/i)).toBeInTheDocument();
      });
    });

    it('should validate email addresses', async () => {
      const user = userEvent.setup();
      render(<NotificationManager />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add.*rule/i })).toBeInTheDocument();
      });

      const addButton = screen.getByRole('button', { name: /add.*rule/i });
      await user.click(addButton);

      // Fill in basic info
      const nameInput = screen.getByLabelText(/rule name/i);
      await user.type(nameInput, 'Email Test Rule');

      // Select email channel
      const emailCheckbox = screen.getByLabelText(/email/i);
      await user.click(emailCheckbox);

      // Enter invalid email addresses
      const emailInput = screen.getByLabelText(/email recipients/i);
      await user.type(emailInput, 'invalid-email, another@invalid, valid@example.com');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid email format/i)).toBeInTheDocument();
      });
    });

    it('should validate webhook URL format', async () => {
      const user = userEvent.setup();
      render(<NotificationManager />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add.*rule/i })).toBeInTheDocument();
      });

      const addButton = screen.getByRole('button', { name: /add.*rule/i });
      await user.click(addButton);

      // Fill in basic info
      const nameInput = screen.getByLabelText(/rule name/i);
      await user.type(nameInput, 'Webhook Test Rule');

      // Select webhook channel
      const webhookCheckbox = screen.getByLabelText(/webhook/i);
      await user.click(webhookCheckbox);

      // Enter invalid webhook URL
      const webhookInput = screen.getByLabelText(/webhook url/i);
      await user.type(webhookInput, 'not-a-valid-url');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/webhook url must be a valid http/i)).toBeInTheDocument();
      });
    });

    it('should require at least one notification channel', async () => {
      const user = userEvent.setup();
      render(<NotificationManager />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add.*rule/i })).toBeInTheDocument();
      });

      const addButton = screen.getByRole('button', { name: /add.*rule/i });
      await user.click(addButton);

      // Fill in basic info without selecting any channels
      const nameInput = screen.getByLabelText(/rule name/i);
      await user.type(nameInput, 'No Channel Rule');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/at least one notification channel must be selected/i)).toBeInTheDocument();
      });
    });

    it('should successfully save valid notification rule', async () => {
      const user = userEvent.setup();
      render(<NotificationManager />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add.*rule/i })).toBeInTheDocument();
      });

      const addButton = screen.getByRole('button', { name: /add.*rule/i });
      await user.click(addButton);

      // Fill in valid data
      const nameInput = screen.getByLabelText(/rule name/i);
      await user.type(nameInput, 'New Alert Rule');

      const minSeverityInput = screen.getByLabelText(/minimum severity/i);
      await user.clear(minSeverityInput);
      await user.type(minSeverityInput, '6');

      const maxSeverityInput = screen.getByLabelText(/maximum severity/i);
      await user.clear(maxSeverityInput);
      await user.type(maxSeverityInput, '10');

      // Select email channel
      const emailCheckbox = screen.getByLabelText(/email/i);
      await user.click(emailCheckbox);

      const emailInput = screen.getByLabelText(/email recipients/i);
      await user.type(emailInput, 'test@example.com, admin@example.com');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockApi.post).toHaveBeenCalledWith('/api/notification-rules', {
          rule_name: 'New Alert Rule',
          enabled: true,
          min_severity: 6,
          max_severity: 10,
          categories: [],
          channels: ['email'],
          email_recipients: ['test@example.com', 'admin@example.com'],
          webhook_url: '',
          throttle_minutes: 0
        });
      });

      expect(screen.getByText(/rule saved successfully/i)).toBeInTheDocument();
    });

    it('should test notification delivery', async () => {
      const user = userEvent.setup();
      
      mockApi.post.mockImplementation((url) => {
        if (url.includes('/test')) {
          return Promise.resolve({ 
            data: { 
              success: true, 
              message: 'Test notification sent successfully',
              delivery_results: {
                email: { success: true, recipients: 2 },
                webhook: { success: true, response_code: 200 }
              }
            } 
          });
        }
        return Promise.resolve({ data: { success: true } });
      });

      render(<NotificationManager />);

      await waitFor(() => {
        expect(screen.getByText('High Severity Alerts')).toBeInTheDocument();
      });

      // Find and click test button for High Severity Alerts
      const alertsRow = screen.getByText('High Severity Alerts').closest('tr');
      const testButton = within(alertsRow!).getByRole('button', { name: /test/i });
      await user.click(testButton);

      await waitFor(() => {
        expect(mockApi.post).toHaveBeenCalledWith('/api/notification-rules/1/test');
        expect(screen.getByText(/test notification sent successfully/i)).toBeInTheDocument();
        expect(screen.getByText(/email: 2 recipients/i)).toBeInTheDocument();
        expect(screen.getByText(/webhook: 200/i)).toBeInTheDocument();
      });
    });
  });

  describe('Configuration Integration', () => {
    it('should display comprehensive configuration overview', async () => {
      render(<Configuration />);

      await waitFor(() => {
        expect(screen.getByText('System Configuration')).toBeInTheDocument();
        expect(screen.getByText('Log Sources')).toBeInTheDocument();
        expect(screen.getByText('Notification Rules')).toBeInTheDocument();
        expect(screen.getByText('System Settings')).toBeInTheDocument();
      });

      // Should show counts
      expect(screen.getByText('3 sources configured')).toBeInTheDocument();
      expect(screen.getByText('2 rules configured')).toBeInTheDocument();
    });

    it('should validate system settings', async () => {
      const user = userEvent.setup();
      render(<Configuration />);

      await waitFor(() => {
        expect(screen.getByText('System Settings')).toBeInTheDocument();
      });

      // Find system settings section
      const queueSizeInput = screen.getByLabelText(/max queue size/i);
      await user.clear(queueSizeInput);
      await user.type(queueSizeInput, '0'); // Invalid value

      const batchSizeInput = screen.getByLabelText(/batch size/i);
      await user.clear(batchSizeInput);
      await user.type(batchSizeInput, '10000'); // Too large

      const saveSettingsButton = screen.getByRole('button', { name: /save settings/i });
      await user.click(saveSettingsButton);

      await waitFor(() => {
        expect(screen.getByText(/queue size must be greater than 0/i)).toBeInTheDocument();
        expect(screen.getByText(/batch size must be less than/i)).toBeInTheDocument();
      });
    });

    it('should show configuration validation summary', async () => {
      // Mock API to return validation results
      mockApi.get.mockImplementation((url) => {
        if (url.includes('/validate')) {
          return Promise.resolve({ 
            data: { 
              valid: false,
              issues: [
                { type: 'error', component: 'log_source', message: 'Source "error_source" has permission issues' },
                { type: 'warning', component: 'notification', message: 'No notification rules for low severity events' },
                { type: 'info', component: 'system', message: 'Queue size is set to default value' }
              ]
            } 
          });
        }
        return mockApi.get(url);
      });

      render(<Configuration />);

      await waitFor(() => {
        expect(screen.getByText('Configuration Validation')).toBeInTheDocument();
      });

      // Click validate button
      const validateButton = screen.getByRole('button', { name: /validate configuration/i });
      fireEvent.click(validateButton);

      await waitFor(() => {
        expect(screen.getByText(/permission issues/i)).toBeInTheDocument();
        expect(screen.getByText(/no notification rules for low severity/i)).toBeInTheDocument();
        expect(screen.getByText(/queue size is set to default/i)).toBeInTheDocument();
      });

      // Should show issue counts
      expect(screen.getByText('1 error')).toBeInTheDocument();
      expect(screen.getByText('1 warning')).toBeInTheDocument();
      expect(screen.getByText('1 info')).toBeInTheDocument();
    });

    it('should handle configuration export/import', async () => {
      const user = userEvent.setup();
      
      // Mock export API
      mockApi.get.mockImplementation((url) => {
        if (url.includes('/export')) {
          return Promise.resolve({ 
            data: {
              version: '1.0',
              exported_at: '2023-01-01T00:00:00Z',
              log_sources: mockLogSources,
              notification_rules: mockNotificationRules,
              system_settings: {
                max_queue_size: 10000,
                batch_size: 100
              }
            }
          });
        }
        return mockApi.get(url);
      });

      render(<Configuration />);

      await waitFor(() => {
        expect(screen.getByText('System Configuration')).toBeInTheDocument();
      });

      // Test export
      const exportButton = screen.getByRole('button', { name: /export configuration/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(mockApi.get).toHaveBeenCalledWith('/api/config/export');
        expect(screen.getByText(/configuration exported successfully/i)).toBeInTheDocument();
      });

      // Test import validation
      const importButton = screen.getByRole('button', { name: /import configuration/i });
      await user.click(importButton);

      // Mock file input (simplified)
      const fileInput = screen.getByLabelText(/select configuration file/i);
      const invalidFile = new File(['invalid json'], 'config.json', { type: 'application/json' });
      
      await user.upload(fileInput, invalidFile);

      await waitFor(() => {
        expect(screen.getByText(/invalid configuration file format/i)).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling and Recovery', () => {
    it('should handle network errors gracefully', async () => {
      const user = userEvent.setup();
      
      // Mock network error
      mockApi.get.mockRejectedValue(new Error('Network error'));

      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load log sources/i)).toBeInTheDocument();
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });

      // Should show retry button
      const retryButton = screen.getByRole('button', { name: /retry/i });
      expect(retryButton).toBeInTheDocument();

      // Mock successful retry
      mockApi.get.mockResolvedValue({ data: { sources: mockLogSources } });
      await user.click(retryButton);

      await waitFor(() => {
        expect(screen.getByText('auth_logs')).toBeInTheDocument();
        expect(screen.queryByText(/failed to load/i)).not.toBeInTheDocument();
      });
    });

    it('should handle validation errors from server', async () => {
      const user = userEvent.setup();
      
      // Mock server validation error
      mockApi.post.mockRejectedValue({
        response: {
          status: 400,
          data: {
            error: 'Validation failed',
            details: {
              source_name: ['Source name already exists'],
              path: ['Path is not accessible']
            }
          }
        }
      });

      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add.*source/i })).toBeInTheDocument();
      });

      const addButton = screen.getByRole('button', { name: /add.*source/i });
      await user.click(addButton);

      // Fill in form
      const nameInput = screen.getByLabelText(/source name/i);
      await user.type(nameInput, 'duplicate_name');

      const pathInput = screen.getByLabelText(/path/i);
      await user.type(pathInput, '/inaccessible/path.log');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('Source name already exists')).toBeInTheDocument();
        expect(screen.getByText('Path is not accessible')).toBeInTheDocument();
      });
    });

    it('should handle partial save failures', async () => {
      const user = userEvent.setup();
      
      // Mock partial failure
      mockApi.post.mockResolvedValue({
        data: {
          success: false,
          saved: ['source_name', 'path'],
          failed: ['file_pattern'],
          errors: {
            file_pattern: 'Invalid pattern syntax'
          }
        }
      });

      render(<LogSourceManager />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add.*source/i })).toBeInTheDocument();
      });

      const addButton = screen.getByRole('button', { name: /add.*source/i });
      await user.click(addButton);

      // Fill in form with problematic pattern
      const nameInput = screen.getByLabelText(/source name/i);
      await user.type(nameInput, 'partial_save_test');

      const pathInput = screen.getByLabelText(/path/i);
      await user.type(pathInput, '/var/log/test');

      const typeSelect = screen.getByLabelText(/source type/i);
      await user.selectOptions(typeSelect, 'directory');

      const patternInput = screen.getByLabelText(/file pattern/i);
      await user.type(patternInput, '[invalid-regex');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/partially saved/i)).toBeInTheDocument();
        expect(screen.getByText('Invalid pattern syntax')).toBeInTheDocument();
      });
    });
  });
});