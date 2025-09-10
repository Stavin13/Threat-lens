import React, { useState } from 'react';
import Icon from '../../../components/AppIcon';
import Input from '../../../components/ui/Input';
import Select from '../../../components/ui/Select';
import Button from '../../../components/ui/Button';

const EventsFilterToolbar = ({ 
  filters, 
  onFiltersChange, 
  totalResults = 0,
  onExport,
  onRefresh 
}) => {
  const [isMobileFiltersOpen, setIsMobileFiltersOpen] = useState(false);

  const categoryOptions = [
    { value: 'all', label: 'All Categories' },
    { value: 'authentication', label: 'Authentication' },
    { value: 'network', label: 'Network Security' },
    { value: 'malware', label: 'Malware Detection' },
    { value: 'intrusion', label: 'Intrusion Detection' },
    { value: 'data_access', label: 'Data Access' },
    { value: 'system', label: 'System Events' },
    { value: 'compliance', label: 'Compliance' }
  ];

  const handleFilterChange = (key, value) => {
    onFiltersChange({
      ...filters,
      [key]: value
    });
  };

  const handleSeverityRangeChange = (type, value) => {
    const newRange = { ...filters?.severityRange };
    newRange[type] = parseInt(value);
    handleFilterChange('severityRange', newRange);
  };

  const getSeverityColor = (severity) => {
    if (severity >= 9) return 'bg-red-500';
    if (severity >= 7) return 'bg-orange-500';
    if (severity >= 4) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  const clearAllFilters = () => {
    onFiltersChange({
      category: 'all',
      severityRange: { min: 1, max: 10 },
      dateRange: { start: '', end: '' },
      searchQuery: ''
    });
  };

  const hasActiveFilters = () => {
    return filters?.category !== 'all' || 
           filters?.severityRange?.min !== 1 || 
           filters?.severityRange?.max !== 10 ||
           filters?.dateRange?.start || 
           filters?.dateRange?.end ||
           filters?.searchQuery;
  };

  return (
    <div className="bg-card border border-border rounded-lg shadow-elevation-1">
      {/* Desktop Filter Toolbar */}
      <div className="hidden lg:block p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-4">
            <h2 className="text-lg font-semibold text-foreground">Security Events</h2>
            <div className="flex items-center space-x-2 px-3 py-1 bg-muted rounded-md">
              <Icon name="Database" size={16} className="text-muted-foreground" />
              <span className="text-sm font-medium text-foreground">
                {totalResults?.toLocaleString()} events
              </span>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              iconName="RefreshCw"
              iconPosition="left"
              onClick={onRefresh}
            >
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              iconName="Download"
              iconPosition="left"
              onClick={onExport}
            >
              Export
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Category Filter */}
          <div>
            <Select
              label="Category"
              options={categoryOptions}
              value={filters?.category}
              onChange={(value) => handleFilterChange('category', value)}
              placeholder="Select category"
            />
          </div>

          {/* Severity Range */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Severity Range
            </label>
            <div className="space-y-3">
              <div className="flex items-center space-x-3">
                <span className="text-xs text-muted-foreground w-8">Min:</span>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={filters?.severityRange?.min}
                  onChange={(e) => handleSeverityRangeChange('min', e?.target?.value)}
                  className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer"
                />
                <div className="flex items-center space-x-1">
                  <div className={`w-3 h-3 rounded-full ${getSeverityColor(filters?.severityRange?.min)}`} />
                  <span className="text-sm font-medium text-foreground w-6">
                    {filters?.severityRange?.min}
                  </span>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                <span className="text-xs text-muted-foreground w-8">Max:</span>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={filters?.severityRange?.max}
                  onChange={(e) => handleSeverityRangeChange('max', e?.target?.value)}
                  className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer"
                />
                <div className="flex items-center space-x-1">
                  <div className={`w-3 h-3 rounded-full ${getSeverityColor(filters?.severityRange?.max)}`} />
                  <span className="text-sm font-medium text-foreground w-6">
                    {filters?.severityRange?.max}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Date Range */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Date Range
            </label>
            <div className="space-y-2">
              <Input
                type="date"
                placeholder="Start date"
                value={filters?.dateRange?.start}
                onChange={(e) => handleFilterChange('dateRange', {
                  ...filters?.dateRange,
                  start: e?.target?.value
                })}
              />
              <Input
                type="date"
                placeholder="End date"
                value={filters?.dateRange?.end}
                onChange={(e) => handleFilterChange('dateRange', {
                  ...filters?.dateRange,
                  end: e?.target?.value
                })}
              />
            </div>
          </div>

          {/* Search */}
          <div>
            <Input
              label="Search Messages"
              type="search"
              placeholder="Search event messages..."
              value={filters?.searchQuery}
              onChange={(e) => handleFilterChange('searchQuery', e?.target?.value)}
            />
          </div>
        </div>

        {hasActiveFilters() && (
          <div className="mt-4 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Icon name="Filter" size={16} className="text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Active filters applied</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              iconName="X"
              iconPosition="left"
              onClick={clearAllFilters}
            >
              Clear All
            </Button>
          </div>
        )}
      </div>
      {/* Mobile Filter Header */}
      <div className="lg:hidden p-4 border-b border-border">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-foreground">Security Events</h2>
          <Button
            variant="outline"
            size="sm"
            iconName="Filter"
            iconPosition="left"
            onClick={() => setIsMobileFiltersOpen(!isMobileFiltersOpen)}
          >
            Filters
          </Button>
        </div>
        
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 px-3 py-1 bg-muted rounded-md">
            <Icon name="Database" size={14} className="text-muted-foreground" />
            <span className="text-sm font-medium text-foreground">
              {totalResults?.toLocaleString()}
            </span>
          </div>
          
          <div className="flex items-center space-x-2">
            <Button
              variant="ghost"
              size="sm"
              iconName="RefreshCw"
              onClick={onRefresh}
            />
            <Button
              variant="ghost"
              size="sm"
              iconName="Download"
              onClick={onExport}
            />
          </div>
        </div>
      </div>
      {/* Mobile Filter Panel */}
      {isMobileFiltersOpen && (
        <div className="lg:hidden p-4 border-t border-border bg-muted/30">
          <div className="space-y-4">
            <Select
              label="Category"
              options={categoryOptions}
              value={filters?.category}
              onChange={(value) => handleFilterChange('category', value)}
            />
            
            <Input
              label="Search Messages"
              type="search"
              placeholder="Search events..."
              value={filters?.searchQuery}
              onChange={(e) => handleFilterChange('searchQuery', e?.target?.value)}
            />
            
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Start Date"
                type="date"
                value={filters?.dateRange?.start}
                onChange={(e) => handleFilterChange('dateRange', {
                  ...filters?.dateRange,
                  start: e?.target?.value
                })}
              />
              <Input
                label="End Date"
                type="date"
                value={filters?.dateRange?.end}
                onChange={(e) => handleFilterChange('dateRange', {
                  ...filters?.dateRange,
                  end: e?.target?.value
                })}
              />
            </div>

            {hasActiveFilters() && (
              <Button
                variant="outline"
                size="sm"
                iconName="X"
                iconPosition="left"
                onClick={clearAllFilters}
                fullWidth
              >
                Clear All Filters
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default EventsFilterToolbar;