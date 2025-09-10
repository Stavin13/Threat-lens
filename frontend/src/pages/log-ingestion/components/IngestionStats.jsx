import React from 'react';
import Icon from '../../../components/AppIcon';

const IngestionStats = ({ stats }) => {
  const statCards = [
    {
      id: 'total_uploads',
      label: 'Total Uploads',
      value: stats?.totalUploads || 0,
      icon: 'Upload',
      color: 'text-primary',
      bgColor: 'bg-primary/10'
    },
    {
      id: 'events_processed',
      label: 'Events Processed',
      value: stats?.eventsProcessed || 0,
      icon: 'Activity',
      color: 'text-success',
      bgColor: 'bg-success/10'
    },
    {
      id: 'processing_queue',
      label: 'In Queue',
      value: stats?.queueDepth || 0,
      icon: 'Clock',
      color: 'text-warning',
      bgColor: 'bg-warning/10'
    },
    {
      id: 'failed_uploads',
      label: 'Failed',
      value: stats?.failedUploads || 0,
      icon: 'XCircle',
      color: 'text-error',
      bgColor: 'bg-error/10'
    }
  ];

  const formatNumber = (num) => {
    if (num >= 1000000) {
      return (num / 1000000)?.toFixed(1) + 'M';
    } else if (num >= 1000) {
      return (num / 1000)?.toFixed(1) + 'K';
    }
    return num?.toLocaleString();
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {statCards?.map((stat) => (
        <div key={stat?.id} className="bg-card rounded-lg border border-border p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground mb-1">
                {stat?.label}
              </p>
              <p className="text-2xl font-bold text-foreground">
                {formatNumber(stat?.value)}
              </p>
            </div>
            <div className={`flex items-center justify-center w-10 h-10 rounded-lg ${stat?.bgColor}`}>
              <Icon name={stat?.icon} size={20} className={stat?.color} />
            </div>
          </div>
          
          {stat?.id === 'events_processed' && stats?.processingRate && (
            <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
              <Icon name="TrendingUp" size={12} />
              <span>{stats?.processingRate}/min</span>
            </div>
          )}
          
          {stat?.id === 'processing_queue' && stats?.avgProcessingTime && (
            <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
              <Icon name="Timer" size={12} />
              <span>~{stats?.avgProcessingTime}s avg</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default IngestionStats;