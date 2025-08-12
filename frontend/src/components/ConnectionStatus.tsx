import React from 'react';
import { ConnectionStatus as ConnectionStatusType } from '../services/websocket';

interface ConnectionStatusProps {
  status: ConnectionStatusType;
  onReconnect?: () => void;
  className?: string;
}

const ConnectionStatus: React.FC<ConnectionStatusProps> = ({ 
  status, 
  onReconnect,
  className = '' 
}) => {
  const getStatusColor = () => {
    if (status.connected) return 'bg-green-500';
    if (status.connecting) return 'bg-yellow-500';
    if (status.error) return 'bg-red-500';
    return 'bg-gray-500';
  };

  const getStatusText = () => {
    if (status.connected) return 'Connected';
    if (status.connecting) return 'Connecting...';
    if (status.error) return 'Disconnected';
    return 'Not connected';
  };

  const getStatusIcon = () => {
    if (status.connected) return '●';
    if (status.connecting) return '◐';
    if (status.error) return '●';
    return '○';
  };

  const formatLastConnected = () => {
    if (!status.lastConnected) return 'Never';
    
    const now = new Date();
    const diff = now.getTime() - status.lastConnected.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  };

  return (
    <div className={`flex items-center space-x-2 ${className}`}>
      {/* Status indicator */}
      <div className="flex items-center space-x-1">
        <div className={`w-2 h-2 rounded-full ${getStatusColor()} ${status.connecting ? 'animate-pulse' : ''}`}>
          <span className="sr-only">{getStatusText()}</span>
        </div>
        <span className="text-sm text-gray-600">
          {getStatusIcon()} {getStatusText()}
        </span>
      </div>

      {/* Detailed status for disconnected state */}
      {!status.connected && (
        <div className="flex items-center space-x-2 text-xs text-gray-500">
          {status.error && (
            <span className="text-red-600" title={status.error}>
              Error
            </span>
          )}
          
          {status.reconnectAttempts > 0 && (
            <span>
              Retry {status.reconnectAttempts}/10
            </span>
          )}

          {status.lastConnected && (
            <span>
              Last: {formatLastConnected()}
            </span>
          )}

          {onReconnect && !status.connecting && (
            <button
              onClick={onReconnect}
              className="text-blue-600 hover:text-blue-800 underline"
              title="Reconnect manually"
            >
              Reconnect
            </button>
          )}
        </div>
      )}

      {/* Connected status details */}
      {status.connected && status.lastConnected && (
        <span className="text-xs text-gray-500">
          Connected {formatLastConnected()}
        </span>
      )}
    </div>
  );
};

export default ConnectionStatus;