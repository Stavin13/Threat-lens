"""
Test Data Fixtures for ThreatLens Integration Tests

Provides realistic test data including various log formats, edge cases,
and performance testing datasets.
"""
from datetime import datetime, timedelta
from typing import Dict, List
import random


class TestDataFixtures:
    """Provides test data for various log formats and scenarios."""
    
    def get_macos_system_log(self) -> str:
        """Get realistic macOS system.log content."""
        return """Jan 15 10:30:45 MacBook-Pro kernel[0]: System boot completed successfully
Jan 15 10:31:02 MacBook-Pro loginwindow[123]: User john logged in successfully
Jan 15 10:31:15 MacBook-Pro sshd[456]: Failed password for admin from 192.168.1.100 port 22 ssh2
Jan 15 10:31:30 MacBook-Pro SecurityAgent[789]: Authentication failed for user admin
Jan 15 10:32:00 MacBook-Pro networkd[101]: Network interface en0 connected to WiFi network 'HomeNetwork'
Jan 15 10:32:15 MacBook-Pro kernel[0]: Memory pressure warning - available memory below threshold
Jan 15 10:32:30 MacBook-Pro securityd[202]: Certificate validation failed for com.suspicious.app"""
    
    def get_macos_auth_log(self) -> str:
        """Get realistic macOS auth.log content."""
        return """Jan 15 10:30:45 MacBook-Pro authd[789]: Authentication successful for user 'john'
Jan 15 10:31:00 MacBook-Pro sshd[456]: Failed login attempt from 192.168.1.100
Jan 15 10:31:15 MacBook-Pro SecurityAgent[123]: User authentication denied for 'admin'
Jan 15 10:31:30 MacBook-Pro sudo[654]: john : TTY=ttys000 ; PWD=/Users/john ; USER=root ; COMMAND=/bin/ls
Jan 15 10:31:45 MacBook-Pro authd[789]: Password change successful for user 'john'"""
    
    def get_mixed_log_formats(self) -> str:
        """Get mixed log formats in single content."""
        return """Jan 15 10:30:45 MacBook-Pro kernel[0]: System startup initiated
Jan 15 10:31:00 server01 sshd[1234]: Failed password for root from 10.0.0.1 port 22 ssh2
2024-01-15T10:31:15Z nginx[567]: 192.168.1.50 - - [15/Jan/2024:10:31:15 +0000] "GET /admin HTTP/1.1" 401 1234
Jan 15 10:31:30 MacBook-Pro SecurityAgent[789]: Authentication failed for user admin
[2024-01-15 10:31:45] ERROR: Database connection failed - timeout after 30s
Jan 15 10:32:00 MacBook-Pro networkd[101]: Suspicious network activity detected from 192.168.1.200"""
    
    def get_comprehensive_log_sample(self) -> str:
        """Get comprehensive log sample for report generation testing."""
        return """Jan 15 08:00:00 MacBook-Pro kernel[0]: System boot completed
Jan 15 08:15:30 MacBook-Pro loginwindow[123]: User alice logged in successfully
Jan 15 09:22:15 MacBook-Pro sshd[456]: Failed password for root from 203.0.113.1 port 22 ssh2
Jan 15 09:22:20 MacBook-Pro sshd[456]: Failed password for root from 203.0.113.1 port 22 ssh2
Jan 15 09:22:25 MacBook-Pro sshd[456]: Failed password for root from 203.0.113.1 port 22 ssh2
Jan 15 10:45:12 MacBook-Pro SecurityAgent[789]: Authentication failed for user admin
Jan 15 11:30:00 MacBook-Pro securityd[202]: Suspicious certificate detected for unknown.malware.com
Jan 15 12:15:45 MacBook-Pro networkd[101]: Unusual network traffic pattern detected
Jan 15 14:20:30 MacBook-Pro kernel[0]: Memory pressure warning - system performance may be affected
Jan 15 15:45:00 MacBook-Pro authd[321]: Successful authentication for user alice
Jan 15 16:30:15 MacBook-Pro sshd[789]: Accepted publickey for alice from 192.168.1.50 port 22 ssh2
Jan 15 17:00:00 MacBook-Pro SecurityAgent[456]: Screen lock activated"""
    
    def get_problematic_log_content(self) -> str:
        """Get log content with various problematic entries."""
        return """Jan 15 10:30:45 MacBook-Pro test[123]: Normal log entry
This is not a valid log entry format at all
Jan 15 10:31:00 MacBook-Pro kernel[0]: Another normal entry with unicode: café résumé naïve
Invalid entry without proper timestamp or format
Jan 15 10:31:15 MacBook-Pro app[456]: Entry with special chars: !@#$%^&*()[]{}|\\:";'<>?,./
Jan 15 10:31:30 MacBook-Pro test[789]: Very long entry: """ + "x" * 500 + """
Jan 15 10:31:45 MacBook-Pro test[101]: Entry that might cause_failure in analysis
Jan 15 10:32:00 MacBook-Pro test[202]: Final normal entry"""
    
    def get_edge_case_logs(self) -> Dict[str, str]:
        """Get various edge case log formats."""
        return {
            "empty_lines": """Jan 15 10:30:45 MacBook-Pro test[123]: Entry 1

Jan 15 10:31:00 MacBook-Pro test[456]: Entry 2

""",
            "unicode_content": """Jan 15 10:30:45 MacBook-Pro test[123]: Unicode test: 你好世界 🔒 🚨
Jan 15 10:31:00 MacBook-Pro test[456]: Emoji test: 🔐 🛡️ ⚠️ 🚫
Jan 15 10:31:15 MacBook-Pro test[789]: Special chars: àáâãäåæçèéêë""",
            "very_long_lines": """Jan 15 10:30:45 MacBook-Pro test[123]: """ + "Very long log entry " * 100,
            "malformed_timestamps": """Invalid timestamp format: MacBook-Pro test[123]: Entry 1
Jan 32 25:70:99 MacBook-Pro test[456]: Invalid date/time
Jan 15 10:30:45 MacBook-Pro test[789]: Valid entry after invalid ones""",
            "missing_components": """Jan 15 10:30:45 : Missing source
Jan 15 10:31:00 MacBook-Pro : Missing process info
: Missing everything except message""",
            "json_in_logs": """Jan 15 10:30:45 MacBook-Pro app[123]: {"event": "login", "user": "test", "status": "success"}
Jan 15 10:31:00 MacBook-Pro app[456]: {"event": "error", "message": "Database connection failed", "code": 500}""",
            "xml_in_logs": """Jan 15 10:30:45 MacBook-Pro app[123]: <event><type>security</type><message>Access denied</message></event>
Jan 15 10:31:00 MacBook-Pro app[456]: <log level="error">System failure detected</log>"""
        }
    
    def generate_large_log_dataset(self, num_entries: int) -> str:
        """Generate large log dataset for performance testing."""
        entries = []
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        
        sources = ["kernel", "sshd", "authd", "SecurityAgent", "networkd", "securityd", "loginwindow"]
        categories = ["system", "auth", "network", "security", "application"]
        
        message_templates = {
            "system": [
                "System boot completed",
                "Memory pressure warning",
                "Disk space low on volume /",
                "Process {} terminated unexpectedly",
                "System performance degraded"
            ],
            "auth": [
                "User {} logged in successfully",
                "Failed password for {} from {}",
                "Authentication successful for user {}",
                "User {} logged out",
                "Password change for user {}"
            ],
            "network": [
                "Network interface {} connected",
                "Suspicious network activity from {}",
                "Connection established to {}",
                "Network timeout for {}",
                "Firewall blocked connection from {}"
            ],
            "security": [
                "Certificate validation failed",
                "Suspicious activity detected",
                "Security policy violation",
                "Malware signature detected",
                "Access denied for resource {}"
            ],
            "application": [
                "Application {} started",
                "Application {} crashed",
                "Service {} restarted",
                "Configuration updated for {}",
                "Performance alert for {}"
            ]
        }
        
        for i in range(num_entries):
            # Generate timestamp
            timestamp = base_time + timedelta(seconds=i * 2)
            time_str = timestamp.strftime("%b %d %H:%M:%S")
            
            # Select random components
            source = random.choice(sources)
            pid = random.randint(100, 9999)
            category = random.choice(categories)
            
            # Generate message
            template = random.choice(message_templates[category])
            if "{}" in template:
                if category == "auth":
                    message = template.format(f"user{i % 10}")
                elif category == "network":
                    message = template.format(f"192.168.1.{i % 255}")
                else:
                    message = template.format(f"service{i % 5}")
            else:
                message = template
            
            # Create log entry
            entry = f"{time_str} MacBook-Pro {source}[{pid}]: {message}"
            entries.append(entry)
        
        return "\n".join(entries)
    
    def get_sample_log_entry(self, index: int) -> str:
        """Get a single sample log entry for concurrent testing."""
        timestamp = f"Jan 15 10:30:{index % 60:02d}"
        pid = 1000 + index
        messages = [
            "User authentication successful",
            "Network connection established",
            "System process started",
            "Security check completed",
            "Application event logged"
        ]
        
        message = messages[index % len(messages)]
        return f"{timestamp} MacBook-Pro test[{pid}]: {message} - entry {index}"
    
    def get_websocket_test_events(self) -> List[Dict]:
        """Get sample events for WebSocket testing."""
        return [
            {
                "id": "ws-event-1",
                "timestamp": "2024-01-15T10:30:45Z",
                "source": "test-source",
                "message": "WebSocket test event 1",
                "category": "system",
                "severity": 3
            },
            {
                "id": "ws-event-2", 
                "timestamp": "2024-01-15T10:31:00Z",
                "source": "test-source",
                "message": "WebSocket test event 2",
                "category": "auth",
                "severity": 7
            }
        ]
    
    def get_report_test_data(self) -> str:
        """Get log data specifically designed for report generation testing."""
        return """Jan 15 06:00:00 MacBook-Pro kernel[0]: System startup - daily operations begin
Jan 15 08:30:15 MacBook-Pro loginwindow[123]: User alice logged in successfully
Jan 15 09:15:30 MacBook-Pro sshd[456]: Failed password for root from 203.0.113.1 port 22 ssh2
Jan 15 09:15:35 MacBook-Pro sshd[456]: Failed password for root from 203.0.113.1 port 22 ssh2
Jan 15 09:15:40 MacBook-Pro sshd[456]: Failed password for root from 203.0.113.1 port 22 ssh2
Jan 15 10:22:10 MacBook-Pro SecurityAgent[789]: Authentication failed for user admin
Jan 15 11:45:20 MacBook-Pro securityd[202]: Suspicious certificate detected for malicious.example.com
Jan 15 12:30:00 MacBook-Pro networkd[101]: Unusual network traffic pattern detected
Jan 15 13:15:45 MacBook-Pro kernel[0]: Memory pressure warning - system performance affected
Jan 15 14:00:30 MacBook-Pro authd[321]: Successful authentication for user bob
Jan 15 15:30:15 MacBook-Pro sshd[789]: Accepted publickey for alice from 192.168.1.50 port 22 ssh2
Jan 15 16:45:00 MacBook-Pro SecurityAgent[456]: Screen lock activated
Jan 15 17:30:20 MacBook-Pro securityd[202]: Security policy violation detected
Jan 15 18:15:10 MacBook-Pro networkd[101]: Firewall blocked suspicious connection from 198.51.100.1
Jan 15 19:00:00 MacBook-Pro authd[321]: User alice logged out
Jan 15 20:30:45 MacBook-Pro kernel[0]: System performance normal - daily operations complete"""
    
    def get_ai_analysis_test_scenarios(self) -> List[Dict]:
        """Get scenarios for testing AI analysis integration."""
        return [
            {
                "log_entry": "Jan 15 10:30:45 MacBook-Pro sshd[456]: Failed password for root from 203.0.113.1 port 22 ssh2",
                "expected_severity_range": (7, 9),
                "expected_category": "auth",
                "should_contain": ["brute force", "attack", "security"]
            },
            {
                "log_entry": "Jan 15 10:31:00 MacBook-Pro kernel[0]: System boot completed successfully",
                "expected_severity_range": (1, 3),
                "expected_category": "system", 
                "should_contain": ["normal", "startup", "system"]
            },
            {
                "log_entry": "Jan 15 10:31:15 MacBook-Pro securityd[202]: Certificate validation failed for malicious.example.com",
                "expected_severity_range": (6, 8),
                "expected_category": "security",
                "should_contain": ["certificate", "validation", "security"]
            },
            {
                "log_entry": "Jan 15 10:31:30 MacBook-Pro networkd[101]: Unusual network traffic pattern detected",
                "expected_severity_range": (5, 7),
                "expected_category": "network",
                "should_contain": ["network", "traffic", "unusual"]
            }
        ]
    
    def get_performance_test_scenarios(self) -> Dict[str, Dict]:
        """Get scenarios for performance testing."""
        return {
            "small_batch": {
                "entries": 100,
                "expected_processing_time": 10,
                "expected_ingestion_time": 2
            },
            "medium_batch": {
                "entries": 500,
                "expected_processing_time": 30,
                "expected_ingestion_time": 5
            },
            "large_batch": {
                "entries": 1000,
                "expected_processing_time": 60,
                "expected_ingestion_time": 10
            }
        }
    
    def get_concurrent_test_data(self, num_threads: int) -> List[str]:
        """Get test data for concurrent processing tests."""
        data = []
        for i in range(num_threads):
            log_content = f"""Jan 15 10:30:{i:02d} MacBook-Pro test[{1000+i}]: Concurrent test entry {i}
Jan 15 10:31:{i:02d} MacBook-Pro auth[{2000+i}]: Authentication event {i}
Jan 15 10:32:{i:02d} MacBook-Pro network[{3000+i}]: Network event {i}"""
            data.append(log_content)
        return data
    
    def get_error_simulation_data(self) -> Dict[str, str]:
        """Get data for error simulation and recovery testing."""
        return {
            "parsing_errors": """Invalid log format without timestamp
Jan 15 10:30:45 MacBook-Pro test[123]: Valid entry
Another invalid entry
Jan 15 10:31:00 MacBook-Pro test[456]: Another valid entry""",
            
            "ai_analysis_failures": """Jan 15 10:30:45 MacBook-Pro test[123]: Normal entry
Jan 15 10:31:00 MacBook-Pro test[456]: Entry that causes AI failure
Jan 15 10:31:15 MacBook-Pro test[789]: Another normal entry""",
            
            "database_stress": """Jan 15 10:30:45 MacBook-Pro test[123]: Database stress test entry 1
Jan 15 10:30:46 MacBook-Pro test[124]: Database stress test entry 2
Jan 15 10:30:47 MacBook-Pro test[125]: Database stress test entry 3""",
            
            "memory_pressure": "Jan 15 10:30:45 MacBook-Pro test[123]: " + "Large memory test " * 1000
        }