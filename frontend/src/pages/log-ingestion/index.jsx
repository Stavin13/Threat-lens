import React, { useState, useEffect } from 'react';
import { Helmet } from 'react-helmet';
import NavigationHeader from '../../components/ui/NavigationHeader';
import Icon from '../../components/AppIcon';
import FileUploadTab from './components/FileUploadTab';
import TextInputTab from './components/TextInputTab';
import RecentUploadsSection from './components/RecentUploadsSection';
import IngestionStats from './components/IngestionStats';

const LogIngestion = () => {
  const [activeTab, setActiveTab] = useState('file');
  const [isUploading, setIsUploading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [connectionStatus] = useState({
    connected: true,
    lastUpdate: new Date(Date.now() - 30000)
  });
  const [toastMessage, setToastMessage] = useState(null);

  // Mock data for ingestion stats
  const [stats] = useState({
    totalUploads: 1247,
    eventsProcessed: 89432,
    queueDepth: 12,
    failedUploads: 3,
    processingRate: 156,
    avgProcessingTime: 2.3
  });

  // Mock data for recent uploads
  const [recentUploads] = useState([
    {
      id: 'upload_001',
      filename: 'web-server-logs-2025-01-08.log',
      source: 'web-server-01',
      type: 'file',
      size: 2048576,
      status: 'completed',
      timestamp: new Date(Date.now() - 300000),
      eventsProcessed: 1543
    },
    {
      id: 'upload_002',
      filename: 'firewall-alerts.json',
      source: 'firewall-main',
      type: 'file',
      size: 512000,
      status: 'processing',
      timestamp: new Date(Date.now() - 120000),
      progress: 67
    },
    {
      id: 'upload_003',
      filename: null,
      source: 'application-logs',
      type: 'text',
      size: null,
      status: 'completed',
      timestamp: new Date(Date.now() - 600000),
      eventsProcessed: 234
    },
    {
      id: 'upload_004',
      filename: 'database-audit.log',
      source: 'db-cluster-01',
      type: 'file',
      size: 1024000,
      status: 'failed',
      timestamp: new Date(Date.now() - 900000),
      error: 'Invalid log format detected'
    },
    {
      id: 'upload_005',
      filename: 'auth-service-logs.txt',
      source: 'auth-service',
      type: 'file',
      size: 768000,
      status: 'queued',
      timestamp: new Date(Date.now() - 60000)
    }
  ]);

  const showToast = (message, type = 'success') => {
    setToastMessage({ message, type });
    setTimeout(() => setToastMessage(null), 5000);
  };

  const handleFileUpload = async (formData) => {
    setIsUploading(true);
    
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      showToast('File uploaded successfully and queued for processing', 'success');
    } catch (error) {
      showToast('Failed to upload file. Please try again.', 'error');
      throw error;
    } finally {
      setIsUploading(false);
    }
  };

  const handleTextSubmit = async (logData) => {
    setIsSubmitting(true);
    
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      showToast('Log content submitted successfully for processing', 'success');
    } catch (error) {
      showToast('Failed to submit log content. Please try again.', 'error');
      throw error;
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRetryUpload = async (uploadId) => {
    try {
      // Simulate retry API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      showToast('Upload retry initiated successfully', 'success');
    } catch (error) {
      showToast('Failed to retry upload. Please try again.', 'error');
    }
  };

  const tabs = [
    {
      id: 'file',
      label: 'File Upload',
      icon: 'Upload',
      description: 'Upload log files from your system'
    },
    {
      id: 'text',
      label: 'Text Input',
      icon: 'Type',
      description: 'Paste or type log content directly'
    }
  ];

  return (
    <>
      <Helmet>
        <title>Log Ingestion - ThreatLens</title>
        <meta name="description" content="Upload and process security logs through file upload or direct text input for real-time threat analysis" />
      </Helmet>
      <div className="min-h-screen bg-background">
        <NavigationHeader connectionStatus={connectionStatus} />
        
        <main className="pt-16">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {/* Page Header */}
            <div className="mb-8">
              <div className="flex items-center gap-3 mb-2">
                <div className="flex items-center justify-center w-10 h-10 bg-primary/10 rounded-lg">
                  <Icon name="Upload" size={24} className="text-primary" />
                </div>
                <div>
                  <h1 className="text-3xl font-bold text-foreground">Log Ingestion</h1>
                  <p className="text-muted-foreground">
                    Upload and process security logs for real-time threat analysis
                  </p>
                </div>
              </div>
            </div>

            {/* Ingestion Stats */}
            <IngestionStats stats={stats} />

            {/* Main Content */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
              {/* Left Column - Ingestion Interface */}
              <div className="xl:col-span-2">
                <div className="bg-card rounded-lg border border-border shadow-elevation-1">
                  {/* Tab Navigation */}
                  <div className="border-b border-border">
                    <nav className="flex">
                      {tabs?.map((tab) => (
                        <button
                          key={tab?.id}
                          onClick={() => setActiveTab(tab?.id)}
                          className={`flex-1 flex items-center justify-center gap-2 px-6 py-4 text-sm font-medium transition-colors min-h-touch ${
                            activeTab === tab?.id
                              ? 'text-primary border-b-2 border-primary bg-primary/5' :'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                          }`}
                        >
                          <Icon name={tab?.icon} size={18} />
                          <span className="hidden sm:inline">{tab?.label}</span>
                        </button>
                      ))}
                    </nav>
                  </div>

                  {/* Tab Content */}
                  <div className="p-6">
                    {activeTab === 'file' ? (
                      <FileUploadTab
                        onFileUpload={handleFileUpload}
                        isUploading={isUploading}
                      />
                    ) : (
                      <TextInputTab
                        onTextSubmit={handleTextSubmit}
                        isSubmitting={isSubmitting}
                      />
                    )}
                  </div>
                </div>
              </div>

              {/* Right Column - Processing Guidelines */}
              <div className="space-y-6">
                {/* Processing Guidelines */}
                <div className="bg-card rounded-lg border border-border p-6">
                  <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                    <Icon name="BookOpen" size={20} />
                    Processing Guidelines
                  </h3>
                  
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-sm font-medium text-foreground mb-2">Supported Formats</h4>
                      <ul className="text-xs text-muted-foreground space-y-1">
                        <li>• Standard syslog format (RFC 3164/5424)</li>
                        <li>• JSON structured logs</li>
                        <li>• Common Event Format (CEF)</li>
                        <li>• Custom delimited formats</li>
                      </ul>
                    </div>
                    
                    <div>
                      <h4 className="text-sm font-medium text-foreground mb-2">File Limits</h4>
                      <ul className="text-xs text-muted-foreground space-y-1">
                        <li>• Maximum file size: 50MB</li>
                        <li>• Supported extensions: .log, .txt, .json, .csv</li>
                        <li>• Batch processing available</li>
                      </ul>
                    </div>
                    
                    <div>
                      <h4 className="text-sm font-medium text-foreground mb-2">Processing Time</h4>
                      <ul className="text-xs text-muted-foreground space-y-1">
                        <li>• Small files (&lt;1MB): ~30 seconds</li>
                        <li>• Medium files (1-10MB): ~2-5 minutes</li>
                        <li>• Large files (10-50MB): ~10-15 minutes</li>
                      </ul>
                    </div>
                  </div>
                </div>

                {/* System Status */}
                <div className="bg-card rounded-lg border border-border p-6">
                  <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                    <Icon name="Server" size={20} />
                    System Status
                  </h3>
                  
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Ingestion Service</span>
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-success rounded-full animate-pulse-slow" />
                        <span className="text-xs text-success font-medium">Online</span>
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Processing Queue</span>
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-warning rounded-full" />
                        <span className="text-xs text-warning font-medium">Busy</span>
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">AI Analysis</span>
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-success rounded-full animate-pulse-slow" />
                        <span className="text-xs text-success font-medium">Ready</span>
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Storage</span>
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-success rounded-full" />
                        <span className="text-xs text-success font-medium">78% Available</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Recent Uploads Section */}
            <div className="mt-8">
              <RecentUploadsSection
                uploads={recentUploads}
                onRetry={handleRetryUpload}
              />
            </div>
          </div>
        </main>

        {/* Toast Notification */}
        {toastMessage && (
          <div className="fixed bottom-4 right-4 z-50 animate-in slide-in-from-bottom-2">
            <div className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-elevation-3 ${
              toastMessage?.type === 'success' ?'bg-success text-success-foreground' :'bg-error text-error-foreground'
            }`}>
              <Icon
                name={toastMessage?.type === 'success' ? 'CheckCircle' : 'AlertCircle'}
                size={20}
              />
              <span className="text-sm font-medium">{toastMessage?.message}</span>
              <button
                onClick={() => setToastMessage(null)}
                className="ml-2 hover:opacity-80 transition-opacity"
              >
                <Icon name="X" size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
};

export default LogIngestion;