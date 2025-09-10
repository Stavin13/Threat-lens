import React from 'react';
import Icon from '../../../components/AppIcon';
import Button from '../../../components/ui/Button';

const RecentUploadsSection = ({ uploads, onRetry }) => {
  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return { name: 'CheckCircle', color: 'text-success' };
      case 'processing':
        return { name: 'Loader', color: 'text-primary animate-spin' };
      case 'failed':
        return { name: 'XCircle', color: 'text-error' };
      case 'queued':
        return { name: 'Clock', color: 'text-warning' };
      default:
        return { name: 'Circle', color: 'text-muted-foreground' };
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'completed':
        return 'Completed';
      case 'processing':
        return 'Processing';
      case 'failed':
        return 'Failed';
      case 'queued':
        return 'Queued';
      default:
        return 'Unknown';
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-success/10 text-success border-success/20';
      case 'processing':
        return 'bg-primary/10 text-primary border-primary/20';
      case 'failed':
        return 'bg-error/10 text-error border-error/20';
      case 'queued':
        return 'bg-warning/10 text-warning border-warning/20';
      default:
        return 'bg-muted/10 text-muted-foreground border-border';
    }
  };

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInMinutes = Math.floor((now - date) / (1000 * 60));
    
    if (diffInMinutes < 1) {
      return 'Just now';
    } else if (diffInMinutes < 60) {
      return `${diffInMinutes}m ago`;
    } else if (diffInMinutes < 1440) {
      const hours = Math.floor(diffInMinutes / 60);
      return `${hours}h ago`;
    } else {
      return date?.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return 'N/A';
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i))?.toFixed(2)) + ' ' + sizes?.[i];
  };

  if (!uploads || uploads?.length === 0) {
    return (
      <div className="bg-card rounded-lg border border-border p-8 text-center">
        <div className="flex items-center justify-center w-16 h-16 mx-auto bg-muted rounded-full mb-4">
          <Icon name="Upload" size={32} className="text-muted-foreground" />
        </div>
        <h3 className="text-lg font-medium text-foreground mb-2">No Recent Uploads</h3>
        <p className="text-sm text-muted-foreground">
          Your upload history will appear here once you start ingesting logs
        </p>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-lg border border-border">
      <div className="p-6 border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-foreground">Recent Uploads</h3>
            <p className="text-sm text-muted-foreground">
              Track your log ingestion history and processing status
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Icon name="History" size={16} />
            <span>Last 24 hours</span>
          </div>
        </div>
      </div>
      <div className="divide-y divide-border">
        {uploads?.map((upload) => {
          const statusIcon = getStatusIcon(upload?.status);
          
          return (
            <div key={upload?.id} className="p-6 hover:bg-muted/30 transition-colors">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <div className="flex items-center justify-center w-10 h-10 bg-muted rounded-lg flex-shrink-0">
                    {upload?.type === 'file' ? (
                      <Icon name="FileText" size={20} className="text-muted-foreground" />
                    ) : (
                      <Icon name="Type" size={20} className="text-muted-foreground" />
                    )}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="text-sm font-medium text-foreground truncate">
                        {upload?.filename || 'Manual Entry'}
                      </h4>
                      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium border ${getStatusBadgeClass(upload?.status)}`}>
                        <Icon name={statusIcon?.name} size={12} className={statusIcon?.color} />
                        {getStatusText(upload?.status)}
                      </span>
                    </div>
                    
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Icon name="Server" size={12} />
                        {upload?.source}
                      </span>
                      {upload?.size && (
                        <span className="flex items-center gap-1">
                          <Icon name="HardDrive" size={12} />
                          {formatFileSize(upload?.size)}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Icon name="Clock" size={12} />
                        {formatTimestamp(upload?.timestamp)}
                      </span>
                    </div>
                    
                    {upload?.eventsProcessed && (
                      <div className="mt-2 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Icon name="Activity" size={12} />
                          {upload?.eventsProcessed?.toLocaleString()} events processed
                        </span>
                      </div>
                    )}
                    
                    {upload?.error && (
                      <div className="mt-2 text-xs text-error bg-error/10 rounded px-2 py-1">
                        <span className="flex items-center gap-1">
                          <Icon name="AlertCircle" size={12} />
                          {upload?.error}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
                
                <div className="flex items-center gap-2 flex-shrink-0">
                  {upload?.status === 'processing' && (
                    <div className="text-xs text-muted-foreground">
                      {upload?.progress}%
                    </div>
                  )}
                  
                  {upload?.status === 'failed' && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onRetry(upload?.id)}
                      iconName="RotateCcw"
                      iconPosition="left"
                    >
                      Retry
                    </Button>
                  )}
                  
                  {upload?.status === 'completed' && (
                    <Button
                      variant="ghost"
                      size="sm"
                      iconName="ExternalLink"
                    >
                      View
                    </Button>
                  )}
                </div>
              </div>
              {upload?.status === 'processing' && upload?.progress && (
                <div className="mt-3 ml-13">
                  <div className="w-full bg-muted rounded-full h-1.5">
                    <div
                      className="bg-primary h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${upload?.progress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="p-4 border-t border-border bg-muted/30">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            Showing {uploads?.length} recent uploads
          </span>
          <Button variant="ghost" size="sm" iconName="MoreHorizontal">
            View All
          </Button>
        </div>
      </div>
    </div>
  );
};

export default RecentUploadsSection;