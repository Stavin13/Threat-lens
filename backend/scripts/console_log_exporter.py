#!/usr/bin/env python3
"""
macOS Console Log Exporter for ThreatLens

This script helps export Console logs and integrate them with ThreatLens.
It can export logs from the Console app or use the 'log' command to capture
system logs directly.
"""

import subprocess
import sys
import os
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

def run_log_command(
    predicate: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    process: Optional[str] = None,
    subsystem: Optional[str] = None,
    category: Optional[str] = None,
    level: str = "default"
) -> str:
    """
    Run the macOS 'log' command to capture system logs.
    
    Args:
        predicate: Custom predicate for filtering
        start_time: Start time in format 'YYYY-MM-DD HH:MM:SS'
        end_time: End time in format 'YYYY-MM-DD HH:MM:SS'
        process: Filter by process name
        subsystem: Filter by subsystem
        category: Filter by category
        level: Log level (default, info, debug)
        
    Returns:
        Raw log output as string
    """
    cmd = ["log", "show", "--style", "syslog"]
    
    # Add time range if specified
    if start_time:
        cmd.extend(["--start", start_time])
    if end_time:
        cmd.extend(["--end", end_time])
    
    # Add filters
    if process:
        cmd.extend(["--process", process])
    if subsystem:
        cmd.extend(["--subsystem", subsystem])
    if category:
        cmd.extend(["--category", category])
    
    # Add log level flags (macOS uses --info and --debug flags, not --level)
    if level == "info":
        cmd.append("--info")
    elif level == "debug":
        cmd.extend(["--info", "--debug"])
    # For "default" level, don't add any flags (shows default level messages only)
    
    # Add custom predicate if specified
    if predicate:
        cmd.extend(["--predicate", predicate])
    
    try:
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print(f"Error running log command: {result.stderr}")
            return ""
        
        return result.stdout
    
    except subprocess.TimeoutExpired:
        print("Log command timed out after 60 seconds")
        return ""
    except Exception as e:
        print(f"Error running log command: {e}")
        return ""

def export_recent_logs(hours: int = 1) -> str:
    """
    Export recent system logs from the last N hours.
    
    Args:
        hours: Number of hours to look back
        
    Returns:
        Raw log content
    """
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"Exporting logs from {start_str} to {end_str}")
    
    return run_log_command(start_time=start_str, end_time=end_str)

def export_security_logs(hours: int = 24) -> str:
    """
    Export security-related logs from the last N hours.
    
    Args:
        hours: Number of hours to look back
        
    Returns:
        Raw log content
    """
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Security-focused predicate
    predicate = (
        'eventMessage CONTAINS "authentication" OR '
        'eventMessage CONTAINS "login" OR '
        'eventMessage CONTAINS "password" OR '
        'eventMessage CONTAINS "sudo" OR '
        'eventMessage CONTAINS "ssh" OR '
        'eventMessage CONTAINS "failed" OR '
        'eventMessage CONTAINS "denied" OR '
        'eventMessage CONTAINS "blocked" OR '
        'eventMessage CONTAINS "security" OR '
        'eventMessage CONTAINS "violation" OR '
        'process == "sshd" OR '
        'process == "sudo" OR '
        'process == "loginwindow" OR '
        'subsystem == "com.apple.security"'
    )
    
    print(f"Exporting security logs from {start_str} to {end_str}")
    
    return run_log_command(
        predicate=predicate,
        start_time=start_str,
        end_time=end_str,
        level="info"
    )

def export_process_logs(process_name: str, hours: int = 1) -> str:
    """
    Export logs for a specific process.
    
    Args:
        process_name: Name of the process to filter by
        hours: Number of hours to look back
        
    Returns:
        Raw log content
    """
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"Exporting logs for process '{process_name}' from {start_str} to {end_str}")
    
    return run_log_command(
        process=process_name,
        start_time=start_str,
        end_time=end_str
    )

def save_logs_to_file(content: str, filename: str) -> str:
    """
    Save log content to a file.
    
    Args:
        content: Log content to save
        filename: Output filename
        
    Returns:
        Full path to saved file
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path("data/console_logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Add timestamp to filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = Path(filename).stem
    extension = Path(filename).suffix or ".log"
    
    output_file = logs_dir / f"{base_name}_{timestamp}{extension}"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Logs saved to: {output_file}")
    return str(output_file)

def main():
    """Main function with command-line interface."""
    parser = argparse.ArgumentParser(
        description="Export macOS Console logs for ThreatLens analysis"
    )
    
    parser.add_argument(
        "--mode", 
        choices=["recent", "security", "process", "custom"],
        default="recent",
        help="Export mode (default: recent)"
    )
    
    parser.add_argument(
        "--hours",
        type=int,
        default=1,
        help="Number of hours to look back (default: 1)"
    )
    
    parser.add_argument(
        "--process",
        type=str,
        help="Process name to filter by (for process mode)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="console_export.log",
        help="Output filename (default: console_export.log)"
    )
    
    parser.add_argument(
        "--predicate",
        type=str,
        help="Custom predicate for filtering (for custom mode)"
    )
    
    parser.add_argument(
        "--level",
        choices=["default", "info", "debug"],
        default="default",
        help="Log level (default: default)"
    )
    
    args = parser.parse_args()
    
    # Export logs based on mode
    content = ""
    
    if args.mode == "recent":
        content = export_recent_logs(args.hours)
    elif args.mode == "security":
        content = export_security_logs(args.hours)
    elif args.mode == "process":
        if not args.process:
            print("Error: --process is required for process mode")
            sys.exit(1)
        content = export_process_logs(args.process, args.hours)
    elif args.mode == "custom":
        if not args.predicate:
            print("Error: --predicate is required for custom mode")
            sys.exit(1)
        
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=args.hours)
        start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        content = run_log_command(
            predicate=args.predicate,
            start_time=start_str,
            end_time=end_str,
            level=args.level
        )
    
    if not content.strip():
        print("No logs found or error occurred during export")
        sys.exit(1)
    
    # Save to file
    output_path = save_logs_to_file(content, args.output)
    
    # Print summary
    lines = content.strip().split('\n')
    print(f"\nExport Summary:")
    print(f"- Total lines: {len(lines)}")
    print(f"- Output file: {output_path}")
    print(f"- File size: {len(content)} bytes")
    
    print(f"\nTo analyze with ThreatLens, you can:")
    print(f"1. Upload the file through the web interface")
    print(f"2. Use the API: curl -X POST -F 'file=@{output_path}' http://localhost:8000/api/ingest/file")
    print(f"3. Copy and paste the content into the text input")

if __name__ == "__main__":
    main()