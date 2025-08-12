# Requirements Document

## Introduction

ThreatLens is an AI-powered security log analyzer that transforms raw security logs into actionable intelligence. The system ingests security logs, parses them into structured events, applies AI-based severity scoring and explanations, and generates both a web dashboard and automated daily PDF reports. This solution bridges the gap between raw log data and meaningful security insights by leveraging AI to provide context, severity assessment, and recommendations for security events.

## Requirements

### Requirement 1

**User Story:** As a security analyst, I want to upload raw log files or text through an API, so that I can process security logs from various sources into the system.

#### Acceptance Criteria

1. WHEN a user sends a POST request to /ingest-log with a log file THEN the system SHALL accept and store the raw log data
2. WHEN a user sends a POST request to /ingest-log with log text THEN the system SHALL accept and store the raw log text
3. WHEN log ingestion is successful THEN the system SHALL return a confirmation response with ingestion ID
4. WHEN log ingestion fails THEN the system SHALL return an appropriate error message
5. WHEN a new log is ingested THEN the system SHALL automatically trigger parsing and AI analysis

### Requirement 2

**User Story:** As a security analyst, I want to retrieve parsed security events with filtering capabilities, so that I can review and analyze security incidents efficiently.

#### Acceptance Criteria

1. WHEN a user sends a GET request to /events THEN the system SHALL return a list of parsed security events
2. WHEN a user applies filters to /events THEN the system SHALL return events matching the filter criteria
3. WHEN a user requests a specific event via GET /event/{id} THEN the system SHALL return detailed analysis including AI-generated severity score and explanation
4. WHEN an event ID doesn't exist THEN the system SHALL return a 404 error
5. WHEN events are returned THEN each event SHALL include timestamp, source, message, severity score, and AI explanation

### Requirement 3

**User Story:** As a security analyst, I want the system to automatically parse raw logs into structured events, so that I can work with organized security data instead of raw text.

#### Acceptance Criteria

1. WHEN raw log data is processed THEN the system SHALL extract timestamp, source, and message components using regex parsing
2. WHEN log parsing occurs THEN the system SHALL categorize events by type (authentication, network, system, etc.)
3. WHEN parsing fails for a log entry THEN the system SHALL log the error and continue processing remaining entries
4. WHEN events are parsed THEN the system SHALL store them in SQLite database with structured fields
5. WHEN parsing is complete THEN the system SHALL trigger AI analysis for severity scoring

### Requirement 4

**User Story:** As a security analyst, I want AI-powered analysis of security events, so that I can understand the severity and implications of each security incident.

#### Acceptance Criteria

1. WHEN a parsed event is analyzed THEN the system SHALL generate a severity score from 1-10 using Claude AI
2. WHEN AI analysis occurs THEN the system SHALL provide a human-readable explanation of the security event
3. WHEN AI analysis occurs THEN the system SHALL generate actionable recommendations for the security event
4. WHEN AI analysis fails THEN the system SHALL assign a default severity score and log the error
5. WHEN analysis is complete THEN the system SHALL store the AI-generated insights with the event record

### Requirement 5

**User Story:** As a security manager, I want automated daily PDF reports of security events, so that I can review security posture and share reports with stakeholders.

#### Acceptance Criteria

1. WHEN a user requests GET /report/daily THEN the system SHALL generate a PDF report for the current day's events
2. WHEN the daily report is generated THEN it SHALL include event summaries, severity distributions, and key insights
3. WHEN it's midnight THEN the system SHALL automatically generate and save a daily PDF report to /data/reports
4. WHEN automatic report generation occurs THEN the system SHALL include events from the previous 24-hour period
5. WHEN report generation fails THEN the system SHALL log the error and retry once

### Requirement 6

**User Story:** As a security analyst, I want a web dashboard to visualize security events, so that I can quickly assess the current security status and investigate incidents.

#### Acceptance Criteria

1. WHEN a user accesses the dashboard THEN the system SHALL display a table of security events with filtering capabilities
2. WHEN the dashboard loads THEN it SHALL show a severity bar chart visualizing the distribution of event severities
3. WHEN a user clicks on an event in the table THEN the system SHALL display detailed AI analysis in a modal or detail view
4. WHEN dashboard data is displayed THEN it SHALL be updated in real-time or near real-time
5. WHEN no events exist THEN the dashboard SHALL display an appropriate empty state message

### Requirement 7

**User Story:** As a system administrator, I want automated processing hooks, so that the system can operate autonomously without manual intervention.

#### Acceptance Criteria

1. WHEN a new log is ingested THEN the system SHALL automatically trigger parsing and AI analysis without manual intervention
2. WHEN parsing completes THEN the system SHALL automatically trigger AI analysis for all new events
3. WHEN it's midnight THEN the system SHALL automatically generate and save a daily PDF report
4. WHEN automatic processes fail THEN the system SHALL log errors and attempt recovery where possible
5. WHEN hooks execute THEN the system SHALL maintain audit logs of all automated actions

### Requirement 8

**User Story:** As a security analyst, I want to see the difference between raw logs and ThreatLens analyzed output, so that I can understand the value added by the AI analysis.

#### Acceptance Criteria

1. WHEN demonstrating the system THEN it SHALL process sample logs from macOS system.log and auth.log
2. WHEN displaying results THEN the system SHALL show both raw log entries and their corresponding analyzed versions
3. WHEN comparing views THEN users SHALL be able to see the original message alongside AI-generated severity and explanation
4. WHEN demo data is processed THEN it SHALL showcase various types of security events and their AI analysis
5. WHEN the demo runs THEN it SHALL demonstrate the complete workflow from ingestion to reporting