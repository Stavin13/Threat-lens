// Use proxy in development, direct URL in production
const API_BASE = import.meta.env.DEV 
  ? '/api'  // Use proxy path in development
  : (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');

import { authService } from './auth';

class ApiService {
  constructor() {
    this.baseURL = API_BASE;
    console.log('API Service initialized with base URL:', this.baseURL);
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    console.log(`API Request: ${url}`, config);

    try {
      // Attach auth header if available
      const token = authService.getToken();
      if (token) {
        config.headers = { ...config.headers, Authorization: `Bearer ${token}` };
      }

      const response = await fetch(url, config);
      
      console.log(`API Response: ${url}`, {
        status: response.status,
        statusText: response.statusText,
        headers: Object.fromEntries(response.headers.entries())
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error(`API Error Response: ${url}`, errorText);
        throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
      }

      // Handle different content types
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        const data = await response.json();
        console.log(`API Success: ${url}`, data);
        return data;
      }
      const text = await response.text();
      console.log(`API Success (text): ${url}`, text);
      return text;
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error);
      throw error;
    }
  }

  // Health & Status
  async getHealth() {
    return this.request('/health');
  }

  async getHealthSimple() {
    return this.request('/health-simple');
  }

  async getStats() {
    return this.request('/stats');
  }

  // Events
  async getEvents(params = {}) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value);
      }
    });
    
    const queryString = searchParams.toString();
    const endpoint = queryString ? `/events?${queryString}` : '/events';
    return this.request(endpoint);
  }

  async getEvent(id) {
    return this.request(`/event/${id}`);
  }

  // Log Ingestion
  async ingestFile(file, source = 'frontend') {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source', source);

    return this.request('/ingest-log', {
      method: 'POST',
      headers: {}, // Remove Content-Type to let browser set it for FormData
      body: formData,
    });
  }

  async ingestText(content, source = 'frontend') {
    return this.request('/api/ingest/text', {
      method: 'POST',
      body: JSON.stringify({ content, source }),
    });
  }

  // Real-time Monitoring
  async getRealtimeStatus() {
    return this.request('/realtime/status');
  }

  async getRealtimeMetrics() {
    // Backend exposes general API metrics at /metrics
    return this.request('/metrics');
  }

  async getMonitoringConfig() {
    // Backend route is /realtime/config
    return this.request('/realtime/config');
  }

  // Reports
  async getReports() {
    return this.request('/reports/files');
  }

  async triggerReport() {
    return this.request('/scheduler/trigger-report', {
      method: 'POST',
    });
  }

  async getSchedulerStatus() {
    return this.request('/scheduler/status');
  }

  // WebSocket Info
  async getWebSocketInfo() {
    return this.request('/ws/info');
  }

  // Processing Control
  async triggerProcessing(rawLogId) {
    return this.request(`/trigger-processing/${rawLogId}`, {
      method: 'POST',
    });
  }
}

export const apiService = new ApiService();
export default apiService;