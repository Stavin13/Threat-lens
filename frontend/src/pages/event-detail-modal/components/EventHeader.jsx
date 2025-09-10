import React from 'react';
import Icon from '../../../components/AppIcon';
import Button from '../../../components/ui/Button';

const EventHeader = ({ event, onClose, onPrevious, onNext, hasPrevious, hasNext }) => {
  const getSeverityColor = (severity) => {
    if (severity >= 9) return 'text-red-600 bg-red-50';
    if (severity >= 7) return 'text-orange-600 bg-orange-50';
    if (severity >= 4) return 'text-yellow-600 bg-yellow-50';
    return 'text-green-600 bg-green-50';
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp)?.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  return (
    <div className="flex items-center justify-between p-6 border-b border-border bg-card">
      <div className="flex items-center space-x-4">
        <div className={`px-3 py-1 rounded-full text-sm font-medium ${getSeverityColor(event?.severity)}`}>
          Severity {event?.severity}
        </div>
        <div className="flex flex-col">
          <h2 className="text-lg font-semibold text-foreground">
            Event Details
          </h2>
          <div className="flex items-center space-x-4 text-sm text-muted-foreground">
            <span className="flex items-center space-x-1">
              <Icon name="Clock" size={14} />
              <span>{formatTimestamp(event?.timestamp)}</span>
            </span>
            <span className="flex items-center space-x-1">
              <Icon name="Server" size={14} />
              <span>{event?.source}</span>
            </span>
          </div>
        </div>
      </div>
      <div className="flex items-center space-x-2">
        <Button
          variant="outline"
          size="sm"
          onClick={onPrevious}
          disabled={!hasPrevious}
          iconName="ChevronLeft"
          iconPosition="left"
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onNext}
          disabled={!hasNext}
          iconName="ChevronRight"
          iconPosition="right"
        >
          Next
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          iconName="X"
        />
      </div>
    </div>
  );
};

export default EventHeader;