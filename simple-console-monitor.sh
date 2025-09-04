#!/bin/bash

echo "🔍 Simple Console Log Monitor for ThreatLens"
echo "============================================="

# Function to capture and send recent Console logs
capture_and_send() {
    echo "📥 Capturing recent Console logs..."
    
    # Get logs from the last 5 minutes using the macOS log command
    # Focus on security-related events to keep the volume manageable
    recent_logs=$(log show --style syslog --last 5m --predicate 'eventMessage CONTAINS "failed" OR eventMessage CONTAINS "denied" OR eventMessage CONTAINS "error" OR eventMessage CONTAINS "authentication" OR eventMessage CONTAINS "login" OR process == "sshd" OR process == "sudo"' 2>/dev/null | head -100)
    
    if [ -z "$recent_logs" ]; then
        echo "ℹ️  No recent security-related logs found"
        return
    fi
    
    # Count the lines
    line_count=$(echo "$recent_logs" | wc -l | tr -d ' ')
    echo "✅ Captured $line_count log lines"
    
    # Send to ThreatLens
    echo "📤 Sending to ThreatLens..."
    response=$(curl -s -X POST http://localhost:8000/ingest-log \
        -F "content=$recent_logs" \
        -F "source=console_monitor_$(date +%s)")
    
    if echo "$response" | grep -q "raw_log_id"; then
        raw_log_id=$(echo "$response" | jq -r '.raw_log_id' 2>/dev/null)
        echo "✅ Successfully sent logs to ThreatLens"
        echo "   Raw Log ID: $raw_log_id"
        
        # Wait a moment for processing
        sleep 3
        
        # Check if events were created
        events=$(curl -s "http://localhost:8000/events?per_page=5" | jq '.total' 2>/dev/null)
        echo "📊 Total events in database: $events"
        
    else
        echo "❌ Failed to send logs to ThreatLens"
        echo "   Response: $response"
    fi
}

# Check if ThreatLens is running
echo "🔍 Checking ThreatLens status..."
if ! curl -s http://localhost:8000/health-simple > /dev/null; then
    echo "❌ ThreatLens is not running on http://localhost:8000"
    echo "   Please start ThreatLens first with: ./start-backend.sh"
    exit 1
fi

echo "✅ ThreatLens is running"

# Run once or continuously based on argument
if [ "$1" = "--continuous" ]; then
    echo "🔄 Starting continuous monitoring (every 30 seconds)..."
    echo "   Press Ctrl+C to stop"
    
    while true; do
        echo ""
        echo "$(date): Monitoring cycle"
        capture_and_send
        echo "⏳ Waiting 30 seconds..."
        sleep 30
    done
else
    echo "🔍 Running single capture..."
    capture_and_send
    echo ""
    echo "💡 To run continuously, use: $0 --continuous"
fi