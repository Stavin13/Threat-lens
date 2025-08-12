import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import SeverityChart from '../SeverityChart';
import { EventResponse } from '../../types';

// Mock Chart.js
jest.mock('react-chartjs-2', () => ({
  Bar: ({ data, options, ...props }: any) => {
    const handleClick = (severity: number) => {
      if (options?.onClick) {
        const mockEvent = {} as any;
        const mockElements = [{ index: severity - 1 }];
        options.onClick(mockEvent, mockElements);
      }
    };

    return (
      <div data-testid="bar-chart" {...props}>
        <div data-testid="chart-title">{options?.plugins?.title?.text}</div>
        {data?.labels?.map((label: string, index: number) => (
          <div
            key={label}
            data-testid={`bar-${label}`}
            data-value={data.datasets[0].data[index]}
            onClick={() => handleClick(parseInt(label))}
            style={{ cursor: options?.onClick ? 'pointer' : 'default' }}
          >
            Severity {label}: {data.datasets[0].data[index]} events
          </div>
        ))}
      </div>
    );
  },
}));

// Mock Chart.js registration
jest.mock('chart.js', () => ({
  Chart: {
    register: jest.fn(),
  },
  CategoryScale: {},
  LinearScale: {},
  BarElement: {},
  Title: {},
  Tooltip: {},
  Legend: {},
}));

describe('SeverityChart Integration Tests', () => {
  const createMockEvent = (id: string, severity: number, category: string = 'system'): EventResponse => ({
    event: {
      id,
      timestamp: new Date().toISOString(),
      source: 'test.log',
      message: `Test event ${id}`,
      category,
    },
    analysis: {
      severity_score: severity,
      explanation: `Test explanation for severity ${severity}`,
      recommendations: [`Test recommendation for event ${id}`],
    },
  });

  it('handles real-time event updates correctly', async () => {
    const initialEvents = [
      createMockEvent('1', 5),
      createMockEvent('2', 7),
    ];

    const { rerender } = render(<SeverityChart events={initialEvents} />);

    // Initial state: 2 events, average 6.0, 1 high severity
    expect(screen.getByText('Total Events').previousElementSibling).toHaveTextContent('2');
    expect(screen.getByText('6.0')).toBeInTheDocument();
    expect(screen.getByText('High Severity (6+)').previousElementSibling).toHaveTextContent('1');

    // Simulate new events arriving
    const updatedEvents = [
      ...initialEvents,
      createMockEvent('3', 9), // New critical event
      createMockEvent('4', 2), // New low severity event
    ];

    rerender(<SeverityChart events={updatedEvents} />);

    // Updated state: 4 events, average 5.75, 2 high severity
    await waitFor(() => {
      expect(screen.getByText('Total Events').previousElementSibling).toHaveTextContent('4');
      expect(screen.getByText('5.8')).toBeInTheDocument(); // (5+7+9+2)/4 = 5.75 rounded to 5.8
      expect(screen.getByText('High Severity (6+)').previousElementSibling).toHaveTextContent('2');
    });

    // Check individual severity bars
    expect(screen.getByTestId('bar-2')).toHaveAttribute('data-value', '1');
    expect(screen.getByTestId('bar-5')).toHaveAttribute('data-value', '1');
    expect(screen.getByTestId('bar-7')).toHaveAttribute('data-value', '1');
    expect(screen.getByTestId('bar-9')).toHaveAttribute('data-value', '1');
  });

  it('handles click-to-filter functionality', async () => {
    const events = [
      createMockEvent('1', 3),
      createMockEvent('2', 3),
      createMockEvent('3', 7),
      createMockEvent('4', 9),
    ];

    const mockOnSeverityClick = jest.fn();
    render(<SeverityChart events={events} onSeverityClick={mockOnSeverityClick} />);

    // Click on severity 3 bar (should have 2 events)
    const severity3Bar = screen.getByTestId('bar-3');
    expect(severity3Bar).toHaveAttribute('data-value', '2');
    
    fireEvent.click(severity3Bar);

    await waitFor(() => {
      expect(mockOnSeverityClick).toHaveBeenCalledWith(3);
    });

    // Click on severity 7 bar (should have 1 event)
    const severity7Bar = screen.getByTestId('bar-7');
    expect(severity7Bar).toHaveAttribute('data-value', '1');
    
    fireEvent.click(severity7Bar);

    await waitFor(() => {
      expect(mockOnSeverityClick).toHaveBeenCalledWith(7);
    });

    expect(mockOnSeverityClick).toHaveBeenCalledTimes(2);
  });

  it('handles large datasets efficiently', () => {
    // Create a large dataset with various severities
    const largeEventSet: EventResponse[] = [];
    for (let i = 1; i <= 1000; i++) {
      const severity = (i % 10) + 1; // Distribute across all severity levels
      largeEventSet.push(createMockEvent(i.toString(), severity));
    }

    const startTime = performance.now();
    render(<SeverityChart events={largeEventSet} />);
    const endTime = performance.now();

    // Should render within reasonable time (less than 100ms)
    expect(endTime - startTime).toBeLessThan(100);

    // Check that all severity levels have correct counts (100 each)
    for (let severity = 1; severity <= 10; severity++) {
      expect(screen.getByTestId(`bar-${severity}`)).toHaveAttribute('data-value', '100');
    }

    // Check statistics
    expect(screen.getByText('Total Events').previousElementSibling).toHaveTextContent('1000');
    expect(screen.getByText('5.5')).toBeInTheDocument(); // Average of 1-10
    expect(screen.getByText('High Severity (6+)').previousElementSibling).toHaveTextContent('500'); // Severities 6-10
  });

  it('handles mixed event categories correctly', () => {
    const mixedEvents = [
      createMockEvent('1', 8, 'authentication'),
      createMockEvent('2', 6, 'network'),
      createMockEvent('3', 4, 'system'),
      createMockEvent('4', 2, 'application'),
      createMockEvent('5', 9, 'security'),
    ];

    render(<SeverityChart events={mixedEvents} />);

    // Should aggregate all events regardless of category
    expect(screen.getByText('Total Events').previousElementSibling).toHaveTextContent('5');
    expect(screen.getByText('5.8')).toBeInTheDocument(); // (8+6+4+2+9)/5 = 5.8
    expect(screen.getByText('High Severity (6+)').previousElementSibling).toHaveTextContent('3'); // 8, 6, 9

    // Check individual bars
    expect(screen.getByTestId('bar-2')).toHaveAttribute('data-value', '1');
    expect(screen.getByTestId('bar-4')).toHaveAttribute('data-value', '1');
    expect(screen.getByTestId('bar-6')).toHaveAttribute('data-value', '1');
    expect(screen.getByTestId('bar-8')).toHaveAttribute('data-value', '1');
    expect(screen.getByTestId('bar-9')).toHaveAttribute('data-value', '1');
  });

  it('maintains performance with frequent updates', async () => {
    let events = [createMockEvent('1', 5)];
    const { rerender } = render(<SeverityChart events={events} />);

    // Simulate rapid updates (like real-time data)
    for (let i = 2; i <= 50; i++) {
      events = [...events, createMockEvent(i.toString(), (i % 10) + 1)];
      
      const startTime = performance.now();
      rerender(<SeverityChart events={events} />);
      const endTime = performance.now();

      // Each update should be fast
      expect(endTime - startTime).toBeLessThan(50);
    }

    // Final state should be correct
    expect(screen.getByText('Total Events').previousElementSibling).toHaveTextContent('50');
  });
});