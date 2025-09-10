// Utility functions for formatting data from the API

export function formatTimestamp(timestamp) {
  if (!timestamp) return 'N/A';
  
  try {
    const date = new Date(timestamp);
    return date.toLocaleString();
  } catch (error) {
    return timestamp;
  }
}

export function formatSeverity(score) {
  if (score === undefined || score === null) return 'Unknown';
  
  const num = Number(score);
  if (isNaN(num)) return 'Unknown';
  
  if (num >= 9) return 'Critical';
  if (num >= 7) return 'High';
  if (num >= 5) return 'Medium';
  if (num >= 3) return 'Low';
  return 'Info';
}

export function getSeverityColor(score) {
  const num = Number(score);
  if (isNaN(num)) return 'gray';
  
  if (num >= 9) return 'red';
  if (num >= 7) return 'orange';
  if (num >= 5) return 'yellow';
  if (num >= 3) return 'blue';
  return 'gray';
}

export function formatCategory(category) {
  if (!category) return 'Unknown';
  
  return category.charAt(0).toUpperCase() + category.slice(1).toLowerCase();
}

export function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

export function formatDuration(ms) {
  if (!ms || ms === 0) return '0ms';
  
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 3600000) return `${(ms / 60000).toFixed(1)}m`;
  
  return `${(ms / 3600000).toFixed(1)}h`;
}

export function formatPercentage(value, total) {
  if (!total || total === 0) return '0%';
  
  const percentage = (value / total) * 100;
  return `${percentage.toFixed(1)}%`;
}

export function truncateText(text, maxLength = 100) {
  if (!text) return '';
  
  if (text.length <= maxLength) return text;
  
  return text.substring(0, maxLength) + '...';
}