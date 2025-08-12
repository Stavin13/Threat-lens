import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Layout, Dashboard, Events, Reports, IngestLogs, Configuration } from './components';
import ErrorBoundary from './components/ErrorBoundary';
import ErrorFallback from './components/ErrorFallback';
import { useGlobalErrorHandler } from './hooks/useErrorHandler';
import './App.css';

function App() {
  // Set up global error handling
  const globalErrorHandler = useGlobalErrorHandler();

  const handleAppError = (error: Error, errorInfo: React.ErrorInfo) => {
    // Log error to external service or console
    console.error('Application Error:', error, errorInfo);
    
    // You could send this to a logging service
    // logErrorToService({ error, errorInfo });
  };

  return (
    <ErrorBoundary 
      onError={handleAppError}
      fallback={
        <ErrorFallback 
          title="Application Error"
          message="The ThreatLens application encountered an unexpected error. Please reload the page or try again later."
          showDetails={process.env.NODE_ENV === 'development'}
        />
      }
    >
      <Router>
        <ErrorBoundary
          fallback={
            <ErrorFallback 
              title="Navigation Error"
              message="There was an error with the application navigation. Please try refreshing the page."
            />
          }
        >
          <Layout>
            <Routes>
              <Route 
                path="/" 
                element={
                  <ErrorBoundary
                    fallback={
                      <ErrorFallback 
                        title="Dashboard Error"
                        message="Unable to load the dashboard. Please check your connection and try again."
                      />
                    }
                  >
                    <Dashboard />
                  </ErrorBoundary>
                } 
              />
              <Route 
                path="/events" 
                element={
                  <ErrorBoundary
                    fallback={
                      <ErrorFallback 
                        title="Events Error"
                        message="Unable to load the events page. Please try again."
                      />
                    }
                  >
                    <Events />
                  </ErrorBoundary>
                } 
              />
              <Route 
                path="/reports" 
                element={
                  <ErrorBoundary
                    fallback={
                      <ErrorFallback 
                        title="Reports Error"
                        message="Unable to load the reports page. Please try again."
                      />
                    }
                  >
                    <Reports />
                  </ErrorBoundary>
                } 
              />
              <Route 
                path="/ingest" 
                element={
                  <ErrorBoundary
                    fallback={
                      <ErrorFallback 
                        title="Ingestion Error"
                        message="Unable to load the log ingestion page. Please try again."
                      />
                    }
                  >
                    <IngestLogs />
                  </ErrorBoundary>
                } 
              />
              <Route 
                path="/config" 
                element={
                  <ErrorBoundary
                    fallback={
                      <ErrorFallback 
                        title="Configuration Error"
                        message="Unable to load the configuration page. Please try again."
                      />
                    }
                  >
                    <Configuration />
                  </ErrorBoundary>
                } 
              />
            </Routes>
          </Layout>
        </ErrorBoundary>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
