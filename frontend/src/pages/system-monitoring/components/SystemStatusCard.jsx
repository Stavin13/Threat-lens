import React from 'react';
import Icon from '../../../components/AppIcon';

const SystemStatusCard = ({ component, status, uptime, lastActivity, metrics }) => {
  const getStatusColor = () => {
    switch (status) {
      case 'healthy':
        return 'text-success';
      case 'warning':
        return 'text-warning';
      case 'error':
        return 'text-error';
      default:
        return 'text-muted-foreground';
    }
  };

  const getStatusBgColor = () => {
    switch (status) {
      case 'healthy':
        return 'bg-success/10';
      case 'warning':
        return 'bg-warning/10';
      case 'error':
        return 'bg-error/10';
      default:
        return 'bg-muted/10';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'healthy':
        return 'CheckCircle';
      case 'warning':
        return 'AlertTriangle';
      case 'error':
        return 'XCircle';
      default:
        return 'Circle';
    }
  };

  const formatUptime = (seconds) => {
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

  const formatLastActivity = (timestamp) => {
    const now = new Date();
    const diff = Math.floor((now - new Date(timestamp)) / 1000);
    
    if (diff < 60) {
      return 'Just now';
    } else if (diff < 3600) {
      const minutes = Math.floor(diff / 60);
      return `${minutes}m ago`;
    } else if (diff < 86400) {
      const hours = Math.floor(diff / 3600);
      return `${hours}h ago`;
    } else {
      return new Date(timestamp)?.toLocaleDateString();
    }
  };

  return (
    <div className="bg-card border border-border rounded-lg p-6 shadow-elevation-1">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className={`p-2 rounded-md ${getStatusBgColor()}`}>
            <Icon name={getStatusIcon()} size={20} className={getStatusColor()} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-foreground capitalize">
              {component?.replace('_', ' ')}
            </h3>
            <p className={`text-sm font-medium ${getStatusColor()}`}>
              {status?.charAt(0)?.toUpperCase() + status?.slice(1)}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm text-muted-foreground">Uptime</p>
          <p className="text-lg font-semibold text-foreground">
            {formatUptime(uptime)}
          </p>
        </div>
      </div>
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground">Last Activity</span>
          <span className="text-sm font-medium text-foreground">
            {formatLastActivity(lastActivity)}
          </span>
        </div>
        
        {metrics && (
          <div className="grid grid-cols-2 gap-4 pt-3 border-t border-border">
            {Object.entries(metrics)?.map(([key, value]) => (
              <div key={key} className="text-center">
                <p className="text-xs text-muted-foreground capitalize">
                  {key?.replace('_', ' ')}
                </p>
                <p className="text-sm font-semibold text-foreground">{value}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SystemStatusCard;