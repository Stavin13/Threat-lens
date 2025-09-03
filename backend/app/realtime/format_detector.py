"""
Automatic log format detection and adaptive parsing.

This module provides advanced log format detection capabilities that can
automatically identify unknown log formats and create adaptive parsing rules.
"""

import re
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Any, Set
from enum import Enum
from collections import defaultdict, Counter
from dataclasses import dataclass

from app.schemas import ParsedEvent, EventCategory
from app.parser import LogParser, LogFormat, ParsingError

logger = logging.getLogger(__name__)


class FormatConfidence(Enum):
    """Confidence levels for format detection."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass
class FormatPattern:
    """Detected format pattern with metadata."""
    name: str
    regex_pattern: str
    confidence: FormatConfidence
    sample_lines: List[str]
    field_mapping: Dict[str, int]  # Maps field names to regex group indices
    timestamp_format: Optional[str] = None
    delimiter: Optional[str] = None
    frequency: int = 0  # How often this pattern appears


@dataclass
class ParsedField:
    """Parsed field from a log line."""
    name: str
    value: str
    position: int
    confidence: float


class LogFormatDetector:
    """
    Advanced log format detector with machine learning-like capabilities.
    
    Analyzes log samples to automatically detect formats and create
    adaptive parsing rules for unknown log types.
    """
    
    # Common timestamp patterns with their regex and format strings
    TIMESTAMP_PATTERNS = {
        'syslog': {
            'regex': r'\b(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\b',
            'format': '%b %d %H:%M:%S',
            'example': 'Jan 15 10:30:45'
        },
        'iso_datetime': {
            'regex': r'\b(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\b',
            'format': '%Y-%m-%d %H:%M:%S',
            'example': '2024-01-15 10:30:45'
        },
        'iso_with_ms': {
            'regex': r'\b(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\b',
            'format': '%Y-%m-%d %H:%M:%S.%f',
            'example': '2024-01-15 10:30:45.123'
        },
        'us_datetime': {
            'regex': r'\b(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\b',
            'format': '%m/%d/%Y %H:%M:%S',
            'example': '01/15/2024 10:30:45'
        },
        'epoch_seconds': {
            'regex': r'\b(\d{10})\b',
            'format': 'epoch',
            'example': '1705312245'
        },
        'epoch_milliseconds': {
            'regex': r'\b(\d{13})\b',
            'format': 'epoch_ms',
            'example': '1705312245123'
        },
        'apache_common': {
            'regex': r'\[(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}\s+[+-]\d{4})\]',
            'format': '%d/%b/%Y:%H:%M:%S %z',
            'example': '[15/Jan/2024:10:30:45 +0000]'
        }
    }
    
    # Common field patterns
    FIELD_PATTERNS = {
        'hostname': r'\b([a-zA-Z0-9\-\.]+)\b',
        'ip_address': r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b',
        'process_name': r'\b([a-zA-Z0-9_\-]+)\b',
        'pid': r'\[(\d+)\]',
        'log_level': r'\b(DEBUG|INFO|WARN|WARNING|ERROR|FATAL|TRACE)\b',
        'quoted_string': r'"([^"]*)"',
        'bracketed_content': r'\[([^\]]*)\]',
        'parenthesized_content': r'\(([^)]*)\)'
    }
    
    # Common delimiters
    DELIMITERS = [' ', '\t', '|', ',', ';', ':', '=']
    
    def __init__(self, min_sample_size: int = 10, max_patterns: int = 5):
        """
        Initialize the format detector.
        
        Args:
            min_sample_size: Minimum number of lines needed for detection
            max_patterns: Maximum number of patterns to maintain
        """
        self.min_sample_size = min_sample_size
        self.max_patterns = max_patterns
        
        # Detected patterns cache
        self.detected_patterns: Dict[str, FormatPattern] = {}
        
        # Learning data
        self.sample_lines: List[str] = []
        self.field_statistics: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Base parser for fallback
        self.base_parser = LogParser()
    
    def analyze_log_sample(self, log_lines: List[str]) -> List[FormatPattern]:
        """
        Analyze a sample of log lines to detect formats.
        
        Args:
            log_lines: List of log lines to analyze
            
        Returns:
            List of detected format patterns
        """
        if len(log_lines) < self.min_sample_size:
            logger.warning(f"Sample size {len(log_lines)} is below minimum {self.min_sample_size}")
        
        logger.info(f"Analyzing {len(log_lines)} log lines for format detection")
        
        # Store samples for learning
        self.sample_lines.extend(log_lines[:100])  # Keep only recent samples
        if len(self.sample_lines) > 1000:
            self.sample_lines = self.sample_lines[-500:]
        
        # Detect timestamp patterns
        timestamp_patterns = self._detect_timestamp_patterns(log_lines)
        
        # Detect field structures
        field_structures = self._detect_field_structures(log_lines)
        
        # Detect delimiters
        delimiter_info = self._detect_delimiters(log_lines)
        
        # Combine findings into format patterns
        patterns = self._create_format_patterns(
            log_lines, timestamp_patterns, field_structures, delimiter_info
        )
        
        # Update detected patterns cache
        for pattern in patterns:
            pattern_key = f"{pattern.name}_{hash(pattern.regex_pattern)}"
            if pattern_key in self.detected_patterns:
                # Update existing pattern
                existing = self.detected_patterns[pattern_key]
                existing.frequency += pattern.frequency
                existing.sample_lines.extend(pattern.sample_lines[:5])
                existing.sample_lines = existing.sample_lines[-10:]  # Keep recent samples
            else:
                self.detected_patterns[pattern_key] = pattern
        
        # Keep only top patterns
        if len(self.detected_patterns) > self.max_patterns:
            sorted_patterns = sorted(
                self.detected_patterns.values(),
                key=lambda p: (p.frequency, p.confidence.value),
                reverse=True
            )
            self.detected_patterns = {
                f"{p.name}_{hash(p.regex_pattern)}": p
                for p in sorted_patterns[:self.max_patterns]
            }
        
        logger.info(f"Detected {len(patterns)} format patterns")
        return patterns
    
    def _detect_timestamp_patterns(self, log_lines: List[str]) -> Dict[str, Any]:
        """
        Detect timestamp patterns in log lines.
        
        Args:
            log_lines: List of log lines
            
        Returns:
            Dictionary with timestamp pattern information
        """
        pattern_matches = defaultdict(list)
        
        for line in log_lines[:50]:  # Analyze first 50 lines
            for pattern_name, pattern_info in self.TIMESTAMP_PATTERNS.items():
                matches = re.findall(pattern_info['regex'], line)
                if matches:
                    pattern_matches[pattern_name].extend(matches)
        
        # Find the most common timestamp pattern
        best_pattern = None
        max_matches = 0
        
        for pattern_name, matches in pattern_matches.items():
            if len(matches) > max_matches:
                max_matches = len(matches)
                best_pattern = pattern_name
        
        result = {
            'best_pattern': best_pattern,
            'pattern_counts': dict(pattern_matches),
            'confidence': FormatConfidence.HIGH if max_matches > len(log_lines) * 0.8 else
                         FormatConfidence.MEDIUM if max_matches > len(log_lines) * 0.5 else
                         FormatConfidence.LOW
        }
        
        logger.debug(f"Timestamp detection: {result}")
        return result
    
    def _detect_field_structures(self, log_lines: List[str]) -> Dict[str, Any]:
        """
        Detect field structures in log lines.
        
        Args:
            log_lines: List of log lines
            
        Returns:
            Dictionary with field structure information
        """
        field_positions = defaultdict(list)
        field_patterns = defaultdict(int)
        
        for line in log_lines[:50]:
            # Detect various field patterns
            for field_name, pattern in self.FIELD_PATTERNS.items():
                matches = list(re.finditer(pattern, line))
                for match in matches:
                    field_positions[field_name].append({
                        'start': match.start(),
                        'end': match.end(),
                        'value': match.group(1) if match.groups() else match.group(0),
                        'line': line
                    })
                    field_patterns[field_name] += 1
        
        # Analyze field consistency
        consistent_fields = {}
        for field_name, positions in field_positions.items():
            if len(positions) >= len(log_lines) * 0.3:  # Present in at least 30% of lines
                # Check position consistency
                start_positions = [pos['start'] for pos in positions]
                position_variance = max(start_positions) - min(start_positions)
                
                consistent_fields[field_name] = {
                    'frequency': len(positions),
                    'position_variance': position_variance,
                    'sample_values': [pos['value'] for pos in positions[:5]],
                    'is_consistent': position_variance < 50  # Arbitrary threshold
                }
        
        return {
            'consistent_fields': consistent_fields,
            'field_patterns': dict(field_patterns),
            'total_fields_detected': len(consistent_fields)
        }
    
    def _detect_delimiters(self, log_lines: List[str]) -> Dict[str, Any]:
        """
        Detect common delimiters in log lines.
        
        Args:
            log_lines: List of log lines
            
        Returns:
            Dictionary with delimiter information
        """
        delimiter_counts = Counter()
        
        for line in log_lines[:50]:
            for delimiter in self.DELIMITERS:
                delimiter_counts[delimiter] += line.count(delimiter)
        
        # Find most common delimiter (excluding space which is always common)
        non_space_delimiters = {k: v for k, v in delimiter_counts.items() if k != ' '}
        
        primary_delimiter = None
        if non_space_delimiters:
            primary_delimiter = max(non_space_delimiters.items(), key=lambda x: x[1])[0]
        
        return {
            'delimiter_counts': dict(delimiter_counts),
            'primary_delimiter': primary_delimiter,
            'has_structured_delimiter': primary_delimiter is not None and 
                                      delimiter_counts[primary_delimiter] > len(log_lines) * 2
        }
    
    def _create_format_patterns(
        self,
        log_lines: List[str],
        timestamp_info: Dict[str, Any],
        field_info: Dict[str, Any],
        delimiter_info: Dict[str, Any]
    ) -> List[FormatPattern]:
        """
        Create format patterns from detected information.
        
        Args:
            log_lines: Original log lines
            timestamp_info: Timestamp detection results
            field_info: Field structure detection results
            delimiter_info: Delimiter detection results
            
        Returns:
            List of FormatPattern objects
        """
        patterns = []
        
        # Create pattern based on timestamp and field detection
        if timestamp_info['best_pattern']:
            timestamp_pattern = self.TIMESTAMP_PATTERNS[timestamp_info['best_pattern']]
            
            # Build regex pattern
            pattern_parts = []
            field_mapping = {}
            group_index = 1
            
            # Add timestamp group
            pattern_parts.append(f"({timestamp_pattern['regex'][2:-2]})")  # Remove \b boundaries
            field_mapping['timestamp'] = group_index
            group_index += 1
            
            # Add common field patterns based on detection
            consistent_fields = field_info['consistent_fields']
            
            # Add hostname/source if detected
            if 'hostname' in consistent_fields and consistent_fields['hostname']['is_consistent']:
                pattern_parts.append(r'\s+(\S+)')
                field_mapping['hostname'] = group_index
                group_index += 1
            
            # Add process name if detected
            if 'process_name' in consistent_fields:
                pattern_parts.append(r'\s+([^:\[\s]+)')
                field_mapping['process'] = group_index
                group_index += 1
            
            # Add PID if detected
            if 'pid' in consistent_fields:
                pattern_parts.append(r'(?:\[(\d+)\])?')
                field_mapping['pid'] = group_index
                group_index += 1
            
            # Add separator and message
            pattern_parts.append(r'\s*:\s*(.+)')
            field_mapping['message'] = group_index
            
            # Combine pattern
            full_pattern = ''.join(pattern_parts)
            
            # Determine confidence
            confidence = FormatConfidence.HIGH
            if timestamp_info['confidence'] == FormatConfidence.MEDIUM:
                confidence = FormatConfidence.MEDIUM
            elif len(consistent_fields) < 2:
                confidence = FormatConfidence.LOW
            
            pattern = FormatPattern(
                name=f"detected_{timestamp_info['best_pattern']}",
                regex_pattern=full_pattern,
                confidence=confidence,
                sample_lines=log_lines[:5],
                field_mapping=field_mapping,
                timestamp_format=timestamp_pattern['format'],
                delimiter=delimiter_info.get('primary_delimiter'),
                frequency=len(log_lines)
            )
            
            patterns.append(pattern)
        
        # Create delimiter-based pattern if structured delimiter detected
        if delimiter_info['has_structured_delimiter']:
            delimiter = delimiter_info['primary_delimiter']
            
            # Create simple delimiter-based pattern
            escaped_delimiter = re.escape(delimiter)
            pattern_parts = []
            field_mapping = {}
            
            # Estimate number of fields
            sample_line = log_lines[0]
            field_count = sample_line.count(delimiter) + 1
            
            for i in range(min(field_count, 6)):  # Limit to 6 fields
                if i > 0:
                    pattern_parts.append(escaped_delimiter)
                pattern_parts.append(r'([^' + escaped_delimiter + r']*)')
                field_mapping[f'field_{i+1}'] = i + 1
            
            full_pattern = ''.join(pattern_parts)
            
            pattern = FormatPattern(
                name=f"delimited_{delimiter.replace(' ', 'space')}",
                regex_pattern=full_pattern,
                confidence=FormatConfidence.MEDIUM,
                sample_lines=log_lines[:3],
                field_mapping=field_mapping,
                delimiter=delimiter,
                frequency=len(log_lines)
            )
            
            patterns.append(pattern)
        
        # Create generic fallback pattern
        if not patterns:
            # Very basic pattern that captures everything
            pattern = FormatPattern(
                name="generic_fallback",
                regex_pattern=r'(.+)',
                confidence=FormatConfidence.LOW,
                sample_lines=log_lines[:3],
                field_mapping={'message': 1},
                frequency=len(log_lines)
            )
            patterns.append(pattern)
        
        return patterns
    
    def parse_with_detected_format(
        self,
        log_content: str,
        raw_log_id: str,
        format_pattern: Optional[FormatPattern] = None
    ) -> List[ParsedEvent]:
        """
        Parse log content using detected format patterns.
        
        Args:
            log_content: Raw log content
            raw_log_id: Raw log ID
            format_pattern: Specific format pattern to use (optional)
            
        Returns:
            List of ParsedEvent objects
        """
        lines = log_content.strip().split('\n')
        
        # Auto-detect format if not provided
        if not format_pattern:
            detected_patterns = self.analyze_log_sample(lines[:20])  # Use first 20 lines for detection
            if detected_patterns:
                format_pattern = max(detected_patterns, key=lambda p: (p.confidence.value, p.frequency))
            else:
                # Fallback to base parser
                logger.warning("No format detected, falling back to base parser")
                return self.base_parser.parse_log_entries(log_content, raw_log_id)
        
        logger.info(f"Parsing with detected format: {format_pattern.name}")
        
        events = []
        pattern = re.compile(format_pattern.regex_pattern)
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                event = self._parse_line_with_pattern(
                    line, pattern, format_pattern, raw_log_id
                )
                if event:
                    events.append(event)
                else:
                    # Try fallback parsing
                    fallback_event = self._parse_fallback(line, raw_log_id)
                    if fallback_event:
                        events.append(fallback_event)
                        
            except Exception as e:
                logger.debug(f"Error parsing line {line_num} with detected format: {e}")
                # Try fallback parsing
                try:
                    fallback_event = self._parse_fallback(line, raw_log_id)
                    if fallback_event:
                        events.append(fallback_event)
                except Exception:
                    logger.warning(f"Failed to parse line {line_num}: {line[:100]}...")
                    continue
        
        logger.info(f"Parsed {len(events)} events using detected format")
        return events
    
    def _parse_line_with_pattern(
        self,
        line: str,
        pattern: re.Pattern,
        format_pattern: FormatPattern,
        raw_log_id: str
    ) -> Optional[ParsedEvent]:
        """
        Parse a single line using a detected pattern.
        
        Args:
            line: Log line to parse
            pattern: Compiled regex pattern
            format_pattern: Format pattern metadata
            raw_log_id: Raw log ID
            
        Returns:
            ParsedEvent object or None
        """
        match = pattern.match(line)
        if not match:
            return None
        
        groups = match.groups()
        field_mapping = format_pattern.field_mapping
        
        # Extract timestamp
        timestamp = datetime.now(timezone.utc)  # Default
        if 'timestamp' in field_mapping:
            timestamp_str = groups[field_mapping['timestamp'] - 1]
            timestamp = self._parse_timestamp_with_format(
                timestamp_str, format_pattern.timestamp_format
            )
        
        # Extract source
        source = "unknown"
        if 'hostname' in field_mapping:
            hostname = groups[field_mapping['hostname'] - 1]
            source = hostname
            
            if 'process' in field_mapping:
                process = groups[field_mapping['process'] - 1]
                source = f"{hostname}:{process}"
                
                if 'pid' in field_mapping and field_mapping['pid'] <= len(groups):
                    pid = groups[field_mapping['pid'] - 1]
                    if pid:
                        source += f"[{pid}]"
        elif 'process' in field_mapping:
            source = groups[field_mapping['process'] - 1]
        
        # Extract message
        message = line  # Default to full line
        if 'message' in field_mapping:
            message = groups[field_mapping['message'] - 1]
        elif len(groups) > 0:
            message = groups[-1]  # Use last group as message
        
        # Categorize event
        category = self.base_parser._categorize_event(message, source)
        
        return ParsedEvent(
            id=str(__import__('uuid').uuid4()),
            raw_log_id=raw_log_id,
            timestamp=timestamp,
            source=source,
            message=message.strip(),
            category=category,
            parsed_at=datetime.now(timezone.utc)
        )
    
    def _parse_timestamp_with_format(self, timestamp_str: str, format_str: Optional[str]) -> datetime:
        """
        Parse timestamp using detected format.
        
        Args:
            timestamp_str: Timestamp string
            format_str: Format string or special format name
            
        Returns:
            datetime object
        """
        if not format_str:
            return datetime.now(timezone.utc)
        
        try:
            if format_str == 'epoch':
                return datetime.fromtimestamp(int(timestamp_str), tz=timezone.utc)
            elif format_str == 'epoch_ms':
                return datetime.fromtimestamp(int(timestamp_str) / 1000, tz=timezone.utc)
            else:
                # Handle syslog format without year
                if format_str == '%b %d %H:%M:%S':
                    dt = datetime.strptime(timestamp_str, format_str)
                    return dt.replace(year=datetime.now().year, tzinfo=timezone.utc)
                else:
                    dt = datetime.strptime(timestamp_str, format_str)
                    return dt.replace(tzinfo=timezone.utc)
                    
        except (ValueError, OSError) as e:
            logger.debug(f"Failed to parse timestamp '{timestamp_str}' with format '{format_str}': {e}")
            return datetime.now(timezone.utc)
    
    def _parse_fallback(self, line: str, raw_log_id: str) -> Optional[ParsedEvent]:
        """
        Fallback parsing for lines that don't match detected patterns.
        
        Args:
            line: Log line to parse
            raw_log_id: Raw log ID
            
        Returns:
            ParsedEvent object or None
        """
        try:
            return self.base_parser._parse_generic_line(line, raw_log_id)
        except Exception as e:
            logger.debug(f"Fallback parsing failed: {e}")
            return None
    
    def get_detected_patterns(self) -> List[FormatPattern]:
        """
        Get all detected format patterns.
        
        Returns:
            List of detected FormatPattern objects
        """
        return list(self.detected_patterns.values())
    
    def clear_detected_patterns(self) -> None:
        """Clear all detected patterns and learning data."""
        self.detected_patterns.clear()
        self.sample_lines.clear()
        self.field_statistics.clear()
        logger.info("Cleared all detected patterns and learning data")
    
    def get_detection_statistics(self) -> Dict[str, Any]:
        """
        Get format detection statistics.
        
        Returns:
            Dictionary with detection statistics
        """
        return {
            'total_patterns': len(self.detected_patterns),
            'sample_lines_count': len(self.sample_lines),
            'patterns_by_confidence': {
                confidence.value: len([p for p in self.detected_patterns.values() 
                                     if p.confidence == confidence])
                for confidence in FormatConfidence
            },
            'most_frequent_pattern': max(
                self.detected_patterns.values(),
                key=lambda p: p.frequency,
                default=None
            ).name if self.detected_patterns else None
        }


# Convenience functions
def detect_log_format(log_lines: List[str]) -> List[FormatPattern]:
    """
    Detect log format from sample lines.
    
    Args:
        log_lines: List of log lines to analyze
        
    Returns:
        List of detected format patterns
    """
    detector = LogFormatDetector()
    return detector.analyze_log_sample(log_lines)


def parse_with_auto_detection(log_content: str, raw_log_id: str) -> List[ParsedEvent]:
    """
    Parse log content with automatic format detection.
    
    Args:
        log_content: Raw log content
        raw_log_id: Raw log ID
        
    Returns:
        List of ParsedEvent objects
    """
    detector = LogFormatDetector()
    return detector.parse_with_detected_format(log_content, raw_log_id)