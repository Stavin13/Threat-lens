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

describe('SeverityChart', () => {
  const mockEvents: EventResponse[] = [
    {
      event: {
        id: '1',
        timestamp: '2024-01-01T10:00:00Z',
        source: 'system.log',
        message: 'Failed login attempt',
        category: 'authentication',
      },
      analysis: {
        severity_score: 8,
        explanation: 'High severity authentication failure',
        recommendations: ['Monitor for brute force attacks'],
      },
    },
    {
      event: {
        id: '2',
        timestamp: '2024-01-01T10:05:00Z',
        source: 'auth.log',
        message: 'User logged in successfully',
        category: 'authentication',
      },
      analysis: {
        severity_score: 2,
        explanation: 'Normal login event',
        recommendations: ['No action required'],
      },
    },
    {
      event: {
        id: '3',
        timestamp: '2024-01-01T10:10:00Z',
        source: 'system.log',
        message: 'Critical system error',
        category: 'system',
      },
      analysis: {
        severity_score: 9,
        explanation: 'Critical system failure',
        recommendations: ['Immediate investigation required'],
      },
    },
    {
      event: {
        id: '4',
        timestamp: '2024-01-01T10:15:00Z',
        source: 'network.log',
        message: 'Network connection established',
        category: 'network',
      },
      analysis: {
        severity_score: 3,
        explanation: 'Normal network activity',
        recommendations: ['Monitor for unusual patterns'],
      },
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(<SeverityChart events={[]} />);
    expect(screen.getByText('Severity Distribution')).toBeInTheDocument();
  });

  it('displays chart title', () => {
    render(<SeverityChart events={mockEvents} />);
    expect(screen.getByTestId('chart-title')).toHaveTextContent('Event Severity Distribution');
  });

  it('displays summary statistics correctly', () => {
    render(<SeverityChart events={mockEvents} />);
    
    // Total events
    expect(screen.getByText('Total Events').previousElementSibling).toHaveTextContent('4');
    expect(screen.getByText('Total Events')).toBeInTheDocument();
    
    // Average severity (8+2+9+3)/4 = 5.5
    expect(screen.getByText('5.5')).toBeInTheDocument();
    expect(screen.getByText('Avg Severity')).toBeInTheDocument();
    
    // High severity count (severity >= 6): 2 events
    expect(screen.getByText('High Severity (6+)').previousElementSibling).toHaveTextContent('2');
    expect(screen.getByText('High Severity (6+)')).toBeInTheDocument();
  });

  it('displays all severity levels from 1-10', () => {
    render(<SeverityChart events={mockEvents} />);
    
    for (let i = 1; i <= 10; i++) {
      expect(screen.getByTestId(`bar-${i}`)).toBeInTheDocument();
    }
  });

  it('shows correct event counts for each severity level', () => {
    render(<SeverityChart events={mockEvents} />);
    
    // Severity 2: 1 event
    expect(screen.getByTestId('bar-2')).toHaveAttribute('data-value', '1');
    
    // Severity 3: 1 event
    expect(screen.getByTestId('bar-3')).toHaveAttribute('data-value', '1');
    
    // Severity 8: 1 event
    expect(screen.getByTestId('bar-8')).toHaveAttribute('data-value', '1');
    
    // Severity 9: 1 event
    expect(screen.getByTestId('bar-9')).toHaveAttribute('data-value', '1');
    
    // Other severities: 0 events
    expect(screen.getByTestId('bar-1')).toHaveAttribute('data-value', '0');
    expect(screen.getByTestId('bar-4')).toHaveAttribute('data-value', '0');
    expect(screen.getByTestId('bar-5')).toHaveAttribute('data-value', '0');
  });

  it('handles click events when onSeverityClick is provided', async () => {
    const mockOnSeverityClick = jest.fn();
    render(<SeverityChart events={mockEvents} onSeverityClick={mockOnSeverityClick} />);
    
    const severityBar = screen.getByTestId('bar-8');
    fireEvent.click(severityBar);
    
    await waitFor(() => {
      expect(mockOnSeverityClick).toHaveBeenCalledWith(8);
    });
  });

  it('displays click instruction when onSeverityClick is provided', () => {
    const mockOnSeverityClick = jest.fn();
    render(<SeverityChart events={mockEvents} onSeverityClick={mockOnSeverityClick} />);
    
    expect(screen.getByText('Click bars to filter by severity')).toBeInTheDocument();
  });

  it('does not display click instruction when onSeverityClick is not provided', () => {
    render(<SeverityChart events={mockEvents} />);
    
    expect(screen.queryByText('Click bars to filter by severity')).not.toBeInTheDocument();
  });

  it('displays empty state when no events are provided', () => {
    render(<SeverityChart events={[]} />);
    
    expect(screen.getByText('No events to display')).toBeInTheDocument();
    expect(screen.getByText('Upload logs to see severity distribution')).toBeInTheDocument();
    expect(screen.getByText('📊')).toBeInTheDocument();
  });

  it('displays severity legend', () => {
    render(<SeverityChart events={mockEvents} />);
    
    expect(screen.getByText('1-2: Very Low')).toBeInTheDocument();
    expect(screen.getByText('3-4: Low')).toBeInTheDocument();
    expect(screen.getByText('5-6: Medium')).toBeInTheDocument();
    expect(screen.getByText('7-8: High')).toBeInTheDocument();
    expect(screen.getByText('9-10: Critical')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <SeverityChart events={mockEvents} className="custom-class" />
    );
    
    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('calculates statistics correctly with single event', () => {
    const singleEvent = [mockEvents[0]]; // Severity 8
    render(<SeverityChart events={singleEvent} />);
    
    // Check for specific statistics in their context
    expect(screen.getByText('Total Events').previousElementSibling).toHaveTextContent('1');
    expect(screen.getByText('8.0')).toBeInTheDocument(); // Average severity
    expect(screen.getByText('High Severity (6+)').previousElementSibling).toHaveTextContent('1');
  });

  it('handles events with edge case severity values', () => {
    const edgeCaseEvents: EventResponse[] = [
      {
        ...mockEvents[0],
        analysis: { ...mockEvents[0].analysis, severity_score: 1 },
      },
      {
        ...mockEvents[1],
        analysis: { ...mockEvents[1].analysis, severity_score: 10 },
      },
    ];
    
    render(<SeverityChart events={edgeCaseEvents} />);
    
    expect(screen.getByTestId('bar-1')).toHaveAttribute('data-value', '1');
    expect(screen.getByTestId('bar-10')).toHaveAttribute('data-value', '1');
    
    // Average: (1+10)/2 = 5.5
    expect(screen.getByText('5.5')).toBeInTheDocument();
    
    // High severity count (>=6): 1 event
    expect(screen.getByText('High Severity (6+)').previousElementSibling).toHaveTextContent('1');
  });

  it('updates when events prop changes', () => {
    const { rerender } = render(<SeverityChart events={mockEvents} />);
    
    // Initial state
    expect(screen.getByText('Total Events').previousElementSibling).toHaveTextContent('4');
    
    // Update with fewer events
    const fewerEvents = mockEvents.slice(0, 2);
    rerender(<SeverityChart events={fewerEvents} />);
    
    expect(screen.getByText('Total Events').previousElementSibling).toHaveTextContent('2');
  });

  it('maintains chart responsiveness', () => {
    render(<SeverityChart events={mockEvents} height={400} />);
    
    const chartContainer = screen.getByTestId('bar-chart').parentElement;
    expect(chartContainer).toHaveStyle('height: 400px');
  });
});