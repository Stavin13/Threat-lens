import React, { useEffect, useRef } from 'react';
import { EventResponse } from '../types';

interface EventDetailProps {
  event: EventResponse | null;
  isOpen: boolean;
  onClose: () => void;
}

const EventDetail: React.FC<EventDetailProps> = ({ event, isOpen, onClose }) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      if (e.key === 'Escape') {
        onClose();
      }

      // Trap focus within modal
      if (e.key === 'Tab') {
        const modal = modalRef.current;
        if (!modal) return;

        const focusableElements = modal.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const firstElement = focusableElements[0] as HTMLElement;
        const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement;

        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      // Focus the close button when modal opens
      setTimeout(() => closeButtonRef.current?.focus(), 100);
      // Prevent body scroll
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  // Handle backdrop click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  // Get severity color and description
  const getSeverityInfo = (severity: number) => {
    if (severity >= 9) {
      return {
        color: 'bg-red-500',
        bgColor: 'bg-red-50',
        textColor: 'text-red-800',
        borderColor: 'border-red-200',
        description: 'Critical',
        icon: '🚨'
      };
    } else if (severity >= 7) {
      return {
        color: 'bg-red-400',
        bgColor: 'bg-red-50',
        textColor: 'text-red-700',
        borderColor: 'border-red-200',
        description: 'High',
        icon: '⚠️'
      };
    } else if (severity >= 5) {
      return {
        color: 'bg-orange-400',
        bgColor: 'bg-orange-50',
        textColor: 'text-orange-700',
        borderColor: 'border-orange-200',
        description: 'Medium',
        icon: '⚡'
      };
    } else if (severity >= 3) {
      return {
        color: 'bg-yellow-400',
        bgColor: 'bg-yellow-50',
        textColor: 'text-yellow-700',
        borderColor: 'border-yellow-200',
        description: 'Low',
        icon: '💡'
      };
    } else {
      return {
        color: 'bg-green-400',
        bgColor: 'bg-green-50',
        textColor: 'text-green-700',
        borderColor: 'border-green-200',
        description: 'Info',
        icon: 'ℹ️'
      };
    }
  };

  // Format timestamp
  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return {
      date: date.toLocaleDateString(),
      time: date.toLocaleTimeString(),
      iso: date.toISOString()
    };
  };

  if (!isOpen || !event) {
    return null;
  }

  const severityInfo = getSeverityInfo(event.analysis.severity_score);
  const formattedTime = formatTimestamp(event.event.timestamp);

  return (
    <div
      className="fixed inset-0 z-50 overflow-y-auto"
      aria-labelledby="modal-title"
      role="dialog"
      aria-modal="true"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
        onClick={handleBackdropClick}
      ></div>

      {/* Modal */}
      <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
        <div
          ref={modalRef}
          className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-4xl"
        >
          {/* Header */}
          <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center">
                <div className={`flex h-12 w-12 items-center justify-center rounded-full ${severityInfo.bgColor}`}>
                  <span className="text-2xl" role="img" aria-label={severityInfo.description}>
                    {severityInfo.icon}
                  </span>
                </div>
                <div className="ml-4">
                  <h3 className="text-lg font-medium leading-6 text-gray-900" id="modal-title">
                    Security Event Details
                  </h3>
                  <p className="text-sm text-gray-500">
                    Event ID: {event.event.id}
                  </p>
                </div>
              </div>
              <button
                ref={closeButtonRef}
                type="button"
                className="rounded-md bg-white text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                onClick={onClose}
                aria-label="Close modal"
              >
                <span className="sr-only">Close</span>
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="px-4 pb-4 sm:px-6 sm:pb-6">
            <div className="space-y-6">
              {/* Severity Score Section */}
              <div className={`rounded-lg border ${severityInfo.borderColor} ${severityInfo.bgColor} p-4`}>
                <div className="flex items-center justify-between mb-3">
                  <h4 className={`text-lg font-semibold ${severityInfo.textColor}`}>
                    Severity Assessment
                  </h4>
                  <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${severityInfo.textColor} ${severityInfo.bgColor} border ${severityInfo.borderColor}`}>
                    {event.analysis.severity_score}/10 - {severityInfo.description}
                  </span>
                </div>
                
                {/* Progress Bar */}
                <div className="w-full bg-gray-200 rounded-full h-3 mb-2">
                  <div
                    className={`h-3 rounded-full transition-all duration-300 ${severityInfo.color}`}
                    style={{ width: `${(event.analysis.severity_score / 10) * 100}%` }}
                    role="progressbar"
                    aria-valuenow={event.analysis.severity_score}
                    aria-valuemin={1}
                    aria-valuemax={10}
                    aria-label={`Severity score: ${event.analysis.severity_score} out of 10`}
                  ></div>
                </div>
                <p className="text-sm text-gray-600">
                  Severity scale: 1-3 (Info), 4-5 (Low), 6-7 (Medium), 8-9 (High), 10 (Critical)
                </p>
              </div>

              {/* Event Information */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium text-gray-900 mb-2">Event Details</h4>
                    <div className="bg-gray-50 rounded-lg p-3 space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm font-medium text-gray-500">Timestamp:</span>
                        <div className="text-right">
                          <div className="text-sm text-gray-900">{formattedTime.date}</div>
                          <div className="text-sm text-gray-900">{formattedTime.time}</div>
                        </div>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm font-medium text-gray-500">Source:</span>
                        <span className="text-sm text-gray-900">{event.event.source}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm font-medium text-gray-500">Category:</span>
                        <span className="inline-flex px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                          {event.event.category}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium text-gray-900 mb-2">Analysis Summary</h4>
                    <div className="bg-gray-50 rounded-lg p-3">
                      <p className="text-sm text-gray-700 leading-relaxed">
                        {event.analysis.explanation}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Raw Log Message */}
              <div>
                <h4 className="text-sm font-medium text-gray-900 mb-2">Raw Log Message</h4>
                <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
                  <pre className="text-sm text-green-400 font-mono whitespace-pre-wrap">
                    {event.event.message}
                  </pre>
                </div>
              </div>

              {/* AI Explanation */}
              <div>
                <h4 className="text-sm font-medium text-gray-900 mb-2">AI Analysis</h4>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start">
                    <div className="flex-shrink-0">
                      <span className="text-2xl" role="img" aria-label="AI Analysis">🤖</span>
                    </div>
                    <div className="ml-3">
                      <p className="text-sm text-blue-800 leading-relaxed">
                        {event.analysis.explanation}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recommendations */}
              {event.analysis.recommendations && event.analysis.recommendations.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-900 mb-2">Recommendations</h4>
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                    <ul className="space-y-2">
                      {event.analysis.recommendations.map((recommendation, index) => (
                        <li key={index} className="flex items-start">
                          <span className="flex-shrink-0 w-5 h-5 text-amber-600 mr-2">
                            <svg fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                          </span>
                          <span className="text-sm text-amber-800">{recommendation}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6">
            <button
              type="button"
              className="inline-flex w-full justify-center rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 sm:ml-3 sm:w-auto"
              onClick={onClose}
            >
              Close
            </button>
            <button
              type="button"
              className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 sm:mt-0 sm:w-auto"
              onClick={() => {
                // Copy event details to clipboard
                const eventDetails = `Event ID: ${event.event.id}
Timestamp: ${formattedTime.date} ${formattedTime.time}
Source: ${event.event.source}
Category: ${event.event.category}
Severity: ${event.analysis.severity_score}/10 (${severityInfo.description})
Message: ${event.event.message}
Analysis: ${event.analysis.explanation}
Recommendations: ${event.analysis.recommendations.join(', ')}`;
                
                if (navigator.clipboard && navigator.clipboard.writeText) {
                  navigator.clipboard.writeText(eventDetails).then(() => {
                    // Could add a toast notification here
                    console.log('Event details copied to clipboard');
                  }).catch((err) => {
                    console.error('Failed to copy to clipboard:', err);
                  });
                } else {
                  console.log('Clipboard API not available');
                }
              }}
            >
              Copy Details
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EventDetail;