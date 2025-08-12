import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import { EventResponse } from '../types';
import SeverityChart from './SeverityChart';
import ConnectionStatus from './ConnectionStatus';
import { useSecurityEvents } from '../hooks/useRealtimeClient';
import { useRealtimeClient } from '../hooks/useRealtimeClient';
import type { SystemStatusData, ProcessingUpdateData, HealthCheckData } from '../services/realtimeClient';

interface HealthSummary {
  overall_status: string;
  timestamp: string;
  uptime_seconds: number;
  monitoring_active: boolean;
  component_health: Record<string, {
    status: string;
    message: string;
    latency_ms?: number;
    last_check: string;
  }>;
  system_metrics?: {
    cpu_percent: number;
    memory_percent: number;
    memory_used_mb: number;
    memory_total_mb: number;
    disk_percent: number;
    disk_used_gb: number;
    disk_total_gb: number;
    load_average: number[];
    timestamp: string;
  };
  component_metrics: Record<string, {
    component: string;
    processing_rate: number;
    average_latency_ms: number;
    error_rate: number;
    queue_size: number;
    active_connections: number;
    uptime_seconds: number;
    timestamp: string;
  }>;
}

const Dashboard: React.FC = () => {
  const [healthData, setHealthData] = useState<HealthSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<number | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  
  // Real-time event counters
  const [eventCounts, setEventCounts] = useState({
    total: 0,
    high_severity: 0,
    medium_severity: 0,
    low_severity: 0,
    last_hour: 0
  });
  
  // Real-time processing metrics
  const [processingMetrics, setProcessingMetrics] = useState({
    processing_rate: 0,
    queue_size: 0,
    active_sources: 0,
    errors_per_minute: 0
  });

  // Use WebSocket for real-time events
  const {
    events: realtimeEvents,
    connectionStatus,
    isConnected,
    connect: reconnectWebSocket
  } = useSecurityEvents();

  // Use enhanced realtime client for system status and processing updates
  const {
    lastSystemStatus,
    lastProcessingUpdate,
    lastHealthCheck,
    isConnected: realtimeConnected,
    connect: connectRealtime
  } = useRealtimeClient({
    onSystemStatus: (data: SystemStatusData) => {
      console.log('System status update:', data);
      // Update health data with real-time system status
      if (data.component && data.status) {
        setHealthData(prev => {
          if (!prev) return prev;
          return {
            ...prev,
            component_health: {
              ...prev.component_health,
              [data.component]: {
                status: data.status,
                message: data.status === 'healthy' ? 'Operating normally' : 'Issues detected',
                last_check: new Date().toISOString()
              }
            }
          };
        });
      }
    },
    onProcessingUpdate: (data: ProcessingUpdateData) => {
      console.log('Processing update:', data);
      // Update processing metrics
      setProcessingMetrics(prev => ({
        ...prev,
        queue_size: prev.queue_size + (data.status === 'completed' ? -1 : 1),
        processing_rate: data.processing_time ? 1000 / data.processing_time : prev.processing_rate
      }));
    },
    onHealthCheck: (data: HealthCheckData) => {
      console.log('Health check update:', data);
      // Update overall health status
      setHealthData(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          overall_status: data.overall_status,
          component_health: data.components ? 
            Object.fromEntries(
              Object.entries(data.components).map(([key, value]) => [
                key, 
                {
                  status: value.status || 'unknown',
                  message: value.message || 'No message',
                  last_check: data.timestamp
                }
              ])
            ) : prev.component_health
        };
      });
    }
  });

  // Fetch initial data and health status
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        setLoading(true);
        
        // Fetch health data and initial events
        const [healthResponse, eventsResponse] = await Promise.all([
          api.get('/api/health/'),
          api.getEvents({ per_page: 50 }) // Get recent events for initial load
        ]);
        
        setHealthData(healthResponse.data);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch initial data:', err);
        setError('Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };

    fetchInitialData();
  }, []);

  // Update health data periodically (less frequently since events are real-time)
  useEffect(() => {
    const fetchHealthData = async () => {
      try {
        const healthResponse = await api.get('/api/health/');
        setHealthData(healthResponse.data);
        setLastUpdate(new Date());
      } catch (err) {
        console.error('Failed to fetch health data:', err);
      }
    };

    // Update health data every 30 seconds
    const healthInterval = setInterval(fetchHealthData, 30000);

    return () => clearInterval(healthInterval);
  }, []);

  // Handle real-time event updates and calculate metrics
  const handleRealtimeUpdate = useCallback(() => {
    setLastUpdate(new Date());
    
    // Calculate event counts and metrics
    const now = new Date();
    const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
    
    const recentEvents = realtimeEvents.filter(event => 
      new Date(event.event.timestamp) > oneHourAgo
    );
    
    const highSeverityCount = realtimeEvents.filter(event => 
      (event.analysis?.severity_score || 0) >= 7
    ).length;
    
    const mediumSeverityCount = realtimeEvents.filter(event => {
      const severity = event.analysis?.severity_score || 0;
      return severity >= 4 && severity < 7;
    }).length;
    
    const lowSeverityCount = realtimeEvents.filter(event => 
      (event.analysis?.severity_score || 0) < 4
    ).length;
    
    setEventCounts({
      total: realtimeEvents.length,
      high_severity: highSeverityCount,
      medium_severity: mediumSeverityCount,
      low_severity: lowSeverityCount,
      last_hour: recentEvents.length
    });
  }, [realtimeEvents]);

  useEffect(() => {
    handleRealtimeUpdate();
  }, [realtimeEvents, handleRealtimeUpdate]);

  // Handle severity filter from chart click
  const handleSeverityClick = (severity: number) => {
    setSeverityFilter(severityFilter === severity ? null : severity);
  };

  // Combine real-time events with any cached events and filter
  const allEvents = realtimeEvents;
  const filteredEvents = severityFilter 
    ? allEvents.filter(event => event.analysis?.severity_score === severityFilter)
    : allEvents;

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy':
        return 'bg-green-500';
      case 'warning':
        return 'bg-yellow-500';
      case 'critical':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy':
        return '✓';
      case 'warning':
        return '⚠';
      case 'critical':
        return '!';
      default:
        return '?';
    }
  };

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) {
      return `${days}d ${hours}h ${minutes}m`;
    } else if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else {
      return `${minutes}m`;
    }
  };

  const formatBytes = (bytes: number, decimals = 1) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="border-b border-gray-200 pb-4">
          <h1 className="text-2xl font-bold text-gray-900">Security Dashboard</h1>
          <p className="text-gray-600 mt-1">Loading system status...</p>
        </div>
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="border-b border-gray-200 pb-4">
          <h1 className="text-2xl font-bold text-gray-900">Security Dashboard</h1>
          <p className="text-red-600 mt-1">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="border-b border-gray-200 pb-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Security Dashboard</h1>
            <p className="text-gray-600 mt-1">
              Overview of security events and system status
            </p>
          </div>
          <div className="flex items-center space-x-4">
            <div className="text-sm text-gray-500">
              Last updated: {lastUpdate.toLocaleTimeString()}
            </div>
            <ConnectionStatus 
              status={connectionStatus} 
              onReconnect={reconnectWebSocket}
              className="border-l pl-4"
            />
          </div>
        </div>
      </div>

      {/* Real-time Event Counters */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-bold">📊</span>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Total Events
                  </dt>
                  <dd className="text-lg font-medium text-gray-900">
                    {eventCounts.total.toLocaleString()}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-red-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-bold">🚨</span>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    High Severity
                  </dt>
                  <dd className="text-lg font-medium text-gray-900">
                    {eventCounts.high_severity}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-yellow-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-bold">⚠️</span>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Medium Severity
                  </dt>
                  <dd className="text-lg font-medium text-gray-900">
                    {eventCounts.medium_severity}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-bold">ℹ️</span>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Low Severity
                  </dt>
                  <dd className="text-lg font-medium text-gray-900">
                    {eventCounts.low_severity}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-purple-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-bold">⏰</span>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Last Hour
                  </dt>
                  <dd className="text-lg font-medium text-gray-900">
                    {eventCounts.last_hour}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* System Health Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className={`w-8 h-8 ${getStatusColor(healthData?.overall_status || 'unknown')} rounded-full flex items-center justify-center`}>
                  <span className="text-white text-sm font-bold">
                    {getStatusIcon(healthData?.overall_status || 'unknown')}
                  </span>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Overall System Status
                  </dt>
                  <dd className="text-lg font-medium text-gray-900 capitalize">
                    {healthData?.overall_status || 'Unknown'}
                    {realtimeConnected && (
                      <span className="ml-2 inline-flex items-center">
                        <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                      </span>
                    )}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-bold">⏱</span>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    System Uptime
                  </dt>
                  <dd className="text-lg font-medium text-gray-900">
                    {healthData?.uptime_seconds ? formatUptime(healthData.uptime_seconds) : '--'}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-purple-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-bold">💾</span>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Memory Usage
                  </dt>
                  <dd className="text-lg font-medium text-gray-900">
                    {healthData?.system_metrics ? 
                      `${healthData.system_metrics.memory_percent.toFixed(1)}%` : '--'}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-orange-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-bold">🖥</span>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    CPU Usage
                  </dt>
                  <dd className="text-lg font-medium text-gray-900">
                    {healthData?.system_metrics ? 
                      `${healthData.system_metrics.cpu_percent.toFixed(1)}%` : '--'}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Real-time Processing Metrics */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-gray-900">
            Real-time Processing Metrics
          </h2>
          {realtimeConnected && (
            <div className="flex items-center text-sm text-green-600">
              <div className="w-2 h-2 bg-green-500 rounded-full mr-1 animate-pulse"></div>
              Live Updates
            </div>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">
              {processingMetrics.processing_rate.toFixed(1)}
            </div>
            <div className="text-sm text-gray-500">Events/sec</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">
              {processingMetrics.queue_size}
            </div>
            <div className="text-sm text-gray-500">Queue Size</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">
              {processingMetrics.active_sources}
            </div>
            <div className="text-sm text-gray-500">Active Sources</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600">
              {processingMetrics.errors_per_minute.toFixed(1)}
            </div>
            <div className="text-sm text-gray-500">Errors/min</div>
          </div>
        </div>
      </div>

      {/* Component Health Status */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">
          Component Health Status
        </h2>
        {healthData?.component_health && Object.keys(healthData.component_health).length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(healthData.component_health).map(([component, health]) => (
              <div key={component} className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium text-gray-900 capitalize">
                    {component.replace('_', ' ')}
                  </h3>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    health.status === 'healthy' ? 'bg-green-100 text-green-800' :
                    health.status === 'warning' ? 'bg-yellow-100 text-yellow-800' :
                    health.status === 'critical' ? 'bg-red-100 text-red-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {health.status}
                  </span>
                </div>
                <p className="text-sm text-gray-600 mb-2">{health.message}</p>
                {health.latency_ms && (
                  <p className="text-xs text-gray-500">
                    Latency: {health.latency_ms.toFixed(1)}ms
                  </p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <p>No component health data available</p>
          </div>
        )}
      </div>

      {/* System Metrics */}
      {healthData?.system_metrics && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            System Resource Metrics
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <h3 className="text-sm font-medium text-gray-500 mb-2">Memory</h3>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Used:</span>
                  <span>{formatBytes(healthData.system_metrics.memory_used_mb * 1024 * 1024)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Total:</span>
                  <span>{formatBytes(healthData.system_metrics.memory_total_mb * 1024 * 1024)}</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full" 
                    style={{ width: `${healthData.system_metrics.memory_percent}%` }}
                  ></div>
                </div>
              </div>
            </div>
            
            <div>
              <h3 className="text-sm font-medium text-gray-500 mb-2">Disk</h3>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Used:</span>
                  <span>{healthData.system_metrics.disk_used_gb.toFixed(1)} GB</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Total:</span>
                  <span>{healthData.system_metrics.disk_total_gb.toFixed(1)} GB</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-green-600 h-2 rounded-full" 
                    style={{ width: `${healthData.system_metrics.disk_percent}%` }}
                  ></div>
                </div>
              </div>
            </div>
            
            <div>
              <h3 className="text-sm font-medium text-gray-500 mb-2">Load Average</h3>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>1 min:</span>
                  <span>{healthData.system_metrics.load_average[0]?.toFixed(2) || 'N/A'}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>5 min:</span>
                  <span>{healthData.system_metrics.load_average[1]?.toFixed(2) || 'N/A'}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>15 min:</span>
                  <span>{healthData.system_metrics.load_average[2]?.toFixed(2) || 'N/A'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Component Performance Metrics */}
      {healthData?.component_metrics && Object.keys(healthData.component_metrics).length > 0 && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            Component Performance Metrics
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {Object.entries(healthData.component_metrics).map(([component, metrics]) => (
              <div key={component} className="border rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-900 mb-3 capitalize">
                  {component.replace('_', ' ')}
                </h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">Processing Rate:</span>
                    <div className="font-medium">{metrics.processing_rate.toFixed(2)}/sec</div>
                  </div>
                  <div>
                    <span className="text-gray-500">Avg Latency:</span>
                    <div className="font-medium">{metrics.average_latency_ms.toFixed(1)}ms</div>
                  </div>
                  <div>
                    <span className="text-gray-500">Error Rate:</span>
                    <div className="font-medium">{metrics.error_rate.toFixed(2)}/min</div>
                  </div>
                  <div>
                    <span className="text-gray-500">Queue Size:</span>
                    <div className="font-medium">{metrics.queue_size}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Real-time Status Banner */}
      {(!isConnected || !realtimeConnected) && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-yellow-800">
                Real-time updates {!isConnected && !realtimeConnected ? 'unavailable' : 'partially available'}
              </h3>
              <div className="text-sm text-yellow-700 mt-1 space-y-1">
                {!isConnected && (
                  <p>Security events: Real-time updates not available. {connectionStatus.error && `Error: ${connectionStatus.error}`}</p>
                )}
                {!realtimeConnected && (
                  <p>System status: Real-time updates not available.</p>
                )}
                {(isConnected || realtimeConnected) && (
                  <p>Some real-time features are working, but full functionality requires all connections.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Real-time Connection Status */}
      {(isConnected && realtimeConnected) && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-green-800">
                Real-time monitoring active
              </h3>
              <p className="text-sm text-green-700 mt-1">
                All real-time features are operational. Dashboard updates automatically with new events and system status.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Severity Chart */}
      <SeverityChart 
        events={allEvents} 
        onSeverityClick={handleSeverityClick}
        className="mb-6"
      />

      {/* Filtered Events Summary */}
      {severityFilter && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-blue-800">
                Filtered by Severity {severityFilter}
              </h3>
              <p className="text-sm text-blue-600">
                Showing {filteredEvents.length} event{filteredEvents.length !== 1 ? 's' : ''}
              </p>
            </div>
            <button
              onClick={() => setSeverityFilter(null)}
              className="text-blue-600 hover:text-blue-800 text-sm font-medium"
            >
              Clear Filter
            </button>
          </div>
        </div>
      )}

      {/* Recent Events */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-gray-900">
            Recent Security Events
          </h2>
          <div className="flex items-center space-x-2">
            {isConnected && (
              <div className="flex items-center text-sm text-green-600">
                <div className="w-2 h-2 bg-green-500 rounded-full mr-1 animate-pulse"></div>
                Live
              </div>
            )}
            <span className="text-sm text-gray-500">
              {filteredEvents.length} event{filteredEvents.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>
        {filteredEvents.length > 0 ? (
          <div className="space-y-4">
            {filteredEvents.slice(0, 10).map((eventResponse) => {
              const severity = eventResponse.analysis?.severity_score || 0;
              return (
                <div key={eventResponse.event.id} className="border-l-4 border-gray-200 pl-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          severity >= 8 ? 'bg-red-100 text-red-800' :
                          severity >= 6 ? 'bg-orange-100 text-orange-800' :
                          severity >= 4 ? 'bg-yellow-100 text-yellow-800' :
                          severity >= 2 ? 'bg-blue-100 text-blue-800' :
                          'bg-green-100 text-green-800'
                        }`}>
                          Severity {severity}
                        </span>
                        <span className="text-sm text-gray-500 capitalize">
                          {eventResponse.event.category}
                        </span>
                        <span className="text-sm text-gray-500">
                          {eventResponse.event.source}
                        </span>
                      </div>
                      <p className="text-sm text-gray-900 mt-1">
                        {eventResponse.event.message.length > 100 
                          ? `${eventResponse.event.message.substring(0, 100)}...`
                          : eventResponse.event.message
                        }
                      </p>
                      <p className="text-xs text-gray-600 mt-1">
                        {eventResponse.analysis?.explanation || 'No analysis available'}
                      </p>
                    </div>
                    <div className="text-sm text-gray-500">
                      {new Date(eventResponse.event.timestamp).toLocaleString()}
                    </div>
                  </div>
                </div>
              );
            })}
            {filteredEvents.length > 10 && (
              <div className="text-center pt-4">
                <p className="text-sm text-gray-500">
                  Showing 10 of {filteredEvents.length} events
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <div className="text-4xl mb-2">🔍</div>
            <p>No security events found</p>
            <p className="text-sm">
              {severityFilter 
                ? `No events with severity ${severityFilter}` 
                : 'Upload logs to see security events'
              }
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;