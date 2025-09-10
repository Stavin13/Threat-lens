import React, { useState } from 'react';
import Icon from '../../../components/AppIcon';
import Button from '../../../components/ui/Button';
import { Checkbox } from '../../../components/ui/Checkbox';

const EventsDataTable = ({ 
  events = [], 
  selectedEvents = [], 
  onEventSelect, 
  onEventClick,
  sortConfig,
  onSort,
  loading = false 
}) => {
  const [expandedRows, setExpandedRows] = useState(new Set());

  const getSeverityColor = (severity) => {
    if (severity >= 9) return 'bg-red-500 text-white';
    if (severity >= 7) return 'bg-orange-500 text-white';
    if (severity >= 4) return 'bg-yellow-500 text-black';
    return 'bg-green-500 text-white';
  };

  const getSeverityLabel = (severity) => {
    if (severity >= 9) return 'Critical';
    if (severity >= 7) return 'High';
    if (severity >= 4) return 'Medium';
    return 'Low';
  };

  const getCategoryIcon = (category) => {
    const icons = {
      authentication: 'Key',
      network: 'Wifi',
      malware: 'Shield',
      intrusion: 'AlertTriangle',
      data_access: 'Database',
      system: 'Server',
      compliance: 'FileCheck'
    };
    return icons?.[category] || 'AlertCircle';
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp)?.toLocaleString('en-US', {
      month: 'short',
      day: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const handleSort = (column) => {
    const direction = sortConfig?.column === column && sortConfig?.direction === 'asc' ? 'desc' : 'asc';
    onSort({ column, direction });
  };

  const getSortIcon = (column) => {
    if (sortConfig?.column !== column) return 'ArrowUpDown';
    return sortConfig?.direction === 'asc' ? 'ArrowUp' : 'ArrowDown';
  };

  const toggleRowExpansion = (eventId) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded?.has(eventId)) {
      newExpanded?.delete(eventId);
    } else {
      newExpanded?.add(eventId);
    }
    setExpandedRows(newExpanded);
  };

  const handleSelectAll = (checked) => {
    if (checked) {
      onEventSelect(events?.map(event => event?.id));
    } else {
      onEventSelect([]);
    }
  };

  const isAllSelected = events?.length > 0 && selectedEvents?.length === events?.length;
  const isIndeterminate = selectedEvents?.length > 0 && selectedEvents?.length < events?.length;

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-lg shadow-elevation-1">
        <div className="p-6">
          <div className="animate-pulse space-y-4">
            {[...Array(5)]?.map((_, i) => (
              <div key={i} className="flex items-center space-x-4">
                <div className="w-4 h-4 bg-muted rounded" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-muted rounded w-3/4" />
                  <div className="h-3 bg-muted rounded w-1/2" />
                </div>
                <div className="w-16 h-6 bg-muted rounded" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-lg shadow-elevation-1 overflow-hidden">
      {/* Desktop Table */}
      <div className="hidden lg:block overflow-x-auto">
        <table className="w-full">
          <thead className="bg-muted/50 border-b border-border">
            <tr>
              <th className="w-12 p-4">
                <Checkbox
                  checked={isAllSelected}
                  indeterminate={isIndeterminate}
                  onChange={(e) => handleSelectAll(e?.target?.checked)}
                />
              </th>
              <th className="text-left p-4">
                <Button
                  variant="ghost"
                  size="sm"
                  iconName={getSortIcon('timestamp')}
                  iconPosition="right"
                  onClick={() => handleSort('timestamp')}
                  className="font-semibold text-foreground"
                >
                  Timestamp
                </Button>
              </th>
              <th className="text-left p-4">
                <Button
                  variant="ghost"
                  size="sm"
                  iconName={getSortIcon('source')}
                  iconPosition="right"
                  onClick={() => handleSort('source')}
                  className="font-semibold text-foreground"
                >
                  Source
                </Button>
              </th>
              <th className="text-left p-4">
                <Button
                  variant="ghost"
                  size="sm"
                  iconName={getSortIcon('category')}
                  iconPosition="right"
                  onClick={() => handleSort('category')}
                  className="font-semibold text-foreground"
                >
                  Category
                </Button>
              </th>
              <th className="text-left p-4">Message</th>
              <th className="text-left p-4">
                <Button
                  variant="ghost"
                  size="sm"
                  iconName={getSortIcon('severity')}
                  iconPosition="right"
                  onClick={() => handleSort('severity')}
                  className="font-semibold text-foreground"
                >
                  Severity
                </Button>
              </th>
              <th className="w-12 p-4"></th>
            </tr>
          </thead>
          <tbody>
            {events?.map((event) => (
              <React.Fragment key={event?.id}>
                <tr 
                  className="border-b border-border hover:bg-muted/30 cursor-pointer transition-colors"
                  onClick={() => onEventClick(event)}
                >
                  <td className="p-4" onClick={(e) => e?.stopPropagation()}>
                    <Checkbox
                      checked={selectedEvents?.includes(event?.id)}
                      onChange={(e) => {
                        if (e?.target?.checked) {
                          onEventSelect([...selectedEvents, event?.id]);
                        } else {
                          onEventSelect(selectedEvents?.filter(id => id !== event?.id));
                        }
                      }}
                    />
                  </td>
                  <td className="p-4">
                    <div className="text-sm font-medium text-foreground">
                      {formatTimestamp(event?.timestamp)}
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="text-sm text-foreground font-medium">
                      {event?.source}
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center space-x-2">
                      <Icon 
                        name={getCategoryIcon(event?.category)} 
                        size={16} 
                        className="text-muted-foreground" 
                      />
                      <span className="text-sm text-foreground capitalize">
                        {event?.category?.replace('_', ' ')}
                      </span>
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="text-sm text-foreground max-w-md truncate">
                      {event?.message}
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSeverityColor(event?.severity)}`}>
                        {event?.severity}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {getSeverityLabel(event?.severity)}
                      </span>
                    </div>
                  </td>
                  <td className="p-4" onClick={(e) => e?.stopPropagation()}>
                    <Button
                      variant="ghost"
                      size="sm"
                      iconName={expandedRows?.has(event?.id) ? 'ChevronUp' : 'ChevronDown'}
                      onClick={() => toggleRowExpansion(event?.id)}
                    />
                  </td>
                </tr>
                {expandedRows?.has(event?.id) && (
                  <tr className="bg-muted/20">
                    <td colSpan="7" className="p-4">
                      <div className="space-y-3">
                        <div>
                          <h4 className="text-sm font-semibold text-foreground mb-2">Full Message</h4>
                          <p className="text-sm text-muted-foreground bg-background p-3 rounded border">
                            {event?.message}
                          </p>
                        </div>
                        {event?.details && (
                          <div>
                            <h4 className="text-sm font-semibold text-foreground mb-2">Additional Details</h4>
                            <div className="text-sm text-muted-foreground space-y-1">
                              {Object.entries(event?.details)?.map(([key, value]) => (
                                <div key={key} className="flex">
                                  <span className="font-medium w-24 capitalize">{key}:</span>
                                  <span>{value}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {/* Mobile Card Layout */}
      <div className="lg:hidden">
        {events?.map((event) => (
          <div 
            key={event?.id}
            className="p-4 border-b border-border last:border-b-0 hover:bg-muted/30 cursor-pointer transition-colors"
            onClick={() => onEventClick(event)}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center space-x-2" onClick={(e) => e?.stopPropagation()}>
                <Checkbox
                  checked={selectedEvents?.includes(event?.id)}
                  onChange={(e) => {
                    if (e?.target?.checked) {
                      onEventSelect([...selectedEvents, event?.id]);
                    } else {
                      onEventSelect(selectedEvents?.filter(id => id !== event?.id));
                    }
                  }}
                />
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSeverityColor(event?.severity)}`}>
                  {event?.severity}
                </span>
              </div>
              <div className="text-xs text-muted-foreground">
                {formatTimestamp(event?.timestamp)}
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <Icon 
                  name={getCategoryIcon(event?.category)} 
                  size={14} 
                  className="text-muted-foreground" 
                />
                <span className="text-sm font-medium text-foreground capitalize">
                  {event?.category?.replace('_', ' ')}
                </span>
                <span className="text-sm text-muted-foreground">•</span>
                <span className="text-sm text-muted-foreground">{event?.source}</span>
              </div>
              
              <p className="text-sm text-foreground line-clamp-2">
                {event?.message}
              </p>
            </div>
          </div>
        ))}
      </div>
      {events?.length === 0 && !loading && (
        <div className="p-12 text-center">
          <Icon name="Database" size={48} className="text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">No Events Found</h3>
          <p className="text-muted-foreground">
            No security events match your current filter criteria.
          </p>
        </div>
      )}
    </div>
  );
};

export default EventsDataTable;