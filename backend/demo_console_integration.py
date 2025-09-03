#!/usr/bin/env python3
"""
Demo script showing Console log integration with ThreatLens.
"""

import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent))

from app.parser import LogParser
from app.schemas import EventCategory

def demo_console_parsing():
    """Demonstrate Console log parsing capabilities."""
    
    print("🔍 ThreatLens Console Integration Demo")
    print("=" * 50)
    
    # Sample Console logs from your screenshot
    console_logs = """11:28:24.138308+0200 powerd DestinationCheck check on battery 8
11:28:24.234174+0200 WindowsApp [Info] Process button state click event SenderID:0x1000000c6
11:28:24.270904+0200 bluetoothd BLE Scanner Device found: 0xDC2C6E-A108-3948-B99F9A9D9A9A
11:28:25.123456+0200 sshd[1234] Failed password for invalid user admin from 192.168.1.100 port 22 ssh2
11:28:26.789012+0200 sudo user1 : TTY=ttys000 ; PWD=/Users/user1 ; USER=root ; COMMAND=/bin/ls
11:28:27.456789+0200 loginwindow[45] Login Window Application Started
11:28:28.111222+0200 kernel[0] CODE SIGNING: cs_invalid_page(0x1000): p=1789[GoogleChrome] denying page sending SIGKILL"""
    
    print("📥 Sample Console Logs:")
    for i, line in enumerate(console_logs.strip().split('\n'), 1):
        print(f"  {i}. {line}")
    
    print(f"\n🔬 Parsing with ThreatLens...")
    
    parser = LogParser()
    events = parser.parse_log_entries(console_logs, "demo_console_log")
    
    print(f"✅ Successfully parsed {len(events)} events")
    print(f"📊 Parsing stats: {parser.get_parsing_stats()}")
    
    print(f"\n📋 Parsed Events:")
    for i, event in enumerate(events, 1):
        print(f"\n{i}. {event.source}")
        print(f"   🕐 Time: {event.timestamp.strftime('%H:%M:%S.%f')[:-3]} UTC")
        print(f"   📂 Category: {event.category.value}")
        print(f"   💬 Message: {event.message}")
        
        # Highlight security events
        if event.category in [EventCategory.AUTH, EventCategory.SECURITY]:
            print(f"   🚨 SECURITY EVENT DETECTED!")
    
    # Show threat analysis
    print(f"\n🔍 Threat Analysis:")
    
    auth_events = [e for e in events if e.category == EventCategory.AUTH]
    system_events = [e for e in events if e.category == EventCategory.SYSTEM]
    security_keywords = ['failed', 'denied', 'invalid', 'sigkill', 'error']
    
    suspicious_events = []
    for event in events:
        if any(keyword in event.message.lower() for keyword in security_keywords):
            suspicious_events.append(event)
    
    print(f"   🔐 Authentication Events: {len(auth_events)}")
    print(f"   ⚙️  System Events: {len(system_events)}")
    print(f"   ⚠️  Suspicious Events: {len(suspicious_events)}")
    
    if suspicious_events:
        print(f"\n🚨 Suspicious Activity Detected:")
        for event in suspicious_events:
            print(f"   • {event.source}: {event.message}")
    
    print(f"\n🌐 Next Steps:")
    print(f"   1. Use scripts/console_integration.py for live integration")
    print(f"   2. Set up automated monitoring with cron jobs")
    print(f"   3. Configure real-time alerts for security events")
    print(f"   4. View detailed analysis in ThreatLens dashboard")

if __name__ == "__main__":
    demo_console_parsing()