import React from 'react';
import Icon from '../../../components/AppIcon';
import Button from '../../../components/ui/Button';

const BulkActionsBar = ({ 
  selectedCount = 0, 
  onClearSelection, 
  onBulkExport, 
  onBulkMarkReviewed,
  onBulkDelete 
}) => {
  if (selectedCount === 0) {
    return null;
  }

  return (
    <div className="bg-primary/10 border border-primary/20 rounded-lg p-4 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-3 sm:space-y-0">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <Icon name="CheckSquare" size={20} className="text-primary" />
            <span className="font-medium text-foreground">
              {selectedCount} event{selectedCount !== 1 ? 's' : ''} selected
            </span>
          </div>
          
          <Button
            variant="ghost"
            size="sm"
            iconName="X"
            onClick={onClearSelection}
            className="text-muted-foreground hover:text-foreground"
          >
            Clear
          </Button>
        </div>

        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            iconName="Download"
            iconPosition="left"
            onClick={onBulkExport}
          >
            Export Selected
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            iconName="Eye"
            iconPosition="left"
            onClick={onBulkMarkReviewed}
          >
            Mark Reviewed
          </Button>
          
          <Button
            variant="destructive"
            size="sm"
            iconName="Trash2"
            iconPosition="left"
            onClick={onBulkDelete}
          >
            Delete Selected
          </Button>
        </div>
      </div>
    </div>
  );
};

export default BulkActionsBar;