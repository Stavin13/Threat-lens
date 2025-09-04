#!/bin/bash

echo "🔧 Testing Backend Processing Fix"
echo "================================="

echo "1. Adding a test log entry..."
response=$(curl -s -X POST http://localhost:8000/ingest-log \
  -F "content=Sep 15 10:30:45 server sshd[1234]: Failed password for invalid user admin from 192.168.1.100 port 22 ssh2" \
  -F "source=test_processing_fix")

echo "Response: $response"

# Extract raw_log_id from response
raw_log_id=$(echo "$response" | jq -r '.raw_log_id' 2>/dev/null)

if [ "$raw_log_id" != "null" ] && [ -n "$raw_log_id" ]; then
    echo "✅ Log ingested with ID: $raw_log_id"
    
    echo "2. Waiting for background processing..."
    sleep 10
    
    echo "3. Checking if events were created..."
    events=$(curl -s "http://localhost:8000/events" | jq '.total' 2>/dev/null)
    echo "Total events in database: $events"
    
    echo "4. Checking processing stats..."
    curl -s "http://localhost:8000/stats" | jq '.processing' 2>/dev/null
    
    if [ "$events" -gt 0 ]; then
        echo "🎉 SUCCESS! Events are being processed correctly!"
        echo "5. Checking the latest events..."
        curl -s "http://localhost:8000/events?per_page=3" | jq '.events[] | {id, category, message: .message[0:100]}' 2>/dev/null
    else
        echo "❌ Events still not being processed. Checking logs..."
        echo "Recent errors:"
        tail -5 backend/logs/threatlens.log | grep -i error || echo "No recent errors found"
    fi
else
    echo "❌ Failed to ingest log"
fi