import React, { useState, useEffect } from 'react';
import { LogSourceConfig, MonitoringConfig } from '../types';
import { api } from '../services/api';
import LogSourceManager from './LogSourceManager';
import NotificationManager from './NotificationManager';
import SystemMonitoring from './SystemMonitoring';

interface ConfigurationProps {}

const Configuration: React.FC<ConfigurationProps> = () => {
  const [activeTab, setActiveTab] = useState<'sources' | 'notifications' | 'monitoring'>('sources');
  const [config, setConfig] = useState<MonitoringConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadConfiguration();
  }, []);

  const loadConfiguration = async () => {
    try {
      setLoading(true);
      setError(null);
      const configData = await api.getMonitoringConfig();
      setConfig(configData);
    } catch (err: any) {
      console.error('Failed to load configuration:', err);
      setError(err.message || 'Failed to load configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleConfigUpdate = () => {
    // Reload configuration after updates
    loadConfiguration();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-gray-600">Loading configuration...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <span className="text-red-400">⚠️</span>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">Configuration Error</h3>
            <div className="mt-2 text-sm text-red-700">
              <p>{error}</p>
            </div>
            <div className="mt-4">
              <button
                onClick={loadConfiguration}
                className="bg-red-100 hover:bg-red-200 text-red-800 px-3 py-1 rounded text-sm"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'sources', name: 'Log Sources', icon: '📁' },
    { id: 'notifications', name: 'Notifications', icon: '🔔' },
    { id: 'monitoring', name: 'System Monitoring', icon: '📊' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h1 className="text-2xl font-bold text-gray-900">Configuration Management</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage real-time log monitoring configuration, notification rules, and system settings.
          </p>
        </div>
      </div>

      {/* Configuration Status */}
      {config && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium text-gray-900">System Status</h3>
                <p className="text-sm text-gray-500">Real-time monitoring configuration</p>
              </div>
              <div className="flex items-center space-x-4">
                <div className="flex items-center">
                  <div className={`w-3 h-3 rounded-full mr-2 ${config.enabled ? 'bg-green-400' : 'bg-red-400'}`}></div>
                  <span className="text-sm font-medium">
                    {config.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
                <div className="text-sm text-gray-500">
                  {config.log_sources.length} sources configured
                </div>
                <div className="text-sm text-gray-500">
                  {config.notification_rules.length} notification rules
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="bg-white shadow rounded-lg">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8 px-6">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span className="mr-2">{tab.icon}</span>
                {tab.name}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === 'sources' && config && (
            <LogSourceManager 
              config={config} 
              onUpdate={handleConfigUpdate}
            />
          )}
          {activeTab === 'notifications' && config && (
            <NotificationManager 
              config={config} 
              onUpdate={handleConfigUpdate}
            />
          )}
          {activeTab === 'monitoring' && config && (
            <SystemMonitoring 
              config={config} 
              onUpdate={handleConfigUpdate}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default Configuration;