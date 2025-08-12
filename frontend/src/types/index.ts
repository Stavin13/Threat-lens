export interface ParsedEvent {
  id: string;
  timestamp: string;
  source: string;
  message: string;
  category: string;
}

export interface AIAnalysis {
  severity_score: number;
  explanation: string;
  recommendations: string[];
}

export interface EventResponse {
  event: ParsedEvent;
  analysis: AIAnalysis;
}

export interface EventFilter {
  start_date?: string;
  end_date?: string;
  min_severity?: number;
  max_severity?: number;
  category?: string;
  source?: string;
  per_page?: number;
}

export interface IngestionRequest {
  content: string;
  source?: string;
}

export interface IngestionResult {
  id: string;
  message: string;
  status: string;
}

export enum EventCategory {
  AUTHENTICATION = 'authentication',
  NETWORK = 'network',
  SYSTEM = 'system',
  APPLICATION = 'application',
  SECURITY = 'security'
}

// Configuration Management Types
export interface LogSourceConfig {
  source_name: string;
  path: string;
  source_type: 'file' | 'directory';
  enabled: boolean;
  recursive: boolean;
  file_pattern?: string;
  polling_interval: number;
  batch_size: number;
  priority: number;
  description?: string;
  tags: string[];
  status: 'active' | 'inactive' | 'error' | 'paused';
  last_monitored?: string;
  file_size?: number;
  last_offset?: number;
  error_message?: string;
}

export interface LogSourceConfigRequest {
  source_name: string;
  path: string;
  source_type: 'file' | 'directory';
  enabled: boolean;
  recursive: boolean;
  file_pattern?: string;
  polling_interval: number;
  batch_size: number;
  priority: number;
  description?: string;
  tags: string[];
}

export interface NotificationRule {
  rule_name: string;
  enabled: boolean;
  min_severity: number;
  max_severity: number;
  categories: string[];
  sources: string[];
  channels: string[];
  throttle_minutes: number;
  email_recipients: string[];
  webhook_url?: string;
  slack_channel?: string;
}

export interface NotificationRuleRequest {
  rule_name: string;
  enabled: boolean;
  min_severity: number;
  max_severity: number;
  categories: string[];
  sources: string[];
  channels: string[];
  throttle_minutes: number;
  email_recipients: string[];
  webhook_url?: string;
  slack_channel?: string;
}

export interface MonitoringConfig {
  enabled: boolean;
  max_concurrent_sources: number;
  processing_batch_size: number;
  max_queue_size: number;
  health_check_interval: number;
  max_error_count: number;
  retry_interval: number;
  file_read_chunk_size: number;
  websocket_max_connections: number;
  log_sources: LogSourceConfig[];
  notification_rules: NotificationRule[];
  config_version: string;
  created_at?: string;
  updated_at?: string;
}