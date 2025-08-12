import { renderHook, act } from '@testing-library/react';
import useErrorHandler from '../useErrorHandler';

// Mock console.error to avoid noise in tests
const originalError = console.error;
beforeAll(() => {
  console.error = jest.fn();
});

afterAll(() => {
  console.error = originalError;
});

describe('useErrorHandler', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('initializes with no error', () => {
    const { result } = renderHook(() => useErrorHandler());

    expect(result.current.error).toBeNull();
    expect(result.current.isError).toBe(false);
  });

  it('sets error from string', () => {
    const { result } = renderHook(() => useErrorHandler());

    act(() => {
      result.current.setError('Test error message');
    });

    expect(result.current.error).toEqual({
      message: 'Test error message',
      timestamp: expect.any(Date)
    });
    expect(result.current.isError).toBe(true);
  });

  it('sets error from Error object', () => {
    const { result } = renderHook(() => useErrorHandler());
    const testError = new Error('Test error');

    act(() => {
      result.current.setError(testError);
    });

    expect(result.current.error).toEqual({
      message: 'Test error',
      code: 'Error',
      details: {
        stack: expect.any(String)
      },
      timestamp: expect.any(Date)
    });
    expect(result.current.isError).toBe(true);
  });

  it('sets error from ErrorInfo object', () => {
    const { result } = renderHook(() => useErrorHandler());
    const errorInfo = {
      message: 'Custom error',
      code: 'CUSTOM_ERROR',
      details: { context: 'test' },
      timestamp: new Date(),
      correlationId: 'test-id'
    };

    act(() => {
      result.current.setError(errorInfo);
    });

    expect(result.current.error).toEqual(errorInfo);
    expect(result.current.isError).toBe(true);
  });

  it('clears error', () => {
    const { result } = renderHook(() => useErrorHandler());

    act(() => {
      result.current.setError('Test error');
    });

    expect(result.current.isError).toBe(true);

    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
    expect(result.current.isError).toBe(false);
  });

  it('handles axios error with response', () => {
    const { result } = renderHook(() => useErrorHandler());
    const axiosError = {
      response: {
        status: 400,
        data: {
          message: 'Bad request',
          correlation_id: 'test-correlation-id'
        }
      }
    };

    act(() => {
      result.current.handleError(axiosError);
    });

    expect(result.current.error).toEqual({
      message: 'Bad request',
      code: 'HTTP_400',
      details: axiosError.response.data,
      timestamp: expect.any(Date),
      correlationId: 'test-correlation-id'
    });
  });

  it('handles axios error with different status codes', () => {
    const { result } = renderHook(() => useErrorHandler());

    // Test 404 error
    act(() => {
      result.current.handleError({
        response: { status: 404, data: {} }
      });
    });

    expect(result.current.error?.message).toBe('Resource not found');

    // Test 401 error
    act(() => {
      result.current.handleError({
        response: { status: 401, data: {} }
      });
    });

    expect(result.current.error?.message).toBe('Unauthorized access');

    // Test 500 error
    act(() => {
      result.current.handleError({
        response: { status: 500, data: {} }
      });
    });

    expect(result.current.error?.message).toBe('Server error. Please try again later.');
  });

  it('handles network error', () => {
    const { result } = renderHook(() => useErrorHandler());
    const networkError = {
      request: { url: 'http://example.com' }
    };

    act(() => {
      result.current.handleError(networkError);
    });

    expect(result.current.error).toEqual({
      message: 'Network error. Please check your connection and try again.',
      code: 'NETWORK_ERROR',
      details: { request: networkError.request },
      timestamp: expect.any(Date)
    });
  });

  it('handles unknown error type', () => {
    const { result } = renderHook(() => useErrorHandler());
    const unknownError = { weird: 'error' };

    act(() => {
      result.current.handleError(unknownError);
    });

    expect(result.current.error).toEqual({
      message: 'An unknown error occurred',
      code: 'UNKNOWN_ERROR',
      details: unknownError,
      timestamp: expect.any(Date)
    });
  });

  it('retries with error handling - success case', async () => {
    const { result } = renderHook(() => useErrorHandler());
    const mockFn = jest.fn().mockResolvedValue('success');

    const returnValue = await act(async () => {
      return result.current.retryWithErrorHandling(mockFn);
    });

    expect(returnValue).toBe('success');
    expect(result.current.isError).toBe(false);
    expect(mockFn).toHaveBeenCalledTimes(1);
  });

  it('retries with error handling - error case', async () => {
    const { result } = renderHook(() => useErrorHandler());
    const mockFn = jest.fn().mockRejectedValue(new Error('Test error'));

    const returnValue = await act(async () => {
      return result.current.retryWithErrorHandling(mockFn);
    });

    expect(returnValue).toBeNull();
    expect(result.current.isError).toBe(true);
    expect(result.current.error?.message).toBe('Test error');
    expect(mockFn).toHaveBeenCalledTimes(1);
  });

  it('clears error before retry', async () => {
    const { result } = renderHook(() => useErrorHandler());

    // Set initial error
    act(() => {
      result.current.setError('Initial error');
    });

    expect(result.current.isError).toBe(true);

    // Retry with successful function
    const mockFn = jest.fn().mockResolvedValue('success');

    await act(async () => {
      return result.current.retryWithErrorHandling(mockFn);
    });

    expect(result.current.isError).toBe(false);
  });

  it('logs errors in development mode', () => {
    const originalEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'development';

    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
    const { result } = renderHook(() => useErrorHandler());

    act(() => {
      result.current.setError('Test error');
    });

    expect(consoleSpy).toHaveBeenCalledWith(
      'Error handled:',
      expect.objectContaining({
        message: 'Test error'
      })
    );

    consoleSpy.mockRestore();
    process.env.NODE_ENV = originalEnv;
  });

  it('handles rate limit errors with retry after', () => {
    const { result } = renderHook(() => useErrorHandler());
    const rateLimitError = {
      response: {
        status: 429,
        data: {} // No specific message, should use default
      }
    };

    act(() => {
      result.current.handleError(rateLimitError);
    });

    expect(result.current.error?.message).toBe('Too many requests. Please try again later.');
    expect(result.current.error?.code).toBe('HTTP_429');
  });

  it('preserves correlation ID from error response', () => {
    const { result } = renderHook(() => useErrorHandler());
    const errorWithCorrelation = {
      response: {
        status: 500,
        data: {
          message: 'Server error',
          correlation_id: 'abc-123-def'
        }
      }
    };

    act(() => {
      result.current.handleError(errorWithCorrelation);
    });

    expect(result.current.error?.correlationId).toBe('abc-123-def');
  });
});