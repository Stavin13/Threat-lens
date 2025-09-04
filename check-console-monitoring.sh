#!/bin/bash

echo "📊 ThreatLens Console Monitoring Status"
echo "======================================="

# Check if backend is running
if curl -s http://localhost:8000/health-simple > /dev/null; then
    echo "✅ ThreatLens Backend: Running"
else
    echo "❌ ThreatLens Backend: Not running"
    exit 1
fi

# Check if console monitor is running
if pgrep -f "simple-console-monitor.sh --continuous" > /dev/null; then
    echo "✅ Console Monitor: Running"
    
    # Show recent monitor activity
    echo ""
    echo "📋 Recent Monitor Activity:"
    tail -5 console-monitor.log | grep -E "(Monitoring cycle|Successfully sent|Total events)"
else
    echo "❌ Console Monitor: Not running"
    echo "💡 Start with: ./simple-console-monitor.sh --continuous"
fi

# Get current event statistics
echo ""
echo "📈 Current Event Statistics:"
stats=$(curl -s "http://localhost:8000/events" | jq '{total: .total, events_shown: (.events | length)}' 2>/dev/null)
echo "$stats"

# Show recent events by category
echo ""
echo "🏷️  Recent Events by Category:"
curl -s "http://localhost:8000/events?per_page=20" | jq -r '.events[] | "\(.category): \(.message[0:60])..."' 2>/dev/null | sort | uniq -c | sort -nr

echo ""
echo "🌐 View full dashboard at: http://localhost:8000/docs"