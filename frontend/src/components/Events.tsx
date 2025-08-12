import React, { useState } from 'react';
import EventTable from './EventTable';
import ConnectionStatus from './ConnectionStatus';
import { useSecurityEvents } from '../hooks/useRealtimeClient';

const Events: React.FC = () => {
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  // Use WebSocket for real-time events
  const {
    events: realtimeEvents,
    connectionStatus,
    isConnected,
    connect: reconnectWebSocket
  } = useSecurityEvents();

  const handleEventSelect = (eventId: string) => {
    setSelectedEventId(eventId);
  };

  return (
    <div className="space-y-6">
      <div className="border-b border-gray-200 pb-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Security Events</h1>
            <p className="text-gray-600 mt-1">
              Browse and analyze security events with AI-powered insights
            </p>
          </div>
          <div className="flex items-center space-x-4">
            <div className="text-sm text-gray-500">
              {realtimeEvents.length} event{realtimeEvents.length !== 1 ? 's' : ''}
            </div>
            <ConnectionStatus 
              status={connectionStatus} 
              onReconnect={reconnectWebSocket}
              className="border-l pl-4"
            />
          </div>
        </div>
      </div>

      {/* Real-time Status Banner */}
      {!isConnected && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-yellow-800">
                Real-time updates unavailable
              </h3>
              <p className="text-sm text-yellow-700 mt-1">
                Event table is showing cached data. Real-time event updates are not available.
                {connectionStatus.error && ` Error: ${connectionStatus.error}`}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Event Table */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-900">
              Security Events
            </h2>
            {isConnected && (
              <div className="flex items-center text-sm text-green-600">
                <div className="w-2 h-2 bg-green-500 rounded-full mr-1 animate-pulse"></div>
                Live Updates
              </div>
            )}
          </div>
        </div>
        
        <EventTable 
          events={realtimeEvents}
          onEventSelect={handleEventSelect}
          selectedEventId={selectedEventId}
          realTimeEnabled={isConnected}
        />
      </div>
    </div>
  );
};

export default Events;