import React, { useState, useEffect } from 'react';
import SeverityChart from './SeverityChart';
import { EventResponse } from '../types';

const SeverityChartDemo: React.FC = () => {
  const [events, setEvents] = useState<EventResponse[]>([]);
  const [selectedSeverity, setSelectedSeverity] = useState<number | null>(null);

  // Sample events for demonstration
  const sampleEvents: EventResponse[] = [
    {
      event: {
        id: '1',
        timestamp: '2024-01-08T10:00:00Z',
        source: 'auth.log',
        message: 'Failed login attempt for user admin',
        category: 'authentication',
      },
      analysis: {
        severity_score: 8,
        explanation: 'Multiple failed login attempts detected for admin account',
        recommendations: ['Monitor for brute force attacks', 'Consider account lockout policies'],
      },
    },
    {
      event: {
        id: '2',
        timestamp: '2024-01-08T10:05:00Z',
        source: 'system.log',
        message: 'User john logged in successfully',
        category: 'authentication',
      },
      analysis: {
        severity_score: 2,
        explanation: 'Normal user login event',
        recommendations: ['No action required'],
      },
    },
    {
      event: {
        id: '3',
        timestamp: '2024-01-08T10:10:00Z',
        source: 'system.log',
        message: 'Critical system error: disk space low',
        category: 'system',
      },
      analysis: {
        severity_score: 9,
        explanation: 'Critical system resource issue detected',
        recommendations: ['Free up disk space immediately', 'Monitor system resources'],
      },
    },
    {
      event: {
        id: '4',
        timestamp: '2024-01-08T10:15:00Z',
        source: 'network.log',
        message: 'Network connection established to 192.168.1.100',
        category: 'network',
      },
      analysis: {
        severity_score: 3,
        explanation: 'Normal network activity',
        recommendations: ['Monitor for unusual patterns'],
      },
    },
    {
      event: {
        id: '5',
        timestamp: '2024-01-08T10:20:00Z',
        source: 'security.log',
        message: 'Suspicious file access detected',
        category: 'security',
      },
      analysis: {
        severity_score: 7,
        explanation: 'Potential unauthorized file access',
        recommendations: ['Investigate file access patterns', 'Review user permissions'],
      },
    },
    {
      event: {
        id: '6',
        timestamp: '2024-01-08T10:25:00Z',
        source: 'app.log',
        message: 'Application started successfully',
        category: 'application',
      },
      analysis: {
        severity_score: 1,
        explanation: 'Normal application startup',
        recommendations: ['No action required'],
      },
    },
  ];

  useEffect(() => {
    // Simulate loading events
    setEvents(sampleEvents);
  }, []);

  const handleSeverityClick = (severity: number) => {
    setSelectedSeverity(selectedSeverity === severity ? null : severity);
  };

  const filteredEvents = selectedSeverity 
    ? events.filter(event => event.analysis.severity_score === selectedSeverity)
    : events;

  const addRandomEvent = () => {
    const severities = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    const categories = ['authentication', 'system', 'network', 'security', 'application'];
    const sources = ['auth.log', 'system.log', 'network.log', 'security.log', 'app.log'];
    
    const randomSeverity = severities[Math.floor(Math.random() * severities.length)];
    const randomCategory = categories[Math.floor(Math.random() * categories.length)];
    const randomSource = sources[Math.floor(Math.random() * sources.length)];
    
    const newEvent: EventResponse = {
      event: {
        id: `demo-${Date.now()}`,
        timestamp: new Date().toISOString(),
        source: randomSource,
        message: `Demo event with severity ${randomSeverity}`,
        category: randomCategory,
      },
      analysis: {
        severity_score: randomSeverity,
        explanation: `Demo analysis for severity ${randomSeverity} event`,
        recommendations: [`Demo recommendation for severity ${randomSeverity}`],
      },
    };

    setEvents(prev => [...prev, newEvent]);
  };

  const clearEvents = () => {
    setEvents([]);
    setSelectedSeverity(null);
  };

  const resetToSample = () => {
    setEvents(sampleEvents);
    setSelectedSeverity(null);
  };

  return (
    <div className="space-y-6 p-6">
      <div className="border-b border-gray-200 pb-4">
        <h1 className="text-2xl font-bold text-gray-900">Severity Chart Demo</h1>
        <p className="text-gray-600 mt-1">
          Interactive demonstration of the severity visualization chart
        </p>
      </div>

      {/* Controls */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h2 className="text-lg font-medium text-gray-900 mb-3">Demo Controls</h2>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={addRandomEvent}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            Add Random Event
          </button>
          <button
            onClick={resetToSample}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
          >
            Reset to Sample Data
          </button>
          <button
            onClick={clearEvents}
            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
          >
            Clear All Events
          </button>
        </div>
      </div>

      {/* Severity Chart */}
      <SeverityChart 
        events={events} 
        onSeverityClick={handleSeverityClick}
        height={400}
      />

      {/* Filter Status */}
      {selectedSeverity && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-blue-800">
                Filtered by Severity {selectedSeverity}
              </h3>
              <p className="text-sm text-blue-600">
                Showing {filteredEvents.length} event{filteredEvents.length !== 1 ? 's' : ''}
              </p>
            </div>
            <button
              onClick={() => setSelectedSeverity(null)}
              className="text-blue-600 hover:text-blue-800 text-sm font-medium"
            >
              Clear Filter
            </button>
          </div>
        </div>
      )}

      {/* Event List */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">
          {selectedSeverity ? `Events with Severity ${selectedSeverity}` : 'All Events'}
        </h2>
        {filteredEvents.length > 0 ? (
          <div className="space-y-4">
            {filteredEvents.map((eventResponse) => (
              <div key={eventResponse.event.id} className="border-l-4 border-gray-200 pl-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        eventResponse.analysis.severity_score >= 8 ? 'bg-red-100 text-red-800' :
                        eventResponse.analysis.severity_score >= 6 ? 'bg-orange-100 text-orange-800' :
                        eventResponse.analysis.severity_score >= 4 ? 'bg-yellow-100 text-yellow-800' :
                        eventResponse.analysis.severity_score >= 2 ? 'bg-blue-100 text-blue-800' :
                        'bg-green-100 text-green-800'
                      }`}>
                        Severity {eventResponse.analysis.severity_score}
                      </span>
                      <span className="text-sm text-gray-500 capitalize">
                        {eventResponse.event.category}
                      </span>
                      <span className="text-sm text-gray-500">
                        {eventResponse.event.source}
                      </span>
                    </div>
                    <p className="text-sm text-gray-900 mt-1">
                      {eventResponse.event.message}
                    </p>
                    <p className="text-xs text-gray-600 mt-1">
                      {eventResponse.analysis.explanation}
                    </p>
                  </div>
                  <div className="text-sm text-gray-500">
                    {new Date(eventResponse.event.timestamp).toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <div className="text-4xl mb-2">📊</div>
            <p>No events to display</p>
            <p className="text-sm">
              {selectedSeverity 
                ? `No events with severity ${selectedSeverity}` 
                : 'Click "Add Random Event" to see the chart in action'
              }
            </p>
          </div>
        )}
      </div>

      {/* Feature Highlights */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">
          Chart Features Demonstrated
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <h3 className="font-medium text-gray-900">Interactive Features</h3>
            <ul className="text-sm text-gray-600 space-y-1">
              <li>• Click bars to filter by severity level</li>
              <li>• Hover tooltips with event details</li>
              <li>• Real-time updates when events change</li>
              <li>• Responsive design for different screen sizes</li>
            </ul>
          </div>
          <div className="space-y-2">
            <h3 className="font-medium text-gray-900">Visual Elements</h3>
            <ul className="text-sm text-gray-600 space-y-1">
              <li>• Color-coded severity levels</li>
              <li>• Summary statistics display</li>
              <li>• Severity legend with ranges</li>
              <li>• Empty state handling</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SeverityChartDemo;