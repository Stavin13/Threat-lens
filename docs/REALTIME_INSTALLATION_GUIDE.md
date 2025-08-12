# ThreatLens Real-Time Monitoring Installation Guide

## Overview

This guide provides step-by-step instructions for installing and configuring ThreatLens real-time monitoring capabilities. Follow these instructions to set up a complete real-time log monitoring system.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Prerequisites](#prerequisites)
3. [Installation Steps](#installation-steps)
4. [Configuration](#configuration)
5. [Verification](#verification)
6. [Post-Installation Setup](#post-installation-setup)
7. [Troubleshooting Installation Issues](#troubleshooting-installation-issues)

## System Requirements

### Minimum Requirements

- **Operating System**: Linux (Ubuntu 18.04+, CentOS 7+, RHEL 7+), macOS 10.14+, Windows 10+
- **Python**: 3.8 or higher
- **Memory**: 2 GB RAM minimum, 4 GB recommended
- **Storage**: 10 GB free disk space minimum, 50 GB recommended
- **CPU**: 2 cores minimum, 4 cores recommended
- **Network**: Stable internet connection for AI analysis features

### Recommended Requirements

- **Operating System**: Ubuntu 20.04 LTS or CentOS 8
- **Python**: 3.9 or 3.10
- **Memory**: 8 GB RAM or higher
- **Storage**: 100 GB SSD storage
- **CPU**: 4+ cores with 2.5 GHz or higher
- **Network**: High-speed internet connection

### Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| Ubuntu 18.04+ | ✅ Fully Supported | Recommended for production |
| CentOS 7+ | ✅ Fully Supported | Enterprise deployments |
| RHEL 7+ | ✅ Fully Supported | Enterprise deployments |
| macOS 10.14+ | ✅ Supported | Development and testing |
| Windows 10+ | ⚠️ Limited Support | Development only |
| Docker | ✅ Fully Supported | Containerized deployments |

## Prerequisites

### 1. Python Installation

#### Ubuntu/Debian

```bash
# Update package list
sudo apt update

# Install Python 3.9 and pip
sudo apt install python3.9 python3.9-pip python3.9-venv python3.9-dev

# Verify installation
python3.9 --version
pip3.9 --version
```

#### CentOS/RHEL

```bash
# Install EPEL repository
sudo yum install epel-release

# Install Python 3.9
sudo yum install python39 python39-pip python39-devel

# Verify installation
python3.9 --version
pip3.9 --version
```

#### macOS

```bash
# Using Homebrew (recommended)
brew install python@3.9

# Or using pyenv
brew install pyenv
pyenv install 3.9.16
pyenv global 3.9.16

# Verify installation
python3 --version
pip3 --version
```

### 2. System Dependencies

#### Ubuntu/Debian

```bash
# Install system dependencies
sudo apt install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    libevent-dev \
    libsqlite3-dev \
    pkg-config \
    curl \
    wget \
    git

# Install file system monitoring dependencies
sudo apt install -y inotify-tools
```

#### CentOS/RHEL

```bash
# Install development tools
sudo yum groupinstall "Development Tools"

# Install system dependencies
sudo yum install -y \
    openssl-devel \
    libffi-devel \
    libevent-devel \
    sqlite-devel \
    pkgconfig \
    curl \
    wget \
    git

# Install file system monitoring dependencies
sudo yum install -y inotify-tools
```

#### macOS

```bash
# Install Xcode command line tools
xcode-select --install

# Install additional dependencies via Homebrew
brew install openssl libffi libevent sqlite pkg-config
```

### 3. User and Permissions Setup

```bash
# Create dedicated user for ThreatLens (recommended for production)
sudo useradd -r -s /bin/bash -d /opt/threatlens threatlens

# Create directories
sudo mkdir -p /opt/threatlens/{app,logs,data,config}
sudo chown -R threatlens:threatlens /opt/threatlens

# Add threatlens user to log groups (for log file access)
sudo usermod -a -G adm,syslog threatlens
```

## Installation Steps

### Step 1: Download ThreatLens

#### Option A: Git Clone (Recommended for Development)

```bash
# Clone the repository
git clone https://github.com/your-org/threatlens.git
cd threatlens

# Switch to stable branch (if available)
git checkout stable
```

#### Option B: Download Release Package

```bash
# Download latest release
wget https://github.com/your-org/threatlens/releases/latest/download/threatlens.tar.gz

# Extract package
tar -xzf threatlens.tar.gz
cd threatlens
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3.9 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### Step 3: Install Python Dependencies

```bash
# Install base requirements
pip install -r requirements.txt

# Install real-time monitoring dependencies
pip install \
    watchdog==3.0.0 \
    websockets==11.0.3 \
    asyncio-mqtt==0.13.0 \
    aiofiles==23.2.1 \
    python-multipart==0.0.6

# Install optional dependencies for enhanced features
pip install \
    prometheus-client==0.17.1 \
    psutil==5.9.5 \
    schedule==1.2.0

# Verify installation
pip list | grep -E "(watchdog|websockets|fastapi|sqlite)"
```

### Step 4: Database Setup

```bash
# Initialize database
python app/init_db.py

# Run database migrations
python -m app.migrations.runner

# Verify database setup
sqlite3 data/threatlens.db ".tables"
```

### Step 5: Configuration Setup

```bash
# Copy example configuration
cp .env.example .env

# Create monitoring configuration directory
mkdir -p config

# Create default monitoring configuration
cat > config/monitoring_config.json << 'EOF'
{
  "log_sources": [],
  "processing_batch_size": 100,
  "max_queue_size": 10000,
  "notification_rules": [],
  "health_check_interval": 60,
  "websocket_settings": {
    "ping_interval": 30,
    "ping_timeout": 10,
    "max_connections": 100
  }
}
EOF
```

### Step 6: Environment Configuration

Edit the `.env` file with your specific settings:

```bash
# Basic Configuration
DEBUG=false
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# Database Configuration
DATABASE_URL=sqlite:///data/threatlens.db

# Real-time Monitoring Configuration
REALTIME_ENABLED=true
WEBSOCKET_ENABLED=true
FILE_MONITORING_ENABLED=true

# Processing Configuration
PROCESSING_BATCH_SIZE=100
MAX_QUEUE_SIZE=10000
PROCESSING_WORKERS=2

# AI Analysis Configuration (optional)
GROQ_API_KEY=your_groq_api_key_here
AI_ANALYSIS_ENABLED=true
AI_ANALYSIS_TIMEOUT=10.0

# Notification Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true

# Security Configuration
SECRET_KEY=your-secret-key-here
API_KEY=your-api-key-here
```

## Configuration

### Basic Configuration

#### 1. Log Source Configuration

Create your first log source configuration:

```bash
# Using the API (after starting ThreatLens)
curl -X POST \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "path": "/var/log/syslog",
       "source_name": "System Logs",
       "enabled": true,
       "polling_interval": 1.0,
       "file_pattern": "*",
       "recursive": false
     }' \
     http://localhost:8000/api/log-sources
```

#### 2. Notification Configuration

Configure email notifications:

```bash
curl -X POST \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Email Alerts",
       "type": "email",
       "enabled": true,
       "configuration": {
         "smtp_server": "smtp.gmail.com",
         "smtp_port": 587,
         "username": "alerts@company.com",
         "password": "your-app-password",
         "recipients": ["admin@company.com"],
         "use_tls": true
       }
     }' \
     http://localhost:8000/api/notifications/channels
```

### Advanced Configuration

#### 1. Performance Tuning

For high-volume log processing:

```bash
# In .env file
PROCESSING_BATCH_SIZE=200
MAX_QUEUE_SIZE=50000
PROCESSING_WORKERS=4
DB_CONNECTION_POOL_SIZE=20

# System-level optimizations
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
echo 'fs.file-max=65536' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

#### 2. Security Configuration

```bash
# Generate secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set up SSL/TLS (production)
# In .env file
USE_SSL=true
SSL_CERT_PATH=/path/to/cert.pem
SSL_KEY_PATH=/path/to/key.pem
```

#### 3. Monitoring and Metrics

```bash
# Enable Prometheus metrics
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090

# Enable detailed logging
LOG_LEVEL=DEBUG
ENABLE_PERFORMANCE_LOGGING=true
```

## Verification

### Step 1: Start ThreatLens

```bash
# Activate virtual environment
source venv/bin/activate

# Start ThreatLens
python main.py
```

### Step 2: Verify Services

#### Check HTTP API

```bash
# Test basic API
curl http://localhost:8000/api/health

# Test with authentication
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/api/health
```

#### Check WebSocket Connection

```bash
# Install websocat for testing
cargo install websocat

# Test WebSocket connection
echo '{"type":"ping"}' | websocat ws://localhost:8000/ws?token=YOUR_API_KEY
```

#### Check File Monitoring

```bash
# Create test log file
echo "Test log entry $(date)" >> /tmp/test.log

# Add log source via API
curl -X POST \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "path": "/tmp/test.log",
       "source_name": "Test Logs",
       "enabled": true,
       "polling_interval": 1.0
     }' \
     http://localhost:8000/api/log-sources

# Add more entries and verify they're processed
for i in {1..5}; do
    echo "Test entry $i $(date)" >> /tmp/test.log
    sleep 2
done

# Check if events were created
curl -H "Authorization: Bearer YOUR_API_KEY" \
     "http://localhost:8000/api/events/recent?limit=10"
```

### Step 3: Verify Frontend

```bash
# Install frontend dependencies (if not already done)
cd frontend
npm install

# Start frontend development server
npm start

# Or build for production
npm run build
```

Access the web interface at `http://localhost:3000` (development) or `http://localhost:8000` (production).

## Post-Installation Setup

### 1. System Service Setup (Production)

Create systemd service file:

```bash
sudo tee /etc/systemd/system/threatlens.service << 'EOF'
[Unit]
Description=ThreatLens Real-Time Log Monitoring
After=network.target

[Service]
Type=simple
User=threatlens
Group=threatlens
WorkingDirectory=/opt/threatlens
Environment=PATH=/opt/threatlens/venv/bin
ExecStart=/opt/threatlens/venv/bin/python main.py
Restart=always
RestartSec=10

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/threatlens

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable threatlens
sudo systemctl start threatlens

# Check service status
sudo systemctl status threatlens
```

### 2. Log Rotation Setup

```bash
sudo tee /etc/logrotate.d/threatlens << 'EOF'
/opt/threatlens/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 threatlens threatlens
    postrotate
        systemctl reload threatlens
    endscript
}
EOF
```

### 3. Firewall Configuration

```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 8000/tcp
sudo ufw allow 3000/tcp  # If running frontend separately

# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --reload
```

### 4. Backup Configuration

```bash
# Create backup script
cat > /opt/threatlens/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/threatlens/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
cp data/threatlens.db $BACKUP_DIR/threatlens_$DATE.db

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz config/ .env

# Remove backups older than 30 days
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
EOF

chmod +x /opt/threatlens/backup.sh

# Add to crontab
echo "0 2 * * * /opt/threatlens/backup.sh" | sudo crontab -u threatlens -
```

### 5. Monitoring Setup

```bash
# Install monitoring tools
pip install prometheus-client psutil

# Create monitoring script
cat > /opt/threatlens/monitor.sh << 'EOF'
#!/bin/bash
while true; do
    # Check if ThreatLens is running
    if ! pgrep -f "python.*main.py" > /dev/null; then
        echo "$(date): ThreatLens not running, attempting restart"
        systemctl restart threatlens
    fi
    
    # Check disk space
    DISK_USAGE=$(df /opt/threatlens | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ $DISK_USAGE -gt 90 ]; then
        echo "$(date): Disk usage high: ${DISK_USAGE}%"
    fi
    
    sleep 60
done
EOF

chmod +x /opt/threatlens/monitor.sh
```

## Troubleshooting Installation Issues

### Common Installation Problems

#### 1. Python Version Issues

```bash
# Check Python version
python3 --version

# If wrong version, install correct version
sudo apt install python3.9 python3.9-pip python3.9-venv

# Create virtual environment with specific version
python3.9 -m venv venv
```

#### 2. Permission Issues

```bash
# Fix ownership
sudo chown -R threatlens:threatlens /opt/threatlens

# Fix permissions
sudo chmod -R 755 /opt/threatlens
sudo chmod -R 644 /opt/threatlens/config/*
sudo chmod 600 /opt/threatlens/.env
```

#### 3. Dependency Installation Failures

```bash
# Update system packages
sudo apt update && sudo apt upgrade

# Install build dependencies
sudo apt install build-essential python3-dev

# Clear pip cache
pip cache purge

# Reinstall dependencies
pip install --no-cache-dir -r requirements.txt
```

#### 4. Database Issues

```bash
# Check database file permissions
ls -la data/threatlens.db

# Recreate database if corrupted
rm data/threatlens.db
python app/init_db.py
python -m app.migrations.runner
```

#### 5. Port Conflicts

```bash
# Check if port is in use
netstat -tlnp | grep :8000

# Kill process using port
sudo fuser -k 8000/tcp

# Use different port
export PORT=8001
```

### Installation Verification Checklist

- [ ] Python 3.8+ installed and accessible
- [ ] Virtual environment created and activated
- [ ] All dependencies installed without errors
- [ ] Database initialized and migrations applied
- [ ] Configuration files created and populated
- [ ] ThreatLens starts without errors
- [ ] HTTP API responds to health checks
- [ ] WebSocket connection can be established
- [ ] File monitoring detects changes
- [ ] Frontend loads and displays data
- [ ] System service configured (production)
- [ ] Firewall rules configured
- [ ] Backup system configured

### Getting Help

If you encounter issues during installation:

1. **Check the logs**: `tail -f logs/threatlens.log`
2. **Verify system requirements**: Ensure all prerequisites are met
3. **Check the troubleshooting guide**: See `REALTIME_TROUBLESHOOTING.md`
4. **Search existing issues**: Check GitHub issues for similar problems
5. **Contact support**: Provide detailed error messages and system information

### Next Steps

After successful installation:

1. **Configure log sources**: Add your log files for monitoring
2. **Set up notifications**: Configure email, Slack, or webhook notifications
3. **Customize dashboard**: Configure the web interface for your needs
4. **Set up monitoring**: Configure system health monitoring
5. **Plan maintenance**: Set up regular backups and updates

## Production Deployment Dependencies

### Real-Time Monitoring Dependencies

The real-time monitoring features require additional Python packages beyond the base ThreatLens installation:

```bash
# Core real-time dependencies
pip install \
    watchdog==3.0.0 \
    websockets==11.0.3 \
    asyncio-mqtt==0.13.0 \
    aiofiles==23.2.1 \
    python-multipart==0.0.6

# Performance and monitoring dependencies
pip install \
    prometheus-client==0.17.1 \
    psutil==5.9.5 \
    schedule==1.2.0 \
    redis==4.6.0

# Production server dependencies
pip install \
    gunicorn==21.2.0 \
    gevent==23.7.0 \
    uvloop==0.17.0

# Optional database dependencies
pip install \
    psycopg2-binary==2.9.7  # For PostgreSQL
    pymysql==1.1.0          # For MySQL
```

### System Service Dependencies

```bash
# Install system services for production
# Ubuntu/Debian
apt install -y \
    supervisor \
    nginx \
    redis-server \
    postgresql-13 \
    logrotate \
    fail2ban

# CentOS/RHEL
yum install -y \
    supervisor \
    nginx \
    redis \
    postgresql13-server \
    logrotate \
    fail2ban
```

### File System Monitoring Setup

```bash
# Increase inotify limits for file monitoring
echo 'fs.inotify.max_user_watches=524288' >> /etc/sysctl.conf
echo 'fs.inotify.max_user_instances=256' >> /etc/sysctl.conf
sysctl -p

# Verify inotify limits
cat /proc/sys/fs/inotify/max_user_watches
cat /proc/sys/fs/inotify/max_user_instances
```

## Performance Considerations

### Hardware Sizing Guidelines

#### Small Deployment (< 10,000 events/day)
- **CPU**: 4 cores @ 2.5GHz
- **Memory**: 8 GB RAM
- **Storage**: 100 GB SSD
- **Network**: 1 Gbps
- **Concurrent Users**: 10-20

#### Medium Deployment (10,000-100,000 events/day)
- **CPU**: 8 cores @ 3.0GHz
- **Memory**: 32 GB RAM
- **Storage**: 500 GB NVMe SSD
- **Network**: 10 Gbps
- **Concurrent Users**: 50-100

#### Large Deployment (> 100,000 events/day)
- **CPU**: 16+ cores @ 3.5GHz
- **Memory**: 64+ GB RAM
- **Storage**: 1+ TB NVMe SSD
- **Network**: 25+ Gbps
- **Concurrent Users**: 200+

### Performance Optimization

```bash
# System-level optimizations
echo 'net.core.rmem_max = 134217728' >> /etc/sysctl.conf
echo 'net.core.wmem_max = 134217728' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_rmem = 4096 65536 134217728' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_wmem = 4096 65536 134217728' >> /etc/sysctl.conf
echo 'vm.swappiness = 10' >> /etc/sysctl.conf
echo 'fs.file-max = 65536' >> /etc/sysctl.conf
sysctl -p

# Increase file descriptor limits
echo 'threatlens soft nofile 65536' >> /etc/security/limits.conf
echo 'threatlens hard nofile 65536' >> /etc/security/limits.conf
```

## Security Hardening

### System Security

```bash
# Disable unnecessary services
systemctl disable bluetooth
systemctl disable cups
systemctl disable avahi-daemon

# Configure firewall
ufw enable
ufw default deny incoming
ufw default allow outgoing
ufw allow from 10.0.0.0/8 to any port 22
ufw allow 8000
ufw allow 443

# Install and configure fail2ban
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3

[threatlens]
enabled = true
port = 8000
logpath = /var/log/threatlens/access.log
maxretry = 10
EOF

systemctl enable fail2ban
systemctl start fail2ban
```

### Application Security

```bash
# Generate secure keys
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Set secure file permissions
chmod 600 .env.production
chmod 755 /opt/threatlens
chmod 644 /opt/threatlens/config/*
chown -R threatlens:threatlens /opt/threatlens
```

## Monitoring and Observability

### System Monitoring Setup

```bash
# Install monitoring tools
pip install prometheus-client psutil

# Create monitoring configuration
cat > /opt/threatlens/monitoring.yml << 'EOF'
metrics:
  enabled: true
  port: 9090
  path: /metrics
  
health_checks:
  enabled: true
  interval: 30
  endpoints:
    - database
    - file_monitor
    - websocket_server
    - processing_queue

alerts:
  enabled: true
  channels:
    - email
    - webhook
  rules:
    - name: high_cpu_usage
      condition: cpu_usage > 80
      duration: 300
    - name: high_memory_usage
      condition: memory_usage > 85
      duration: 300
    - name: queue_backlog
      condition: queue_depth > 10000
      duration: 60
EOF
```

### Log Management

```bash
# Configure centralized logging
cat > /etc/rsyslog.d/50-threatlens.conf << 'EOF'
# ThreatLens logging
$template ThreatLensFormat,"%timestamp:::date-rfc3339% %hostname% %syslogtag% %msg%\n"
if $programname == 'threatlens' then /var/log/threatlens/threatlens.log;ThreatLensFormat
& stop
EOF

systemctl restart rsyslog

# Set up log rotation
cat > /etc/logrotate.d/threatlens << 'EOF'
/var/log/threatlens/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 threatlens threatlens
    postrotate
        systemctl reload threatlens
    endscript
}
EOF
```

## Disaster Recovery

### Backup Strategy

```bash
# Create backup script
cat > /opt/threatlens/scripts/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/threatlens/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

mkdir -p $BACKUP_DIR

# Backup database
if [[ "$DATABASE_URL" == sqlite* ]]; then
    sqlite3 data/threatlens.db ".backup $BACKUP_DIR/database_$DATE.db"
else
    pg_dump $DATABASE_URL > $BACKUP_DIR/database_$DATE.sql
fi

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz config/ .env.production

# Backup logs (last 7 days)
find logs/ -name "*.log" -mtime -7 -exec tar -czf $BACKUP_DIR/logs_$DATE.tar.gz {} +

# Remove old backups
find $BACKUP_DIR -name "*.db" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "*.sql" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $DATE"
EOF

chmod +x /opt/threatlens/scripts/backup.sh

# Schedule backups
echo "0 2 * * * /opt/threatlens/scripts/backup.sh" | crontab -u threatlens -
```

### Recovery Procedures

```bash
# Create recovery script
cat > /opt/threatlens/scripts/restore.sh << 'EOF'
#!/bin/bash
BACKUP_FILE=$1
BACKUP_TYPE=$2

if [ -z "$BACKUP_FILE" ] || [ -z "$BACKUP_TYPE" ]; then
    echo "Usage: $0 <backup_file> <database|config|logs>"
    exit 1
fi

case $BACKUP_TYPE in
    database)
        if [[ "$DATABASE_URL" == sqlite* ]]; then
            sqlite3 data/threatlens.db ".restore $BACKUP_FILE"
        else
            psql $DATABASE_URL < $BACKUP_FILE
        fi
        ;;
    config)
        tar -xzf $BACKUP_FILE -C /opt/threatlens/
        ;;
    logs)
        tar -xzf $BACKUP_FILE -C /opt/threatlens/
        ;;
    *)
        echo "Invalid backup type: $BACKUP_TYPE"
        exit 1
        ;;
esac

echo "Restore completed for $BACKUP_TYPE"
EOF

chmod +x /opt/threatlens/scripts/restore.sh
```

## Maintenance Procedures

### Regular Maintenance Tasks

```bash
# Create maintenance script
cat > /opt/threatlens/scripts/maintenance.sh << 'EOF'
#!/bin/bash

echo "Starting ThreatLens maintenance..."

# Update system packages
apt update && apt upgrade -y

# Clean up old log files
find /var/log/threatlens -name "*.log.*" -mtime +30 -delete

# Optimize database
if [[ "$DATABASE_URL" == sqlite* ]]; then
    sqlite3 data/threatlens.db "VACUUM; ANALYZE;"
else
    psql $DATABASE_URL -c "VACUUM ANALYZE;"
fi

# Clear temporary files
find /tmp -name "threatlens*" -mtime +1 -delete

# Restart services
systemctl restart threatlens
systemctl restart nginx

# Check service status
systemctl status threatlens
systemctl status nginx

echo "Maintenance completed"
EOF

chmod +x /opt/threatlens/scripts/maintenance.sh

# Schedule monthly maintenance
echo "0 3 1 * * /opt/threatlens/scripts/maintenance.sh" | crontab -u root -
```

### Health Monitoring

```bash
# Create health check script
cat > /opt/threatlens/scripts/health_check.sh << 'EOF'
#!/bin/bash

HEALTH_URL="http://localhost:8000/api/health"
ALERT_EMAIL="admin@company.com"

# Check if ThreatLens is responding
if ! curl -f -s $HEALTH_URL > /dev/null; then
    echo "ThreatLens health check failed" | mail -s "ThreatLens Alert" $ALERT_EMAIL
    systemctl restart threatlens
fi

# Check disk space
DISK_USAGE=$(df /opt/threatlens | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 90 ]; then
    echo "Disk usage is at ${DISK_USAGE}%" | mail -s "ThreatLens Disk Alert" $ALERT_EMAIL
fi

# Check memory usage
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
if [ $MEMORY_USAGE -gt 90 ]; then
    echo "Memory usage is at ${MEMORY_USAGE}%" | mail -s "ThreatLens Memory Alert" $ALERT_EMAIL
fi
EOF

chmod +x /opt/threatlens/scripts/health_check.sh

# Run health checks every 5 minutes
echo "*/5 * * * * /opt/threatlens/scripts/health_check.sh" | crontab -u threatlens -
```

For detailed configuration instructions, see the [Configuration Guide](REALTIME_CONFIGURATION_GUIDE.md).
For deployment strategies and advanced setups, see the [Deployment Guide](REALTIME_DEPLOYMENT_GUIDE.md).
For operational procedures, see the [User Guide](REALTIME_USER_GUIDE.md).
For configuration best practices, see the [Configuration Best Practices](REALTIME_CONFIGURATION_BEST_PRACTICES.md).