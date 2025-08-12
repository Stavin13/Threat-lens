import React from 'react';

const Reports: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="border-b border-gray-200 pb-4">
        <h1 className="text-2xl font-bold text-gray-900">Security Reports</h1>
        <p className="text-gray-600 mt-1">
          Generate and download daily security reports
        </p>
      </div>

      <div className="bg-white shadow rounded-lg p-6">
        <div className="text-center py-12 text-gray-500">
          <div className="text-6xl mb-4">📄</div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Report Generation Interface
          </h3>
          <p>
            Report generation and download functionality will be available
            once the backend report endpoints are fully integrated.
          </p>
        </div>
      </div>
    </div>
  );
};

export default Reports;