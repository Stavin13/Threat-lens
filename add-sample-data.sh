#!/bin/bash

echo "📊 Adding Sample Data to ThreatLens"
echo "==================================="

# Wait a moment to avoid rate limiting
sleep 2

echo "Adding sample SSH login attempt..."
curl -X POST http://localhost:8000/ingest-log \
  -F "content=Sep 15 10:30:45 server sshd[1234]: Failed password for invalid user admin from 192.168.1.100 port 22 ssh2" \
  -F "source=ssh_logs"

sleep 3

echo -e "\nAdding sample web server error..."
curl -X POST http://localhost:8000/ingest-log \
  -F "content=2024-09-15 10:31:20 [error] 5678#0: *1 access forbidden by rule, client: 10.0.0.50, server: example.com, request: GET /admin HTTP/1.1" \
  -F "source=nginx_logs"

sleep 3

echo -e "\nAdding sample system error..."
curl -X POST http://localhost:8000/ingest-log \
  -F "content=Sep 15 10:32:10 server kernel: [12345.678901] segfault at 7f8b8c000000 ip 00007f8b8c000000 sp 00007fff12345678 error 14 in libc.so.6" \
  -F "source=system_logs"

sleep 3

echo -e "\nAdding sample successful authentication..."
curl -X POST http://localhost:8000/ingest-log \
  -F "content=Sep 15 10:33:00 server sshd[9876]: Accepted publickey for user from 192.168.1.200 port 22 ssh2: RSA SHA256:abc123def456" \
  -F "source=ssh_logs"

echo -e "\n✅ Sample data added!"
echo "🌐 Visit http://localhost:3000 to see your dashboard!"
echo "📊 It may take a few moments for the data to be processed and appear."