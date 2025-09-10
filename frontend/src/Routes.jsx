import React from "react";
import { BrowserRouter, Routes as RouterRoutes, Route, Navigate } from "react-router-dom";
import ScrollToTop from "components/ScrollToTop";
import ErrorBoundary from "components/ErrorBoundary";
import NotFound from "pages/NotFound";
import SystemMonitoring from './pages/system-monitoring';
import SecurityDashboard from './pages/security-dashboard';
import EventDetailModal from './pages/event-detail-modal';
import LogIngestion from './pages/log-ingestion';
import EventsManagement from './pages/events-management';

const Routes = () => {
  return (
    <BrowserRouter>
      <ErrorBoundary>
      <ScrollToTop />
      <RouterRoutes>
        {/* Default to Security Dashboard */}
        <Route path="/" element={<Navigate to="/security-dashboard" replace />} />
        <Route path="/system-monitoring" element={<SystemMonitoring />} />
        <Route path="/security-dashboard" element={<SecurityDashboard />} />
        <Route path="/event-detail-modal" element={<EventDetailModal />} />
        <Route path="/log-ingestion" element={<LogIngestion />} />
        <Route path="/events-management" element={<EventsManagement />} />
        <Route path="*" element={<NotFound />} />
      </RouterRoutes>
      </ErrorBoundary>
    </BrowserRouter>
  );
};

export default Routes;
