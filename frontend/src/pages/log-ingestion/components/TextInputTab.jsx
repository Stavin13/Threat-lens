import React, { useState } from 'react';
import Icon from '../../../components/AppIcon';
import Button from '../../../components/ui/Button';
import Input from '../../../components/ui/Input';

const TextInputTab = ({ onTextSubmit, isSubmitting }) => {
  const [logContent, setLogContent] = useState('');
  const [source, setSource] = useState('');
  const [errors, setErrors] = useState({});

  const maxCharacters = 50000;
  const characterCount = logContent?.length;
  const isNearLimit = characterCount > maxCharacters * 0.9;
  const isOverLimit = characterCount > maxCharacters;

  const validateForm = () => {
    const newErrors = {};
    
    if (!logContent?.trim()) {
      newErrors.content = 'Log content is required';
    } else if (logContent?.trim()?.length < 10) {
      newErrors.content = 'Log content must be at least 10 characters';
    } else if (isOverLimit) {
      newErrors.content = `Content exceeds maximum limit of ${maxCharacters?.toLocaleString()} characters`;
    }
    
    if (!source?.trim()) {
      newErrors.source = 'Log source is required';
    } else if (source?.trim()?.length < 3) {
      newErrors.source = 'Source must be at least 3 characters';
    }

    setErrors(newErrors);
    return Object.keys(newErrors)?.length === 0;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;

    const logData = {
      content: logContent?.trim(),
      source: source?.trim(),
      timestamp: new Date()?.toISOString(),
      type: 'manual_entry'
    };

    try {
      await onTextSubmit(logData);
      setLogContent('');
      setSource('');
      setErrors({});
    } catch (error) {
      setErrors({ submit: 'Failed to submit log content. Please try again.' });
    }
  };

  const handleContentChange = (e) => {
    const value = e?.target?.value;
    setLogContent(value);
    
    // Clear content error when user starts typing
    if (errors?.content && value?.trim()?.length >= 10) {
      setErrors(prev => ({ ...prev, content: '' }));
    }
  };

  const handleSourceChange = (e) => {
    const value = e?.target?.value;
    setSource(value);
    
    // Clear source error when user starts typing
    if (errors?.source && value?.trim()?.length >= 3) {
      setErrors(prev => ({ ...prev, source: '' }));
    }
  };

  const insertSampleLog = () => {
    const sampleLog = `2025-01-08 05:29:27 [INFO] web-server-01: HTTP/1.1 GET /api/users/profile - 200 OK - 45ms - User: john.doe@company.com - IP: 192.168.1.100
2025-01-08 05:29:28 [WARN] web-server-01: Rate limit approaching for IP 192.168.1.100 - 85/100 requests in last minute
2025-01-08 05:29:29 [ERROR] auth-service: Failed login attempt - User: admin@company.com - IP: 203.0.113.45 - Reason: Invalid credentials
2025-01-08 05:29:30 [INFO] database: Query executed successfully - Table: user_sessions - Duration: 12ms - Rows affected: 1
2025-01-08 05:29:31 [CRITICAL] firewall: Blocked suspicious traffic - Source: 198.51.100.42 - Destination: 192.168.1.10:22 - Rule: SSH_BRUTE_FORCE_PROTECTION`;
    
    setLogContent(sampleLog);
    setSource('sample-system');
  };

  return (
    <div className="space-y-6">
      {/* Header with Sample Button */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">Manual Log Entry</h3>
          <p className="text-sm text-muted-foreground">
            Paste or type log content directly for immediate processing
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={insertSampleLog}
          iconName="FileText"
          iconPosition="left"
        >
          Insert Sample
        </Button>
      </div>
      {/* Source Input */}
      <Input
        label="Log Source"
        type="text"
        placeholder="e.g., web-server-01, firewall-main, application-logs"
        description="Specify the source system or application generating these logs"
        value={source}
        onChange={handleSourceChange}
        error={errors?.source}
        required
        className="w-full"
      />
      {/* Text Area */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-foreground">
          Log Content <span className="text-error">*</span>
        </label>
        <div className="relative">
          <textarea
            value={logContent}
            onChange={handleContentChange}
            placeholder={`Paste your log content here...\n\nExample format:\n2025-01-08 05:29:27 [INFO] system: Message content\n2025-01-08 05:29:28 [WARN] system: Warning message`}
            className={`w-full h-64 px-3 py-2 text-sm border rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-colors ${
              errors?.content
                ? 'border-error focus:ring-error/20' :'border-border hover:border-border/80'
            } bg-input text-foreground placeholder:text-muted-foreground`}
            style={{ fontFamily: 'JetBrains Mono, monospace' }}
          />
          
          {/* Character Count */}
          <div className="absolute bottom-2 right-2 text-xs text-muted-foreground bg-background/80 px-2 py-1 rounded">
            <span className={isNearLimit ? (isOverLimit ? 'text-error' : 'text-warning') : ''}>
              {characterCount?.toLocaleString()}
            </span>
            <span className="text-muted-foreground">
              /{maxCharacters?.toLocaleString()}
            </span>
          </div>
        </div>
        
        {errors?.content && (
          <p className="text-sm text-error flex items-center gap-1">
            <Icon name="AlertCircle" size={14} />
            {errors?.content}
          </p>
        )}
        
        <p className="text-xs text-muted-foreground">
          Supports standard log formats with timestamps, severity levels, and structured content
        </p>
      </div>
      {/* Format Guidelines */}
      <div className="bg-muted/50 rounded-lg p-4">
        <h4 className="text-sm font-medium text-foreground mb-2 flex items-center gap-2">
          <Icon name="Info" size={16} />
          Formatting Guidelines
        </h4>
        <ul className="text-xs text-muted-foreground space-y-1">
          <li>• Include timestamps in ISO format or standard log format</li>
          <li>• Use severity levels: [INFO], [WARN], [ERROR], [CRITICAL]</li>
          <li>• Separate multiple log entries with line breaks</li>
          <li>• Include source system identifiers when possible</li>
        </ul>
      </div>
      {/* Submit Error */}
      {errors?.submit && (
        <div className="bg-error/10 border border-error/20 rounded-lg p-3">
          <p className="text-sm text-error flex items-center gap-2">
            <Icon name="AlertTriangle" size={16} />
            {errors?.submit}
          </p>
        </div>
      )}
      {/* Submit Button */}
      <Button
        variant="default"
        size="lg"
        fullWidth
        onClick={handleSubmit}
        disabled={!logContent?.trim() || !source?.trim() || isOverLimit || isSubmitting}
        loading={isSubmitting}
        iconName="Send"
        iconPosition="left"
      >
        Submit Log Content
      </Button>
    </div>
  );
};

export default TextInputTab;