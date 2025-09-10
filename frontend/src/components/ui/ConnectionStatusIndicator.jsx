import React from 'react';
import Icon from '../AppIcon';

const ConnectionStatusIndicator = ({ status = { connected: true, lastUpdate: new Date() } }) => {
  const { connected, lastUpdate } = status;
  
  const getStatusColor = () => {
    if (connected) {
      return 'text-success';
    }
    return 'text-error';
  };

  const getStatusText = () => {
    if (connected) {
      return 'Connected';
    }
    return 'Disconnected';
  };

  const formatLastUpdate = () => {
    if (!lastUpdate) return '';
    
    const now = new Date();
    const diff = Math.floor((now - new Date(lastUpdate)) / 1000);
    
    if (diff < 60) {
      return 'Just now';
    } else if (diff < 3600) {
      const minutes = Math.floor(diff / 60);
      return `${minutes}m ago`;
    } else if (diff < 86400) {
      const hours = Math.floor(diff / 3600);
      return `${hours}h ago`;
    } else {
      return new Date(lastUpdate)?.toLocaleDateString();
    }
  };

  return (
    <div className="flex items-center space-x-2 px-3 py-1.5 rounded-md bg-muted/50">
      <div className="relative">
        <Icon 
          name="Wifi" 
          size={16} 
          className={`${getStatusColor()} ${connected ? 'animate-pulse-slow' : ''}`}
        />
        {connected && (
          <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-success rounded-full animate-pulse-slow" />
        )}
      </div>
      
      <div className="hidden sm:flex flex-col">
        <span className={`text-xs font-medium ${getStatusColor()}`}>
          {getStatusText()}
        </span>
        {lastUpdate && (
          <span className="text-xs text-muted-foreground">
            {formatLastUpdate()}
          </span>
        )}
      </div>
      
      {/* Mobile - Status dot only */}
      <div className="sm:hidden">
        <div className={`w-2 h-2 rounded-full ${connected ? 'bg-success animate-pulse-slow' : 'bg-error'}`} />
      </div>
    </div>
  );
};

export default ConnectionStatusIndicator;