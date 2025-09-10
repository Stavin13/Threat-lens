import React from 'react';
import Icon from '../../../components/AppIcon';

const PerformanceMetrics = ({ metrics }) => {
  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i))?.toFixed(2)) + ' ' + sizes?.[i];
  };

  const formatPercentage = (value) => {
    return `${value?.toFixed(1)}%`;
  };

  const getUsageColor = (percentage) => {
    if (percentage >= 90) return 'text-error';
    if (percentage >= 75) return 'text-warning';
    return 'text-success';
  };

  const getUsageBgColor = (percentage) => {
    if (percentage >= 90) return 'bg-error';
    if (percentage >= 75) return 'bg-warning';
    return 'bg-success';
  };

  const MetricCard = ({ icon, title, value, percentage, subtitle }) => (
    <div className="bg-card border border-border rounded-lg p-6 shadow-elevation-1">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-md bg-muted/50">
            <Icon name={icon} size={20} className="text-muted-foreground" />
          </div>
          <div>
            <h4 className="text-sm font-medium text-muted-foreground">{title}</h4>
            <p className="text-lg font-semibold text-foreground">{value}</p>
          </div>
        </div>
        {percentage !== undefined && (
          <div className="text-right">
            <p className={`text-sm font-semibold ${getUsageColor(percentage)}`}>
              {formatPercentage(percentage)}
            </p>
          </div>
        )}
      </div>
      
      {percentage !== undefined && (
        <div className="space-y-2">
          <div className="w-full bg-muted rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-300 ${getUsageBgColor(percentage)}`}
              style={{ width: `${Math.min(percentage, 100)}%` }}
            />
          </div>
          {subtitle && (
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-foreground">Performance Metrics</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          icon="Cpu"
          title="CPU Usage"
          value={formatPercentage(metrics?.cpu?.usage)}
          percentage={metrics?.cpu?.usage}
          subtitle={`${metrics?.cpu?.cores} cores available`}
        />
        
        <MetricCard
          icon="HardDrive"
          title="Memory Usage"
          value={formatBytes(metrics?.memory?.used)}
          percentage={(metrics?.memory?.used / metrics?.memory?.total) * 100}
          subtitle={`${formatBytes(metrics?.memory?.total)} total`}
        />
        
        <MetricCard
          icon="Database"
          title="Disk Usage"
          value={formatBytes(metrics?.disk?.used)}
          percentage={(metrics?.disk?.used / metrics?.disk?.total) * 100}
          subtitle={`${formatBytes(metrics?.disk?.available)} available`}
        />
        
        <MetricCard
          icon="Activity"
          title="Throughput"
          value={`${metrics?.throughput?.current?.toLocaleString()}/s`}
          percentage={undefined}
          subtitle={`Peak: ${metrics?.throughput?.peak?.toLocaleString()}/s`}
        />
      </div>
      {/* Additional System Info */}
      <div className="bg-card border border-border rounded-lg p-6 shadow-elevation-1">
        <h4 className="text-md font-semibold text-foreground mb-4">System Information</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Platform:</span>
            <span className="ml-2 font-medium text-foreground">{metrics?.system?.platform}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Architecture:</span>
            <span className="ml-2 font-medium text-foreground">{metrics?.system?.architecture}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Node Version:</span>
            <span className="ml-2 font-medium text-foreground">{metrics?.system?.nodeVersion}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Load Average:</span>
            <span className="ml-2 font-medium text-foreground">
              {metrics?.system?.loadAverage?.map(load => load?.toFixed(2))?.join(', ')}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Network Interfaces:</span>
            <span className="ml-2 font-medium text-foreground">{metrics?.system?.networkInterfaces}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Process ID:</span>
            <span className="ml-2 font-medium text-foreground">{metrics?.system?.processId}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PerformanceMetrics;