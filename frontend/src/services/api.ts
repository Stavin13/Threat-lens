import axios from 'axios';
import { EventResponse, EventFilter, IngestionRequest, IngestionResult, LogSourceConfigRequest, MonitoringConfig, LogSourceConfig, NotificationRuleRequest, NotificationRule } from '../types';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  // Generic HTTP methods
  get: async (url: string, config?: any) => {
    return await apiClient.get(url, config);
  },

  post: async (url: string, data?: any, config?: any) => {
    return await apiClient.post(url, data, config);
  },

  put: async (url: string, data?: any, config?: any) => {
    return await apiClient.put(url, data, config);
  },

  delete: async (url: string, config?: any) => {
    return await apiClient.delete(url, config);
  },

  // Event endpoints
  getEvents: async (filters?: EventFilter): Promise<EventResponse[]> => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          params.append(key, value.toString());
        }
      });
    }
    
    const response = await apiClient.get(`/events?${params.toString()}`);
    return response.data;
  },

  getEvent: async (id: string): Promise<EventResponse> => {
    const response = await apiClient.get(`/event/${id}`);
    return response.data;
  },

  // Ingestion endpoints
  ingestLog: async (data: IngestionRequest): Promise<IngestionResult> => {
    const response = await apiClient.post('/ingest-log', data);
    return response.data;
  },

  ingestLogFile: async (file: File): Promise<IngestionResult> => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await apiClient.post('/ingest-log', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Report endpoints
  getDailyReport: async (date?: string): Promise<Blob> => {
    const params = date ? `?date=${date}` : '';
    const response = await apiClient.get(`/report/daily${params}`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Health endpoints
  getHealthSummary: async () => {
    const response = await apiClient.get('/api/health/');
    return response.data;
  },

  getSystemMetrics: async (hours: number = 1) => {
    const response = await apiClient.get(`/api/health/metrics/system?hours=${hours}`);
    return response.data;
  },

  getComponentMetrics: async () => {
    const response = await apiClient.get('/api/health/metrics/components');
    return response.data;
  },

  getPrometheusMetrics: async () => {
    const response = await apiClient.get('/api/health/metrics/prometheus');
    return response.data;
  },

  // Configuration Management endpoints
  getMonitoringConfig: async (): Promise<MonitoringConfig> => {
    const response = await apiClient.get('/realtime/config');
    return response.data;
  },

  getConfigSummary: async (): Promise<any> => {
    const response = await apiClient.get('/realtime/config/summary');
    return response.data;
  },

  validateConfig: async (): Promise<any> => {
    const response = await apiClient.get('/realtime/config/validate');
    return response.data;
  },

  // Log Source Management endpoints
  getLogSources: async (): Promise<LogSourceConfig[]> => {
    const response = await apiClient.get('/realtime/log-sources');
    return response.data;
  },

  getLogSource: async (sourceName: string): Promise<LogSourceConfig> => {
    const response = await apiClient.get(`/realtime/log-sources/${sourceName}`);
    return response.data;
  },

  createLogSource: async (data: LogSourceConfigRequest): Promise<LogSourceConfig> => {
    const response = await apiClient.post('/realtime/log-sources', data);
    return response.data;
  },

  updateLogSource: async (sourceName: string, data: LogSourceConfigRequest): Promise<LogSourceConfig> => {
    const response = await apiClient.put(`/realtime/log-sources/${sourceName}`, data);
    return response.data;
  },

  deleteLogSource: async (sourceName: string): Promise<{ message: string }> => {
    const response = await apiClient.delete(`/realtime/log-sources/${sourceName}`);
    return response.data;
  },

  testLogSource: async (sourceName: string): Promise<{ status: string; message: string; details?: any }> => {
    const response = await apiClient.post(`/realtime/log-sources/${sourceName}/test`);
    return response.data;
  },

  getLogSourceHealth: async (sourceName: string): Promise<any> => {
    const response = await apiClient.get(`/api/health/components/log_source_${sourceName}`);
    return response.data;
  },

  // Notification Rule Management endpoints
  getNotificationRules: async (): Promise<NotificationRule[]> => {
    const response = await apiClient.get('/realtime/notification-rules');
    return response.data;
  },

  getNotificationRule: async (ruleName: string): Promise<NotificationRule> => {
    const response = await apiClient.get(`/realtime/notification-rules/${ruleName}`);
    return response.data;
  },

  createNotificationRule: async (data: NotificationRuleRequest): Promise<NotificationRule> => {
    const response = await apiClient.post('/realtime/notification-rules', data);
    return response.data;
  },

  updateNotificationRule: async (ruleName: string, data: NotificationRuleRequest): Promise<NotificationRule> => {
    const response = await apiClient.put(`/realtime/notification-rules/${ruleName}`, data);
    return response.data;
  },

  deleteNotificationRule: async (ruleName: string): Promise<{ message: string }> => {
    const response = await apiClient.delete(`/realtime/notification-rules/${ruleName}`);
    return response.data;
  },

  testNotificationRule: async (ruleName: string, testData: any): Promise<{ message: string }> => {
    const response = await apiClient.post(`/realtime/notification-rules/${ruleName}/test`, testData);
    return response.data;
  },

  getNotificationHistory: async (limit: number = 50): Promise<any[]> => {
    const response = await apiClient.get(`/realtime/notification-history?limit=${limit}`);
    return response.data;
  },
};

// Request interceptor for adding auth headers if needed
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Log error details
    console.error('API Error:', {
      url: error.config?.url,
      method: error.config?.method,
      status: error.response?.status,
      data: error.response?.data,
      correlationId: error.response?.headers['x-correlation-id']
    });

    // Handle specific error cases
    if (error.response?.status === 401) {
      // Handle unauthorized access
      localStorage.removeItem('auth_token');
      // Don't redirect in development to avoid disrupting the dev experience
      if (process.env.NODE_ENV === 'production') {
        window.location.href = '/login';
      }
    } else if (error.response?.status === 429) {
      // Rate limiting - add retry after header info
      const retryAfter = error.response.headers['retry-after'];
      if (retryAfter) {
        error.retryAfter = parseInt(retryAfter, 10);
      }
    } else if (error.response?.status >= 500) {
      // Server errors - add context for user-friendly messages
      error.isServerError = true;
    } else if (!error.response) {
      // Network errors
      error.isNetworkError = true;
    }

    return Promise.reject(error);
  }
);

export default api;