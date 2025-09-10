import React from 'react';
import Icon from '../../../components/AppIcon';

const SystemStatusPanel = ({ components = [] }) => {
  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'healthy': case'running': case'active':
        return 'text-success';
      case 'warning': case'degraded':
        return 'text-warning';
      case 'error': case'failed': case'inactive':
        return 'text-error';
      default:
        return 'text-muted-foreground';
    }
  };

  const getStatusIcon = (status) => {
    switch (status?.toLowerCase()) {
      case 'healthy': case'running': case'active':
        return 'CheckCircle';
      case 'warning': case'degraded':
        return 'AlertTriangle';
      case 'error': case'failed': case'inactive':
        return 'XCircle';
      default:
        return 'Circle';
    }
  };

  const getStatusBadge = (status) => {
    switch (status?.toLowerCase()) {
      case 'healthy': case'running': case'active':
        return 'bg-success/10 text-success border-success/20';
      case 'warning': case'degraded':
        return 'bg-warning/10 text-warning border-warning/20';
      case 'error': case'failed': case'inactive':
        return 'bg-error/10 text-error border-error/20';
      default:
        return 'bg-muted text-muted-foreground border-border';
    }
  };

  const formatUptime = (uptime) => {
    const hours = Math.floor(uptime / 3600);
    const minutes = Math.floor((uptime % 3600) / 60);
    
    if (hours > 24) {
      const days = Math.floor(hours / 24);
      return `${days}d ${hours % 24}h`;
    }
    
    return `${hours}h ${minutes}m`;
  };

  return (
    <div className="bg-card border border-border rounded-lg shadow-elevation-1">
      <div className="p-6 border-b border-border">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">System Status</h2>
          <Icon name="Server" size={20} className="text-muted-foreground" />
        </div>
      </div>
      <div className="p-6">
        <div className="space-y-4">
          {components?.length === 0 ? (
            <div className="text-center py-8">
              <Icon name="Server" size={48} className="text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No system components</p>
            </div>
          ) : (
            components?.map((component) => (
              <div key={component?.name} className="flex items-center justify-between p-3 rounded-md border border-border hover:bg-muted/50 transition-micro">
                <div className="flex items-center space-x-3">
                  <Icon 
                    name={getStatusIcon(component?.status)} 
                    size={20} 
                    className={getStatusColor(component?.status)}
                  />
                  <div>
                    <h3 className="text-sm font-medium text-foreground">
                      {component?.displayName || component?.name}
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      {component?.description || `${component?.name} service`}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center space-x-3">
                  {component?.uptime && (
                    <span className="text-xs text-muted-foreground">
                      {formatUptime(component?.uptime)}
                    </span>
                  )}
                  <span className={`inline-flex items-center px-2 py-1 rounded-md border text-xs font-medium ${getStatusBadge(component?.status)}`}>
                    {component?.status}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
        
        {components?.length > 0 && (
          <div className="mt-6 pt-4 border-t border-border">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Last updated:</span>
              <span className="text-foreground font-medium">
                {new Date()?.toLocaleTimeString('en-US', {
                  hour: '2-digit',
                  minute: '2-digit'
                })}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SystemStatusPanel;