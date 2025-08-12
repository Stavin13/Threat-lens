"""
Unit tests for the log parsing engine.

Tests cover regex patterns, timestamp parsing, event categorization,
error handling, and edge cases for the parser module.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch
import uuid

from app.parser import (
    LogParser, 
    parse_log_entries, 
    extract_timestamp, 
    categorize_event,
    ParsingError,
    LogFormat
)
from app.schemas import ParsedEvent, EventCategory


class TestLogParser:
    """Test cases for the LogParser class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = LogParser()
        self.sample_raw_log_id = str(uuid.uuid4())
    
    def test_init(self):
        """Test parser initialization."""
        parser = LogParser()
        assert parser.stats['total_lines'] == 0
        assert parser.stats['parsed_events'] == 0
        assert parser.stats['failed_lines'] == 0
        assert all(count == 0 for count in parser.stats['categories'].values())
    
    def test_parse_macos_system_log_single_line(self):
        """Test parsing a single macOS system.log line."""
        log_line = "Jan 15 10:30:45 MacBook-Pro kernel[0]: USB disconnect, address 1"
        
        events = self.parser.parse_log_entries(log_line, self.sample_raw_log_id)
        
        assert len(events) == 1
        event = events[0]
        assert event.source == "MacBook-Pro:kernel[0]"
        assert event.message == "USB disconnect, address 1"
        assert event.category == EventCategory.KERNEL
        assert event.timestamp.month == 1
        assert event.timestamp.day == 15
        assert event.timestamp.hour == 10
        assert event.timestamp.minute == 30
        assert event.timestamp.second == 45
    
    def test_parse_macos_auth_log_single_line(self):
        """Test parsing a single macOS auth.log line."""
        log_line = "Jan 15 14:22:33 MacBook-Pro sudo[1234]: user : TTY=ttys000 ; PWD=/Users/user ; USER=root ; COMMAND=/bin/ls"
        
        events = self.parser.parse_log_entries(log_line, self.sample_raw_log_id)
        
        assert len(events) == 1
        event = events[0]
        assert event.source == "MacBook-Pro:sudo[1234]"
        assert "TTY=ttys000" in event.message
        assert event.category == EventCategory.AUTH
        assert event.timestamp.hour == 14
        assert event.timestamp.minute == 22
        assert event.timestamp.second == 33
    
    def test_parse_multiple_log_lines(self):
        """Test parsing multiple log lines."""
        log_content = """Jan 15 10:30:45 MacBook-Pro kernel[0]: USB disconnect, address 1
Jan 15 10:31:02 MacBook-Pro loginwindow[123]: Login Window Application Started
Jan 15 10:31:15 MacBook-Pro sshd[456]: Failed password for user from 192.168.1.100"""
        
        events = self.parser.parse_log_entries(log_content, self.sample_raw_log_id)
        
        assert len(events) == 3
        assert events[0].category == EventCategory.KERNEL
        assert events[1].category == EventCategory.SYSTEM
        assert events[2].category == EventCategory.AUTH
        assert all(event.raw_log_id == self.sample_raw_log_id for event in events)
    
    def test_parse_log_with_empty_lines(self):
        """Test parsing log content with empty lines."""
        log_content = """Jan 15 10:30:45 MacBook-Pro kernel[0]: USB disconnect, address 1

Jan 15 10:31:02 MacBook-Pro loginwindow[123]: Login Window Application Started

"""
        
        events = self.parser.parse_log_entries(log_content, self.sample_raw_log_id)
        
        assert len(events) == 2
        assert self.parser.stats['total_lines'] == 3  # Empty lines are not counted in split
    
    def test_parse_empty_log_content(self):
        """Test parsing empty log content."""
        with pytest.raises(ParsingError, match="Empty log content provided"):
            self.parser.parse_log_entries("", self.sample_raw_log_id)
        
        with pytest.raises(ParsingError, match="Empty log content provided"):
            self.parser.parse_log_entries("   \n  \n  ", self.sample_raw_log_id)
    
    def test_parse_log_no_parseable_lines(self):
        """Test parsing log with no parseable lines."""
        log_content = "This is not a valid log line\nNeither is this one"
        
        # Should not raise an error, but should create generic events
        events = self.parser.parse_log_entries(log_content, self.sample_raw_log_id)
        
        assert len(events) == 2
        # Generic parsing may extract some sources from the text
        assert all(event.category == EventCategory.UNKNOWN for event in events)
    
    def test_parse_timestamp_syslog_format(self):
        """Test timestamp parsing for syslog format."""
        test_cases = [
            ("Jan 15 10:30:45", 1, 15, 10, 30, 45),
            ("Dec 31 23:59:59", 12, 31, 23, 59, 59),
            ("Feb  5 08:15:30", 2, 5, 8, 15, 30),  # Single digit day with space
        ]
        
        for timestamp_str, month, day, hour, minute, second in test_cases:
            result = self.parser._parse_timestamp(timestamp_str)
            assert result.month == month
            assert result.day == day
            assert result.hour == hour
            assert result.minute == minute
            assert result.second == second
            assert result.tzinfo == timezone.utc
    
    def test_parse_timestamp_iso_format(self):
        """Test timestamp parsing for ISO format."""
        timestamp_str = "2024-01-15 10:30:45"
        result = self.parser._parse_timestamp(timestamp_str)
        
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 45
        assert result.tzinfo == timezone.utc
    
    def test_parse_timestamp_us_format(self):
        """Test timestamp parsing for US format."""
        timestamp_str = "01/15/2024 10:30:45"
        result = self.parser._parse_timestamp(timestamp_str)
        
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 45
        assert result.tzinfo == timezone.utc
    
    def test_parse_timestamp_invalid_format(self):
        """Test timestamp parsing with invalid format."""
        with pytest.raises(ParsingError, match="Unable to parse timestamp"):
            self.parser._parse_timestamp("invalid timestamp")
    
    def test_parse_timestamp_invalid_values(self):
        """Test timestamp parsing with invalid values."""
        with pytest.raises(ParsingError, match="Invalid timestamp values"):
            self.parser._parse_timestamp("Jan 32 25:70:80")  # Invalid day, hour, minute, second
    
    def test_categorize_event_auth(self):
        """Test event categorization for authentication events."""
        test_cases = [
            ("Failed password for user", "sshd", EventCategory.AUTH),
            ("sudo: user : command not allowed", "sudo", EventCategory.AUTH),
            ("Login successful for user", "loginwindow", EventCategory.AUTH),
            ("Authentication failure", "pam", EventCategory.AUTH),
        ]
        
        for message, source, expected_category in test_cases:
            result = self.parser._categorize_event(message, source)
            assert result == expected_category
    
    def test_categorize_event_system(self):
        """Test event categorization for system events."""
        test_cases = [
            ("System boot completed", "init", EventCategory.SYSTEM),
            ("Service started successfully", "systemd", EventCategory.SYSTEM),
            ("Disk mounted at /home", "mount", EventCategory.SYSTEM),
            ("Process terminated", "systemd", EventCategory.SYSTEM),
        ]
        
        for message, source, expected_category in test_cases:
            result = self.parser._categorize_event(message, source)
            assert result == expected_category
    
    def test_categorize_event_network(self):
        """Test event categorization for network events."""
        test_cases = [
            ("TCP connection established", "network", EventCategory.NETWORK),
            ("DNS query for example.com", "dns", EventCategory.NETWORK),
            ("Firewall blocked connection", "firewall", EventCategory.NETWORK),
            ("DHCP lease renewed", "dhcp", EventCategory.NETWORK),
        ]
        
        for message, source, expected_category in test_cases:
            result = self.parser._categorize_event(message, source)
            assert result == expected_category
    
    def test_categorize_event_security(self):
        """Test event categorization for security events."""
        test_cases = [
            ("Malware detected and quarantined", "antivirus", EventCategory.SECURITY),
            ("Suspicious activity blocked", "security", EventCategory.SECURITY),
            ("Intrusion attempt detected", "ids", EventCategory.SECURITY),
            ("Security violation reported", "monitor", EventCategory.SECURITY),
        ]
        
        for message, source, expected_category in test_cases:
            result = self.parser._categorize_event(message, source)
            assert result == expected_category
    
    def test_categorize_event_application(self):
        """Test event categorization for application events."""
        test_cases = [
            ("Application crashed with error", "myapp", EventCategory.APPLICATION),
            ("Software update completed", "updater", EventCategory.APPLICATION),
            ("Program exception occurred", "launcher", EventCategory.APPLICATION),
            ("Debug information logged", "debugger", EventCategory.APPLICATION),
        ]
        
        for message, source, expected_category in test_cases:
            result = self.parser._categorize_event(message, source)
            assert result == expected_category
    
    def test_categorize_event_kernel(self):
        """Test event categorization for kernel events."""
        test_cases = [
            ("Kernel panic occurred", "kernel", EventCategory.KERNEL),
            ("USB device connected", "kernel", EventCategory.KERNEL),
            ("Interrupt handler registered", "kernel", EventCategory.KERNEL),
            ("Memory allocation failed", "kernel", EventCategory.KERNEL),
        ]
        
        for message, source, expected_category in test_cases:
            result = self.parser._categorize_event(message, source)
            assert result == expected_category
    
    def test_categorize_event_unknown(self):
        """Test event categorization for unknown events."""
        result = self.parser._categorize_event("Random message with no keywords", "unknown")
        assert result == EventCategory.UNKNOWN
    
    def test_parse_generic_line_with_timestamp(self):
        """Test parsing generic line with extractable timestamp."""
        line = "2024-01-15 10:30:45 some_process: This is a generic log message"
        
        event = self.parser._parse_generic_line(line, self.sample_raw_log_id)
        
        assert event is not None
        assert event.timestamp.year == 2024
        assert event.timestamp.month == 1
        assert event.timestamp.day == 15
        assert event.source == "some_process"
        assert event.message == "This is a generic log message"
    
    def test_parse_generic_line_without_timestamp(self):
        """Test parsing generic line without timestamp."""
        line = "This is a log message without timestamp"
        
        with patch('app.parser.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            event = self.parser._parse_generic_line(line, self.sample_raw_log_id)
        
        assert event is not None
        assert event.source in ["unknown", "This"]  # May extract first word as source
        assert "log message without timestamp" in event.message
        assert event.category == EventCategory.UNKNOWN
    
    def test_get_parsing_stats(self):
        """Test getting parsing statistics."""
        log_content = """Jan 15 10:30:45 MacBook-Pro kernel[0]: USB disconnect, address 1
Jan 15 10:31:02 MacBook-Pro loginwindow[123]: Login Window Application Started
Invalid log line that won't parse properly"""
        
        events = self.parser.parse_log_entries(log_content, self.sample_raw_log_id)
        stats = self.parser.get_parsing_stats()
        
        assert stats['total_lines'] == 3
        assert stats['parsed_events'] == 3  # All lines should parse (including generic)
        assert stats['failed_lines'] == 0
        assert stats['categories']['kernel'] >= 1
        assert stats['categories']['system'] >= 1 or stats['categories']['unknown'] >= 1
    
    def test_regex_patterns_coverage(self):
        """Test that all regex patterns are properly defined."""
        assert LogFormat.MACOS_SYSTEM in LogParser.PATTERNS
        assert LogFormat.MACOS_AUTH in LogParser.PATTERNS
        assert LogFormat.GENERIC_SYSLOG in LogParser.PATTERNS
        
        # Test that patterns compile without errors
        for pattern in LogParser.PATTERNS.values():
            assert pattern.pattern is not None
    
    def test_month_mapping_complete(self):
        """Test that month mapping is complete."""
        expected_months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        for month in expected_months:
            assert month in LogParser.MONTH_MAP
        
        assert len(LogParser.MONTH_MAP) == 12
    
    def test_category_keywords_complete(self):
        """Test that category keywords are defined for all categories."""
        for category in EventCategory:
            if category != EventCategory.UNKNOWN:
                assert category in LogParser.CATEGORY_KEYWORDS
                assert len(LogParser.CATEGORY_KEYWORDS[category]) > 0


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_raw_log_id = str(uuid.uuid4())
    
    def test_parse_log_entries_function(self):
        """Test the parse_log_entries convenience function."""
        log_content = "Jan 15 10:30:45 MacBook-Pro kernel[0]: USB disconnect, address 1"
        
        events = parse_log_entries(log_content, self.sample_raw_log_id)
        
        assert len(events) == 1
        assert isinstance(events[0], ParsedEvent)
        assert events[0].raw_log_id == self.sample_raw_log_id
    
    def test_extract_timestamp_function(self):
        """Test the extract_timestamp convenience function."""
        log_line = "Jan 15 10:30:45 MacBook-Pro kernel[0]: USB disconnect, address 1"
        
        timestamp = extract_timestamp(log_line)
        
        assert timestamp is not None
        assert timestamp.month == 1
        assert timestamp.day == 15
        assert timestamp.hour == 10
        assert timestamp.minute == 30
        assert timestamp.second == 45
    
    def test_extract_timestamp_function_no_timestamp(self):
        """Test extract_timestamp with line containing no timestamp."""
        log_line = "This line has no timestamp"
        
        timestamp = extract_timestamp(log_line)
        
        # Should still return a timestamp (current time) from generic parsing
        assert timestamp is not None
    
    def test_categorize_event_function(self):
        """Test the categorize_event convenience function."""
        result = categorize_event("Failed password for user", "sshd")
        assert result == EventCategory.AUTH
        
        result = categorize_event("Kernel panic occurred")
        assert result == EventCategory.KERNEL
        
        result = categorize_event("Random message")
        assert result == EventCategory.UNKNOWN


class TestErrorHandling:
    """Test cases for error handling and edge cases."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = LogParser()
        self.sample_raw_log_id = str(uuid.uuid4())
    
    def test_malformed_log_entries_graceful_failure(self):
        """Test that malformed entries are handled gracefully."""
        log_content = """Jan 15 10:30:45 MacBook-Pro kernel[0]: Valid log entry
This is a malformed entry
Jan 15 10:31:00 MacBook-Pro sshd[123]: Another valid entry
"""
        
        # Should not raise an exception
        events = self.parser.parse_log_entries(log_content, self.sample_raw_log_id)
        
        # Should still parse the valid entries plus create generic events for malformed ones
        assert len(events) >= 2
        stats = self.parser.get_parsing_stats()
        assert stats['total_lines'] == 3
    
    def test_very_long_log_lines(self):
        """Test handling of very long log lines."""
        long_message = "A" * 10000
        log_line = f"Jan 15 10:30:45 MacBook-Pro test[123]: {long_message}"
        
        events = self.parser.parse_log_entries(log_line, self.sample_raw_log_id)
        
        assert len(events) == 1
        assert len(events[0].message) == 10000
    
    def test_special_characters_in_log(self):
        """Test handling of special characters in log content."""
        log_line = "Jan 15 10:30:45 MacBook-Pro test[123]: Message with special chars: !@#$%^&*()[]{}|\\:;\"'<>?,./"
        
        events = self.parser.parse_log_entries(log_line, self.sample_raw_log_id)
        
        assert len(events) == 1
        assert "!@#$%^&*()" in events[0].message
    
    def test_unicode_characters_in_log(self):
        """Test handling of unicode characters in log content."""
        log_line = "Jan 15 10:30:45 MacBook-Pro test[123]: Message with unicode: 你好世界 🌍 café naïve"
        
        events = self.parser.parse_log_entries(log_line, self.sample_raw_log_id)
        
        assert len(events) == 1
        assert "你好世界" in events[0].message
        assert "🌍" in events[0].message
        assert "café" in events[0].message
    
    def test_parsing_error_exception(self):
        """Test ParsingError exception."""
        error = ParsingError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)


class TestRealWorldLogSamples:
    """Test cases with realistic log samples."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = LogParser()
        self.sample_raw_log_id = str(uuid.uuid4())
    
    def test_macos_system_log_samples(self):
        """Test with realistic macOS system.log samples."""
        log_content = """Jan 15 10:30:45 MacBook-Pro kernel[0]: USB disconnect, address 1
Jan 15 10:30:46 MacBook-Pro UserEventAgent[123]: Captive: [CNInfoNetworkActive:1709] en0: SSID 'MyWiFi' making interface primary (protected network)
Jan 15 10:30:47 MacBook-Pro com.apple.xpc.launchd[1]: (com.apple.WebKit.Networking.xpc[456]) Service exited with abnormal code: 1
Jan 15 10:30:48 MacBook-Pro WindowServer[789]: CGXDisplayDidWakeNotification [123456789]: posting kCGSDisplayDidWake
Jan 15 10:30:49 MacBook-Pro loginwindow[101]: Login Window Application Started"""
        
        events = self.parser.parse_log_entries(log_content, self.sample_raw_log_id)
        
        assert len(events) == 5
        
        # Check specific event details
        usb_event = events[0]
        assert "USB disconnect" in usb_event.message
        assert usb_event.category == EventCategory.KERNEL
        assert usb_event.source == "MacBook-Pro:kernel[0]"
        
        network_event = events[1]
        assert "SSID" in network_event.message
        assert network_event.category == EventCategory.NETWORK
        
        login_event = events[4]
        assert "Login Window" in login_event.message
        assert login_event.category in [EventCategory.SYSTEM, EventCategory.AUTH]  # Could be either
    
    def test_macos_auth_log_samples(self):
        """Test with realistic macOS auth.log samples."""
        log_content = """Jan 15 14:22:33 MacBook-Pro sudo[1234]: user : TTY=ttys000 ; PWD=/Users/user ; USER=root ; COMMAND=/bin/ls
Jan 15 14:22:34 MacBook-Pro sshd[5678]: Failed password for invalid user admin from 192.168.1.100 port 22 ssh2
Jan 15 14:22:35 MacBook-Pro su[9012]: pam_authenticate: Authentication failure
Jan 15 14:22:36 MacBook-Pro login[3456]: USER_PROCESS: 789 ttys000"""
        
        events = self.parser.parse_log_entries(log_content, self.sample_raw_log_id)
        
        assert len(events) == 4
        
        # All should be categorized as AUTH events
        for event in events:
            assert event.category == EventCategory.AUTH
        
        # Check specific event details
        sudo_event = events[0]
        assert "sudo" in sudo_event.source
        assert "COMMAND=/bin/ls" in sudo_event.message
        
        ssh_event = events[1]
        assert "Failed password" in ssh_event.message
        assert "192.168.1.100" in ssh_event.message
    
    def test_mixed_log_formats(self):
        """Test with mixed log formats in single content."""
        log_content = """Jan 15 10:30:45 MacBook-Pro kernel[0]: USB disconnect, address 1
2024-01-15 10:30:46 server application: Started successfully
01/15/2024 10:30:47 backup_service: Backup completed
Jan 15 10:30:48 MacBook-Pro sshd[123]: Connection established"""
        
        events = self.parser.parse_log_entries(log_content, self.sample_raw_log_id)
        
        assert len(events) == 4
        
        # Check that different timestamp formats are handled
        timestamps = [event.timestamp for event in events]
        assert all(ts.day == 15 for ts in timestamps)
        assert all(ts.month == 1 for ts in timestamps)
        
        # Check that different sources are preserved
        sources = [event.source for event in events]
        assert "MacBook-Pro:kernel[0]" in sources
        assert any("server" in source or "application" in source for source in sources)
        assert any("backup_service" in source for source in sources)
        assert "MacBook-Pro:sshd[123]" in sources