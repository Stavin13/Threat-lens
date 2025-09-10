import React from 'react';
import Icon from '../../../components/AppIcon';
import Button from '../../../components/ui/Button';

const EventDetailModal = ({ event, isOpen, onClose }) => {
  if (!isOpen || !event) return null;

  const getSeverityColor = (severity) => {
    if (severity >= 9) return 'bg-red-500 text-white';
    if (severity >= 7) return 'bg-orange-500 text-white';
    if (severity >= 4) return 'bg-yellow-500 text-black';
    return 'bg-green-500 text-white';
  };

  const getSeverityLabel = (severity) => {
    if (severity >= 9) return 'Critical';
    if (severity >= 7) return 'High';
    if (severity >= 4) return 'Medium';
    return 'Low';
  };

  const getCategoryIcon = (category) => {
    const icons = {
      authentication: 'Key',
      network: 'Wifi',
      malware: 'Shield',
      intrusion: 'AlertTriangle',
      data_access: 'Database',
      system: 'Server',
      compliance: 'FileCheck'
    };
    return icons?.[category] || 'AlertCircle';
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp)?.toLocaleString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short'
    });
  };

  const handleBackdropClick = (e) => {
    if (e?.target === e?.currentTarget) {
      onClose();
    }
  };

  return (
    <div 
      className="fixed inset-0 z-[1200] flex items-center justify-center p-4 bg-black/50"
      onClick={handleBackdropClick}
    >
      <div className="bg-card rounded-lg shadow-elevation-4 w-full max-w-4xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg ${getSeverityColor(event?.severity)}`}>
              <Icon name={getCategoryIcon(event?.category)} size={20} />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-foreground">Security Event Details</h2>
              <p className="text-sm text-muted-foreground">Event ID: {event?.id}</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            iconName="X"
            onClick={onClose}
          />
        </div>

        {/* Content */}
        <div className="overflow-y-auto max-h-[calc(90vh-80px)]">
          <div className="p-6 space-y-6">
            {/* Basic Information */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-semibold text-foreground">Timestamp</label>
                  <p className="text-sm text-muted-foreground mt-1">
                    {formatTimestamp(event?.timestamp)}
                  </p>
                </div>
                
                <div>
                  <label className="text-sm font-semibold text-foreground">Source</label>
                  <p className="text-sm text-muted-foreground mt-1">{event?.source}</p>
                </div>
                
                <div>
                  <label className="text-sm font-semibold text-foreground">Category</label>
                  <div className="flex items-center space-x-2 mt-1">
                    <Icon 
                      name={getCategoryIcon(event?.category)} 
                      size={16} 
                      className="text-muted-foreground" 
                    />
                    <span className="text-sm text-muted-foreground capitalize">
                      {event?.category?.replace('_', ' ')}
                    </span>
                  </div>
                </div>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-semibold text-foreground">Severity</label>
                  <div className="flex items-center space-x-3 mt-1">
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${getSeverityColor(event?.severity)}`}>
                      {event?.severity}/10
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {getSeverityLabel(event?.severity)}
                    </span>
                  </div>
                </div>
                
                {event?.details?.user_id && (
                  <div>
                    <label className="text-sm font-semibold text-foreground">User ID</label>
                    <p className="text-sm text-muted-foreground mt-1">{event?.details?.user_id}</p>
                  </div>
                )}
                
                {event?.details?.ip_address && (
                  <div>
                    <label className="text-sm font-semibold text-foreground">IP Address</label>
                    <p className="text-sm text-muted-foreground mt-1 font-mono">{event?.details?.ip_address}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Event Message */}
            <div>
              <label className="text-sm font-semibold text-foreground">Event Message</label>
              <div className="mt-2 p-4 bg-muted/30 rounded-lg border">
                <p className="text-sm text-foreground">{event?.message}</p>
              </div>
            </div>

            {/* AI Analysis Section */}
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 rounded-lg p-6 border border-blue-200 dark:border-blue-800">
              <div className="flex items-center space-x-2 mb-4">
                <Icon name="Brain" size={20} className="text-blue-600" />
                <h3 className="text-lg font-semibold text-foreground">AI Security Analysis</h3>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-semibold text-foreground">Threat Assessment</label>
                  <div className="flex items-center space-x-3 mt-2">
                    <div className={`w-4 h-4 rounded-full ${getSeverityColor(event?.severity)?.replace('text-white', '')?.replace('text-black', '')}`} />
                    <span className="text-sm font-medium text-foreground">
                      Severity Score: {event?.severity}/10 ({getSeverityLabel(event?.severity)} Risk)
                    </span>
                  </div>
                </div>
                
                <div>
                  <label className="text-sm font-semibold text-foreground">Analysis</label>
                  <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                    {event?.aiAnalysis?.explanation || `This ${event?.category?.replace('_', ' ')} event has been classified as ${getSeverityLabel(event?.severity)?.toLowerCase()} severity based on the event characteristics, source reputation, and potential impact assessment. The system detected patterns consistent with ${event?.category === 'authentication' ? 'authentication anomalies' : event?.category === 'network' ? 'network security concerns' : event?.category === 'malware' ? 'malicious activity indicators' : 'security policy violations'}.`}
                  </p>
                </div>
                
                <div>
                  <label className="text-sm font-semibold text-foreground">Recommended Actions</label>
                  <ul className="mt-2 space-y-2">
                    {(event?.aiAnalysis?.recommendations || [
                      'Review event details and correlate with other security events',
                      'Verify the legitimacy of the source and user activity',
                      'Consider implementing additional monitoring for this source',
                      'Update security policies if this represents a new threat pattern'
                    ])?.map((recommendation, index) => (
                      <li key={index} className="flex items-start space-x-2">
                        <Icon name="CheckCircle" size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                        <span className="text-sm text-muted-foreground">{recommendation}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            {/* Additional Details */}
            {event?.details && Object.keys(event?.details)?.length > 0 && (
              <div>
                <label className="text-sm font-semibold text-foreground">Additional Details</label>
                <div className="mt-2 bg-muted/30 rounded-lg border overflow-hidden">
                  <div className="p-4 space-y-3">
                    {Object.entries(event?.details)?.map(([key, value]) => (
                      <div key={key} className="flex items-start justify-between py-2 border-b border-border last:border-b-0">
                        <span className="text-sm font-medium text-foreground capitalize min-w-0 flex-shrink-0 mr-4">
                          {key?.replace('_', ' ')}:
                        </span>
                        <span className="text-sm text-muted-foreground text-right font-mono">
                          {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Raw Log Data */}
            <div>
              <label className="text-sm font-semibold text-foreground">Raw Log Data</label>
              <div className="mt-2 bg-black rounded-lg p-4 overflow-x-auto">
                <pre className="text-xs text-green-400 font-mono whitespace-pre-wrap">
                  {event?.rawLog || JSON.stringify({
                    timestamp: event?.timestamp,
                    source: event?.source,
                    category: event?.category,
                    severity: event?.severity,
                    message: event?.message,
                    details: event?.details || {}
                  }, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between p-6 border-t border-border bg-muted/20">
          <div className="flex items-center space-x-2 text-sm text-muted-foreground">
            <Icon name="Clock" size={16} />
            <span>Last updated: {formatTimestamp(event?.timestamp)}</span>
          </div>
          
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              iconName="Download"
              iconPosition="left"
            >
              Export Event
            </Button>
            <Button
              variant="outline"
              size="sm"
              iconName="Flag"
              iconPosition="left"
            >
              Mark for Review
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={onClose}
            >
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EventDetailModal;