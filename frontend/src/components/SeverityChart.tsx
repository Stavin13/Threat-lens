import React, { useMemo, useCallback } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
  TooltipItem,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { EventResponse } from '../types';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

interface SeverityChartProps {
  events: EventResponse[];
  onSeverityClick?: (severity: number) => void;
  className?: string;
  height?: number;
}

interface SeverityData {
  severity: number;
  count: number;
  events: EventResponse[];
}

const SeverityChart: React.FC<SeverityChartProps> = ({
  events,
  onSeverityClick,
  className = '',
  height = 300,
}) => {
  // Process events to create severity distribution data
  const severityData = useMemo(() => {
    const severityMap = new Map<number, SeverityData>();
    
    // Initialize all severity levels 1-10
    for (let i = 1; i <= 10; i++) {
      severityMap.set(i, {
        severity: i,
        count: 0,
        events: [],
      });
    }
    
    // Count events by severity
    events.forEach(event => {
      const severity = event.analysis.severity_score;
      const existing = severityMap.get(severity);
      if (existing) {
        existing.count += 1;
        existing.events.push(event);
      }
    });
    
    return Array.from(severityMap.values());
  }, [events]);

  // Get color for severity level
  const getSeverityColor = useCallback((severity: number): string => {
    if (severity >= 8) return '#dc2626'; // red-600 - Critical
    if (severity >= 6) return '#ea580c'; // orange-600 - High
    if (severity >= 4) return '#d97706'; // amber-600 - Medium
    if (severity >= 2) return '#ca8a04'; // yellow-600 - Low
    return '#16a34a'; // green-600 - Very Low
  }, []);

  // Get severity label
  const getSeverityLabel = useCallback((severity: number): string => {
    if (severity >= 8) return 'Critical';
    if (severity >= 6) return 'High';
    if (severity >= 4) return 'Medium';
    if (severity >= 2) return 'Low';
    return 'Very Low';
  }, []);

  // Chart data configuration
  const chartData = useMemo(() => ({
    labels: severityData.map(d => `${d.severity}`),
    datasets: [
      {
        label: 'Event Count',
        data: severityData.map(d => d.count),
        backgroundColor: severityData.map(d => getSeverityColor(d.severity)),
        borderColor: severityData.map(d => getSeverityColor(d.severity)),
        borderWidth: 1,
        hoverBackgroundColor: severityData.map(d => getSeverityColor(d.severity) + 'CC'),
        hoverBorderColor: severityData.map(d => getSeverityColor(d.severity)),
        hoverBorderWidth: 2,
      },
    ],
  }), [severityData, getSeverityColor]);

  // Chart options configuration
  const chartOptions: ChartOptions<'bar'> = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false, // Hide legend since we have custom severity labels
      },
      title: {
        display: true,
        text: 'Event Severity Distribution',
        font: {
          size: 16,
          weight: 'bold',
        },
        color: '#374151', // gray-700
      },
      tooltip: {
        callbacks: {
          title: (tooltipItems: TooltipItem<'bar'>[]) => {
            const severity = parseInt(tooltipItems[0].label);
            return `Severity ${severity} (${getSeverityLabel(severity)})`;
          },
          label: (context: TooltipItem<'bar'>) => {
            const count = context.parsed.y;
            return `${count} event${count !== 1 ? 's' : ''}`;
          },
          afterLabel: (context: TooltipItem<'bar'>) => {
            const severity = parseInt(context.label);
            const data = severityData.find(d => d.severity === severity);
            if (data && data.events.length > 0) {
              const recentEvent = data.events[data.events.length - 1];
              return `Latest: ${recentEvent.event.source}`;
            }
            return '';
          },
        },
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        titleColor: '#ffffff',
        bodyColor: '#ffffff',
        borderColor: '#374151',
        borderWidth: 1,
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Severity Level',
          font: {
            size: 12,
            weight: 'bold',
          },
          color: '#6b7280', // gray-500
        },
        grid: {
          display: false,
        },
        ticks: {
          color: '#6b7280',
        },
      },
      y: {
        title: {
          display: true,
          text: 'Number of Events',
          font: {
            size: 12,
            weight: 'bold',
          },
          color: '#6b7280', // gray-500
        },
        beginAtZero: true,
        ticks: {
          stepSize: 1,
          color: '#6b7280',
        },
        grid: {
          color: '#f3f4f6', // gray-100
        },
      },
    },
    onClick: (event, elements) => {
      if (elements.length > 0 && onSeverityClick) {
        const elementIndex = elements[0].index;
        const severity = severityData[elementIndex].severity;
        onSeverityClick(severity);
      }
    },
    onHover: (event, elements) => {
      const canvas = event.native?.target as HTMLCanvasElement;
      if (canvas) {
        canvas.style.cursor = elements.length > 0 && onSeverityClick ? 'pointer' : 'default';
      }
    },
  }), [severityData, getSeverityLabel, onSeverityClick]);

  // Calculate summary statistics
  const totalEvents = events.length;
  const averageSeverity = totalEvents > 0 
    ? events.reduce((sum, event) => sum + event.analysis.severity_score, 0) / totalEvents 
    : 0;
  const highSeverityCount = events.filter(event => event.analysis.severity_score >= 6).length;

  return (
    <div className={`bg-white shadow rounded-lg p-6 ${className}`}>
      <div className="mb-4">
        <div className="flex justify-between items-center mb-2">
          <h2 className="text-lg font-medium text-gray-900">
            Severity Distribution
          </h2>
          {onSeverityClick && (
            <p className="text-sm text-gray-500">
              Click bars to filter by severity
            </p>
          )}
        </div>
        
        {/* Summary Statistics */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900">{totalEvents}</div>
            <div className="text-sm text-gray-500">Total Events</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900">
              {averageSeverity.toFixed(1)}
            </div>
            <div className="text-sm text-gray-500">Avg Severity</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600">{highSeverityCount}</div>
            <div className="text-sm text-gray-500">High Severity (6+)</div>
          </div>
        </div>
      </div>

      {/* Chart Container */}
      <div style={{ height: `${height}px` }}>
        {totalEvents > 0 ? (
          <Bar data={chartData} options={chartOptions} />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <div className="text-4xl mb-2">📊</div>
              <p>No events to display</p>
              <p className="text-sm">Upload logs to see severity distribution</p>
            </div>
          </div>
        )}
      </div>

      {/* Severity Legend */}
      <div className="mt-4 pt-4 border-t border-gray-200">
        <div className="flex flex-wrap gap-4 justify-center">
          {[
            { range: '1-2', label: 'Very Low', color: '#16a34a' },
            { range: '3-4', label: 'Low', color: '#ca8a04' },
            { range: '5-6', label: 'Medium', color: '#d97706' },
            { range: '7-8', label: 'High', color: '#ea580c' },
            { range: '9-10', label: 'Critical', color: '#dc2626' },
          ].map(({ range, label, color }) => (
            <div key={range} className="flex items-center space-x-2">
              <div
                className="w-3 h-3 rounded"
                style={{ backgroundColor: color }}
              />
              <span className="text-sm text-gray-600">
                {range}: {label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default SeverityChart;