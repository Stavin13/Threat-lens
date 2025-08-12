import React, { useState, useEffect, useCallback } from 'react';
import { MonitoringConfig } from '../types';
import { api } from '../services/api';

interface SystemMonitoringProps {
  config: MonitoringConfig;
  onUpdate: () => void;
}

interface SystemMetrics {
  cpu_percent: number;
  memory_percent: number;
  memory_used_mb: number;
  memory_total_mb: number;
  disk_percent: number;
  disk_used_gb: number;
  disk_total_gb: number;
  load_average: number[];
  timestamp: string;
}

interface ComponentHealth {
  component: string;
  status: 'healthy' | 'warning' | 'critical' | 'unknown';
  message: string;
  timestamp: string;
  metrics: Record<string, any>;
  latency_ms?: number;
}

interface ComponentMetrics {
  component: string;
  processing_rate: number;
  average_latency_ms: number;
  error_rate: number;
  queue_size: number;
  active_connections: number;
  uptime_seconds: number;
  timestamp: string;
}

interface HealthSummary {
  overall_status: string;
  timestamp: string;
  uptime_seconds: number;
  monitoring_active: boolean;
  component_health: Record<string, ComponentHealth>;
  system_metrics?: SystemMetrics;
  component_metrics: Record<string, ComponentMetrics>;
}

interface DiagnosticResult {
  timestamp: string;
  overall_status: string;
  system_info: Record<string, any>;
  component_diagnostics: Record<string, any>;
  performance_metrics: Record<string, any>;
  error_analysis: Record<string, any>;
  resource_usage: Record<string, any>;
  recommendations: string[];
}

const SystemMonitoring: React.FC<SystemMonitoringProps> = ({ config, onUpdate }) => {
  const [healthSummary, setHealthSummary] = useState<HealthSummary | null>(null);
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics[]>([]);
  const [diagnostics, setDiagnostics] = useState<DiagnosticResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'metrics' | 'diagnostics' | 'settings'>('overview');
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadHealthSummary = useCallback(async () => {
    try {
      const response = await api.getHealthSummary();
      setHealthSummary(response);
      setError(null);
    } catch (err: any) {
      console.error('Failed to load health summary:', err);
      setError('Failed to load health summary');
    }
  }, []);

  const loadSystemMetrics = useCallback(async (hours: number = 1) => {
    try {
      const response = await api.getSystemMetrics(hours);
      setSystemMetrics(response);
    } catch (err: any) {
      console.error('Failed to load system metrics:', err);
    }
  }, []);

  const loadDiagnostics = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get('/api/health/diagnostics/full');
      setDiagnostics(response.data);
    } catch (err: any) {
      console.error('Failed to load diagnostics:', err);
      setError('Failed to load diagnostics');
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshData = useCallback(async () => {
    setRefreshing(true);
    try {
      await Promise.all([
        loadHealthSummary(),
        loadSystemMetrics(),
        activeTab === 'diagnostics' && loadDiagnostics()
      ].filter(Boolean));
    } finally {
      setRefreshing(false);
    }
  }, [loadHealthSummary, loadSystemMetrics, loadDiagnostics, activeTab]);

  useEffect(() => {
    refreshData();
  }, [refreshData]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      if (activeTab !== 'diagnostics') { // Don't auto-refresh diagnostics as it's expensive
        refreshData();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [autoRefresh, activeTab, refreshData]);

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy': return 'text-green-600 bg-green-100';
      case 'warning': return 'text-yellow-600 bg-yellow-100';
      case 'critical': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy': return '✅';
      case 'warning': return '⚠️';
      case 'critical': return '❌';
      default: return '❓';
    }
  };

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${days}d ${hours}h ${minutes}m`;
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getMetricTrend = (values: number[]) => {
    if (values.length < 2) return 'stable';
    const recent = values.slice(-5);
    const avg = recent.reduce((a, b) => a + b, 0) / recent.length;
    const older = values.slice(-10, -5);
    if (older.length === 0) return 'stable';
    const oldAvg = older.reduce((a, b) => a + b, 0) / older.length;
    
    if (avg > oldAvg * 1.1) return 'increasing';
    if (avg < oldAvg * 0.9) return 'decreasing';
    return 'stable';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-lg font-medium text-gray-900">System Monitoring</h2>
          <p className="text-sm text-gray-500">
            Monitor system health, performance metrics, and troubleshooting information
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <label className="flex items-center text-sm text-gray-600">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded mr-2"
            />
            Auto-refresh
          </label>
          <button
            onClick={refreshData}
            disabled={refreshing}
            className="bg-gray-100 hover:bg-gray-200 disabled:bg-gray-50 text-gray-700 px-3 py-2 rounded-md text-sm font-medium flex items-center"
          >
            <span className={`mr-2 ${refreshing ? 'animate-spin' : ''}`}>
              {refreshing ? '⟳' : '🔄'}
            </span>
            Refresh
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <span className="text-red-400">⚠️</span>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error</h3>
              <div className="mt-2 text-sm text-red-700">
                <p>{error}</p>
              </div>
              <div className="mt-4">
                <button
                  onClick={() => setError(null)}
                  className="bg-red-100 hover:bg-red-200 text-red-800 px-3 py-1 rounded text-sm"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'overview'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('metrics')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'metrics'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Metrics
          </button>
          <button
            onClick={() => setActiveTab('diagnostics')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'diagnostics'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Diagnostics
          </button>
          <button
            onClick={() => setActiveTab('settings')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'settings'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Settings
          </button>
        </nav>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && healthSummary && (
        <div className="space-y-6">
          {/* Overall Status */}
          <div className="bg-white shadow rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium text-gray-900">System Status</h3>
                <div className="mt-2 flex items-center space-x-4">
                  <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(healthSummary.overall_status)}`}>
                    <span className="mr-2">{getStatusIcon(healthSummary.overall_status)}</span>
                    {healthSummary.overall_status}
                  </span>
                  <span className="text-sm text-gray-500">
                    Uptime: {formatUptime(healthSummary.uptime_seconds)}
                  </span>
                  <span className="text-sm text-gray-500">
                    Monitoring: {healthSummary.monitoring_active ? '✅ Active' : '❌ Inactive'}
                  </span>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm text-gray-500">Last Updated</div>
                <div className="text-sm font-medium text-gray-900">
                  {new Date(healthSummary.timestamp).toLocaleString()}
                </div>
              </div>
            </div>
          </div>

          {/* System Metrics Summary */}
          {healthSummary.system_metrics && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white shadow rounded-lg p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <span className="text-2xl">🖥️</span>
                  </div>
                  <div className="ml-4">
                    <div className="text-sm font-medium text-gray-500">CPU Usage</div>
                    <div className="text-2xl font-bold text-gray-900">
                      {healthSummary.system_metrics.cpu_percent.toFixed(1)}%
                    </div>
                    {healthSummary.system_metrics.load_average && (
                      <div className="text-sm text-gray-500">
                        Load: {healthSummary.system_metrics.load_average[0]?.toFixed(2)}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="bg-white shadow rounded-lg p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <span className="text-2xl">💾</span>
                  </div>
                  <div className="ml-4">
                    <div className="text-sm font-medium text-gray-500">Memory Usage</div>
                    <div className="text-2xl font-bold text-gray-900">
                      {healthSummary.system_metrics.memory_percent.toFixed(1)}%
                    </div>
                    <div className="text-sm text-gray-500">
                      {formatBytes(healthSummary.system_metrics.memory_used_mb * 1024 * 1024)} / {formatBytes(healthSummary.system_metrics.memory_total_mb * 1024 * 1024)}
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-white shadow rounded-lg p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <span className="text-2xl">💿</span>
                  </div>
                  <div className="ml-4">
                    <div className="text-sm font-medium text-gray-500">Disk Usage</div>
                    <div className="text-2xl font-bold text-gray-900">
                      {healthSummary.system_metrics.disk_percent.toFixed(1)}%
                    </div>
                    <div className="text-sm text-gray-500">
                      {healthSummary.system_metrics.disk_used_gb.toFixed(1)} GB / {healthSummary.system_metrics.disk_total_gb.toFixed(1)} GB
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Component Health */}
          <div className="bg-white shadow rounded-lg">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">Component Health</h3>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(healthSummary.component_health).map(([name, health]) => (
                  <div key={name} className="border border-gray-200 rounded-md p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <span className="text-lg">{getStatusIcon(health.status)}</span>
                        <div>
                          <h4 className="text-sm font-medium text-gray-900">{health.component}</h4>
                          <p className="text-sm text-gray-500">{health.message}</p>
                        </div>
                      </div>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(health.status)}`}>
                        {health.status}
                      </span>
                    </div>
                    {health.latency_ms && (
                      <div className="mt-2 text-xs text-gray-500">
                        Latency: {health.latency_ms.toFixed(1)}ms
                      </div>
                    )}
                    <div className="mt-1 text-xs text-gray-400">
                      Last check: {new Date(health.timestamp).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Component Performance */}
          {Object.keys(healthSummary.component_metrics).length > 0 && (
            <div className="bg-white shadow rounded-lg">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900">Component Performance</h3>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(healthSummary.component_metrics).map(([name, metrics]) => (
                    <div key={name} className="border border-gray-200 rounded-md p-4">
                      <h4 className="text-sm font-medium text-gray-900 mb-3">{metrics.component}</h4>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <div className="text-gray-500">Processing Rate</div>
                          <div className="font-medium">{metrics.processing_rate.toFixed(1)}/s</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Avg Latency</div>
                          <div className="font-medium">{metrics.average_latency_ms.toFixed(1)}ms</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Error Rate</div>
                          <div className="font-medium">{metrics.error_rate.toFixed(2)}/min</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Queue Size</div>
                          <div className="font-medium">{metrics.queue_size}</div>
                        </div>
                      </div>
                      <div className="mt-2 text-xs text-gray-400">
                        Uptime: {formatUptime(metrics.uptime_seconds)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Metrics Tab */}
      {activeTab === 'metrics' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-medium text-gray-900">Historical Metrics</h3>
            <div className="flex space-x-2">
              <button
                onClick={() => loadSystemMetrics(1)}
                className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded"
              >
                1h
              </button>
              <button
                onClick={() => loadSystemMetrics(6)}
                className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded"
              >
                6h
              </button>
              <button
                onClick={() => loadSystemMetrics(24)}
                className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded"
              >
                24h
              </button>
            </div>
          </div>

          {systemMetrics.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* CPU Metrics */}
              <div className="bg-white shadow rounded-lg p-6">
                <h4 className="text-lg font-medium text-gray-900 mb-4">CPU Usage</h4>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Current:</span>
                    <span className="font-medium">{systemMetrics[systemMetrics.length - 1]?.cpu_percent.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Average:</span>
                    <span className="font-medium">
                      {(systemMetrics.reduce((sum, m) => sum + m.cpu_percent, 0) / systemMetrics.length).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Peak:</span>
                    <span className="font-medium">{Math.max(...systemMetrics.map(m => m.cpu_percent)).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Trend:</span>
                    <span className={`font-medium ${
                      getMetricTrend(systemMetrics.map(m => m.cpu_percent)) === 'increasing' ? 'text-red-600' :
                      getMetricTrend(systemMetrics.map(m => m.cpu_percent)) === 'decreasing' ? 'text-green-600' :
                      'text-gray-600'
                    }`}>
                      {getMetricTrend(systemMetrics.map(m => m.cpu_percent))}
                    </span>
                  </div>
                </div>
              </div>

              {/* Memory Metrics */}
              <div className="bg-white shadow rounded-lg p-6">
                <h4 className="text-lg font-medium text-gray-900 mb-4">Memory Usage</h4>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Current:</span>
                    <span className="font-medium">{systemMetrics[systemMetrics.length - 1]?.memory_percent.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Average:</span>
                    <span className="font-medium">
                      {(systemMetrics.reduce((sum, m) => sum + m.memory_percent, 0) / systemMetrics.length).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Peak:</span>
                    <span className="font-medium">{Math.max(...systemMetrics.map(m => m.memory_percent)).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Used:</span>
                    <span className="font-medium">
                      {formatBytes((systemMetrics[systemMetrics.length - 1]?.memory_used_mb || 0) * 1024 * 1024)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Disk Metrics */}
              <div className="bg-white shadow rounded-lg p-6">
                <h4 className="text-lg font-medium text-gray-900 mb-4">Disk Usage</h4>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Current:</span>
                    <span className="font-medium">{systemMetrics[systemMetrics.length - 1]?.disk_percent.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Used:</span>
                    <span className="font-medium">{systemMetrics[systemMetrics.length - 1]?.disk_used_gb.toFixed(1)} GB</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Total:</span>
                    <span className="font-medium">{systemMetrics[systemMetrics.length - 1]?.disk_total_gb.toFixed(1)} GB</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Free:</span>
                    <span className="font-medium">
                      {((systemMetrics[systemMetrics.length - 1]?.disk_total_gb || 0) - (systemMetrics[systemMetrics.length - 1]?.disk_used_gb || 0)).toFixed(1)} GB
                    </span>
                  </div>
                </div>
              </div>

              {/* Load Average */}
              <div className="bg-white shadow rounded-lg p-6">
                <h4 className="text-lg font-medium text-gray-900 mb-4">System Load</h4>
                <div className="space-y-2">
                  {systemMetrics[systemMetrics.length - 1]?.load_average && (
                    <>
                      <div className="flex justify-between text-sm">
                        <span>1 minute:</span>
                        <span className="font-medium">{systemMetrics[systemMetrics.length - 1].load_average[0]?.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span>5 minutes:</span>
                        <span className="font-medium">{systemMetrics[systemMetrics.length - 1].load_average[1]?.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span>15 minutes:</span>
                        <span className="font-medium">{systemMetrics[systemMetrics.length - 1].load_average[2]?.toFixed(2)}</span>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white shadow rounded-lg p-8 text-center">
              <span className="text-4xl mb-4 block">📊</span>
              <h3 className="text-lg font-medium text-gray-900 mb-2">No metrics data available</h3>
              <p className="text-sm text-gray-500">Metrics will appear here once the system starts collecting data.</p>
            </div>
          )}
        </div>
      )}

      {/* Diagnostics Tab */}
      {activeTab === 'diagnostics' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-medium text-gray-900">System Diagnostics</h3>
            <button
              onClick={loadDiagnostics}
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-4 py-2 rounded-md text-sm font-medium"
            >
              {loading ? 'Running...' : 'Run Diagnostics'}
            </button>
          </div>

          {diagnostics ? (
            <div className="space-y-6">
              {/* Diagnostic Summary */}
              <div className="bg-white shadow rounded-lg p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-lg font-medium text-gray-900">Diagnostic Summary</h4>
                    <div className="mt-2 flex items-center space-x-4">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(diagnostics.overall_status)}`}>
                        <span className="mr-2">{getStatusIcon(diagnostics.overall_status)}</span>
                        {diagnostics.overall_status}
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-gray-500">Run Time</div>
                    <div className="text-sm font-medium text-gray-900">
                      {new Date(diagnostics.timestamp).toLocaleString()}
                    </div>
                  </div>
                </div>
              </div>

              {/* Recommendations */}
              {diagnostics.recommendations.length > 0 && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
                  <h4 className="text-lg font-medium text-blue-900 mb-4">Recommendations</h4>
                  <ul className="space-y-2">
                    {diagnostics.recommendations.map((recommendation, index) => (
                      <li key={index} className="flex items-start">
                        <span className="text-blue-600 mr-2">💡</span>
                        <span className="text-sm text-blue-800">{recommendation}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Component Diagnostics */}
              <div className="bg-white shadow rounded-lg">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h4 className="text-lg font-medium text-gray-900">Component Diagnostics</h4>
                </div>
                <div className="p-6">
                  <div className="space-y-4">
                    {Object.entries(diagnostics.component_diagnostics).map(([name, result]: [string, any]) => (
                      <div key={name} className="border border-gray-200 rounded-md p-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-3">
                            <span className="text-lg">{getStatusIcon(result.status)}</span>
                            <div>
                              <h5 className="text-sm font-medium text-gray-900">{result.check_name}</h5>
                              <p className="text-sm text-gray-500">{result.message}</p>
                            </div>
                          </div>
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(result.status)}`}>
                            {result.status}
                          </span>
                        </div>
                        {result.recommendations && result.recommendations.length > 0 && (
                          <div className="mt-3 pl-8">
                            <div className="text-xs font-medium text-gray-700 mb-1">Recommendations:</div>
                            <ul className="text-xs text-gray-600 space-y-1">
                              {result.recommendations.map((rec: string, index: number) => (
                                <li key={index}>• {rec}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Performance Analysis */}
              {diagnostics.performance_metrics && (
                <div className="bg-white shadow rounded-lg">
                  <div className="px-6 py-4 border-b border-gray-200">
                    <h4 className="text-lg font-medium text-gray-900">Performance Analysis</h4>
                  </div>
                  <div className="p-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {Object.entries(diagnostics.performance_metrics).map(([key, value]: [string, any]) => (
                        <div key={key} className="border border-gray-200 rounded-md p-3">
                          <div className="text-sm font-medium text-gray-900 capitalize">
                            {key.replace(/_/g, ' ')}
                          </div>
                          <div className="text-sm text-gray-600 mt-1">
                            {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white shadow rounded-lg p-8 text-center">
              <span className="text-4xl mb-4 block">🔍</span>
              <h3 className="text-lg font-medium text-gray-900 mb-2">No diagnostics data available</h3>
              <p className="text-sm text-gray-500">Click "Run Diagnostics" to perform a comprehensive system analysis.</p>
            </div>
          )}
        </div>
      )}

      {/* Settings Tab */}
      {activeTab === 'settings' && (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Current System Settings</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="border border-gray-200 rounded-md p-3">
                <h4 className="text-sm font-medium text-gray-900">Processing Settings</h4>
                <div className="mt-2 space-y-1 text-sm text-gray-500">
                  <div>Max Concurrent Sources: {config.max_concurrent_sources}</div>
                  <div>Processing Batch Size: {config.processing_batch_size}</div>
                  <div>Max Queue Size: {config.max_queue_size}</div>
                </div>
              </div>
              
              <div className="border border-gray-200 rounded-md p-3">
                <h4 className="text-sm font-medium text-gray-900">Health Monitoring</h4>
                <div className="mt-2 space-y-1 text-sm text-gray-500">
                  <div>Health Check Interval: {config.health_check_interval}s</div>
                  <div>Max Error Count: {config.max_error_count}</div>
                  <div>Retry Interval: {config.retry_interval}s</div>
                </div>
              </div>
              
              <div className="border border-gray-200 rounded-md p-3">
                <h4 className="text-sm font-medium text-gray-900">Performance Settings</h4>
                <div className="mt-2 space-y-1 text-sm text-gray-500">
                  <div>File Read Chunk Size: {formatBytes(config.file_read_chunk_size)}</div>
                  <div>WebSocket Max Connections: {config.websocket_max_connections}</div>
                </div>
              </div>
              
              <div className="border border-gray-200 rounded-md p-3">
                <h4 className="text-sm font-medium text-gray-900">Configuration Info</h4>
                <div className="mt-2 space-y-1 text-sm text-gray-500">
                  <div>Version: {config.config_version}</div>
                  {config.updated_at && (
                    <div>Last Updated: {new Date(config.updated_at).toLocaleString()}</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SystemMonitoring;