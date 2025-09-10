import React, { useState } from 'react';
import Icon from '../../../components/AppIcon';
import Button from '../../../components/ui/Button';

const EventActions = ({ event, onMarkForFollowUp, onExportReport, onCopyEventData }) => {
  const [isMarkedForFollowUp, setIsMarkedForFollowUp] = useState(event?.markedForFollowUp || false);
  const [exportLoading, setExportLoading] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);

  const handleMarkForFollowUp = async () => {
    try {
      await onMarkForFollowUp(event?.id, !isMarkedForFollowUp);
      setIsMarkedForFollowUp(!isMarkedForFollowUp);
    } catch (error) {
      console.error('Failed to mark for follow-up:', error);
    }
  };

  const handleExportReport = async () => {
    setExportLoading(true);
    try {
      await onExportReport(event?.id);
    } catch (error) {
      console.error('Failed to export report:', error);
    } finally {
      setExportLoading(false);
    }
  };

  const handleCopyEventData = async () => {
    try {
      await onCopyEventData(event);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch (error) {
      console.error('Failed to copy event data:', error);
    }
  };

  const getStatusActions = () => {
    const currentStatus = event?.status || 'open';
    const statusOptions = [
      { value: 'open', label: 'Open', icon: 'Circle', color: 'text-red-500' },
      { value: 'investigating', label: 'Investigating', icon: 'Search', color: 'text-yellow-500' },
      { value: 'resolved', label: 'Resolved', icon: 'CheckCircle', color: 'text-green-500' },
      { value: 'false_positive', label: 'False Positive', icon: 'X', color: 'text-gray-500' }
    ];

    return statusOptions?.filter(option => option?.value !== currentStatus);
  };

  return (
    <div className="space-y-6">
      {/* Primary Actions */}
      <div className="flex flex-wrap gap-3">
        <Button
          variant={isMarkedForFollowUp ? "default" : "outline"}
          onClick={handleMarkForFollowUp}
          iconName={isMarkedForFollowUp ? "BookmarkCheck" : "Bookmark"}
          iconPosition="left"
        >
          {isMarkedForFollowUp ? 'Marked for Follow-up' : 'Mark for Follow-up'}
        </Button>

        <Button
          variant="outline"
          onClick={handleExportReport}
          loading={exportLoading}
          iconName="Download"
          iconPosition="left"
        >
          Export Analysis Report
        </Button>

        <Button
          variant="outline"
          onClick={handleCopyEventData}
          iconName={copySuccess ? "Check" : "Copy"}
          iconPosition="left"
        >
          {copySuccess ? 'Copied!' : 'Copy Event Data'}
        </Button>
      </div>
      {/* Status Management */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-foreground flex items-center space-x-2">
          <Icon name="Flag" size={16} />
          <span>Status Management</span>
        </h4>
        
        <div className="flex items-center space-x-3 p-3 bg-muted rounded-md">
          <div className="flex items-center space-x-2">
            <Icon 
              name={event?.status === 'resolved' ? 'CheckCircle' : 
                    event?.status === 'investigating' ? 'Search' : 'Circle'} 
              size={16} 
              className={event?.status === 'resolved' ? 'text-green-500' : 
                        event?.status === 'investigating' ? 'text-yellow-500' : 'text-red-500'} 
            />
            <span className="text-sm font-medium text-foreground capitalize">
              Current: {event?.status || 'open'}
            </span>
          </div>
          
          <div className="flex space-x-2">
            {getStatusActions()?.map((statusOption) => (
              <Button
                key={statusOption?.value}
                variant="outline"
                size="sm"
                iconName={statusOption?.icon}
                iconPosition="left"
                onClick={() => {
                  // Handle status change
                  console.log(`Changing status to: ${statusOption?.value}`);
                }}
              >
                {statusOption?.label}
              </Button>
            ))}
          </div>
        </div>
      </div>
      {/* Investigation Tools */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-foreground flex items-center space-x-2">
          <Icon name="Search" size={16} />
          <span>Investigation Tools</span>
        </h4>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Button
            variant="outline"
            size="sm"
            iconName="Globe"
            iconPosition="left"
            onClick={() => {
              // Open IP lookup
              if (event?.ipAddress) {
                window.open(`https://whatismyipaddress.com/ip/${event?.ipAddress}`, '_blank');
              }
            }}
            disabled={!event?.ipAddress}
          >
            IP Lookup
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            iconName="Shield"
            iconPosition="left"
            onClick={() => {
              // Open threat intelligence
              console.log('Opening threat intelligence for:', event?.source);
            }}
          >
            Threat Intel
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            iconName="Search"
            iconPosition="left"
            onClick={() => {
              // Search similar events
              console.log('Searching similar events for:', event?.category);
            }}
          >
            Similar Events
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            iconName="Clock"
            iconPosition="left"
            onClick={() => {
              // View timeline
              console.log('Viewing timeline for:', event?.source);
            }}
          >
            View Timeline
          </Button>
        </div>
      </div>
      {/* Collaboration */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-foreground flex items-center space-x-2">
          <Icon name="Users" size={16} />
          <span>Collaboration</span>
        </h4>
        
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            iconName="MessageSquare"
            iconPosition="left"
            onClick={() => {
              // Add comment
              console.log('Adding comment to event:', event?.id);
            }}
          >
            Add Comment
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            iconName="UserPlus"
            iconPosition="left"
            onClick={() => {
              // Assign to analyst
              console.log('Assigning event to analyst:', event?.id);
            }}
          >
            Assign Analyst
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            iconName="Bell"
            iconPosition="left"
            onClick={() => {
              // Create alert
              console.log('Creating alert for event:', event?.id);
            }}
          >
            Create Alert
          </Button>
        </div>
      </div>
      {/* Event Metadata */}
      <div className="p-4 bg-muted rounded-md">
        <h5 className="text-sm font-medium text-foreground mb-3">Event Metadata</h5>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div>
            <span className="text-muted-foreground">Created:</span>
            <p className="text-foreground font-medium">
              {new Date(event.timestamp)?.toLocaleDateString()}
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">Last Modified:</span>
            <p className="text-foreground font-medium">
              {new Date(event.lastModified || event.timestamp)?.toLocaleDateString()}
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">Assigned To:</span>
            <p className="text-foreground font-medium">
              {event?.assignedTo || 'Unassigned'}
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">Priority:</span>
            <p className={`font-medium ${
              event?.priority === 'High' ? 'text-red-600' :
              event?.priority === 'Medium' ? 'text-yellow-600' : 'text-green-600'
            }`}>
              {event?.priority || 'Normal'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EventActions;