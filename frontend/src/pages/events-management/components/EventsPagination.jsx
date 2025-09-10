import React from 'react';

import Button from '../../../components/ui/Button';
import Select from '../../../components/ui/Select';

const EventsPagination = ({ 
  currentPage = 1, 
  totalPages = 1, 
  totalItems = 0, 
  itemsPerPage = 25, 
  onPageChange, 
  onItemsPerPageChange 
}) => {
  const perPageOptions = [
    { value: '10', label: '10 per page' },
    { value: '25', label: '25 per page' },
    { value: '50', label: '50 per page' },
    { value: '100', label: '100 per page' }
  ];

  const getVisiblePages = () => {
    const delta = 2;
    const range = [];
    const rangeWithDots = [];

    for (let i = Math.max(2, currentPage - delta); 
         i <= Math.min(totalPages - 1, currentPage + delta); 
         i++) {
      range?.push(i);
    }

    if (currentPage - delta > 2) {
      rangeWithDots?.push(1, '...');
    } else {
      rangeWithDots?.push(1);
    }

    rangeWithDots?.push(...range);

    if (currentPage + delta < totalPages - 1) {
      rangeWithDots?.push('...', totalPages);
    } else if (totalPages > 1) {
      rangeWithDots?.push(totalPages);
    }

    return rangeWithDots;
  };

  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalItems);

  if (totalItems === 0) {
    return null;
  }

  return (
    <div className="bg-card border border-border rounded-lg shadow-elevation-1 p-4">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
        {/* Results Info */}
        <div className="flex items-center space-x-4">
          <div className="text-sm text-muted-foreground">
            Showing {startItem?.toLocaleString()} to {endItem?.toLocaleString()} of {totalItems?.toLocaleString()} events
          </div>
          
          <div className="hidden sm:block">
            <Select
              options={perPageOptions}
              value={itemsPerPage?.toString()}
              onChange={(value) => onItemsPerPageChange(parseInt(value))}
              className="w-32"
            />
          </div>
        </div>

        {/* Pagination Controls */}
        <div className="flex items-center justify-center lg:justify-end space-x-2">
          {/* Previous Button */}
          <Button
            variant="outline"
            size="sm"
            iconName="ChevronLeft"
            disabled={currentPage === 1}
            onClick={() => onPageChange(currentPage - 1)}
            className="min-w-touch"
          >
            <span className="hidden sm:inline">Previous</span>
          </Button>

          {/* Page Numbers */}
          <div className="hidden md:flex items-center space-x-1">
            {getVisiblePages()?.map((page, index) => (
              <React.Fragment key={index}>
                {page === '...' ? (
                  <span className="px-3 py-2 text-sm text-muted-foreground">...</span>
                ) : (
                  <Button
                    variant={currentPage === page ? "default" : "ghost"}
                    size="sm"
                    onClick={() => onPageChange(page)}
                    className="min-w-[40px] min-h-touch"
                  >
                    {page}
                  </Button>
                )}
              </React.Fragment>
            ))}
          </div>

          {/* Mobile Page Info */}
          <div className="md:hidden flex items-center space-x-2 px-3 py-2 bg-muted rounded-md">
            <span className="text-sm font-medium text-foreground">
              {currentPage} of {totalPages}
            </span>
          </div>

          {/* Next Button */}
          <Button
            variant="outline"
            size="sm"
            iconName="ChevronRight"
            disabled={currentPage === totalPages}
            onClick={() => onPageChange(currentPage + 1)}
            className="min-w-touch"
          >
            <span className="hidden sm:inline">Next</span>
          </Button>
        </div>
      </div>
      {/* Mobile Items Per Page */}
      <div className="sm:hidden mt-4 pt-4 border-t border-border">
        <Select
          label="Items per page"
          options={perPageOptions}
          value={itemsPerPage?.toString()}
          onChange={(value) => onItemsPerPageChange(parseInt(value))}
        />
      </div>
    </div>
  );
};

export default EventsPagination;