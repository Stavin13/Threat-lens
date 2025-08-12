import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { EventResponse, EventFilter, EventCategory } from '../types';
import { api } from '../services/api';
import EventDetail from './EventDetail';
import { useSecurityEvents } from '../hooks/useRealtimeClient';
import { useRealtimeClient } from '../hooks/useRealtimeClient';
import type { ProcessingUpdateData } from '../services/realtimeClient';

interface EventTableProps {
  className?: string;
  events?: EventResponse[];
  onEventSelect?: (eventId: string) => void;
  selectedEventId?: string | null;
  realTimeEnabled?: boolean;
  autoRefresh?: boolean;
  showProcessingStatus?: boolean;
}

interface SortConfig {
  key: keyof EventResponse['event'] | 'severity_score';
  direction: 'asc' | 'desc';
}

interface PaginationConfig {
  currentPage: number;
  itemsPerPage: number;
  totalItems: number;
}

const EventTable: React.FC<EventTableProps> = ({ 
  className = '', 
  events: propEvents,
  onEventSelect,
  selectedEventId,
  realTimeEnabled = false,
  autoRefresh = false,
  showProcessingStatus = false
}) => {
  const [events, setEvents] = useState<EventResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortConfig, setSortConfig] = useState<SortConfig>({ key: 'timestamp', direction: 'desc' });
  const [filters, setFilters] = useState<EventFilter>({});
  const [pagination, setPagination] = useState<PaginationConfig>({
    currentPage: 1,
    itemsPerPage: 10,
    totalItems: 0
  });
  const [selectedEvent, setSelectedEvent] = useState<EventResponse | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [processingEvents, setProcessingEvents] = useState<Set<string>>(new Set());
  const [newEventIds, setNewEventIds] = useState<Set<string>>(new Set());
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  // Use real-time events if enabled
  const {
    events: realtimeEvents,
    connectionStatus,
    isConnected: realtimeConnected
  } = useSecurityEvents();

  // Use realtime client for processing updates
  const {
    lastProcessingUpdate,
    isConnected: processingConnected
  } = useRealtimeClient({
    onProcessingUpdate: (data: ProcessingUpdateData) => {
      if (showProcessingStatus) {
        setProcessingEvents(prev => {
          const updated = new Set(prev);
          if (data.status === 'processing') {
            updated.add(data.raw_log_id);
          } else {
            updated.delete(data.raw_log_id);
          }
          return updated;
        });
      }
    }
  });

  // Fetch events from API
  const fetchEvents = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getEvents(filters);
      setEvents(response);
      setPagination(prev => ({ ...prev, totalItems: response.length }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch events');
      setEvents([]);
    } finally {
      setLoading(false);
    }
  };

  // Handle real-time event updates
  const handleRealtimeEvents = useCallback(() => {
    if (realTimeEnabled && realtimeEvents.length > 0) {
      // Mark new events for highlighting
      const currentEventIds = new Set(events.map(e => e.event.id));
      const newIds = new Set(
        realtimeEvents
          .filter(e => !currentEventIds.has(e.event.id))
          .map(e => e.event.id)
      );
      
      if (newIds.size > 0) {
        setNewEventIds(newIds);
        // Clear new event highlighting after 5 seconds
        setTimeout(() => {
          setNewEventIds(prev => {
            const updated = new Set(prev);
            newIds.forEach(id => updated.delete(id));
            return updated;
          });
        }, 5000);
      }

      setEvents(realtimeEvents);
      setPagination(prev => ({ ...prev, totalItems: realtimeEvents.length }));
      setLastUpdate(new Date());
    }
  }, [realTimeEnabled, realtimeEvents, events]);

  // Use prop events if provided, otherwise use real-time events or fetch from API
  useEffect(() => {
    if (propEvents) {
      setEvents(propEvents);
      setLoading(false);
      setError(null);
      setPagination(prev => ({ ...prev, totalItems: propEvents.length }));
    } else if (realTimeEnabled) {
      handleRealtimeEvents();
      setLoading(false);
    } else {
      fetchEvents();
    }
  }, [propEvents, filters, realTimeEnabled, handleRealtimeEvents]);

  // Auto-refresh functionality
  useEffect(() => {
    if (autoRefresh && !realTimeEnabled && !propEvents) {
      const interval = setInterval(() => {
        fetchEvents();
      }, 30000); // Refresh every 30 seconds

      return () => clearInterval(interval);
    }
  }, [autoRefresh, realTimeEnabled, propEvents]);

  // Sort events based on current sort configuration
  const sortedEvents = useMemo(() => {
    const sorted = [...events].sort((a, b) => {
      let aValue: any;
      let bValue: any;

      if (sortConfig.key === 'severity_score') {
        aValue = a.analysis.severity_score;
        bValue = b.analysis.severity_score;
      } else {
        aValue = a.event[sortConfig.key];
        bValue = b.event[sortConfig.key];
      }

      // Handle timestamp sorting
      if (sortConfig.key === 'timestamp') {
        aValue = new Date(aValue).getTime();
        bValue = new Date(bValue).getTime();
      }

      if (aValue < bValue) {
        return sortConfig.direction === 'asc' ? -1 : 1;
      }
      if (aValue > bValue) {
        return sortConfig.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });

    return sorted;
  }, [events, sortConfig]);

  // Paginate sorted events
  const paginatedEvents = useMemo(() => {
    const startIndex = (pagination.currentPage - 1) * pagination.itemsPerPage;
    const endIndex = startIndex + pagination.itemsPerPage;
    return sortedEvents.slice(startIndex, endIndex);
  }, [sortedEvents, pagination.currentPage, pagination.itemsPerPage]);

  // Handle sorting
  const handleSort = (key: keyof EventResponse['event'] | 'severity_score') => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  // Handle filter changes
  const handleFilterChange = (newFilters: Partial<EventFilter>) => {
    setFilters(prev => ({ ...prev, ...newFilters }));
    setPagination(prev => ({ ...prev, currentPage: 1 })); // Reset to first page
  };

  // Handle pagination
  const handlePageChange = (page: number) => {
    setPagination(prev => ({ ...prev, currentPage: page }));
  };

  // Clear all filters
  const clearFilters = () => {
    setFilters({});
    setPagination(prev => ({ ...prev, currentPage: 1 }));
  };

  // Format timestamp for display
  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  // Get severity color class
  const getSeverityColor = (severity: number) => {
    if (severity >= 8) return 'text-red-600 bg-red-100';
    if (severity >= 6) return 'text-orange-600 bg-orange-100';
    if (severity >= 4) return 'text-yellow-600 bg-yellow-100';
    return 'text-green-600 bg-green-100';
  };

  // Calculate total pages
  const totalPages = Math.ceil(pagination.totalItems / pagination.itemsPerPage);

  // Handle event detail view
  const handleViewDetails = async (eventId: string) => {
    // If onEventSelect prop is provided, use it instead of modal
    if (onEventSelect) {
      onEventSelect(eventId);
      return;
    }

    try {
      const eventResponse = await api.getEvent(eventId);
      setSelectedEvent(eventResponse);
      setIsModalOpen(true);
    } catch (err) {
      console.error('Failed to fetch event details:', err);
      // Could add error toast here
    }
  };

  // Handle modal close
  const handleCloseModal = () => {
    setIsModalOpen(false);
    setSelectedEvent(null);
  };

  if (loading) {
    return (
      <div className={`bg-white shadow rounded-lg ${className}`}>
        <div className="p-6">
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-4 bg-gray-200 rounded"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`bg-white shadow rounded-lg ${className}`}>
        <div className="p-6">
          <div className="text-center py-8">
            <div className="text-red-500 text-4xl mb-4">⚠️</div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Error Loading Events</h3>
            <p className="text-gray-600 mb-4">{error}</p>
            <button
              onClick={fetchEvents}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white shadow rounded-lg ${className}`}>
      {/* Header with real-time indicator */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <h3 className="text-lg font-medium text-gray-900">
              Security Events ({events.length})
            </h3>
            {newEventIds.size > 0 && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                {newEventIds.size} new
              </span>
            )}
          </div>
          <div className="flex items-center space-x-4">
            {autoRefresh && !realTimeEnabled && (
              <div className="flex items-center text-sm text-blue-600">
                <div className="w-2 h-2 bg-blue-500 rounded-full mr-1 animate-pulse"></div>
                Auto-refresh
              </div>
            )}
            {realTimeEnabled && (
              <div className="flex items-center text-sm">
                {realtimeConnected ? (
                  <div className="flex items-center text-green-600">
                    <div className="w-2 h-2 bg-green-500 rounded-full mr-1 animate-pulse"></div>
                    Live Updates
                  </div>
                ) : (
                  <div className="flex items-center text-red-600">
                    <div className="w-2 h-2 bg-red-500 rounded-full mr-1"></div>
                    Disconnected
                  </div>
                )}
              </div>
            )}
            {showProcessingStatus && processingConnected && (
              <div className="flex items-center text-sm text-purple-600">
                <div className="w-2 h-2 bg-purple-500 rounded-full mr-1 animate-pulse"></div>
                Processing Monitor
              </div>
            )}
            <div className="text-sm text-gray-500">
              Updated: {lastUpdate.toLocaleTimeString()}
            </div>
          </div>
        </div>
      </div>

      {/* Filters Section */}
      <div className="p-6 border-b border-gray-200">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Date Range Filter */}
          <div>
            <label htmlFor="start-date" className="block text-sm font-medium text-gray-700 mb-1">
              Start Date
            </label>
            <input
              id="start-date"
              type="datetime-local"
              value={filters.start_date || ''}
              onChange={(e) => handleFilterChange({ start_date: e.target.value || undefined })}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="end-date" className="block text-sm font-medium text-gray-700 mb-1">
              End Date
            </label>
            <input
              id="end-date"
              type="datetime-local"
              value={filters.end_date || ''}
              onChange={(e) => handleFilterChange({ end_date: e.target.value || undefined })}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
          </div>

          {/* Severity Range Filter */}
          <div>
            <label htmlFor="min-severity" className="block text-sm font-medium text-gray-700 mb-1">
              Min Severity
            </label>
            <select
              id="min-severity"
              value={filters.min_severity || ''}
              onChange={(e) => handleFilterChange({ min_severity: e.target.value ? parseInt(e.target.value) : undefined })}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="">Any</option>
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(num => (
                <option key={num} value={num}>{num}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="max-severity" className="block text-sm font-medium text-gray-700 mb-1">
              Max Severity
            </label>
            <select
              id="max-severity"
              value={filters.max_severity || ''}
              onChange={(e) => handleFilterChange({ max_severity: e.target.value ? parseInt(e.target.value) : undefined })}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="">Any</option>
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(num => (
                <option key={num} value={num}>{num}</option>
              ))}
            </select>
          </div>

          {/* Category Filter */}
          <div>
            <label htmlFor="category" className="block text-sm font-medium text-gray-700 mb-1">
              Category
            </label>
            <select
              id="category"
              value={filters.category || ''}
              onChange={(e) => handleFilterChange({ category: e.target.value || undefined })}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="">All Categories</option>
              {Object.values(EventCategory).map(category => (
                <option key={category} value={category}>
                  {category.charAt(0).toUpperCase() + category.slice(1)}
                </option>
              ))}
            </select>
          </div>

          {/* Source Filter */}
          <div>
            <label htmlFor="source" className="block text-sm font-medium text-gray-700 mb-1">
              Source
            </label>
            <input
              id="source"
              type="text"
              placeholder="Filter by source..."
              value={filters.source || ''}
              onChange={(e) => handleFilterChange({ source: e.target.value || undefined })}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
          </div>

          {/* Clear Filters Button */}
          <div className="flex items-end">
            <button
              onClick={clearFilters}
              className="w-full bg-gray-100 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-200 text-sm"
            >
              Clear Filters
            </button>
          </div>

          {/* Items per page */}
          <div>
            <label htmlFor="items-per-page" className="block text-sm font-medium text-gray-700 mb-1">
              Items per page
            </label>
            <select
              id="items-per-page"
              value={pagination.itemsPerPage}
              onChange={(e) => setPagination(prev => ({ ...prev, itemsPerPage: parseInt(e.target.value), currentPage: 1 }))}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </div>
        </div>
      </div>

      {/* Table Section */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('timestamp')}
              >
                <div className="flex items-center space-x-1">
                  <span>Timestamp</span>
                  {sortConfig.key === 'timestamp' && (
                    <span>{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>
                  )}
                </div>
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('severity_score')}
              >
                <div className="flex items-center space-x-1">
                  <span>Severity</span>
                  {sortConfig.key === 'severity_score' && (
                    <span>{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>
                  )}
                </div>
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('source')}
              >
                <div className="flex items-center space-x-1">
                  <span>Source</span>
                  {sortConfig.key === 'source' && (
                    <span>{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>
                  )}
                </div>
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('category')}
              >
                <div className="flex items-center space-x-1">
                  <span>Category</span>
                  {sortConfig.key === 'category' && (
                    <span>{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>
                  )}
                </div>
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Message
              </th>
              {showProcessingStatus && (
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
              )}
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {paginatedEvents.length === 0 ? (
              <tr>
                <td colSpan={showProcessingStatus ? 7 : 6} className="px-6 py-12 text-center text-gray-500">
                  <div className="text-4xl mb-4">📋</div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No Events Found</h3>
                  <p>No security events match your current filters.</p>
                  {realTimeEnabled && !realtimeConnected && (
                    <p className="mt-2 text-sm text-red-600">
                      Real-time connection unavailable. Some events may not be visible.
                    </p>
                  )}
                </td>
              </tr>
            ) : (
              paginatedEvents.map((eventResponse) => {
                const isNew = newEventIds.has(eventResponse.event.id);
                const isProcessing = processingEvents.has(eventResponse.event.id);
                
                return (
                  <tr 
                    key={eventResponse.event.id} 
                    className={`hover:bg-gray-50 transition-colors duration-200 ${
                      selectedEventId === eventResponse.event.id ? 'bg-blue-50 border-l-4 border-blue-500' : 
                      isNew ? 'bg-green-50 border-l-4 border-green-500' : ''
                    }`}
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <div className="flex items-center space-x-2">
                        <span>{formatTimestamp(eventResponse.event.timestamp)}</span>
                        {isNew && (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            NEW
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getSeverityColor(eventResponse.analysis.severity_score)}`}>
                        {eventResponse.analysis.severity_score}/10
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {eventResponse.event.source}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                        {eventResponse.event.category}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">
                      {eventResponse.event.message}
                    </td>
                    {showProcessingStatus && (
                      <td className="px-6 py-4 whitespace-nowrap">
                        {isProcessing ? (
                          <div className="flex items-center text-xs text-purple-600">
                            <div className="w-2 h-2 bg-purple-500 rounded-full mr-1 animate-pulse"></div>
                            Processing
                          </div>
                        ) : (
                          <span className="inline-flex items-center px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded-full">
                            Complete
                          </span>
                        )}
                      </td>
                    )}
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <button
                        onClick={() => handleViewDetails(eventResponse.event.id)}
                        className="text-blue-600 hover:text-blue-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded"
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Section */}
      {totalPages > 1 && (
        <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
          <div className="text-sm text-gray-700">
            Showing {((pagination.currentPage - 1) * pagination.itemsPerPage) + 1} to{' '}
            {Math.min(pagination.currentPage * pagination.itemsPerPage, pagination.totalItems)} of{' '}
            {pagination.totalItems} results
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handlePageChange(pagination.currentPage - 1)}
              disabled={pagination.currentPage === 1}
              className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Previous
            </button>
            
            {/* Page numbers */}
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let pageNum: number;
              if (totalPages <= 5) {
                pageNum = i + 1;
              } else if (pagination.currentPage <= 3) {
                pageNum = i + 1;
              } else if (pagination.currentPage >= totalPages - 2) {
                pageNum = totalPages - 4 + i;
              } else {
                pageNum = pagination.currentPage - 2 + i;
              }
              
              return (
                <button
                  key={pageNum}
                  onClick={() => handlePageChange(pageNum)}
                  className={`px-3 py-1 border rounded text-sm ${
                    pagination.currentPage === pageNum
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {pageNum}
                </button>
              );
            })}
            
            <button
              onClick={() => handlePageChange(pagination.currentPage + 1)}
              disabled={pagination.currentPage === totalPages}
              className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Event Detail Modal */}
      <EventDetail
        event={selectedEvent}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
      />
    </div>
  );
};

export default EventTable;