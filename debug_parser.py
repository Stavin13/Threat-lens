#!/usr/bin/env python3

import sys
import os
sys.path.append('backend')

from app.parser import LogParser
from datetime import datetime, timezone

# Test the parser with the same log entry from the test script
test_log = "Sep 15 10:30:45 server sshd[1234]: Failed password for invalid user admin from 192.168.1.100 port 22 ssh2"

parser = LogParser()
print(f"Current time: {datetime.now(timezone.utc)}")
print(f"Test log: {test_log}")

try:
    events = parser.parse_log_entries(test_log, "test-id")
    print(f"Parsed {len(events)} events")
    for event in events:
        print(f"Event timestamp: {event.timestamp}")
        print(f"Event source: {event.source}")
        print(f"Event message: {event.message}")
        print(f"Event category: {event.category}")
except Exception as e:
    print(f"Error: {e}")
    
    # Let's try to parse just the timestamp part
    try:
        timestamp_str = "Sep 15 10:30:45"
        parsed_ts = parser._parse_timestamp(timestamp_str)
        print(f"Parsed timestamp: {parsed_ts}")
        
        # Check if it's in the future
        now = datetime.now(timezone.utc)
        print(f"Now: {now}")
        print(f"Difference: {parsed_ts - now}")
        print(f"Is future: {parsed_ts > now}")
        
        from datetime import timedelta
        future_limit = now + timedelta(hours=6)
        print(f"Future limit: {future_limit}")
        print(f"Exceeds limit: {parsed_ts > future_limit}")
        
    except Exception as e2:
        print(f"Timestamp parsing error: {e2}")