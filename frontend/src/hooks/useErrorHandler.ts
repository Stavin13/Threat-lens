import { useState, useCallback, useEffect } from 'react';

export interface ErrorInfo {
  message: string;
  code?: string;
  details?: any;
  timestamp: Date;
  correlationId?: string;
}

export interface UseErrorHandlerReturn {
  error: ErrorInfo | null;
  isError: boolean;
  setError: (error: Error | string | ErrorInfo | null) => void;
  clearError: () => void;
  handleError: (error: any) => void;
  retryWithErrorHandling: <T>(fn: () => Promise<T>) => Promise<T | null>;
}

export const useErrorHandler = (): UseErrorHandlerReturn => {
  const [error, setErrorState] = useState<ErrorInfo | null>(null);

  const setError = useCallback((error: Error | string | ErrorInfo | null) => {
    if (!error) {
      setErrorState(null);
      return;
    }

    let errorInfo: ErrorInfo;

    if (typeof error === 'string') {
      errorInfo = {
        message: error,
        timestamp: new Date()
      };
    } else if (error instanceof Error) {
      errorInfo = {
        message: error.message,
        code: error.name,
        details: {
          stack: error.stack
        },
        timestamp: new Date()
      };
    } else {
      errorInfo = {
        ...error,
        timestamp: error.timestamp || new Date()
      };
    }

    setErrorState(errorInfo);

    // Log error to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('Error handled:', errorInfo);
    }

    // In production, you might want to send errors to a logging service
    if (process.env.NODE_ENV === 'production') {
      // Example: Send to logging service
      // logErrorToService(errorInfo);
    }
  }, []);

  const clearError = useCallback(() => {
    setErrorState(null);
  }, []);

  const handleError = useCallback((error: any) => {
    // Handle different types of errors
    if (error?.response) {
      // Axios error with response
      const status = error.response.status;
      const data = error.response.data;
      
      let message = 'An error occurred';
      let code = `HTTP_${status}`;
      let details = data;

      if (data?.message) {
        message = data.message;
      } else if (data?.error) {
        message = data.error;
      } else if (status === 404) {
        message = 'Resource not found';
      } else if (status === 401) {
        message = 'Unauthorized access';
      } else if (status === 403) {
        message = 'Access forbidden';
      } else if (status === 429) {
        message = 'Too many requests. Please try again later.';
      } else if (status >= 500) {
        message = 'Server error. Please try again later.';
      }

      setError({
        message,
        code,
        details,
        timestamp: new Date(),
        correlationId: data?.correlation_id
      });
    } else if (error?.request) {
      // Network error
      setError({
        message: 'Network error. Please check your connection and try again.',
        code: 'NETWORK_ERROR',
        details: { request: error.request },
        timestamp: new Date()
      });
    } else if (error instanceof Error) {
      // Regular JavaScript error
      setError(error);
    } else if (typeof error === 'string') {
      // String error
      setError(error);
    } else {
      // Unknown error type
      setError({
        message: 'An unknown error occurred',
        code: 'UNKNOWN_ERROR',
        details: error,
        timestamp: new Date()
      });
    }
  }, [setError]);

  const retryWithErrorHandling = useCallback(async <T>(
    fn: () => Promise<T>
  ): Promise<T | null> => {
    try {
      clearError();
      return await fn();
    } catch (error) {
      handleError(error);
      return null;
    }
  }, [clearError, handleError]);

  return {
    error,
    isError: error !== null,
    setError,
    clearError,
    handleError,
    retryWithErrorHandling
  };
};

// Hook for global error handling
export const useGlobalErrorHandler = () => {
  const errorHandler = useErrorHandler();

  // Set up global error listeners
  useEffect(() => {
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      console.error('Unhandled promise rejection:', event.reason);
      errorHandler.handleError(event.reason);
      event.preventDefault();
    };

    const handleError = (event: ErrorEvent) => {
      console.error('Global error:', event.error);
      errorHandler.handleError(event.error);
    };

    window.addEventListener('unhandledrejection', handleUnhandledRejection);
    window.addEventListener('error', handleError);

    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
      window.removeEventListener('error', handleError);
    };
  }, [errorHandler]);

  return errorHandler;
};

export default useErrorHandler;