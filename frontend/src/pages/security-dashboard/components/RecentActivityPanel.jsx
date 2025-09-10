import React from 'react';
import Icon from '../../../components/AppIcon';

const RecentActivityPanel = ({ events = [] }) => {
  const getSeverityBadge = (severity) => {
    if (severity >= 9) return 'bg-error text-error-foreground';
    if (severity >= 7) return 'bg-warning text-warning-foreground';
    if (severity >= 4) return 'bg-accent text-accent-foreground';
    return 'bg-success text-success-foreground';
  };

  const getSeverityLabel = (severity) => {
    if (severity >= 9) return 'Critical';
    if (severity >= 7) return 'High';
    if (severity >= 4) return 'Medium';
    return 'Low';
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp)?.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const truncateMessage = (message, maxLength = 80) => {
    if (message?.length <= maxLength) return message;
    return message?.substring(0, maxLength) + '...';
  };

  return (
    <div className="bg-card border border-border rounded-lg shadow-elevation-1">
      <div className="p-6 border-b border-border">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Recent Activity</h2>
          <Icon name="Activity" size={20} className="text-muted-foreground" />
        </div>
      </div>
      <div className="p-6">
        <div className="space-y-4">
          {events?.length === 0 ? (
            <div className="text-center py-8">
              <Icon name="AlertCircle" size={48} className="text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No recent events</p>
            </div>
          ) : (
            events?.map((event) => (
              <div key={event?.id} className="flex items-start space-x-3 p-3 rounded-md hover:bg-muted/50 transition-micro">
                <div className="flex-shrink-0 mt-1">
                  <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getSeverityBadge(event?.severity)}`}>
                    {getSeverityLabel(event?.severity)}
                  </span>
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-sm font-medium text-foreground truncate">
                      {event?.source}
                    </p>
                    <span className="text-xs text-muted-foreground">
                      {formatTimestamp(event?.timestamp)}
                    </span>
                  </div>
                  
                  <p className="text-sm text-muted-foreground">
                    {truncateMessage(event?.message)}
                  </p>
                  
                  <div className="flex items-center mt-2 space-x-2">
                    <span className="inline-flex items-center px-2 py-1 rounded-md bg-muted text-xs text-muted-foreground">
                      {event?.category}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      Severity: {event?.severity}/10
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
        
        {events?.length > 0 && (
          <div className="mt-6 pt-4 border-t border-border">
            <button className="w-full text-sm text-primary hover:text-primary/80 font-medium transition-micro">
              View All Events
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default RecentActivityPanel;