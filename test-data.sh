#!/bin/bash

echo "🧪 Testing ThreatLens Data Flow"
echo "==============================="

# Test backend health
echo "1. Testing backend health..."
curl -s http://localhost:8000/health-simple | jq . || echo "❌ Backend not responding"

# Test stats endpoint
echo -e "\n2. Testing stats endpoint..."
curl -s http://localhost:8000/stats | jq . || echo "❌ Stats endpoint not responding"

# Test events endpoint
echo -e "\n3. Testing events endpoint..."
curl -s http://localhost:8000/events | jq . || echo "❌ Events endpoint not responding"

# Test realtime metrics
echo -e "\n4. Testing realtime metrics..."
curl -s http://localhost:8000/realtime/monitoring/metrics | jq . || echo "❌ Realtime metrics not responding"

# Test realtime status
echo -e "\n5. Testing realtime status..."
curl -s http://localhost:8000/realtime/status | jq . || echo "❌ Realtime status not responding"

# Add some sample log data
echo -e "\n6. Adding sample log data..."

# Sample SSH login attempt
curl -X POST http://localhost:8000/ingest-log \
  -F "content=Sep 15 10:30:45 server sshd[1234]: Failed password for invalid user admin from 192.168.1.100 port 22 ssh2" \
  -F "source=test_ssh_logs"

# Sample web server error
curl -X POST http://localhost:8000/ingest-log \
  -F "content=2024-09-15 10:31:20 [error] 5678#0: *1 access forbidden by rule, client: 10.0.0.50, server: example.com, request: GET /admin HTTP/1.1" \
  -F "source=test_nginx_logs"

# Sample system error
curl -X POST http://localhost:8000/ingest-log \
  -F "content=Sep 15 10:32:10 server kernel: [12345.678901] segfault at 7f8b8c000000 ip 00007f8b8c000000 sp 00007fff12345678 error 14 in libc.so.6" \
  -F "source=test_system_logs"

# Sample authentication success
curl -X POST http://localhost:8000/ingest-log \
  -F "content=Sep 15 10:33:00 server sshd[9876]: Accepted publickey for user from 192.168.1.200 port 22 ssh2: RSA SHA256:abc123def456" \
  -F "source=test_ssh_logs"

# Sample firewall block
curl -X POST http://localhost:8000/ingest-log \
  -F "content=Sep 15 10:34:15 server kernel: [12346.789012] iptables: DROP IN=eth0 OUT= MAC=00:11:22:33:44:55 SRC=203.0.113.10 DST=192.168.1.1 LEN=40 TOS=0x00 PREC=0x00 TTL=64 ID=12345 PROTO=TCP SPT=12345 DPT=22 WINDOW=1024" \
  -F "source=test_firewall_logs"

echo -e "\n✅ Sample data added!"

# Wait a moment for processing
echo -e "\n7. Waiting for processing..."
sleep 5

# Check events again
echo -e "\n8. Checking events after data ingestion..."
curl -s http://localhost:8000/events | jq '.total, .events | length' || echo "❌ Events check failed"

# Check stats again
echo -e "\n9. Checking updated stats..."
curl -s http://localhost:8000/stats | jq '.database' || echo "❌ Stats check failed"

echo -e "\n🎉 Test complete! Check your dashboard at http://localhost:3000"