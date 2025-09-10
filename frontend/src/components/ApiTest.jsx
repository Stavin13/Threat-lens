import React, { useState } from 'react';
import { apiService } from '../services/api';
import Button from './ui/Button';

const ApiTest = () => {
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState({});

  const testEndpoint = async (name, apiCall) => {
    setLoading(prev => ({ ...prev, [name]: true }));
    try {
      const result = await apiCall();
      setResults(prev => ({ ...prev, [name]: { success: true, data: result } }));
    } catch (error) {
      setResults(prev => ({ ...prev, [name]: { success: false, error: error.message } }));
    } finally {
      setLoading(prev => ({ ...prev, [name]: false }));
    }
  };

  const tests = [
    { name: 'Health Check', call: () => apiService.getHealthSimple() },
    { name: 'Stats', call: () => apiService.getStats() },
    { name: 'Events', call: () => apiService.getEvents({ per_page: 5 }) },
    { name: 'Realtime Status', call: () => apiService.getRealtimeStatus() },
    { name: 'Reports', call: () => apiService.getReports() },
  ];

  return (
    <div className="p-6 bg-white rounded-lg shadow">
      <h2 className="text-xl font-bold mb-4">API Connection Test</h2>
      
      <div className="space-y-4">
        {tests.map(test => (
          <div key={test.name} className="flex items-center justify-between p-3 border rounded">
            <span className="font-medium">{test.name}</span>
            <div className="flex items-center space-x-2">
              <Button
                size="sm"
                onClick={() => testEndpoint(test.name, test.call)}
                loading={loading[test.name]}
              >
                Test
              </Button>
              {results[test.name] && (
                <span className={`text-sm ${results[test.name].success ? 'text-green-600' : 'text-red-600'}`}>
                  {results[test.name].success ? '✓ Success' : '✗ Failed'}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {Object.keys(results).length > 0 && (
        <div className="mt-6">
          <h3 className="font-bold mb-2">Results:</h3>
          <pre className="bg-gray-100 p-3 rounded text-sm overflow-auto max-h-96">
            {JSON.stringify(results, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};

export default ApiTest;