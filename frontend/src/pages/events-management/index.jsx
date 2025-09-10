import React, { useState, useEffect } from 'react';
import NavigationHeader from '../../components/ui/NavigationHeader';
import EventsFilterToolbar from './components/EventsFilterToolbar';
import EventsDataTable from './components/EventsDataTable';
import EventDetailModal from './components/EventDetailModal';
import EventsPagination from './components/EventsPagination';
import BulkActionsBar from './components/BulkActionsBar';
import { apiService } from '../../services/api';

const EventsManagement = () => {
  const [events, setEvents] = useState([]);
  const [filteredEvents, setFilteredEvents] = useState([]);
  const [selectedEvents, setSelectedEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(25);
  const [sortConfig, setSortConfig] = useState({ column: 'timestamp', direction: 'desc' });
  const [filters, setFilters] = useState({
    category: 'all',
    severityRange: { min: 1, max: 10 },
    dateRange: { start: '', end: '' },
    searchQuery: ''
  });

  // Load events from API

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await apiService.getEvents({ per_page: 100, sort_by: 'timestamp', sort_order: 'desc' });
        const apiEvents = (res?.events || []).map(e => ({
          id: e.id,
          timestamp: e.timestamp,
          source: e.source,
          category: e.category,
          severity: e?.ai_analysis?.severity_score ?? 0,
          message: e.message,
          details: {},
          aiAnalysis: e?.ai_analysis ? {
            explanation: e.ai_analysis.explanation,
            recommendations: e.ai_analysis.recommendations
          } : undefined
        }));
        setEvents(apiEvents);
        setFilteredEvents(apiEvents);
      } catch (e) {
        setEvents([]);
        setFilteredEvents([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // Apply filters
  useEffect(() => {
    let filtered = [...events];

    // Category filter
    if (filters?.category !== 'all') {
      filtered = filtered?.filter(event => event?.category === filters?.category);
    }

    // Severity range filter
    filtered = filtered?.filter(event => 
      event?.severity >= filters?.severityRange?.min && 
      event?.severity <= filters?.severityRange?.max
    );

    // Date range filter
    if (filters?.dateRange?.start) {
      const startDate = new Date(filters.dateRange.start);
      filtered = filtered?.filter(event => new Date(event.timestamp) >= startDate);
    }
    if (filters?.dateRange?.end) {
      const endDate = new Date(filters.dateRange.end);
      endDate?.setHours(23, 59, 59, 999);
      filtered = filtered?.filter(event => new Date(event.timestamp) <= endDate);
    }

    // Search query filter
    if (filters?.searchQuery) {
      const query = filters?.searchQuery?.toLowerCase();
      filtered = filtered?.filter(event =>
        event?.message?.toLowerCase()?.includes(query) ||
        event?.source?.toLowerCase()?.includes(query) ||
        event?.category?.toLowerCase()?.includes(query)
      );
    }

    // Apply sorting
    filtered?.sort((a, b) => {
      let aValue = a?.[sortConfig?.column];
      let bValue = b?.[sortConfig?.column];

      if (sortConfig?.column === 'timestamp') {
        aValue = new Date(aValue);
        bValue = new Date(bValue);
      }

      if (aValue < bValue) {
        return sortConfig?.direction === 'asc' ? -1 : 1;
      }
      if (aValue > bValue) {
        return sortConfig?.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });

    setFilteredEvents(filtered);
    setCurrentPage(1);
  }, [events, filters, sortConfig]);

  // Get paginated events
  const getPaginatedEvents = () => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return filteredEvents?.slice(startIndex, endIndex);
  };

  const totalPages = Math.ceil(filteredEvents?.length / itemsPerPage);

  const handleEventClick = (event) => {
    setSelectedEvent(event);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setSelectedEvent(null);
  };

  const handleFiltersChange = (newFilters) => {
    setFilters(newFilters);
  };

  const handleSort = (newSortConfig) => {
    setSortConfig(newSortConfig);
  };

  const handlePageChange = (page) => {
    setCurrentPage(page);
  };

  const handleItemsPerPageChange = (newItemsPerPage) => {
    setItemsPerPage(newItemsPerPage);
    setCurrentPage(1);
  };

  const handleEventSelect = (eventIds) => {
    setSelectedEvents(eventIds);
  };

  const handleRefresh = async () => {
    setLoading(true);
    try {
      const res = await apiService.getEvents({ per_page: 100, sort_by: 'timestamp', sort_order: 'desc' });
      const apiEvents = (res?.events || []).map(e => ({
        id: e.id,
        timestamp: e.timestamp,
        source: e.source,
        category: e.category,
        severity: e?.ai_analysis?.severity_score ?? 0,
        message: e.message
      }));
      setEvents(apiEvents);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    const dataStr = JSON.stringify(filteredEvents, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    const exportFileDefaultName = `security-events-${new Date()?.toISOString()?.split('T')?.[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement?.setAttribute('href', dataUri);
    linkElement?.setAttribute('download', exportFileDefaultName);
    linkElement?.click();
  };

  const handleBulkExport = () => {
    const selectedEventsData = events?.filter(event => selectedEvents?.includes(event?.id));
    const dataStr = JSON.stringify(selectedEventsData, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    const exportFileDefaultName = `selected-events-${new Date()?.toISOString()?.split('T')?.[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement?.setAttribute('href', dataUri);
    linkElement?.setAttribute('download', exportFileDefaultName);
    linkElement?.click();
  };

  const handleBulkMarkReviewed = () => {
    console.log('Marking events as reviewed:', selectedEvents);
    setSelectedEvents([]);
  };

  const handleBulkDelete = () => {
    if (window.confirm(`Are you sure you want to delete ${selectedEvents?.length} selected events?`)) {
      const updatedEvents = events?.filter(event => !selectedEvents?.includes(event?.id));
      setEvents(updatedEvents);
      setSelectedEvents([]);
    }
  };

  const handleClearSelection = () => {
    setSelectedEvents([]);
  };

  return (
    <div className="min-h-screen bg-background">
      <NavigationHeader />
      <main className="pt-16">
        <div className="max-w-7xl mx-auto p-6 space-y-6">
          {/* Filter Toolbar */}
          <EventsFilterToolbar
            filters={filters}
            onFiltersChange={handleFiltersChange}
            totalResults={filteredEvents?.length}
            onExport={handleExport}
            onRefresh={handleRefresh}
          />

          {/* Bulk Actions Bar */}
          <BulkActionsBar
            selectedCount={selectedEvents?.length}
            onClearSelection={handleClearSelection}
            onBulkExport={handleBulkExport}
            onBulkMarkReviewed={handleBulkMarkReviewed}
            onBulkDelete={handleBulkDelete}
          />

          {/* Events Data Table */}
          <EventsDataTable
            events={getPaginatedEvents()}
            selectedEvents={selectedEvents}
            onEventSelect={handleEventSelect}
            onEventClick={handleEventClick}
            sortConfig={sortConfig}
            onSort={handleSort}
            loading={loading}
          />

          {/* Pagination */}
          <EventsPagination
            currentPage={currentPage}
            totalPages={totalPages}
            totalItems={filteredEvents?.length}
            itemsPerPage={itemsPerPage}
            onPageChange={handlePageChange}
            onItemsPerPageChange={handleItemsPerPageChange}
          />
        </div>
      </main>
      {/* Event Detail Modal */}
      <EventDetailModal
        event={selectedEvent}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
      />
    </div>
  );
};

export default EventsManagement;