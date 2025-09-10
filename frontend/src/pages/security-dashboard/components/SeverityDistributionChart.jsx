import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const SeverityDistributionChart = ({ data = [] }) => {
  const getBarColor = (severity) => {
    if (severity >= 9) return '#DC2626'; // red-600
    if (severity >= 7) return '#D97706'; // amber-600
    if (severity >= 4) return '#3B82F6'; // blue-500
    return '#059669'; // emerald-600
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload?.length) {
      return (
        <div className="bg-card border border-border rounded-lg shadow-elevation-2 p-3">
          <p className="text-sm font-medium text-foreground">
            Severity {label}
          </p>
          <p className="text-sm text-muted-foreground">
            Events: {payload?.[0]?.value}
          </p>
        </div>
      );
    }
    return null;
  };

  const CustomBar = (props) => {
    const { payload } = props;
    const color = getBarColor(payload?.severity || 0);
    return <Bar {...props} fill={color} />;
  };

  return (
    <div className="bg-card border border-border rounded-lg shadow-elevation-1">
      <div className="p-6 border-b border-border">
        <h2 className="text-lg font-semibold text-foreground">Severity Distribution</h2>
        <p className="text-sm text-muted-foreground mt-1">Event count by severity level</p>
      </div>
      <div className="p-6">
        <div className="w-full h-64" aria-label="Severity Distribution Bar Chart">
          {data?.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-muted-foreground">No data available</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                <XAxis 
                  dataKey="severity" 
                  stroke="#64748B"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis 
                  stroke="#64748B"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar 
                  dataKey="count" 
                  radius={[4, 4, 0, 0]}
                  shape={<CustomBar />}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        
        <div className="mt-4 flex items-center justify-center space-x-6 text-xs">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-sm bg-success"></div>
            <span className="text-muted-foreground">Low (1-3)</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-sm bg-accent"></div>
            <span className="text-muted-foreground">Medium (4-6)</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-sm bg-warning"></div>
            <span className="text-muted-foreground">High (7-8)</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-sm bg-error"></div>
            <span className="text-muted-foreground">Critical (9-10)</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SeverityDistributionChart;