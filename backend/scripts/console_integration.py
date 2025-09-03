#!/usr/bin/env python3
"""
Console Integration Script for ThreatLens

This script provides easy integration with macOS Console logs.
It can capture logs and send them directly to ThreatLens for analysis.
"""

import requests
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from console_log_exporter import export_recent_logs, export_security_logs, export_process_logs

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

def send_to_threatlens(content: str, source: str = "console", api_url: str = "http://localhost:8000") -> dict:
    """
    Send log content to ThreatLens for analysis.
    
    Args:
        content: Log content to analyze
        source: Source identifier for the logs
        api_url: ThreatLens API base URL
        
    Returns:
        Response from ThreatLens API
    """
    try:
        # Send to ingestion endpoint (using form data)
        response = requests.post(
            f"{api_url}/ingest-log",
            data={
                "content": content,
                "source": source
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Successfully sent logs to ThreatLens")
            print(f"   Raw Log ID: {result.get('raw_log_id')}")
            print(f"   Message: {result.get('message')}")
            return result
        else:
            print(f"❌ Error sending logs to ThreatLens: {response.status_code}")
            print(f"   Response: {response.text}")
            return {"error": f"HTTP {response.status_code}: {response.text}"}
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to ThreatLens. Make sure it's running on http://localhost:8000")
        return {"error": "Connection failed"}
    except Exception as e:
        print(f"❌ Error sending logs to ThreatLens: {e}")
        return {"error": str(e)}

def trigger_analysis(raw_log_id: str, api_url: str = "http://localhost:8000") -> dict:
    """
    Trigger analysis of ingested logs.
    
    Args:
        raw_log_id: ID of the raw log to analyze
        api_url: ThreatLens API base URL
        
    Returns:
        Analysis results
    """
    try:
        # Trigger processing (parsing and analysis are handled automatically in background)
        process_response = requests.post(
            f"{api_url}/trigger-processing/{raw_log_id}",
            timeout=60
        )
        
        if process_response.status_code != 200:
            print(f"❌ Error triggering processing: {process_response.status_code}")
            return {"error": f"Processing failed: {process_response.text}"}
        
        process_result = process_response.json()
        print(f"✅ Processing triggered successfully")
        
        # Wait a moment for processing to complete
        import time
        print("⏳ Waiting for processing to complete...")
        time.sleep(3)
        
        return {
            "process_result": process_result
        }
        
    except Exception as e:
        print(f"❌ Error during processing: {e}")
        return {"error": str(e)}

def get_analysis_results(raw_log_id: str, api_url: str = "http://localhost:8000") -> dict:
    """
    Get analysis results for a raw log.
    
    Args:
        raw_log_id: ID of the raw log
        api_url: ThreatLens API base URL
        
    Returns:
        Analysis results
    """
    try:
        # Get events with filtering by raw_log_id (using query parameter)
        response = requests.get(
            f"{api_url}/events",
            params={"per_page": 100},  # Get more events to find our raw_log_id
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            # Filter events by raw_log_id
            matching_events = [
                event for event in data.get("events", [])
                if event.get("raw_log_id") == raw_log_id
            ]
            return {"events": matching_events}
        else:
            print(f"❌ Error getting results: {response.status_code}")
            return {"error": f"HTTP {response.status_code}: {response.text}"}
            
    except Exception as e:
        print(f"❌ Error getting results: {e}")
        return {"error": str(e)}

def print_threat_summary(results: dict):
    """Print a summary of detected threats."""
    events = results.get("events", [])
    if not events:
        print("ℹ️  No events found")
        return
    
    print(f"\n📊 Analysis Summary:")
    print(f"   Total Events: {len(events)}")
    
    # Count by category
    categories = {}
    threat_levels = {}
    
    for event in events:
        category = event.get("category", "unknown")
        categories[category] = categories.get(category, 0) + 1
        
        # Check for threat indicators (you might want to adjust this based on your schema)
        if any(keyword in event.get("message", "").lower() for keyword in 
               ["failed", "denied", "error", "attack", "suspicious", "blocked"]):
            threat_levels["potential_threat"] = threat_levels.get("potential_threat", 0) + 1
        else:
            threat_levels["normal"] = threat_levels.get("normal", 0) + 1
    
    print(f"\n📈 Event Categories:")
    for category, count in sorted(categories.items()):
        print(f"   {category}: {count}")
    
    print(f"\n🚨 Threat Assessment:")
    for level, count in sorted(threat_levels.items()):
        print(f"   {level}: {count}")
    
    # Show recent suspicious events
    suspicious_events = [
        event for event in events[-10:]  # Last 10 events
        if any(keyword in event.get("message", "").lower() for keyword in 
               ["failed", "denied", "error", "attack", "suspicious", "blocked"])
    ]
    
    if suspicious_events:
        print(f"\n⚠️  Recent Suspicious Events:")
        for event in suspicious_events[:5]:  # Show top 5
            timestamp = event.get("timestamp", "unknown")
            source = event.get("source", "unknown")
            message = event.get("message", "")[:100] + "..." if len(event.get("message", "")) > 100 else event.get("message", "")
            print(f"   {timestamp} | {source} | {message}")

def main():
    """Main integration function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Integrate macOS Console logs with ThreatLens"
    )
    
    parser.add_argument(
        "--mode",
        choices=["recent", "security", "process"],
        default="recent",
        help="Type of logs to capture (default: recent)"
    )
    
    parser.add_argument(
        "--hours",
        type=int,
        default=1,
        help="Hours of logs to capture (default: 1)"
    )
    
    parser.add_argument(
        "--process",
        type=str,
        help="Process name to filter (for process mode)"
    )
    
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="ThreatLens API URL (default: http://localhost:8000)"
    )
    
    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="Skip automatic analysis (just ingest)"
    )
    
    args = parser.parse_args()
    
    print("🔍 ThreatLens Console Integration")
    print("=" * 40)
    
    # Capture logs based on mode
    print(f"📥 Capturing {args.mode} logs from last {args.hours} hour(s)...")
    
    content = ""
    source = f"console_{args.mode}"
    
    if args.mode == "recent":
        content = export_recent_logs(args.hours)
    elif args.mode == "security":
        content = export_security_logs(args.hours)
        source = "console_security"
    elif args.mode == "process":
        if not args.process:
            print("❌ --process is required for process mode")
            sys.exit(1)
        content = export_process_logs(args.process, args.hours)
        source = f"console_{args.process}"
    
    if not content.strip():
        print("❌ No logs captured. Try increasing --hours or check your system.")
        sys.exit(1)
    
    lines = content.strip().split('\n')
    print(f"✅ Captured {len(lines)} log lines")
    
    # Send to ThreatLens
    print(f"\n📤 Sending logs to ThreatLens ({args.api_url})...")
    result = send_to_threatlens(content, source, args.api_url)
    
    if "error" in result:
        print("❌ Failed to send logs to ThreatLens")
        sys.exit(1)
    
    raw_log_id = result.get("raw_log_id")
    if not raw_log_id:
        print("❌ No raw_log_id received")
        sys.exit(1)
    
    if args.no_analysis:
        print(f"✅ Logs ingested successfully. Raw Log ID: {raw_log_id}")
        print("ℹ️  Skipping analysis (--no-analysis flag)")
        return
    
    # Trigger analysis
    print(f"\n🔬 Analyzing logs...")
    analysis_result = trigger_analysis(raw_log_id, args.api_url)
    
    if "error" in analysis_result:
        print("❌ Analysis failed")
        return
    
    # Get and display results
    print(f"\n📋 Getting analysis results...")
    results = get_analysis_results(raw_log_id, args.api_url)
    
    if "error" not in results:
        print_threat_summary(results)
    
    print(f"\n🌐 View detailed results at: {args.api_url}/dashboard")
    print(f"📊 Raw Log ID: {raw_log_id}")

if __name__ == "__main__":
    main()