# ThreatLens Frontend Integration

The v0.dev frontend has been successfully integrated with your ThreatLens backend. Here's what's been configured:

## ✅ What's Working

### API Integration
- **Base URL**: Configured to use `http://localhost:8000` (your FastAPI backend)
- **Environment**: Uses `NEXT_PUBLIC_THREATLENS_API_BASE` from `.env.local`
- **Endpoints**: All API calls properly mapped to your backend routes:
  - `/stats` - System statistics
  - `/events` - Event listing with pagination and filtering
  - `/realtime/monitoring/metrics` - Real-time metrics
  - `/realtime/status` - System status
  - `/ingest-log` - Log ingestion (file and text)
  - `/reports/files` - Report management

### WebSocket Integration
- **Real-time updates**: Connected to `/ws` endpoint
- **Authentication**: Uses `NEXT_PUBLIC_THREATLENS_WS_TOKEN` from environment
- **Auto-reconnection**: Handles connection drops gracefully
- **Cache invalidation**: Automatically refreshes data on new events

### Components Ready
- **Dashboard**: Real-time metrics, system status, recent activity
- **Events**: Paginated table with filtering and sorting
- **Ingestion**: File upload and text input forms
- **Reports**: Report generation and file management
- **System**: Monitoring and configuration

## 🚀 Quick Start

### Option 1: Use the startup script
```bash
./start-dev.sh
```

### Option 2: Manual startup
```bash
# Terminal 1 - Backend
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
cd frontend
npm install
npm run dev
```

## 🌐 Access Points

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **WebSocket**: ws://localhost:8000/ws

## 🔧 Configuration

### Environment Variables (.env.local)
```bash
# REST API base URL (backend)
NEXT_PUBLIC_THREATLENS_API_BASE=http://localhost:8000

# Optional JWT or dev token for WebSocket authentication
NEXT_PUBLIC_THREATLENS_WS_TOKEN=dev-token-here

# Timeout for SWR/fetcher (in ms)
NEXT_PUBLIC_THREATLENS_AGENT_TIMEOUT=15000
```

## 📊 Features

### Dashboard
- **Live Metrics**: Events count, high severity alerts, queue depth, processing rate
- **System Status**: File monitor, queue size, WebSocket status, events processed
- **Real-time Updates**: Auto-refreshing data via WebSocket

### Events Page
- **Pagination**: Server-side pagination with configurable page size
- **Filtering**: By category, severity, date range, source
- **Sorting**: By timestamp, severity, source, category
- **Real-time**: New events appear automatically

### Ingestion
- **File Upload**: Drag & drop or browse for log files
- **Text Input**: Paste log content directly
- **Source Tracking**: Specify source for each ingestion

### Reports
- **Generation**: Trigger manual report creation
- **File Management**: View and download existing reports
- **Scheduling**: Integration with backend scheduler

## 🔄 Real-time Features

The frontend automatically:
- Updates metrics when new events are processed
- Refreshes event lists when new events arrive
- Shows connection status in the system panel
- Handles WebSocket reconnections

## 🛠 Troubleshooting

### Common Issues

1. **CORS Errors**: Backend is configured for `localhost:3000`
2. **WebSocket Connection**: Check token in `.env.local`
3. **API Errors**: Verify backend is running on port 8000
4. **Dependencies**: Run `npm install --legacy-peer-deps` if needed

### Debug Mode
Enable debug logging by setting:
```bash
LOG_LEVEL=DEBUG
```

## 🎯 Next Steps

The frontend is fully functional and ready for:
- Custom styling and branding
- Additional filtering options
- Enhanced real-time visualizations
- User authentication integration
- Advanced analytics dashboards

All components are built with TypeScript and follow modern React patterns with proper error handling and loading states.