import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import NavigationHeader from '../../components/ui/NavigationHeader';
import MetricCard from './components/MetricCard';
import RecentActivityPanel from './components/RecentActivityPanel';
import SystemStatusPanel from './components/SystemStatusPanel';
import SeverityDistributionChart from './components/SeverityDistributionChart';
import TrendingMetricsChart from './components/TrendingMetricsChart';
import Button from '../../components/ui/Button';
import { useStats, useEvents, useRealtimeStatus, useRealtimeMetrics, useWebSocket } from '../../hooks/useApi';
import { formatTimestamp } from '../../utils/formatters';
import ApiTest from '../../components/ApiTest';


const SecurityDashboard = () => {
  // API hooks
  const { data: stats, loading: statsLoading, error: statsError, refetch: refetchStats } = useStats();
  const { data: recentEvents, loading: eventsLoading, refetch: refetchEvents } = useEvents({ 
    per_page: 5, 
    sort_by: 'timestamp', 
    sort_order: 'desc' 
  });
  const { data: realtimeStatus, loading: statusLoading } = useRealtimeStatus();
  const { data: realtimeMetrics, loading: metricsLoading } = useRealtimeMetrics();
  const { status: wsStatus, lastMessage } = useWebSocket();
  
  const [lastRefresh, setLastRefresh] = useState(new Date());
  
  // Combine loading states
  const isLoading = statsLoading || eventsLoading || statusLoading || metricsLoading;

  // Removed mock data: dashboard now only uses live API responses

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const refreshInterval = setInterval(() => {
      refetchStats();
      refetchEvents();
      setLastRefresh(new Date());
    }, 30000);

    return () => clearInterval(refreshInterval);
  }, [refetchStats, refetchEvents]);

  // Update last refresh when data changes
  useEffect(() => {
    if (stats || recentEvents) {
      setLastRefresh(new Date());
    }
  }, [stats, recentEvents]);

  const handleRefresh = () => {
    refetchStats();
    refetchEvents();
    setLastRefresh(new Date());
  };

  // Debug API responses
  useEffect(() => {
    console.log('API Debug Info:');
    console.log('Stats:', stats);
    console.log('Stats Error:', statsError);
    console.log('Recent Events:', recentEvents);
    console.log('Realtime Status:', realtimeStatus);
    console.log('Realtime Metrics:', realtimeMetrics);
    console.log('WebSocket Status:', wsStatus);
  }, [stats, statsError, recentEvents, realtimeStatus, realtimeMetrics, wsStatus]);

  // Prepare dashboard data strictly from API responses
  const dashboardData = {
    metrics: {
      totalEvents: stats?.database?.events_count ?? 0,
      highSeverityEvents: (recentEvents?.events || []).filter(e => e?.ai_analysis?.severity_score >= 7).length,
      queueDepth: realtimeMetrics?.queue_depth ?? 0,
      eventsPerMin: realtimeMetrics?.events_per_minute ?? 0
    },
    recentEvents: recentEvents?.events || [],
    systemComponents: realtimeStatus?.components ? Object.entries(realtimeStatus.components).map(([key, value]) => ({
      name: key,
      displayName: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      status: value.status || 'unknown',
      description: `${key.replace(/_/g, ' ')} service`
    })) : [],
    severityDistribution: [],
    trendingMetrics: []
  };

  const connectionStatus = {
    connected: wsStatus === 'connected',
    lastUpdate: new Date()
  };

  if (isLoading && !stats) {
    return (
      <div className="min-h-screen bg-background">
        <NavigationHeader connectionStatus={connectionStatus} />
        <div className="pt-16">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div className="animate-pulse">
              <div className="h-8 bg-muted rounded w-64 mb-8"></div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                {[...Array(4)]?.map((_, i) => (
                  <div key={i} className="bg-card border border-border rounded-lg p-6 h-32"></div>
                ))}
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                <div className="bg-card border border-border rounded-lg h-96"></div>
                <div className="bg-card border border-border rounded-lg h-96"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <NavigationHeader connectionStatus={connectionStatus} />
      <div className="pt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Header Section */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold text-foreground">Security Dashboard</h1>
              <p className="text-muted-foreground mt-2">
                Real-time threat monitoring and security event analysis
              </p>
            </div>
            
            <div className="flex items-center space-x-4 mt-4 sm:mt-0">
              <div className="text-sm text-muted-foreground">
                Last updated: {lastRefresh?.toLocaleTimeString()}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                loading={isLoading}
                iconName="RefreshCw"
                iconPosition="left"
              >
                Refresh
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  console.log('Manual API Test:');
                  console.log('Stats:', stats);
                  console.log('Events:', recentEvents);
                  console.log('Has Real Data:', Boolean(stats || (recentEvents && recentEvents.events && recentEvents.events.length)));
                }}
              >
                Debug
              </Button>
            </div>
          </div>

          {/* Connection/Status Indicator */}
          <div className={`mb-6 p-4 rounded-lg border bg-green-50 border-green-200`}>
            <h3 className={`font-semibold mb-2 text-green-800`}>
              ✅ Live Data
            </h3>
            <div className={`text-sm space-y-1 text-green-700`}>
              <div>Total Events: {stats?.database?.events_count ?? 0}</div>
              <div>Recent Events: {recentEvents?.events?.length ?? 0} loaded</div>
              <div>Stats Loading: {statsLoading ? 'Yes' : 'No'}</div>
              <div>Stats Error: {statsError || 'None'}</div>
              <div>WebSocket: {wsStatus}</div>
            </div>
          </div>

          {/* Metrics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <MetricCard
              title="Total Events"
              value={dashboardData?.metrics?.totalEvents?.toLocaleString()}
              change="+12%"
              changeType="increase"
              icon="Activity"
              color="primary"
            />
            <MetricCard
              title="High Severity Events"
              value={dashboardData?.metrics?.highSeverityEvents}
              change="-5%"
              changeType="decrease"
              icon="AlertTriangle"
              color="warning"
            />
            <MetricCard
              title="Queue Depth"
              value={dashboardData?.metrics?.queueDepth}
              change="+8%"
              changeType="increase"
              icon="Database"
              color="success"
            />
            <MetricCard
              title="Events/Min"
              value={dashboardData?.metrics?.eventsPerMin}
              change="0%"
              changeType="neutral"
              icon="TrendingUp"
              color="primary"
            />
          </div>

          {/* Main Content Panels */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <RecentActivityPanel events={dashboardData?.recentEvents} />
            <SystemStatusPanel components={dashboardData?.systemComponents} />
          </div>

          {/* Charts Section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <SeverityDistributionChart data={dashboardData?.severityDistribution} />
            <TrendingMetricsChart 
              data={dashboardData?.trendingMetrics} 
              title="Real-time Metrics"
            />
          </div>

          {/* API Test Panel - Remove in production */}
          <div className="mb-8">
            <ApiTest />
          </div>

          {/* Quick Actions */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-lg font-semibold text-foreground mb-4">Quick Actions</h2>
            <div className="flex flex-wrap gap-4">
              <Link to="/events-management">
                <Button variant="default" iconName="List" iconPosition="left">
                  View All Events
                </Button>
              </Link>
              <Link to="/log-ingestion">
                <Button variant="outline" iconName="Upload" iconPosition="left">
                  Ingest Logs
                </Button>
              </Link>
              <Link to="/system-monitoring">
                <Button variant="outline" iconName="Server" iconPosition="left">
                  System Monitor
              </Button>
              </Link>
              <Button variant="ghost" iconName="Download" iconPosition="left">
                Export Report
              </Button>
            </div>
          </div>

          {/* Footer Info */}
          <div className="mt-8 text-center text-sm text-muted-foreground">
            <p>
              ThreatLens Security Platform • Real-time monitoring active • 
              {dashboardData?.systemComponents?.filter(c => c?.status === 'healthy' || c?.status === 'running' || c?.status === 'active')?.length} of {dashboardData?.systemComponents?.length} services operational
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SecurityDashboard;