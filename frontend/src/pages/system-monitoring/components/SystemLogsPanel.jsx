import React, { useState } from 'react';
import Icon from '../../../components/AppIcon';
import Button from '../../../components/ui/Button';

const SystemLogsPanel = ({ logs, onExportLogs, onClearLogs }) => {
  const [expandedLog, setExpandedLog] = useState(null);

  const getSeverityColor = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'error':
        return 'text-error bg-error/10';
      case 'warning':
        return 'text-warning bg-warning/10';
      case 'info':
        return 'text-primary bg-primary/10';
      case 'success':
        return 'text-success bg-success/10';
      default:
        return 'text-muted-foreground bg-muted/10';
    }
  };

  const getSeverityIcon = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'error':
        return 'XCircle';
      case 'warning':
        return 'AlertTriangle';
      case 'info':
        return 'Info';
      case 'success':
        return 'CheckCircle';
      default:
        return 'Circle';
    }
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp)?.toLocaleString('en-US', {
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  };

  const toggleLogExpansion = (logId) => {
    setExpandedLog(expandedLog === logId ? null : logId);
  };

  return (
    <div className="bg-card border border-border rounded-lg shadow-elevation-1">
      <div className="flex items-center justify-between p-6 border-b border-border">
        <h3 className="text-lg font-semibold text-foreground">System Logs</h3>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            iconName="Download"
            iconPosition="left"
            onClick={onExportLogs}
          >
            Export
          </Button>
          <Button
            variant="outline"
            size="sm"
            iconName="Trash2"
            iconPosition="left"
            onClick={onClearLogs}
          >
            Clear
          </Button>
        </div>
      </div>
      <div className="max-h-96 overflow-y-auto">
        {logs?.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Icon name="FileText" size={48} className="text-muted-foreground mb-4" />
            <p className="text-muted-foreground">No system logs available</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {logs?.map((log) => (
              <div key={log?.id} className="p-4 hover:bg-muted/30 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3 flex-1">
                    <div className={`p-1.5 rounded-md ${getSeverityColor(log?.severity)}`}>
                      <Icon 
                        name={getSeverityIcon(log?.severity)} 
                        size={16} 
                        className={getSeverityColor(log?.severity)?.split(' ')?.[0]}
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2 mb-1">
                        <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ${getSeverityColor(log?.severity)}`}>
                          {log?.severity?.toUpperCase()}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {formatTimestamp(log?.timestamp)}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {log?.component}
                        </span>
                      </div>
                      <p className="text-sm text-foreground font-medium mb-1">
                        {log?.message}
                      </p>
                      {log?.details && (
                        <div className="text-xs text-muted-foreground">
                          {expandedLog === log?.id ? (
                            <div className="mt-2 p-3 bg-muted/50 rounded-md">
                              <pre className="whitespace-pre-wrap font-mono">
                                {log?.details}
                              </pre>
                            </div>
                          ) : (
                            <p className="truncate">
                              {log?.details?.substring(0, 100)}...
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  {log?.details && (
                    <button
                      onClick={() => toggleLogExpansion(log?.id)}
                      className="ml-2 p-1 rounded-md hover:bg-muted transition-colors"
                    >
                      <Icon 
                        name={expandedLog === log?.id ? 'ChevronUp' : 'ChevronDown'} 
                        size={16} 
                        className="text-muted-foreground"
                      />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SystemLogsPanel;