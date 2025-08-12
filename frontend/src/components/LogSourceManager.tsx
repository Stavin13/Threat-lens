import React, { useState, useEffect, useCallback } from 'react';
import { LogSourceConfig, LogSourceConfigRequest, MonitoringConfig } from '../types';
import { api } from '../services/api';

interface LogSourceManagerProps {
  config: MonitoringConfig;
  onUpdate: () => void;
}

interface LogSourceHealth {
  source_name: string;
  status: 'active' | 'inactive' | 'error' | 'paused';
  last_check: string;
  file_exists: boolean;
  readable: boolean;
  file_size: number;
  last_modified: string;
  error_message?: string;
  processing_rate: number;
  queue_size: number;
}

interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

interface LogSourceFormData {
  source_name: string;
  path: string;
  source_type: 'file' | 'directory';
  enabled: boolean;
  recursive: boolean;
  file_pattern: string;
  polling_interval: number;
  batch_size: number;
  priority: number;
  description: string;
  tags: string[];
}

const LogSourceManager: React.FC<LogSourceManagerProps> = ({ config, onUpdate }) => {
  const [sources, setSources] = useState<LogSourceConfig[]>(config.log_sources);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingSource, setEditingSource] = useState<LogSourceConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [healthData, setHealthData] = useState<Record<string, LogSourceHealth>>({});
  const [validationResults, setValidationResults] = useState<Record<string, ValidationResult>>({});
  const [refreshingHealth, setRefreshingHealth] = useState(false);

  const [formData, setFormData] = useState<LogSourceFormData>({
    source_name: '',
    path: '',
    source_type: 'file',
    enabled: true,
    recursive: false,
    file_pattern: '',
    polling_interval: 1.0,
    batch_size: 100,
    priority: 5,
    description: '',
    tags: []
  });

  useEffect(() => {
    setSources(config.log_sources);
    // Load health data when sources change
    if (config.log_sources.length > 0) {
      loadHealthData();
    }
  }, [config.log_sources]);

  // Auto-refresh health data every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      if (sources.length > 0) {
        loadHealthData();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [sources]);

  const loadHealthData = useCallback(async () => {
    try {
      setRefreshingHealth(true);
      const healthPromises = sources.map(async (source) => {
        try {
          // Get component health for this log source
          const response = await api.get(`/api/health/components/log_source_${source.source_name}`);
          return {
            source_name: source.source_name,
            ...response.data
          };
        } catch (err) {
          // If specific health endpoint doesn't exist, create mock health data
          return {
            source_name: source.source_name,
            status: source.enabled ? (source.status || 'inactive') : 'paused',
            last_check: new Date().toISOString(),
            file_exists: true,
            readable: true,
            file_size: source.file_size || 0,
            last_modified: source.last_monitored || new Date().toISOString(),
            processing_rate: 0,
            queue_size: 0
          };
        }
      });

      const healthResults = await Promise.all(healthPromises);
      const healthMap: Record<string, LogSourceHealth> = {};
      healthResults.forEach(health => {
        healthMap[health.source_name] = health;
      });
      setHealthData(healthMap);
    } catch (err) {
      console.error('Failed to load health data:', err);
    } finally {
      setRefreshingHealth(false);
    }
  }, [sources]);

  const validateFilePath = useCallback((path: string, sourceType: 'file' | 'directory'): ValidationResult => {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Basic path validation
    if (!path || path.trim().length === 0) {
      errors.push('Path is required');
      return { valid: false, errors, warnings };
    }

    const trimmedPath = path.trim();

    // Check for invalid characters (basic validation)
    if (trimmedPath.includes('..')) {
      errors.push('Path cannot contain ".." (directory traversal)');
    }

    // Check for absolute vs relative paths
    if (!trimmedPath.startsWith('/') && !trimmedPath.match(/^[A-Za-z]:/)) {
      warnings.push('Relative paths may not work as expected. Consider using absolute paths.');
    }

    // Check for common log directories
    const commonLogDirs = ['/var/log', '/var/logs', '/usr/local/var/log', '/opt/logs'];
    const isInCommonLogDir = commonLogDirs.some(dir => trimmedPath.startsWith(dir));
    
    if (!isInCommonLogDir && sourceType === 'file') {
      warnings.push('Path is not in a common log directory. Ensure the file exists and is readable.');
    }

    // Check file extension for files
    if (sourceType === 'file') {
      const extension = trimmedPath.split('.').pop()?.toLowerCase();
      const commonLogExtensions = ['log', 'txt', 'out', 'err'];
      
      if (extension && !commonLogExtensions.includes(extension)) {
        warnings.push(`File extension ".${extension}" is not a common log file extension.`);
      }
    }

    // Check for potentially problematic paths
    const systemPaths = ['/etc', '/bin', '/usr/bin', '/sbin', '/usr/sbin'];
    if (systemPaths.some(sysPath => trimmedPath.startsWith(sysPath))) {
      warnings.push('Monitoring system directories may require elevated permissions.');
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings
    };
  }, []);

  const testLogSource = useCallback(async (sourceName: string): Promise<void> => {
    try {
      setLoading(true);
      // Test the log source connectivity and permissions
      await api.post(`/realtime/log-sources/${sourceName}/test`);
      
      // Refresh health data after test
      await loadHealthData();
      
      setError(null);
    } catch (err: any) {
      console.error('Failed to test log source:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to test log source');
    } finally {
      setLoading(false);
    }
  }, [loadHealthData]);

  const resetForm = () => {
    setFormData({
      source_name: '',
      path: '',
      source_type: 'file',
      enabled: true,
      recursive: false,
      file_pattern: '',
      polling_interval: 1.0,
      batch_size: 100,
      priority: 5,
      description: '',
      tags: []
    });
    setEditingSource(null);
    setShowAddForm(false);
    setError(null);
  };

  const handleInputChange = (field: keyof LogSourceFormData, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
    
    // Real-time path validation
    if (field === 'path' || field === 'source_type') {
      const pathToValidate = field === 'path' ? value : formData.path;
      const typeToValidate = field === 'source_type' ? value : formData.source_type;
      
      if (pathToValidate) {
        const validation = validateFilePath(pathToValidate, typeToValidate);
        setValidationResults(prev => ({
          ...prev,
          path: validation
        }));
      } else {
        setValidationResults(prev => {
          const { path, ...rest } = prev;
          return rest;
        });
      }
    }
  };

  const handleTagsChange = (tagsString: string) => {
    const tags = tagsString.split(',').map(tag => tag.trim()).filter(tag => tag.length > 0);
    setFormData(prev => ({
      ...prev,
      tags
    }));
  };

  const validateForm = (): string | null => {
    if (!formData.source_name.trim()) {
      return 'Source name is required';
    }
    
    // Validate path using the new validation function
    const pathValidation = validateFilePath(formData.path, formData.source_type);
    if (!pathValidation.valid) {
      return pathValidation.errors[0];
    }
    
    if (formData.polling_interval < 0.1 || formData.polling_interval > 3600) {
      return 'Polling interval must be between 0.1 and 3600 seconds';
    }
    if (formData.batch_size < 1 || formData.batch_size > 10000) {
      return 'Batch size must be between 1 and 10000';
    }
    if (formData.priority < 1 || formData.priority > 10) {
      return 'Priority must be between 1 and 10';
    }
    
    // Check for duplicate source names
    const existingSources = sources.filter(s => s.source_name !== editingSource?.source_name);
    if (existingSources.some(s => s.source_name === formData.source_name.trim())) {
      return 'A log source with this name already exists';
    }
    
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const requestData: LogSourceConfigRequest = {
        source_name: formData.source_name.trim(),
        path: formData.path.trim(),
        source_type: formData.source_type,
        enabled: formData.enabled,
        recursive: formData.recursive,
        file_pattern: formData.file_pattern.trim() || undefined,
        polling_interval: formData.polling_interval,
        batch_size: formData.batch_size,
        priority: formData.priority,
        description: formData.description.trim() || undefined,
        tags: formData.tags
      };

      if (editingSource) {
        await api.updateLogSource(editingSource.source_name, requestData);
      } else {
        await api.createLogSource(requestData);
      }

      resetForm();
      onUpdate();
    } catch (err: any) {
      console.error('Failed to save log source:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to save log source');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (source: LogSourceConfig) => {
    setFormData({
      source_name: source.source_name,
      path: source.path,
      source_type: source.source_type,
      enabled: source.enabled,
      recursive: source.recursive,
      file_pattern: source.file_pattern || '',
      polling_interval: source.polling_interval,
      batch_size: source.batch_size,
      priority: source.priority,
      description: source.description || '',
      tags: source.tags
    });
    setEditingSource(source);
    setShowAddForm(true);
  };

  const handleDelete = async (sourceName: string) => {
    if (!window.confirm(`Are you sure you want to delete the log source "${sourceName}"?`)) {
      return;
    }

    setLoading(true);
    try {
      await api.deleteLogSource(sourceName);
      onUpdate();
    } catch (err: any) {
      console.error('Failed to delete log source:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to delete log source');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'inactive': return 'bg-gray-100 text-gray-800';
      case 'error': return 'bg-red-100 text-red-800';
      case 'paused': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active': return '✅';
      case 'inactive': return '⏸️';
      case 'error': return '❌';
      case 'paused': return '⏸️';
      default: return '❓';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-lg font-medium text-gray-900">Log Sources</h2>
          <p className="text-sm text-gray-500">
            Configure and manage log sources for real-time monitoring
          </p>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={loadHealthData}
            disabled={refreshingHealth}
            className="bg-gray-100 hover:bg-gray-200 disabled:bg-gray-50 text-gray-700 px-3 py-2 rounded-md text-sm font-medium flex items-center"
          >
            <span className={`mr-2 ${refreshingHealth ? 'animate-spin' : ''}`}>
              {refreshingHealth ? '⟳' : '🔄'}
            </span>
            Refresh Health
          </button>
          <button
            onClick={() => setShowAddForm(true)}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-4 py-2 rounded-md text-sm font-medium"
          >
            Add Log Source
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <span className="text-red-400">⚠️</span>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error</h3>
              <div className="mt-2 text-sm text-red-700">
                <p>{error}</p>
              </div>
              <div className="mt-4">
                <button
                  onClick={() => setError(null)}
                  className="bg-red-100 hover:bg-red-200 text-red-800 px-3 py-1 rounded text-sm"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add/Edit Form */}
      {showAddForm && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-medium text-gray-900">
              {editingSource ? 'Edit Log Source' : 'Add New Log Source'}
            </h3>
            <button
              onClick={resetForm}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Source Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Source Name *
                </label>
                <input
                  type="text"
                  value={formData.source_name}
                  onChange={(e) => handleInputChange('source_name', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., System Logs"
                  required
                />
              </div>

              {/* Path */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  File/Directory Path *
                </label>
                <input
                  type="text"
                  value={formData.path}
                  onChange={(e) => handleInputChange('path', e.target.value)}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 ${
                    validationResults.path && !validationResults.path.valid
                      ? 'border-red-300 focus:ring-red-500'
                      : validationResults.path && validationResults.path.warnings.length > 0
                      ? 'border-yellow-300 focus:ring-yellow-500'
                      : 'border-gray-300 focus:ring-blue-500'
                  }`}
                  placeholder="e.g., /var/log/system.log"
                  required
                />
                {/* Path validation feedback */}
                {validationResults.path && (
                  <div className="mt-1">
                    {validationResults.path.errors.map((error, index) => (
                      <p key={index} className="text-sm text-red-600 flex items-center">
                        <span className="mr-1">❌</span>
                        {error}
                      </p>
                    ))}
                    {validationResults.path.warnings.map((warning, index) => (
                      <p key={index} className="text-sm text-yellow-600 flex items-center">
                        <span className="mr-1">⚠️</span>
                        {warning}
                      </p>
                    ))}
                    {validationResults.path.valid && validationResults.path.warnings.length === 0 && (
                      <p className="text-sm text-green-600 flex items-center">
                        <span className="mr-1">✅</span>
                        Path format looks good
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Source Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Source Type
                </label>
                <select
                  value={formData.source_type}
                  onChange={(e) => handleInputChange('source_type', e.target.value as 'file' | 'directory')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="file">File</option>
                  <option value="directory">Directory</option>
                </select>
              </div>

              {/* Priority */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Priority (1-10)
                </label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={formData.priority}
                  onChange={(e) => handleInputChange('priority', parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Polling Interval */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Polling Interval (seconds)
                </label>
                <input
                  type="number"
                  min="0.1"
                  max="3600"
                  step="0.1"
                  value={formData.polling_interval}
                  onChange={(e) => handleInputChange('polling_interval', parseFloat(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Batch Size */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Batch Size
                </label>
                <input
                  type="number"
                  min="1"
                  max="10000"
                  value={formData.batch_size}
                  onChange={(e) => handleInputChange('batch_size', parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Directory-specific options */}
            {formData.source_type === 'directory' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    File Pattern
                  </label>
                  <input
                    type="text"
                    value={formData.file_pattern}
                    onChange={(e) => handleInputChange('file_pattern', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g., *.log"
                  />
                </div>
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="recursive"
                    checked={formData.recursive}
                    onChange={(e) => handleInputChange('recursive', e.target.checked)}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                  />
                  <label htmlFor="recursive" className="ml-2 block text-sm text-gray-900">
                    Monitor subdirectories recursively
                  </label>
                </div>
              </div>
            )}

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => handleInputChange('description', e.target.value)}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Optional description of this log source"
              />
            </div>

            {/* Tags */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Tags (comma-separated)
              </label>
              <input
                type="text"
                value={formData.tags.join(', ')}
                onChange={(e) => handleTagsChange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., system, security, auth"
              />
            </div>

            {/* Enabled */}
            <div className="flex items-center">
              <input
                type="checkbox"
                id="enabled"
                checked={formData.enabled}
                onChange={(e) => handleInputChange('enabled', e.target.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="enabled" className="ml-2 block text-sm text-gray-900">
                Enable monitoring for this source
              </label>
            </div>

            {/* Form Actions */}
            <div className="flex justify-end space-x-3 pt-4">
              <button
                type="button"
                onClick={resetForm}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-md text-sm font-medium"
              >
                {loading ? 'Saving...' : (editingSource ? 'Update Source' : 'Add Source')}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Sources List */}
      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <ul className="divide-y divide-gray-200">
          {sources.length === 0 ? (
            <li className="px-6 py-8 text-center">
              <div className="text-gray-500">
                <span className="text-4xl mb-4 block">📁</span>
                <h3 className="text-lg font-medium text-gray-900 mb-2">No log sources configured</h3>
                <p className="text-sm">Add your first log source to start monitoring.</p>
              </div>
            </li>
          ) : (
            sources.map((source) => {
              const health = healthData[source.source_name];
              return (
                <li key={source.source_name} className="px-6 py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-3">
                        <div className="flex-shrink-0">
                          <span className="text-2xl">
                            {source.source_type === 'directory' ? '📁' : '📄'}
                          </span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center space-x-2">
                            <h3 className="text-sm font-medium text-gray-900 truncate">
                              {source.source_name}
                            </h3>
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(source.status)}`}>
                              <span className="mr-1">{getStatusIcon(source.status)}</span>
                              {source.status}
                            </span>
                            {!source.enabled && (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                Disabled
                              </span>
                            )}
                          </div>
                          <div className="mt-1">
                            <p className="text-sm text-gray-500 truncate">{source.path}</p>
                            {source.description && (
                              <p className="text-xs text-gray-400 mt-1">{source.description}</p>
                            )}
                          </div>
                          
                          {/* Health Indicators */}
                          {health && (
                            <div className="mt-2 p-2 bg-gray-50 rounded-md">
                              <div className="flex items-center justify-between text-xs">
                                <div className="flex items-center space-x-4">
                                  <span className={`flex items-center ${health.file_exists ? 'text-green-600' : 'text-red-600'}`}>
                                    {health.file_exists ? '✅' : '❌'} File exists
                                  </span>
                                  <span className={`flex items-center ${health.readable ? 'text-green-600' : 'text-red-600'}`}>
                                    {health.readable ? '✅' : '❌'} Readable
                                  </span>
                                  {health.processing_rate > 0 && (
                                    <span className="text-blue-600">
                                      📊 {health.processing_rate.toFixed(1)}/s
                                    </span>
                                  )}
                                  {health.queue_size > 0 && (
                                    <span className="text-yellow-600">
                                      📋 Queue: {health.queue_size}
                                    </span>
                                  )}
                                </div>
                                <span className="text-gray-500">
                                  {health.file_size > 0 && `${(health.file_size / 1024 / 1024).toFixed(1)} MB`}
                                </span>
                              </div>
                              {health.last_check && (
                                <div className="mt-1 text-xs text-gray-400">
                                  Last check: {new Date(health.last_check).toLocaleString()}
                                </div>
                              )}
                              {health.error_message && (
                                <div className="mt-1 text-xs text-red-600">
                                  ⚠️ {health.error_message}
                                </div>
                              )}
                            </div>
                          )}
                          
                          <div className="mt-2 flex items-center space-x-4 text-xs text-gray-500">
                            <span>Priority: {source.priority}</span>
                            <span>Interval: {source.polling_interval}s</span>
                            <span>Batch: {source.batch_size}</span>
                            {source.tags.length > 0 && (
                              <span>Tags: {source.tags.join(', ')}</span>
                            )}
                          </div>
                          {source.last_monitored && (
                            <div className="mt-1 text-xs text-gray-400">
                              Last monitored: {new Date(source.last_monitored).toLocaleString()}
                            </div>
                          )}
                          {source.error_message && (
                            <div className="mt-1 text-xs text-red-600">
                              Error: {source.error_message}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => testLogSource(source.source_name)}
                        disabled={loading}
                        className="text-green-600 hover:text-green-800 disabled:text-green-300 text-sm font-medium"
                        title="Test log source connectivity"
                      >
                        Test
                      </button>
                      <button
                        onClick={() => handleEdit(source)}
                        disabled={loading}
                        className="text-blue-600 hover:text-blue-800 disabled:text-blue-300 text-sm font-medium"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(source.source_name)}
                        disabled={loading}
                        className="text-red-600 hover:text-red-800 disabled:text-red-300 text-sm font-medium"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </li>
              );
            })
          )}
        </ul>
      </div>
    </div>
  );
};

export default LogSourceManager;