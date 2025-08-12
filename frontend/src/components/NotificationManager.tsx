import React, { useState, useEffect, useCallback } from 'react';
import { MonitoringConfig, NotificationRule, NotificationRuleRequest } from '../types';
import { api } from '../services/api';

interface NotificationManagerProps {
  config: MonitoringConfig;
  onUpdate: () => void;
}

interface NotificationFormData {
  rule_name: string;
  enabled: boolean;
  min_severity: number;
  max_severity: number;
  categories: string[];
  sources: string[];
  channels: string[];
  throttle_minutes: number;
  email_recipients: string[];
  webhook_url: string;
  slack_channel: string;
}

interface NotificationTest {
  rule_name: string;
  test_severity: number;
  test_category: string;
  test_source: string;
  test_message: string;
}

interface NotificationHistory {
  id: string;
  rule_name: string;
  event_id: string;
  channel: string;
  status: 'sent' | 'failed' | 'pending';
  sent_at: string;
  error_message?: string;
  event_summary: string;
}

const NotificationManager: React.FC<NotificationManagerProps> = ({ config, onUpdate }) => {
  const [rules, setRules] = useState<NotificationRule[]>(config.notification_rules);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingRule, setEditingRule] = useState<NotificationRule | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showTestForm, setShowTestForm] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [notificationHistory, setNotificationHistory] = useState<NotificationHistory[]>([]);
  const [activeTab, setActiveTab] = useState<'rules' | 'test' | 'history'>('rules');

  const [formData, setFormData] = useState<NotificationFormData>({
    rule_name: '',
    enabled: true,
    min_severity: 7,
    max_severity: 10,
    categories: [],
    sources: [],
    channels: [],
    throttle_minutes: 5,
    email_recipients: [],
    webhook_url: '',
    slack_channel: ''
  });

  const [testData, setTestData] = useState<NotificationTest>({
    rule_name: '',
    test_severity: 8,
    test_category: 'security',
    test_source: 'test',
    test_message: 'This is a test notification message'
  });

  const availableCategories = ['authentication', 'network', 'system', 'application', 'security'];
  const availableChannels = ['email', 'webhook', 'slack'];
  const availableSources = config.log_sources.map(source => source.source_name);

  useEffect(() => {
    setRules(config.notification_rules);
  }, [config.notification_rules]);

  const resetForm = () => {
    setFormData({
      rule_name: '',
      enabled: true,
      min_severity: 7,
      max_severity: 10,
      categories: [],
      sources: [],
      channels: [],
      throttle_minutes: 5,
      email_recipients: [],
      webhook_url: '',
      slack_channel: ''
    });
    setEditingRule(null);
    setShowAddForm(false);
    setError(null);
  };

  const handleInputChange = (field: keyof NotificationFormData, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleArrayInputChange = (field: 'categories' | 'sources' | 'channels' | 'email_recipients', value: string) => {
    const items = value.split(',').map(item => item.trim()).filter(item => item.length > 0);
    setFormData(prev => ({
      ...prev,
      [field]: items
    }));
  };

  const validateForm = (): string | null => {
    if (!formData.rule_name.trim()) {
      return 'Rule name is required';
    }
    
    if (formData.min_severity < 1 || formData.min_severity > 10) {
      return 'Minimum severity must be between 1 and 10';
    }
    
    if (formData.max_severity < 1 || formData.max_severity > 10) {
      return 'Maximum severity must be between 1 and 10';
    }
    
    if (formData.min_severity > formData.max_severity) {
      return 'Minimum severity cannot be greater than maximum severity';
    }
    
    if (formData.channels.length === 0) {
      return 'At least one notification channel must be selected';
    }
    
    if (formData.channels.includes('email') && formData.email_recipients.length === 0) {
      return 'Email recipients are required when email channel is selected';
    }
    
    if (formData.channels.includes('webhook') && !formData.webhook_url.trim()) {
      return 'Webhook URL is required when webhook channel is selected';
    }
    
    if (formData.channels.includes('slack') && !formData.slack_channel.trim()) {
      return 'Slack channel is required when Slack channel is selected';
    }
    
    if (formData.throttle_minutes < 0 || formData.throttle_minutes > 1440) {
      return 'Throttle minutes must be between 0 and 1440 (24 hours)';
    }
    
    // Check for duplicate rule names
    const existingRules = rules.filter(r => r.rule_name !== editingRule?.rule_name);
    if (existingRules.some(r => r.rule_name === formData.rule_name.trim())) {
      return 'A notification rule with this name already exists';
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
      const requestData: NotificationRuleRequest = {
        rule_name: formData.rule_name.trim(),
        enabled: formData.enabled,
        min_severity: formData.min_severity,
        max_severity: formData.max_severity,
        categories: formData.categories,
        sources: formData.sources,
        channels: formData.channels,
        throttle_minutes: formData.throttle_minutes,
        email_recipients: formData.email_recipients,
        webhook_url: formData.webhook_url.trim() || undefined,
        slack_channel: formData.slack_channel.trim() || undefined
      };

      if (editingRule) {
        await api.put(`/realtime/notification-rules/${editingRule.rule_name}`, requestData);
      } else {
        await api.post('/realtime/notification-rules', requestData);
      }

      resetForm();
      onUpdate();
    } catch (err: any) {
      console.error('Failed to save notification rule:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to save notification rule');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (rule: NotificationRule) => {
    setFormData({
      rule_name: rule.rule_name,
      enabled: rule.enabled,
      min_severity: rule.min_severity,
      max_severity: rule.max_severity,
      categories: rule.categories,
      sources: rule.sources,
      channels: rule.channels,
      throttle_minutes: rule.throttle_minutes,
      email_recipients: rule.email_recipients,
      webhook_url: rule.webhook_url || '',
      slack_channel: rule.slack_channel || ''
    });
    setEditingRule(rule);
    setShowAddForm(true);
  };

  const handleDelete = async (ruleName: string) => {
    if (!window.confirm(`Are you sure you want to delete the notification rule "${ruleName}"?`)) {
      return;
    }

    setLoading(true);
    try {
      await api.delete(`/realtime/notification-rules/${ruleName}`);
      onUpdate();
    } catch (err: any) {
      console.error('Failed to delete notification rule:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to delete notification rule');
    } finally {
      setLoading(false);
    }
  };

  const handleTestNotification = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!testData.rule_name) {
      setError('Please select a rule to test');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await api.post(`/realtime/notification-rules/${testData.rule_name}/test`, {
        severity: testData.test_severity,
        category: testData.test_category,
        source: testData.test_source,
        message: testData.test_message
      });
      
      setError(null);
      // Show success message
      alert('Test notification sent successfully!');
      
      // Refresh history
      loadNotificationHistory();
    } catch (err: any) {
      console.error('Failed to send test notification:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to send test notification');
    } finally {
      setLoading(false);
    }
  };

  const loadNotificationHistory = useCallback(async () => {
    try {
      const response = await api.get('/realtime/notification-history?limit=50');
      setNotificationHistory(response.data);
    } catch (err) {
      console.error('Failed to load notification history:', err);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'history') {
      loadNotificationHistory();
    }
  }, [activeTab, loadNotificationHistory]);

  const getSeverityColor = (severity: number) => {
    if (severity >= 9) return 'text-red-600';
    if (severity >= 7) return 'text-yellow-600';
    if (severity >= 5) return 'text-blue-600';
    return 'text-gray-600';
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'sent': return 'bg-green-100 text-green-800';
      case 'failed': return 'bg-red-100 text-red-800';
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-lg font-medium text-gray-900">Notification Rules</h2>
          <p className="text-sm text-gray-500">
            Configure notification rules and channels for high-priority events
          </p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-4 py-2 rounded-md text-sm font-medium"
        >
          Add Rule
        </button>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('rules')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'rules'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Rules ({rules.length})
          </button>
          <button
            onClick={() => setActiveTab('test')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'test'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Test Notifications
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'history'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            History
          </button>
        </nav>
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

      {/* Rules Tab */}
      {activeTab === 'rules' && (
        <>
          {/* Add/Edit Form */}
          {showAddForm && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium text-gray-900">
                  {editingRule ? 'Edit Notification Rule' : 'Add New Notification Rule'}
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
                  {/* Rule Name */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Rule Name *
                    </label>
                    <input
                      type="text"
                      value={formData.rule_name}
                      onChange={(e) => handleInputChange('rule_name', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="e.g., High Severity Security Alerts"
                      required
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
                      Enable this rule
                    </label>
                  </div>

                  {/* Severity Range */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Minimum Severity (1-10)
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="10"
                      value={formData.min_severity}
                      onChange={(e) => handleInputChange('min_severity', parseInt(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Maximum Severity (1-10)
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="10"
                      value={formData.max_severity}
                      onChange={(e) => handleInputChange('max_severity', parseInt(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  {/* Throttle */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Throttle (minutes)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="1440"
                      value={formData.throttle_minutes}
                      onChange={(e) => handleInputChange('throttle_minutes', parseInt(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Minimum time between notifications for the same rule
                    </p>
                  </div>
                </div>

                {/* Categories */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Categories (leave empty for all)
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {availableCategories.map(category => (
                      <label key={category} className="flex items-center">
                        <input
                          type="checkbox"
                          checked={formData.categories.includes(category)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              handleInputChange('categories', [...formData.categories, category]);
                            } else {
                              handleInputChange('categories', formData.categories.filter(c => c !== category));
                            }
                          }}
                          className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        />
                        <span className="ml-2 text-sm text-gray-700 capitalize">{category}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Sources */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Log Sources (leave empty for all)
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {availableSources.map(source => (
                      <label key={source} className="flex items-center">
                        <input
                          type="checkbox"
                          checked={formData.sources.includes(source)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              handleInputChange('sources', [...formData.sources, source]);
                            } else {
                              handleInputChange('sources', formData.sources.filter(s => s !== source));
                            }
                          }}
                          className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        />
                        <span className="ml-2 text-sm text-gray-700">{source}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Channels */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Notification Channels *
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {availableChannels.map(channel => (
                      <label key={channel} className="flex items-center">
                        <input
                          type="checkbox"
                          checked={formData.channels.includes(channel)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              handleInputChange('channels', [...formData.channels, channel]);
                            } else {
                              handleInputChange('channels', formData.channels.filter(c => c !== channel));
                            }
                          }}
                          className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        />
                        <span className="ml-2 text-sm text-gray-700 capitalize">{channel}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Channel-specific configuration */}
                {formData.channels.includes('email') && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Email Recipients (comma-separated) *
                    </label>
                    <input
                      type="text"
                      value={formData.email_recipients.join(', ')}
                      onChange={(e) => handleArrayInputChange('email_recipients', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="admin@example.com, security@example.com"
                    />
                  </div>
                )}

                {formData.channels.includes('webhook') && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Webhook URL *
                    </label>
                    <input
                      type="url"
                      value={formData.webhook_url}
                      onChange={(e) => handleInputChange('webhook_url', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="https://hooks.example.com/webhook"
                    />
                  </div>
                )}

                {formData.channels.includes('slack') && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Slack Channel *
                    </label>
                    <input
                      type="text"
                      value={formData.slack_channel}
                      onChange={(e) => handleInputChange('slack_channel', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="#security-alerts"
                    />
                  </div>
                )}

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
                    {loading ? 'Saving...' : (editingRule ? 'Update Rule' : 'Add Rule')}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Rules List */}
          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
              {rules.length === 0 ? (
                <li className="px-6 py-8 text-center">
                  <div className="text-gray-500">
                    <span className="text-4xl mb-4 block">🔔</span>
                    <h3 className="text-lg font-medium text-gray-900 mb-2">No notification rules configured</h3>
                    <p className="text-sm">Add your first notification rule to start receiving alerts.</p>
                  </div>
                </li>
              ) : (
                rules.map((rule) => (
                  <li key={rule.rule_name} className="px-6 py-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-3">
                          <div className="flex-shrink-0">
                            <span className="text-2xl">🔔</span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center space-x-2">
                              <h3 className="text-sm font-medium text-gray-900 truncate">
                                {rule.rule_name}
                              </h3>
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                rule.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                              }`}>
                                {rule.enabled ? 'Enabled' : 'Disabled'}
                              </span>
                            </div>
                            <div className="mt-1 flex items-center space-x-4 text-xs text-gray-500">
                              <span className={getSeverityColor(rule.min_severity)}>
                                Severity: {rule.min_severity}-{rule.max_severity}
                              </span>
                              <span>Throttle: {rule.throttle_minutes}m</span>
                              <span>Channels: {rule.channels.join(', ')}</span>
                            </div>
                            {rule.categories.length > 0 && (
                              <div className="mt-1 text-xs text-gray-400">
                                Categories: {rule.categories.join(', ')}
                              </div>
                            )}
                            {rule.sources.length > 0 && (
                              <div className="mt-1 text-xs text-gray-400">
                                Sources: {rule.sources.join(', ')}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => handleEdit(rule)}
                          disabled={loading}
                          className="text-blue-600 hover:text-blue-800 disabled:text-blue-300 text-sm font-medium"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(rule.rule_name)}
                          disabled={loading}
                          className="text-red-600 hover:text-red-800 disabled:text-red-300 text-sm font-medium"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </li>
                ))
              )}
            </ul>
          </div>
        </>
      )}

      {/* Test Tab */}
      {activeTab === 'test' && (
        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Test Notifications</h3>
          <p className="text-sm text-gray-500 mb-6">
            Send test notifications to verify your notification rules are working correctly.
          </p>

          <form onSubmit={handleTestNotification} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Rule to Test *
                </label>
                <select
                  value={testData.rule_name}
                  onChange={(e) => setTestData(prev => ({ ...prev, rule_name: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="">Select a rule</option>
                  {rules.filter(r => r.enabled).map(rule => (
                    <option key={rule.rule_name} value={rule.rule_name}>
                      {rule.rule_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Test Severity (1-10)
                </label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={testData.test_severity}
                  onChange={(e) => setTestData(prev => ({ ...prev, test_severity: parseInt(e.target.value) }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Test Category
                </label>
                <select
                  value={testData.test_category}
                  onChange={(e) => setTestData(prev => ({ ...prev, test_category: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {availableCategories.map(category => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Test Source
                </label>
                <input
                  type="text"
                  value={testData.test_source}
                  onChange={(e) => setTestData(prev => ({ ...prev, test_source: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="test-source"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Test Message
              </label>
              <textarea
                value={testData.test_message}
                onChange={(e) => setTestData(prev => ({ ...prev, test_message: e.target.value }))}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="This is a test notification message to verify the notification system is working correctly."
              />
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={loading || !testData.rule_name}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-300 text-white rounded-md text-sm font-medium"
              >
                {loading ? 'Sending...' : 'Send Test Notification'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <div className="px-4 py-5 sm:p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium text-gray-900">Notification History</h3>
              <button
                onClick={loadNotificationHistory}
                className="text-blue-600 hover:text-blue-800 text-sm font-medium"
              >
                Refresh
              </button>
            </div>

            {notificationHistory.length === 0 ? (
              <div className="text-center py-8">
                <span className="text-4xl mb-4 block">📭</span>
                <h3 className="text-lg font-medium text-gray-900 mb-2">No notification history</h3>
                <p className="text-sm text-gray-500">Notification history will appear here once notifications are sent.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {notificationHistory.map((notification) => (
                  <div key={notification.id} className="border border-gray-200 rounded-md p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <span className="text-lg">
                          {notification.channel === 'email' ? '📧' : 
                           notification.channel === 'slack' ? '💬' : 
                           notification.channel === 'webhook' ? '🔗' : '🔔'}
                        </span>
                        <div>
                          <h4 className="text-sm font-medium text-gray-900">
                            {notification.rule_name}
                          </h4>
                          <p className="text-sm text-gray-500">
                            {notification.event_summary}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(notification.status)}`}>
                          {notification.status}
                        </span>
                        <span className="text-xs text-gray-500">
                          {new Date(notification.sent_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                    {notification.error_message && (
                      <div className="mt-2 text-sm text-red-600">
                        Error: {notification.error_message}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationManager;