import React, { useState } from 'react';
import Icon from '../../../components/AppIcon';
import Button from '../../../components/ui/Button';

const ConnectionStatusPanel = ({ connectionStatus, onReconnect, onRefresh }) => {
  const [isReconnecting, setIsReconnecting] = useState(false);

  const handleReconnect = async () => {
    setIsReconnecting(true);
    try {
      await onReconnect();
    } finally {
      setTimeout(() => setIsReconnecting(false), 2000);
    }
  };

  const getConnectionQuality = () => {
    const { latency } = connectionStatus;
    if (latency < 50) return { label: 'Excellent', color: 'text-success', bars: 4 };
    if (latency < 100) return { label: 'Good', color: 'text-success', bars: 3 };
    if (latency < 200) return { label: 'Fair', color: 'text-warning', bars: 2 };
    return { label: 'Poor', color: 'text-error', bars: 1 };
  };

  const quality = getConnectionQuality();

  return (
    <div className="bg-card border border-border rounded-lg p-6 shadow-elevation-1">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-foreground">WebSocket Connection</h3>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            iconName="RefreshCw"
            iconPosition="left"
            onClick={onRefresh}
          >
            Refresh
          </Button>
          <Button
            variant={connectionStatus?.connected ? "outline" : "default"}
            size="sm"
            iconName="Wifi"
            iconPosition="left"
            loading={isReconnecting}
            onClick={handleReconnect}
            disabled={connectionStatus?.connected}
          >
            {isReconnecting ? 'Reconnecting...' : 'Reconnect'}
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Connection Status */}
        <div className="flex items-center space-x-3">
          <div className={`p-2 rounded-md ${connectionStatus?.connected ? 'bg-success/10' : 'bg-error/10'}`}>
            <Icon 
              name={connectionStatus?.connected ? 'CheckCircle' : 'XCircle'} 
              size={20} 
              className={connectionStatus?.connected ? 'text-success' : 'text-error'} 
            />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Status</p>
            <p className={`font-semibold ${connectionStatus?.connected ? 'text-success' : 'text-error'}`}>
              {connectionStatus?.connected ? 'Connected' : 'Disconnected'}
            </p>
          </div>
        </div>

        {/* Connection Quality */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1">
            {[1, 2, 3, 4]?.map((bar) => (
              <div
                key={bar}
                className={`w-1 rounded-full ${
                  bar <= quality?.bars 
                    ? quality?.color?.replace('text-', 'bg-')
                    : 'bg-muted'
                }`}
                style={{ height: `${8 + bar * 2}px` }}
              />
            ))}
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Quality</p>
            <p className={`font-semibold ${quality?.color}`}>
              {quality?.label}
            </p>
          </div>
        </div>

        {/* Latency */}
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-md bg-muted/50">
            <Icon name="Zap" size={20} className="text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Latency</p>
            <p className="font-semibold text-foreground">
              {connectionStatus?.latency}ms
            </p>
          </div>
        </div>

        {/* Messages Count */}
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-md bg-muted/50">
            <Icon name="MessageSquare" size={20} className="text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Messages</p>
            <p className="font-semibold text-foreground">
              {connectionStatus?.messagesReceived?.toLocaleString()}
            </p>
          </div>
        </div>
      </div>
      {/* Connection Details */}
      <div className="mt-6 pt-6 border-t border-border">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Connected Since:</span>
            <span className="ml-2 font-medium text-foreground">
              {new Date(connectionStatus.connectedSince)?.toLocaleString()}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Last Message:</span>
            <span className="ml-2 font-medium text-foreground">
              {new Date(connectionStatus.lastMessage)?.toLocaleTimeString()}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Reconnect Count:</span>
            <span className="ml-2 font-medium text-foreground">
              {connectionStatus?.reconnectCount}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConnectionStatusPanel;