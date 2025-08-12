# ThreatLens Frontend

This is the React TypeScript frontend for the ThreatLens security log analyzer.

## Project Structure

```
src/
├── components/          # React components
│   ├── Layout.tsx      # Main layout wrapper
│   ├── Header.tsx      # Application header
│   ├── Sidebar.tsx     # Navigation sidebar
│   ├── Dashboard.tsx   # Dashboard page
│   ├── Events.tsx      # Events page
│   ├── Reports.tsx     # Reports page
│   ├── IngestLogs.tsx  # Log ingestion page
│   └── index.ts        # Component exports
├── services/           # API and external services
│   ├── api.ts         # Backend API client
│   └── index.ts       # Service exports
├── types/             # TypeScript type definitions
│   └── index.ts       # Type exports
├── App.tsx            # Main application component
├── App.css            # Application styles
├── index.tsx          # Application entry point
└── index.css          # Global styles with Tailwind
```

## Features Implemented

- ✅ React TypeScript project structure
- ✅ API service layer with axios
- ✅ React Router for navigation
- ✅ Responsive layout with header and sidebar
- ✅ Tailwind CSS styling
- ✅ TypeScript type definitions
- ✅ Base page components (Dashboard, Events, Reports, IngestLogs)

## Technologies Used

- React 19.1.1
- TypeScript 4.9.5
- React Router DOM
- Axios for API calls
- Tailwind CSS for styling
- Chart.js for future data visualization

## Development

```bash
npm start    # Start development server
npm build    # Build for production
npm test     # Run tests
```

## Next Steps

The following components will be implemented in subsequent tasks:
- Event table with filtering and sorting
- Event detail modal
- Severity visualization charts
- Real-time dashboard updates
- Log ingestion interface