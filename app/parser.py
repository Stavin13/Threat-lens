"""
Log parsing engine for ThreatLens.

This module provides functionality to parse raw security logs into structured events,
with support for macOS system.log and auth.log formats. It includes regex patterns
for extracting timestamp, source, and message components, along with event
categorization logic.
"""
import re
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import logging

from app.schemas import ParsedEvent, EventCategory

# Configure logging
logger = logging.getLogger(__name__)


class LogFormat(Enum):
    """Supported log formats."""
    MACOS_SYSTEM = "macos_system"
    MACOS_AUTH = "macos_auth"
    GENERIC_SYSLOG = "generic_syslog"
    UNKNOWN = "unknown"


class ParsingError(Exception):
    """Custom exception for parsing errors."""
    pass


class LogParser:
    """Main log parsing class with regex patterns and categorization logic."""
    
    # Regex patterns for different log formats
    PATTERNS = {
        # macOS system.log format: "Jan 15 10:30:45 hostname process[pid]: message"
        LogFormat.MACOS_SYSTEM: re.compile(
            r'(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+([^:]+?)(?:\[(\d+)\])?\s*:\s*(.+)'
        ),
        
        # macOS auth.log format: "Jan 15 10:30:45 hostname process[pid]: message"
        LogFormat.MACOS_AUTH: re.compile(
            r'(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(\w+)(?:\[(\d+)\])?\s*:\s*(.+)'
        ),
        
        # Generic syslog format
        LogFormat.GENERIC_SYSLOG: re.compile(
            r'(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(.+)'
        )
    }
    
    # Month name to number mapping for timestamp parsing
    MONTH_MAP = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    
    # Keywords for event categorization
    CATEGORY_KEYWORDS = {
        EventCategory.AUTH: [
            'login', 'logout', 'authentication', 'password', 'sudo', 'su',
            'ssh', 'failed', 'success', 'user', 'session', 'pam', 'auth',
            'credential', 'token', 'certificate', 'kerberos', 'ldap'
        ],
        EventCategory.KERNEL: [
            'kernel', 'panic', 'oops', 'segfault', 'core', 'dump',
            'interrupt', 'irq', 'dma', 'pci', 'usb', 'acpi'
        ],
        EventCategory.SYSTEM: [
            'boot', 'shutdown', 'restart', 'mount', 'unmount',
            'disk', 'memory', 'cpu', 'process', 'service', 'daemon',
            'system', 'hardware', 'driver', 'module', 'loginwindow',
            'started', 'application'
        ],
        EventCategory.NETWORK: [
            'network', 'tcp', 'udp', 'ip', 'dns', 'dhcp', 'firewall',
            'connection', 'socket', 'port', 'interface', 'ethernet',
            'wifi', 'vpn', 'proxy', 'routing', 'packet'
        ],
        EventCategory.SECURITY: [
            'security', 'threat', 'malware', 'virus', 'attack', 'intrusion',
            'breach', 'vulnerability', 'exploit', 'suspicious', 'blocked',
            'denied', 'quarantine', 'alert', 'warning', 'violation'
        ],
        EventCategory.APPLICATION: [
            'application', 'app', 'software', 'program', 'crash', 'error',
            'exception', 'debug', 'info', 'warning', 'fatal', 'trace'
        ]
    }
    
    def __init__(self):
        """Initialize the log parser."""
        self.stats = {
            'total_lines': 0,
            'parsed_events': 0,
            'failed_lines': 0,
            'categories': {category.value: 0 for category in EventCategory}
        }
    
    def parse_log_entries(self, raw_log: str, raw_log_id: str) -> List[ParsedEvent]:
        """
        Parse raw log content into structured events.
        
        Args:
            raw_log: Raw log content as string
            raw_log_id: ID of the raw log entry
            
        Returns:
            List of ParsedEvent objects
            
        Raises:
            ParsingError: If parsing fails completely
        """
        if not raw_log or not raw_log.strip():
            raise ParsingError("Empty log content provided")
        
        # Reset stats for this parsing session
        self.stats = {
            'total_lines': 0,
            'parsed_events': 0,
            'failed_lines': 0,
            'categories': {category.value: 0 for category in EventCategory}
        }
        
        events = []
        lines = raw_log.strip().split('\n')
        self.stats['total_lines'] = len(lines)
        
        logger.info(f"Starting to parse {len(lines)} log lines")
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            try:
                event = self._parse_single_line(line, raw_log_id)
                if event:
                    events.append(event)
                    self.stats['parsed_events'] += 1
                    self.stats['categories'][event.category.value] += 1
                else:
                    self.stats['failed_lines'] += 1
                    logger.warning(f"Failed to parse line {line_num}: {line[:100]}...")
                    
            except Exception as e:
                self.stats['failed_lines'] += 1
                logger.error(f"Error parsing line {line_num}: {str(e)}")
                continue
        
        logger.info(f"Parsing complete. Events: {self.stats['parsed_events']}, "
                   f"Failed: {self.stats['failed_lines']}")
        
        if not events and self.stats['total_lines'] > 0:
            raise ParsingError("No events could be parsed from the log content")
        
        return events
    
    def _parse_single_line(self, line: str, raw_log_id: str) -> Optional[ParsedEvent]:
        """
        Parse a single log line into a ParsedEvent.
        
        Args:
            line: Single log line to parse
            raw_log_id: ID of the raw log entry
            
        Returns:
            ParsedEvent object or None if parsing fails
        """
        # Try each pattern until one matches
        for log_format, pattern in self.PATTERNS.items():
            match = pattern.match(line)
            if match:
                try:
                    return self._create_event_from_match(
                        match, log_format, line, raw_log_id
                    )
                except Exception as e:
                    logger.debug(f"Failed to create event from match: {str(e)}")
                    continue
        
        # If no pattern matches, try to extract basic information
        return self._parse_generic_line(line, raw_log_id)
    
    def _create_event_from_match(
        self, 
        match: re.Match, 
        log_format: LogFormat, 
        original_line: str,
        raw_log_id: str
    ) -> ParsedEvent:
        """
        Create a ParsedEvent from a regex match.
        
        Args:
            match: Regex match object
            log_format: Detected log format
            original_line: Original log line
            raw_log_id: ID of the raw log entry
            
        Returns:
            ParsedEvent object
        """
        groups = match.groups()
        
        if log_format in [LogFormat.MACOS_SYSTEM, LogFormat.MACOS_AUTH]:
            timestamp_str = groups[0]
            hostname = groups[1]
            process = groups[2]
            pid = groups[3] if len(groups) > 3 and groups[3] else None
            message = groups[4] if len(groups) > 4 else groups[-1]
            
            # Create source identifier
            source = f"{hostname}:{process}"
            if pid:
                source += f"[{pid}]"
                
        elif log_format == LogFormat.GENERIC_SYSLOG:
            timestamp_str = groups[0]
            hostname = groups[1]
            message = groups[2]
            source = hostname
            
        else:
            raise ParsingError(f"Unsupported log format: {log_format}")
        
        # Parse timestamp
        timestamp = self._parse_timestamp(timestamp_str)
        
        # Categorize the event
        category = self._categorize_event(message, source)
        
        # Create the event
        event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=raw_log_id,
            timestamp=timestamp,
            source=source,
            message=message.strip(),
            category=category,
            parsed_at=datetime.now(timezone.utc)
        )
        
        return event
    
    def _parse_generic_line(self, line: str, raw_log_id: str) -> Optional[ParsedEvent]:
        """
        Attempt to parse a line that doesn't match known patterns.
        
        Args:
            line: Log line to parse
            raw_log_id: ID of the raw log entry
            
        Returns:
            ParsedEvent object or None
        """
        # Try to extract any timestamp-like pattern
        timestamp_patterns = [
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',  # ISO format
            r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})',  # US format
            r'(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})',    # Syslog format
        ]
        
        timestamp = None
        remaining_content = line
        
        for pattern in timestamp_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    timestamp = self._parse_timestamp(match.group(1))
                    remaining_content = line[match.end():].strip()
                    break
                except:
                    continue
        
        # If no timestamp found, use current time
        if not timestamp:
            timestamp = datetime.now(timezone.utc)
            remaining_content = line
        
        # Use the entire line as message if no better parsing available
        if not remaining_content:
            remaining_content = line
        
        # Try to extract source from the beginning of the remaining content
        # First try colon-separated format
        colon_match = re.match(r'^(\S+):\s*(.+)', remaining_content)
        if colon_match:
            source = colon_match.group(1)
            message = colon_match.group(2)
        else:
            # Try space-separated format
            space_match = re.match(r'^(\S+)\s+(.+)', remaining_content)
            if space_match:
                source = space_match.group(1)
                message = space_match.group(2)
            else:
                source = "unknown"
                message = remaining_content
        
        # Categorize the event
        category = self._categorize_event(message, source)
        
        return ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=raw_log_id,
            timestamp=timestamp,
            source=source,
            message=message.strip(),
            category=category,
            parsed_at=datetime.now(timezone.utc)
        )
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """
        Parse timestamp string into datetime object.
        
        Args:
            timestamp_str: Timestamp string to parse
            
        Returns:
            datetime object
            
        Raises:
            ParsingError: If timestamp cannot be parsed
        """
        timestamp_str = timestamp_str.strip()
        
        # Handle syslog format: "Jan 15 10:30:45"
        syslog_match = re.match(r'(\w{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})', timestamp_str)
        if syslog_match:
            month_str, day_str, hour_str, minute_str, second_str = syslog_match.groups()
            
            if month_str not in self.MONTH_MAP:
                raise ParsingError(f"Unknown month: {month_str}")
            
            month = self.MONTH_MAP[month_str]
            day = int(day_str)
            hour = int(hour_str)
            minute = int(minute_str)
            second = int(second_str)
            
            # Use current year (syslog doesn't include year)
            year = datetime.now().year
            
            try:
                return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
            except ValueError as e:
                raise ParsingError(f"Invalid timestamp values: {str(e)}")
        
        # Handle ISO format: "2024-01-15 10:30:45"
        iso_match = re.match(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})', timestamp_str)
        if iso_match:
            year, month, day, hour, minute, second = map(int, iso_match.groups())
            try:
                return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
            except ValueError as e:
                raise ParsingError(f"Invalid ISO timestamp: {str(e)}")
        
        # Handle US format: "01/15/2024 10:30:45"
        us_match = re.match(r'(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2}):(\d{2})', timestamp_str)
        if us_match:
            month, day, year, hour, minute, second = map(int, us_match.groups())
            try:
                return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
            except ValueError as e:
                raise ParsingError(f"Invalid US timestamp: {str(e)}")
        
        raise ParsingError(f"Unable to parse timestamp: {timestamp_str}")
    
    def _categorize_event(self, message: str, source: str) -> EventCategory:
        """
        Categorize an event based on message content and source.
        
        Args:
            message: Event message
            source: Event source
            
        Returns:
            EventCategory enum value
        """
        message_lower = message.lower()
        source_lower = source.lower()
        combined_text = f"{message_lower} {source_lower}"
        
        # Score each category based on keyword matches
        category_scores = {}
        
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                # Count occurrences of each keyword
                score += combined_text.count(keyword)
                
                # Give extra weight to exact word matches
                if re.search(r'\b' + re.escape(keyword) + r'\b', combined_text):
                    score += 2
                
                # Give extra weight to source matches (more reliable)
                if keyword in source_lower:
                    score += 3
            
            category_scores[category] = score
        
        # Special handling for kernel events - check source first, but only if it's actually kernel
        if 'kernel' in source_lower and '[0]' in source_lower:
            return EventCategory.KERNEL
        
        # Return the category with the highest score
        if category_scores:
            best_category = max(category_scores.items(), key=lambda x: x[1])
            if best_category[1] > 0:
                return best_category[0]
        
        # Default to UNKNOWN if no keywords match
        return EventCategory.UNKNOWN
    
    def get_parsing_stats(self) -> Dict[str, Any]:
        """
        Get statistics from the last parsing operation.
        
        Returns:
            Dictionary containing parsing statistics
        """
        return self.stats.copy()


# Convenience functions for external use
def parse_log_entries(raw_log: str, raw_log_id: str) -> List[ParsedEvent]:
    """
    Parse raw log content into structured events.
    
    Args:
        raw_log: Raw log content as string
        raw_log_id: ID of the raw log entry
        
    Returns:
        List of ParsedEvent objects
    """
    parser = LogParser()
    return parser.parse_log_entries(raw_log, raw_log_id)


def extract_timestamp(log_line: str) -> Optional[datetime]:
    """
    Extract timestamp from a single log line.
    
    Args:
        log_line: Single log line
        
    Returns:
        datetime object or None if no timestamp found
    """
    parser = LogParser()
    try:
        # Try to parse the line and extract timestamp
        dummy_event = parser._parse_single_line(log_line, "dummy")
        return dummy_event.timestamp if dummy_event else None
    except:
        return None


def categorize_event(message: str, source: str = "") -> EventCategory:
    """
    Categorize an event based on message content and source.
    
    Args:
        message: Event message
        source: Event source (optional)
        
    Returns:
        EventCategory enum value
    """
    parser = LogParser()
    return parser._categorize_event(message, source)