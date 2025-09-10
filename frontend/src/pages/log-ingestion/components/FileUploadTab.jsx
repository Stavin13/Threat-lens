import React, { useState, useRef } from 'react';
import Icon from '../../../components/AppIcon';
import Button from '../../../components/ui/Button';
import Input from '../../../components/ui/Input';

const FileUploadTab = ({ onFileUpload, isUploading }) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [source, setSource] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileInputRef = useRef(null);

  const handleDrag = (e) => {
    e?.preventDefault();
    e?.stopPropagation();
    if (e?.type === 'dragenter' || e?.type === 'dragover') {
      setDragActive(true);
    } else if (e?.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e?.preventDefault();
    e?.stopPropagation();
    setDragActive(false);
    
    if (e?.dataTransfer?.files && e?.dataTransfer?.files?.[0]) {
      const file = e?.dataTransfer?.files?.[0];
      setSelectedFile(file);
    }
  };

  const handleFileSelect = (e) => {
    if (e?.target?.files && e?.target?.files?.[0]) {
      const file = e?.target?.files?.[0];
      setSelectedFile(file);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || !source?.trim()) return;

    const formData = new FormData();
    formData?.append('file', selectedFile);
    formData?.append('source', source);

    // Simulate upload progress
    setUploadProgress(0);
    const progressInterval = setInterval(() => {
      setUploadProgress(prev => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return 90;
        }
        return prev + 10;
      });
    }, 200);

    try {
      await onFileUpload(formData);
      setUploadProgress(100);
      setTimeout(() => {
        setSelectedFile(null);
        setSource('');
        setUploadProgress(0);
      }, 1000);
    } catch (error) {
      setUploadProgress(0);
    } finally {
      clearInterval(progressInterval);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i))?.toFixed(2)) + ' ' + sizes?.[i];
  };

  return (
    <div className="space-y-6">
      {/* Drag and Drop Area */}
      <div
        className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200 ${
          dragActive
            ? 'border-primary bg-primary/5'
            : selectedFile
            ? 'border-success bg-success/5' :'border-border hover:border-primary/50 hover:bg-muted/50'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".log,.txt,.json,.csv"
          onChange={handleFileSelect}
        />

        {selectedFile ? (
          <div className="space-y-4">
            <div className="flex items-center justify-center w-16 h-16 mx-auto bg-success/10 rounded-full">
              <Icon name="FileText" size={32} className="text-success" />
            </div>
            <div>
              <p className="text-lg font-medium text-foreground">{selectedFile?.name}</p>
              <p className="text-sm text-muted-foreground">
                {formatFileSize(selectedFile?.size)} • {selectedFile?.type || 'Unknown type'}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSelectedFile(null)}
              iconName="X"
              iconPosition="left"
            >
              Remove File
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-center w-16 h-16 mx-auto bg-muted rounded-full">
              <Icon name="Upload" size={32} className="text-muted-foreground" />
            </div>
            <div>
              <p className="text-lg font-medium text-foreground">
                Drag and drop your log files here
              </p>
              <p className="text-sm text-muted-foreground">
                or click to browse files
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => fileInputRef?.current?.click()}
              iconName="FolderOpen"
              iconPosition="left"
            >
              Select Files
            </Button>
            <p className="text-xs text-muted-foreground">
              Supported formats: .log, .txt, .json, .csv (Max 50MB)
            </p>
          </div>
        )}

        {dragActive && (
          <div className="absolute inset-0 bg-primary/10 rounded-lg flex items-center justify-center">
            <div className="text-primary font-medium">Drop files here</div>
          </div>
        )}
      </div>
      {/* Source Input */}
      <div className="space-y-4">
        <Input
          label="Log Source"
          type="text"
          placeholder="e.g., web-server-01, firewall-main, application-logs"
          description="Specify the source system or application generating these logs"
          value={source}
          onChange={(e) => setSource(e?.target?.value)}
          required
          className="w-full"
        />

        {/* Upload Progress */}
        {uploadProgress > 0 && uploadProgress < 100 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Uploading...</span>
              <span className="text-foreground font-medium">{uploadProgress}%</span>
            </div>
            <div className="w-full bg-muted rounded-full h-2">
              <div
                className="bg-primary h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Upload Button */}
        <Button
          variant="default"
          size="lg"
          fullWidth
          onClick={handleUpload}
          disabled={!selectedFile || !source?.trim() || isUploading}
          loading={isUploading}
          iconName="Upload"
          iconPosition="left"
        >
          Upload Log File
        </Button>
      </div>
    </div>
  );
};

export default FileUploadTab;