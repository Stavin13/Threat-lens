# ThreatLens Real-Time Monitoring System Requirements

## Overview

This document outlines the comprehensive system requirements for deploying ThreatLens real-time monitoring in various environments. It covers hardware specifications, software dependencies, network requirements, and performance considerations.

## Table of Contents

1. [Hardware Requirements](#hardware-requirements)
2. [Software Requirements](#software-requirements)
3. [Network Requirements](#network-requirements)
4. [Storage Requirements](#storage-requirements)
5. [Performance Considerations](#performance-considerations)
6. [Scalability Requirements](#scalability-requirements)
7. [Security Requirements](#security-requirements)
8. [Monitoring Requirements](#monitoring-requirements)
9. [Environment-Specific Requirements](#environment-specific-requirements)
10. [Compatibility Matrix](#compatibility-matrix)

## Hardware Requirements

### Minimum Requirements (Development/Testing)

| Component | Specification | Notes |
|-----------|---------------|-------|
| **CPU** | 2 cores @ 2.0GHz | Intel/AMD x64 architecture |
| **Memory** | 4 GB RAM | Minimum for basic functionality |
| **Storage** | 20 GB available space | SSD recommended |
| **Network** | 100 Mbps | Stable internet connection |

**Suitable for:**
- Development environments
- Small-scale testing (< 1,000 events/day)
- Proof of concept deployments

### Recommended Requirements (Small Production)

| Component | Specification | Notes |
|-----------|---------------|-------|
| **CPU** | 4 cores @ 2.5GHz | Intel Core i5/AMD Ryzen 5 or equivalent |
| **Memory** | 8 GB RAM | 16 GB recommended for better performance |
| **Storage** | 100 GB SSD | NVMe preferred for database operations |
| **Network** | 1 Gbps | Low latency connection preferred |

**Suitable for:**
- Small organizations (1,000-10,000 events/day)
- Single-node production deployments
- Regional office deployments

### High-Performance Requirements (Medium Production)

| Component | Specification | Notes |
|-----------|---------------|-------|
| **CPU** | 8 cores @ 3.0GHz | Intel Xeon/AMD EPYC or equivalent |
| **Memory** | 32 GB RAM | ECC memory recommended |
| **Storage** | 500 GB NVMe SSD | High IOPS for concurrent processing |
| **Network** | 10 Gbps | Dedicated network interface |

**Suitable for:**
- Medium organizations (10,000-100,000 events/day)
- Multi-node deployments
- High-availability setups

### Enterprise Requirements (Large Production)

| Component | Specification | Notes |
|-----------|---------------|-------|
| **CPU** | 16+ cores @ 3.5GHz | Multi-socket servers recommended |
| **Memory** | 64+ GB RAM | ECC memory required |
| **Storage** | 1+ TB NVMe SSD | RAID 10 configuration |
| **Network** | 25+ Gbps | Redundant network connections |

**Suitable for:**
- Large organizations (> 100,000 events/day)
- Distributed deployments
- Mission-critical environments

### Specialized Hardware Considerations

#### CPU Requirements

```bash
# Check CPU capabilities
lscpu | grep -E "(Model name|CPU\(s\)|Thread|Core|Socket)"

# Verify CPU features
grep -E "(sse|avx|aes)" /proc/cpuinfo

# Recommended CPU features:
# - AES-NI for encryption performance
# - AVX2 for AI analysis acceleration
# - Multiple cores for parallel processing
```

#### Memory Requirements

```bash
# Memory sizing formula:
# Base memory: 2 GB
# Processing buffer: events_per_second * average_event_size * buffer_multiplier
# Database cache: 25% of total database size
# OS and overhead: 2 GB

# Example for 100 events/second, 2KB average size, 10x buffer:
# Base: 2 GB
# Buffer: 100 * 2KB * 10 = 2 MB (negligible)
# DB cache: 25% of 10 GB = 2.5 GB
# OS: 2 GB
# Total: ~7 GB (round up to 8 GB)
```

#### Storage Requirements

```bash
# Storage performance requirements:
# - Random IOPS: 1000+ for database operations
# - Sequential throughput: 500+ MB/s for log ingestion
# - Latency: < 1ms for real-time processing

# Test storage performance:
fio --name=random-read --ioengine=libaio --rw=randread --bs=4k --numjobs=4 --size=1G --runtime=60 --group_reporting

# Expected results for adequate performance:
# IOPS: > 1000
# Latency: < 1ms average
# Bandwidth: > 100 MB/s
```

## Software Requirements

### Operating System Support

#### Linux Distributions (Recommended)

| Distribution | Version | Support Level | Notes |
|--------------|---------|---------------|-------|
| **Ubuntu** | 20.04 LTS, 22.04 LTS | ✅ Full Support | Recommended for production |
| **CentOS** | 8, Stream 8 | ✅ Full Support | Enterprise environments |
| **RHEL** | 8, 9 | ✅ Full Support | Enterprise with support |
| **Debian** | 11, 12 | ✅ Full Support | Stable and reliable |
| **Amazon Linux** | 2 | ✅ Full Support | AWS deployments |
| **SUSE Linux** | 15 SP3+ | ⚠️ Limited Testing | Community support |

#### Other Operating Systems

| OS | Version | Support Level | Notes |
|----|---------|---------------|-------|
| **macOS** | 11+, 12+, 13+ | ⚠️ Development Only | Not recommended for production |
| **Windows** | 10, 11, Server 2019/2022 | ⚠️ Limited Support | Development and testing only |
| **FreeBSD** | 13+ | ❌ Not Supported | May work but untested |

### Python Requirements

```bash
# Python version requirements
Python 3.8.0+  # Minimum supported version
Python 3.9.0+  # Recommended version
Python 3.10.0+ # Latest tested version
Python 3.11.0+ # Experimental support

# Check Python version
python3 --version

# Verify required Python modules are available
python3 -c "import asyncio, sqlite3, json, ssl, hashlib"
```

### System Dependencies

#### Ubuntu/Debian

```bash
# Essential packages
apt update
apt install -y \
    python3-dev \
    python3-pip \
    python3-venv \
    build-essential \
    libssl-dev \
    libffi-dev \
    libevent-dev \
    libsqlite3-dev \
    pkg-config \
    curl \
    wget \
    git

# File system monitoring
apt install -y inotify-tools

# Optional performance packages
apt install -y \
    htop \
    iotop \
    netstat-nat \
    tcpdump \
    strace
```

#### CentOS/RHEL

```bash
# Enable EPEL repository
yum install -y epel-release

# Essential packages
yum groupinstall -y "Development Tools"
yum install -y \
    python39-devel \
    python39-pip \
    openssl-devel \
    libffi-devel \
    libevent-devel \
    sqlite-devel \
    pkgconfig \
    curl \
    wget \
    git

# File system monitoring
yum install -y inotify-tools
```

#### macOS

```bash
# Install Xcode command line tools
xcode-select --install

# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python@3.9 openssl libffi libevent sqlite pkg-config
```

### Database Requirements

#### SQLite (Default)

```bash
# SQLite version requirements
SQLite 3.31.0+  # Minimum for JSON support
SQLite 3.35.0+  # Recommended for performance
SQLite 3.38.0+  # Latest features

# Check SQLite version
sqlite3 --version

# Required SQLite features:
# - JSON1 extension
# - FTS5 full-text search
# - WAL mode support
sqlite3 :memory: "SELECT sqlite_version(), json('{}'), fts5();"
```

#### PostgreSQL (Optional, for high-volume deployments)

```bash
# PostgreSQL version requirements
PostgreSQL 12+  # Minimum supported
PostgreSQL 13+  # Recommended
PostgreSQL 14+  # Latest tested

# Required extensions:
# - pg_stat_statements
# - pg_trgm (for text search)
# - uuid-ossp (for UUID generation)

# Installation on Ubuntu
apt install -y postgresql-13 postgresql-contrib-13

# Installation on CentOS
yum install -y postgresql13-server postgresql13-contrib
```

### Web Server Requirements (Optional)

#### Nginx (Recommended)

```bash
# Nginx version requirements
Nginx 1.18+  # Minimum for WebSocket support
Nginx 1.20+  # Recommended for performance
Nginx 1.22+  # Latest features

# Required modules:
# - http_ssl_module
# - http_v2_module
# - http_realip_module
# - http_gzip_module

# Check Nginx modules
nginx -V 2>&1 | grep -o with-http_[a-z_]*_module
```

#### Apache (Alternative)

```bash
# Apache version requirements
Apache 2.4.25+  # Minimum for WebSocket support

# Required modules:
# - mod_ssl
# - mod_proxy
# - mod_proxy_http
# - mod_proxy_wstunnel
# - mod_rewrite

# Enable required modules
a2enmod ssl proxy proxy_http proxy_wstunnel rewrite
```

## Network Requirements

### Bandwidth Requirements

#### Ingestion Bandwidth

```bash
# Calculate required bandwidth for log ingestion
# Formula: events_per_second * average_event_size * overhead_factor

# Examples:
# Small: 1 event/sec * 2KB * 2 = 4 KB/s
# Medium: 10 events/sec * 2KB * 2 = 40 KB/s  
# Large: 100 events/sec * 2KB * 2 = 400 KB/s
# Enterprise: 1000 events/sec * 2KB * 2 = 4 MB/s
```

#### WebSocket Bandwidth

```bash
# WebSocket bandwidth per connected client
# Base connection: ~1 KB/s
# Event updates: events_per_second * 500 bytes
# Heartbeat: 100 bytes every 30 seconds

# Example for 10 events/sec:
# Base: 1 KB/s
# Updates: 10 * 500 bytes = 5 KB/s
# Total per client: ~6 KB/s

# For 50 concurrent clients: 50 * 6 KB/s = 300 KB/s
```

### Port Requirements

| Port | Protocol | Purpose | Direction | Required |
|------|----------|---------|-----------|----------|
| 8000 | HTTP/HTTPS | Main API and Web UI | Inbound | Yes |
| 8000 | WebSocket | Real-time updates | Inbound | Yes |
| 22 | SSH | System administration | Inbound | Optional |
| 53 | DNS | Domain name resolution | Outbound | Yes |
| 80/443 | HTTP/HTTPS | External API calls | Outbound | Yes |
| 25/587/465 | SMTP | Email notifications | Outbound | Optional |
| 5432 | PostgreSQL | Database (if external) | Outbound | Optional |
| 6379 | Redis | Caching (if external) | Outbound | Optional |
| 9090 | HTTP | Prometheus metrics | Inbound | Optional |

### Firewall Configuration

#### iptables Rules

```bash
# Basic firewall rules for ThreatLens
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# SSH access (restrict to management networks)
iptables -A INPUT -p tcp --dport 22 -s 10.0.0.0/8 -j ACCEPT

# ThreatLens application
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT

# Prometheus metrics (internal only)
iptables -A INPUT -p tcp --dport 9090 -s 10.0.0.0/8 -j ACCEPT

# Drop all other inbound traffic
iptables -A INPUT -j DROP

# Allow all outbound traffic
iptables -A OUTPUT -j ACCEPT
```

#### UFW Configuration (Ubuntu)

```bash
# Enable UFW
ufw enable

# Default policies
ufw default deny incoming
ufw default allow outgoing

# SSH access
ufw allow from 10.0.0.0/8 to any port 22

# ThreatLens application
ufw allow 8000

# Prometheus metrics (internal only)
ufw allow from 10.0.0.0/8 to any port 9090
```

### Network Performance Requirements

```bash
# Network latency requirements:
# - Internal components: < 1ms
# - Database connections: < 5ms
# - External API calls: < 100ms
# - WebSocket connections: < 50ms

# Test network latency
ping -c 10 database-server
ping -c 10 api.groq.com

# Test bandwidth
iperf3 -c target-server -t 30

# Expected results:
# Latency: < 5ms to database
# Bandwidth: > 100 Mbps for high-volume deployments
# Packet loss: < 0.1%
```

## Storage Requirements

### Database Storage

#### SQLite Storage

```bash
# SQLite storage estimation
# Base database: ~10 MB
# Per event: ~2 KB (including indexes)
# Indexes overhead: ~30% of data size

# Storage formula:
# total_storage = base_size + (events_count * event_size * index_overhead)

# Examples:
# 10K events: 10 MB + (10K * 2KB * 1.3) = ~36 MB
# 100K events: 10 MB + (100K * 2KB * 1.3) = ~270 MB
# 1M events: 10 MB + (1M * 2KB * 1.3) = ~2.7 GB
# 10M events: 10 MB + (10M * 2KB * 1.3) = ~27 GB
```

#### PostgreSQL Storage

```bash
# PostgreSQL storage estimation (more efficient for large datasets)
# Base database: ~50 MB
# Per event: ~1.5 KB (better compression)
# Indexes overhead: ~25% of data size

# Storage formula:
# total_storage = base_size + (events_count * event_size * index_overhead)

# Examples:
# 100K events: 50 MB + (100K * 1.5KB * 1.25) = ~238 MB
# 1M events: 50 MB + (1M * 1.5KB * 1.25) = ~1.9 GB
# 10M events: 50 MB + (10M * 1.5KB * 1.25) = ~19 GB
# 100M events: 50 MB + (100M * 1.5KB * 1.25) = ~188 GB
```

### Log File Storage (Optional)

```bash
# Raw log file retention (if enabled)
# Depends on log volume and retention policy

# Typical log volumes:
# Small system: 100 MB/day
# Medium system: 1 GB/day
# Large system: 10 GB/day
# Enterprise: 100+ GB/day

# Storage with compression (70% compression typical):
# Small: 100 MB * 30 days * 0.3 = 900 MB/month
# Medium: 1 GB * 30 days * 0.3 = 9 GB/month
# Large: 10 GB * 30 days * 0.3 = 90 GB/month
# Enterprise: 100 GB * 30 days * 0.3 = 900 GB/month
```

### Backup Storage

```bash
# Backup storage requirements
# Database backup: 1x database size (compressed)
# Configuration backup: ~10 MB
# Log backup: 0.3x raw log size (compressed)

# Recommended backup retention:
# Daily backups: 30 days
# Weekly backups: 12 weeks
# Monthly backups: 12 months

# Total backup storage = daily_size * 30 + weekly_size * 12 + monthly_size * 12
```

### Storage Performance Requirements

| Metric | Minimum | Recommended | High-Performance |
|--------|---------|-------------|------------------|
| **Random IOPS** | 500 | 1,000 | 5,000+ |
| **Sequential Read** | 100 MB/s | 500 MB/s | 1,000+ MB/s |
| **Sequential Write** | 50 MB/s | 200 MB/s | 500+ MB/s |
| **Latency** | < 10ms | < 5ms | < 1ms |

```bash
# Test storage performance
# Random read performance
fio --name=random-read --ioengine=libaio --rw=randread --bs=4k --numjobs=4 --size=1G --runtime=60

# Sequential read performance  
fio --name=sequential-read --ioengine=libaio --rw=read --bs=1M --numjobs=1 --size=1G --runtime=60

# Sequential write performance
fio --name=sequential-write --ioengine=libaio --rw=write --bs=1M --numjobs=1 --size=1G --runtime=60
```

## Performance Considerations

### CPU Performance

```bash
# CPU performance factors:
# - Log parsing: CPU-intensive for complex formats
# - AI analysis: High CPU usage for threat detection
# - WebSocket handling: Moderate CPU usage
# - Database operations: Low to moderate CPU usage

# Performance monitoring:
# - CPU utilization should stay < 80% average
# - Load average should be < number of CPU cores
# - Context switches should be < 10,000/second

# Monitor CPU performance:
top -p $(pgrep -f threatlens)
iostat -c 1 10
vmstat 1 10
```

### Memory Performance

```bash
# Memory usage patterns:
# - Base application: ~500 MB
# - Processing queue: events_in_queue * 2KB
# - Database cache: 25% of database size
# - WebSocket connections: ~10 KB per connection

# Memory monitoring:
# - Memory utilization should stay < 85%
# - Swap usage should be minimal (< 10%)
# - No memory leaks (steady memory usage)

# Monitor memory performance:
free -h
ps aux | grep threatlens
cat /proc/$(pgrep -f threatlens)/status | grep -E "(VmSize|VmRSS|VmSwap)"
```

### I/O Performance

```bash
# I/O patterns:
# - Database writes: Frequent small writes
# - Log file reads: Sequential reads
# - Configuration reads: Infrequent small reads

# I/O monitoring:
# - Disk utilization should stay < 80%
# - Average queue depth should be < 10
# - I/O wait time should be < 10%

# Monitor I/O performance:
iostat -x 1 10
iotop -o
lsof -p $(pgrep -f threatlens)
```

## Scalability Requirements

### Vertical Scaling Limits

| Resource | Small | Medium | Large | Enterprise |
|----------|-------|--------|-------|------------|
| **Max CPU Cores** | 4 | 8 | 16 | 32+ |
| **Max Memory** | 16 GB | 32 GB | 64 GB | 128+ GB |
| **Max Storage** | 500 GB | 2 TB | 10 TB | 50+ TB |
| **Max Events/Day** | 10K | 100K | 1M | 10M+ |

### Horizontal Scaling

```bash
# Horizontal scaling considerations:
# - Multiple application instances behind load balancer
# - Shared database (PostgreSQL cluster recommended)
# - Shared storage for configuration and logs
# - Message queue for coordination (Redis/RabbitMQ)

# Scaling formula:
# instances_needed = peak_events_per_second / events_per_instance_per_second
# events_per_instance_per_second ≈ 10-50 (depending on complexity)

# Example for 1000 events/second peak:
# instances_needed = 1000 / 25 = 40 instances
```

### Database Scaling

```bash
# SQLite scaling limits:
# - Single writer limitation
# - Max database size: ~281 TB (theoretical)
# - Practical limit: ~100 GB for good performance
# - Max concurrent readers: ~1000

# PostgreSQL scaling options:
# - Read replicas for query scaling
# - Partitioning for large tables
# - Connection pooling for connection scaling
# - Sharding for extreme scale (complex)
```

## Security Requirements

### System Security

```bash
# Operating system hardening:
# - Regular security updates
# - Minimal package installation
# - Proper user permissions
# - Firewall configuration
# - SSH key authentication
# - Disable unused services

# Security monitoring:
# - Failed login attempts
# - File integrity monitoring
# - Network connection monitoring
# - Process monitoring
```

### Application Security

```bash
# Application security requirements:
# - HTTPS/TLS encryption
# - API key authentication
# - Input validation
# - SQL injection prevention
# - XSS protection
# - CSRF protection
# - Rate limiting

# Security headers:
# - Strict-Transport-Security
# - X-Frame-Options
# - X-Content-Type-Options
# - X-XSS-Protection
# - Content-Security-Policy
```

### Data Security

```bash
# Data protection requirements:
# - Encryption at rest (database)
# - Encryption in transit (TLS)
# - Secure key management
# - Data masking for sensitive information
# - Audit logging
# - Backup encryption
# - Secure deletion
```

## Monitoring Requirements

### System Monitoring

```bash
# Required system metrics:
# - CPU utilization
# - Memory usage
# - Disk I/O
# - Network I/O
# - Disk space
# - System load
# - Process status

# Monitoring tools:
# - Prometheus + Grafana (recommended)
# - Nagios
# - Zabbix
# - DataDog
# - New Relic
```

### Application Monitoring

```bash
# Required application metrics:
# - Events processed per second
# - Processing latency
# - Queue depth
# - WebSocket connections
# - API response times
# - Error rates
# - Database performance

# Health check endpoints:
# - /api/health (basic health)
# - /api/health/detailed (comprehensive)
# - /metrics (Prometheus format)
```

### Log Monitoring

```bash
# Log monitoring requirements:
# - Centralized log collection
# - Log parsing and analysis
# - Alert on error patterns
# - Log retention policies
# - Log compression
# - Log rotation

# Log levels:
# - ERROR: System errors requiring attention
# - WARN: Potential issues
# - INFO: General information
# - DEBUG: Detailed debugging (development only)
```

## Environment-Specific Requirements

### Development Environment

```bash
# Relaxed requirements for development:
# - Minimum hardware specifications
# - Local SQLite database
# - Debug logging enabled
# - Hot reload capabilities
# - Test data generation
# - Mock external services
```

### Testing Environment

```bash
# Testing environment requirements:
# - Production-like configuration
# - Automated testing capabilities
# - Performance testing tools
# - Load generation tools
# - Monitoring and metrics
# - Isolated network environment
```

### Staging Environment

```bash
# Staging environment requirements:
# - Production hardware specifications
# - Production database setup
# - Production monitoring
# - Blue-green deployment capability
# - Performance testing
# - Security testing
```

### Production Environment

```bash
# Production environment requirements:
# - High availability setup
# - Disaster recovery plan
# - Comprehensive monitoring
# - Security hardening
# - Performance optimization
# - Backup and recovery procedures
# - Change management process
```

## Compatibility Matrix

### Python Version Compatibility

| Python Version | ThreatLens Support | Notes |
|----------------|-------------------|-------|
| 3.7 | ❌ Not Supported | End of life |
| 3.8 | ✅ Supported | Minimum version |
| 3.9 | ✅ Recommended | Best performance |
| 3.10 | ✅ Supported | Latest features |
| 3.11 | ⚠️ Experimental | Limited testing |
| 3.12 | ❌ Not Tested | Future support |

### Database Compatibility

| Database | Version | Support Level | Max Events |
|----------|---------|---------------|------------|
| SQLite | 3.31+ | ✅ Full Support | 10M |
| PostgreSQL | 12+ | ✅ Full Support | 1B+ |
| MySQL | 8.0+ | ⚠️ Limited | 100M |
| MariaDB | 10.5+ | ⚠️ Limited | 100M |

### Operating System Compatibility

| OS Family | Versions | Support Level | Production Ready |
|-----------|----------|---------------|------------------|
| Ubuntu | 18.04, 20.04, 22.04 | ✅ Full Support | Yes |
| CentOS | 7, 8, Stream 8 | ✅ Full Support | Yes |
| RHEL | 7, 8, 9 | ✅ Full Support | Yes |
| Debian | 10, 11, 12 | ✅ Full Support | Yes |
| Amazon Linux | 2 | ✅ Full Support | Yes |
| macOS | 11, 12, 13 | ⚠️ Development Only | No |
| Windows | 10, 11, Server 2019/2022 | ⚠️ Limited | No |

### Browser Compatibility (Frontend)

| Browser | Version | Support Level | WebSocket Support |
|---------|---------|---------------|-------------------|
| Chrome | 90+ | ✅ Full Support | Yes |
| Firefox | 88+ | ✅ Full Support | Yes |
| Safari | 14+ | ✅ Full Support | Yes |
| Edge | 90+ | ✅ Full Support | Yes |
| Internet Explorer | Any | ❌ Not Supported | No |

This comprehensive system requirements document should help you plan and deploy ThreatLens real-time monitoring with confidence, ensuring optimal performance and reliability for your specific environment and use case.