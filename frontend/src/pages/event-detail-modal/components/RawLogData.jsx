import React, { useState } from 'react';
import Icon from '../../../components/AppIcon';
import Button from '../../../components/ui/Button';

const RawLogData = ({ event }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard?.writeText(event?.rawLog);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const formatLogData = (rawLog) => {
    try {
      // Try to parse as JSON for pretty formatting
      const parsed = JSON.parse(rawLog);
      return JSON.stringify(parsed, null, 2);
    } catch {
      // Return as-is if not valid JSON
      return rawLog;
    }
  };

  const getLogSize = (log) => {
    const bytes = new Blob([log])?.size;
    if (bytes < 1024) return `${bytes} bytes`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024)?.toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024))?.toFixed(1)} MB`;
  };

  return (
    <div className="space-y-4">
      {/* Header with actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Icon name="FileText" size={20} className="text-muted-foreground" />
          <h4 className="text-md font-semibold text-foreground">Raw Log Data</h4>
          <span className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded">
            {getLogSize(event?.rawLog)}
          </span>
        </div>
        
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
            iconName={copied ? "Check" : "Copy"}
            iconPosition="left"
          >
            {copied ? 'Copied!' : 'Copy'}
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            iconName="Download"
            iconPosition="left"
            onClick={() => {
              const blob = new Blob([event.rawLog], { type: 'text/plain' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `event-${event?.id}-raw-log.txt`;
              document.body?.appendChild(a);
              a?.click();
              document.body?.removeChild(a);
              URL.revokeObjectURL(url);
            }}
          >
            Download
          </Button>
        </div>
      </div>
      {/* Log metadata */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4 bg-muted rounded-md">
        <div>
          <label className="text-xs font-medium text-muted-foreground">Format</label>
          <p className="text-sm text-foreground mt-1">{event?.logFormat || 'Plain Text'}</p>
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Encoding</label>
          <p className="text-sm text-foreground mt-1">{event?.encoding || 'UTF-8'}</p>
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Lines</label>
          <p className="text-sm text-foreground mt-1">{event?.rawLog?.split('\n')?.length}</p>
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Parsed</label>
          <div className="flex items-center space-x-1 mt-1">
            <Icon 
              name={event?.parsed ? "CheckCircle" : "XCircle"} 
              size={14} 
              className={event?.parsed ? "text-green-500" : "text-red-500"} 
            />
            <span className="text-sm text-foreground">
              {event?.parsed ? 'Successfully' : 'Failed'}
            </span>
          </div>
        </div>
      </div>
      {/* Raw log content */}
      <div className="relative">
        <div className="absolute top-2 right-2 z-10">
          <div className="flex items-center space-x-1 text-xs text-muted-foreground bg-background/80 px-2 py-1 rounded">
            <Icon name="Code" size={12} />
            <span>Raw Log</span>
          </div>
        </div>
        
        <div className="bg-slate-900 text-green-400 p-4 rounded-md overflow-auto max-h-96 font-mono text-sm">
          <pre className="whitespace-pre-wrap break-words">
            {formatLogData(event?.rawLog)}
          </pre>
        </div>
      </div>
      {/* Log parsing details */}
      {event?.parsingDetails && (
        <div className="space-y-3">
          <h5 className="text-sm font-medium text-foreground flex items-center space-x-2">
            <Icon name="Settings" size={16} />
            <span>Parsing Details</span>
          </h5>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 bg-muted rounded-md">
              <label className="text-xs font-medium text-muted-foreground">Parser Used</label>
              <p className="text-sm text-foreground mt-1">{event?.parsingDetails?.parser}</p>
            </div>
            
            <div className="p-3 bg-muted rounded-md">
              <label className="text-xs font-medium text-muted-foreground">Fields Extracted</label>
              <p className="text-sm text-foreground mt-1">{event?.parsingDetails?.fieldsExtracted}</p>
            </div>
            
            <div className="p-3 bg-muted rounded-md">
              <label className="text-xs font-medium text-muted-foreground">Parse Time</label>
              <p className="text-sm text-foreground mt-1">{event?.parsingDetails?.parseTime}ms</p>
            </div>
            
            <div className="p-3 bg-muted rounded-md">
              <label className="text-xs font-medium text-muted-foreground">Confidence</label>
              <div className="flex items-center space-x-2 mt-1">
                <div className="flex-1 bg-background rounded-full h-2">
                  <div 
                    className="h-2 bg-green-500 rounded-full"
                    style={{ width: `${event?.parsingDetails?.confidence}%` }}
                  />
                </div>
                <span className="text-sm text-foreground">{event?.parsingDetails?.confidence}%</span>
              </div>
            </div>
          </div>
          
          {event?.parsingDetails?.warnings && event?.parsingDetails?.warnings?.length > 0 && (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md">
              <div className="flex items-center space-x-2 mb-2">
                <Icon name="AlertTriangle" size={16} className="text-yellow-600" />
                <span className="text-sm font-medium text-yellow-800">Parsing Warnings</span>
              </div>
              <ul className="space-y-1">
                {event?.parsingDetails?.warnings?.map((warning, index) => (
                  <li key={index} className="text-xs text-yellow-700">• {warning}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default RawLogData;