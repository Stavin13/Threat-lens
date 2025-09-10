import React, { useState, useEffect } from 'react';
import { Helmet } from 'react-helmet';
import NavigationHeader from '../../components/ui/NavigationHeader';
import SystemStatusCard from './components/SystemStatusCard';
import MetricsChart from './components/MetricsChart';
import ConnectionStatusPanel from './components/ConnectionStatusPanel';
import SystemLogsPanel from './components/SystemLogsPanel';
import PerformanceMetrics from './components/PerformanceMetrics';
import Button from '../../components/ui/Button';
import { apiService } from '../../services/api';
import { useWebSocket } from '../../hooks/useApi';


const SystemMonitoring = () => {
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(new Date());

  const [systemComponents, setSystemComponents] = useState([]);
  const [performanceMetrics, setPerformanceMetrics] = useState(null);
  const [metricsData, setMetricsData] = useState({ eventsPerMin: [], queueDepth: [], processingTime: [] });
  const [systemLogs, setSystemLogs] = useState([]);
  const { status: wsStatus } = useWebSocket();
  const connectionStatus = { connected: wsStatus === 'connected' };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const status = await apiService.getRealtimeStatus();
      if (status?.components) {
        const comps = Object.entries(status.components).map(([key, value]) => ({
          component: key,
          status: value?.status || 'unknown',
          uptime: value?.uptime_seconds || 0,
          lastActivity: value?.last_activity ? new Date(value.last_activity) : null,
          metrics: value?.metrics || {}
        }));
        setSystemComponents(comps);
      }
      // If you add a metrics endpoint later, populate metricsData here
    } catch {}
    setLastRefresh(new Date());
    setRefreshing(false);
  };

  const handleReconnect = async () => {
    // Simulate reconnection
    await new Promise(resolve => setTimeout(resolve, 2000));
  };

  const handleExportLogs = () => {
    // Simulate log export
    const logData = systemLogs?.map(log => ({
      timestamp: log?.timestamp?.toISOString(),
      severity: log?.severity,
      component: log?.component,
      message: log?.message,
      details: log?.details
    }));
    
    const blob = new Blob([JSON.stringify(logData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `system-logs-${new Date()?.toISOString()?.split('T')?.[0]}.json`;
    document.body?.appendChild(a);
    a?.click();
    document.body?.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleClearLogs = () => {
    // In a real app, this would clear the logs
    console.log('Clearing system logs...');
  };

  const handleSystemRestart = () => {
    // In a real app, this would trigger a system restart
    console.log('Initiating system restart...');
  };

  // Initial load and auto-refresh
  useEffect(() => {
    handleRefresh();
    const interval = setInterval(() => { handleRefresh(); }, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <Helmet>
        <title>System Monitoring - ThreatLens</title>
        <meta name="description" content="Monitor system health, performance metrics, and connection status for the ThreatLens security platform" />
      </Helmet>
      <NavigationHeader connectionStatus={connectionStatus} />
      <main className="pt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Header Section */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold text-foreground">System Monitoring</h1>
              <p className="mt-2 text-muted-foreground">
                Monitor system health, performance metrics, and connection status
              </p>
            </div>
            <div className="mt-4 sm:mt-0 flex items-center space-x-3">
              <div className="text-sm text-muted-foreground">
                Last updated: {lastRefresh?.toLocaleTimeString()}
              </div>
              <Button
                variant="outline"
                iconName="RefreshCw"
                iconPosition="left"
                loading={refreshing}
                onClick={handleRefresh}
              >
                Refresh
              </Button>
              <Button
                variant="destructive"
                iconName="RotateCcw"
                iconPosition="left"
                onClick={handleSystemRestart}
              >
                Restart System
              </Button>
            </div>
          </div>

          {/* System Status Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
            {systemComponents?.map((component) => (
              <SystemStatusCard
                key={component?.component}
                component={component?.component}
                status={component?.status}
                uptime={component?.uptime}
                lastActivity={component?.lastActivity}
                metrics={component?.metrics}
              />
            ))}
          </div>

          {/* Connection Status Panel */}
          <div className="mb-8">
            <ConnectionStatusPanel
              connectionStatus={connectionStatus}
              onReconnect={handleReconnect}
              onRefresh={handleRefresh}
            />
          </div>

          {/* Performance Metrics */}
          {performanceMetrics && (
            <div className="mb-8">
              <PerformanceMetrics metrics={performanceMetrics} />
            </div>
          )}

          {/* Metrics Charts */}
          {metricsData?.eventsPerMin?.length > 0 || metricsData?.queueDepth?.length > 0 || metricsData?.processingTime?.length > 0 ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6 mb-8">
              {metricsData?.eventsPerMin?.length > 0 && (
                <MetricsChart title="Events per Minute" data={metricsData?.eventsPerMin} type="line" dataKey="events_per_min" color="#3B82F6" />
              )}
              {metricsData?.queueDepth?.length > 0 && (
                <MetricsChart title="Queue Depth" data={metricsData?.queueDepth} type="bar" dataKey="queue_depth" color="#059669" />
              )}
              {metricsData?.processingTime?.length > 0 && (
                <MetricsChart title="Processing Time" data={metricsData?.processingTime} type="line" dataKey="processing_time" color="#D97706" />
              )}
            </div>
          ) : null}

          {/* System Logs Panel */}
          {systemLogs?.length > 0 && (
            <div className="mb-8">
              <SystemLogsPanel
                logs={systemLogs}
                onExportLogs={handleExportLogs}
                onClearLogs={handleClearLogs}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default SystemMonitoring;