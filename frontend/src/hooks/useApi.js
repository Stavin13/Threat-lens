import { useState, useEffect, useCallback } from 'react';
import { apiService } from '../services/api';

// Generic hook for API calls
export function useApi(apiCall, dependencies = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('useApi: Starting API call');
      const result = await apiCall();
      console.log('useApi: API call successful', result);
      setData(result);
    } catch (err) {
      console.error('useApi: API call failed', err);
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  }, dependencies);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

// Specific hooks for different endpoints
export function useStats() {
  return useApi(() => apiService.getStats());
}

export function useHealth() {
  return useApi(() => apiService.getHealth());
}

export function useEvents(filters = {}) {
  return useApi(() => apiService.getEvents(filters), [JSON.stringify(filters)]);
}

export function useEvent(id) {
  return useApi(() => apiService.getEvent(id), [id]);
}

export function useRealtimeStatus() {
  return useApi(() => apiService.getRealtimeStatus());
}

export function useRealtimeMetrics() {
  return useApi(() => apiService.getRealtimeMetrics());
}

export function useReports() {
  return useApi(() => apiService.getReports());
}

export function useSchedulerStatus() {
  return useApi(() => apiService.getSchedulerStatus());
}

// Hook for WebSocket connection
export function useWebSocket() {
  const [status, setStatus] = useState('disconnected');
  const [lastMessage, setLastMessage] = useState(null);

  useEffect(() => {
    import('../services/websocket').then(({ wsService }) => {
      const handleConnection = (data) => {
        setStatus(data.status);
      };

      const handleMessage = (data) => {
        setLastMessage(data);
      };

      wsService.on('connection', handleConnection);
      wsService.on('message', handleMessage);
      wsService.connect();

      return () => {
        wsService.off('connection', handleConnection);
        wsService.off('message', handleMessage);
      };
    });
  }, []);

  return { status, lastMessage };
}

// Hook for polling data at intervals
export function usePolling(apiCall, interval = 30000, dependencies = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let intervalId;

    const fetchData = async () => {
      try {
        setError(null);
        const result = await apiCall();
        setData(result);
        setLoading(false);
      } catch (err) {
        setError(err.message || 'An error occurred');
        setLoading(false);
      }
    };

    // Initial fetch
    fetchData();

    // Set up polling
    intervalId = setInterval(fetchData, interval);

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, dependencies);

  return { data, loading, error };
}