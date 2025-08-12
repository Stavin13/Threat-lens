import React from 'react';

const IngestLogs: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="border-b border-gray-200 pb-4">
        <h1 className="text-2xl font-bold text-gray-900">Log Ingestion</h1>
        <p className="text-gray-600 mt-1">
          Upload log files or paste log content for analysis
        </p>
      </div>

      <div className="bg-white shadow rounded-lg p-6">
        <div className="text-center py-12 text-gray-500">
          <div className="text-6xl mb-4">📥</div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Log Ingestion Interface
          </h3>
          <p>
            File upload and text input functionality will be implemented
            as part of the complete dashboard features.
          </p>
        </div>
      </div>
    </div>
  );
};

export default IngestLogs;