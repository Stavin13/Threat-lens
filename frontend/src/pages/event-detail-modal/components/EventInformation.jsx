import React from 'react';
import Icon from '../../../components/AppIcon';

const EventInformation = ({ event }) => {
  const getCategoryIcon = (category) => {
    const iconMap = {
      'Authentication': 'Shield',
      'Network': 'Wifi',
      'System': 'Server',
      'Application': 'Code',
      'Security': 'Lock',
      'Database': 'Database',
      'File System': 'FileText',
      'Web': 'Globe'
    };
    return iconMap?.[category] || 'AlertCircle';
  };

  const getCategoryColor = (category) => {
    const colorMap = {
      'Authentication': 'text-blue-600 bg-blue-50',
      'Network': 'text-green-600 bg-green-50',
      'System': 'text-purple-600 bg-purple-50',
      'Application': 'text-orange-600 bg-orange-50',
      'Security': 'text-red-600 bg-red-50',
      'Database': 'text-indigo-600 bg-indigo-50',
      'File System': 'text-yellow-600 bg-yellow-50',
      'Web': 'text-teal-600 bg-teal-50'
    };
    return colorMap?.[category] || 'text-gray-600 bg-gray-50';
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

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-muted-foreground">Event ID</label>
            <p className="text-sm font-mono text-foreground mt-1">{event?.id}</p>
          </div>
          
          <div>
            <label className="text-sm font-medium text-muted-foreground">Timestamp</label>
            <p className="text-sm text-foreground mt-1">{formatTimestamp(event?.timestamp)}</p>
          </div>
          
          <div>
            <label className="text-sm font-medium text-muted-foreground">Source</label>
            <div className="flex items-center space-x-2 mt-1">
              <Icon name="Server" size={16} className="text-muted-foreground" />
              <p className="text-sm text-foreground">{event?.source}</p>
            </div>
          </div>
          
          <div>
            <label className="text-sm font-medium text-muted-foreground">Category</label>
            <div className="flex items-center space-x-2 mt-1">
              <div className={`flex items-center space-x-2 px-3 py-1 rounded-md ${getCategoryColor(event?.category)}`}>
                <Icon name={getCategoryIcon(event?.category)} size={16} />
                <span className="text-sm font-medium">{event?.category}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-muted-foreground">Severity Level</label>
            <div className="flex items-center space-x-2 mt-1">
              <div className="w-full bg-muted rounded-full h-2">
                <div 
                  className={`h-2 rounded-full ${
                    event?.severity >= 9 ? 'bg-red-500' :
                    event?.severity >= 7 ? 'bg-orange-500' :
                    event?.severity >= 4 ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${event?.severity * 10}%` }}
                />
              </div>
              <span className="text-sm font-medium text-foreground">{event?.severity}/10</span>
            </div>
          </div>
          
          <div>
            <label className="text-sm font-medium text-muted-foreground">User Agent</label>
            <p className="text-sm text-foreground mt-1">{event?.userAgent || 'N/A'}</p>
          </div>
          
          <div>
            <label className="text-sm font-medium text-muted-foreground">IP Address</label>
            <p className="text-sm font-mono text-foreground mt-1">{event?.ipAddress || 'N/A'}</p>
          </div>
          
          <div>
            <label className="text-sm font-medium text-muted-foreground">Status</label>
            <div className="flex items-center space-x-2 mt-1">
              <div className={`w-2 h-2 rounded-full ${
                event?.status === 'resolved' ? 'bg-green-500' :
                event?.status === 'investigating' ? 'bg-yellow-500' : 'bg-red-500'
              }`} />
              <span className="text-sm text-foreground capitalize">{event?.status || 'open'}</span>
            </div>
          </div>
        </div>
      </div>
      <div>
        <label className="text-sm font-medium text-muted-foreground">Event Message</label>
        <div className="mt-2 p-4 bg-muted rounded-md">
          <p className="text-sm text-foreground leading-relaxed">{event?.message}</p>
        </div>
      </div>
      {event?.metadata && (
        <div>
          <label className="text-sm font-medium text-muted-foreground">Additional Metadata</label>
          <div className="mt-2 p-4 bg-muted rounded-md">
            <pre className="text-xs text-foreground font-mono whitespace-pre-wrap">
              {JSON.stringify(event?.metadata, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};

export default EventInformation;