# ThreatLens Deployment Guide

This guide covers deployment options for ThreatLens in various environments.

## 🐳 Docker Deployment (Recommended)

### Development Deployment

```bash
# Clone and setup
git clone <repository-url>
cd threatlens
cp .env.example .env
# Edit .env with your GROQ_API_KEY

# Deploy
./scripts/deploy.sh development
```

### Production Deployment

```bash
# Setup production environment
cp .env.production .env
# Edit .env with production values

# Deploy with production configuration
./scripts/deploy.sh production
```

## 🏗️ Manual Deployment

### Prerequisites

- Python 3.11+
- Node.js 18+
- nginx (for production)
- systemd (for service management)

### Backend Deployment

1. **Setup Python Environment**:
```bash
python3 -m venv /opt/threatlens/venv
source /opt/threatlens/venv/bin/activate
pip install -r requirements.txt
```

2. **Configure Environment**:
```bash
cp .env.production /opt/threatlens/.env
# Edit with production values
```

3. **Initialize Database**:
```bash
cd /opt/threatlens
python setup_env.py
```

4. **Create Systemd Service**:
```ini
# /etc/systemd/system/threatlens-backend.service
[Unit]
Description=ThreatLens Backend
After=network.target

[Service]
Type=exec
User=threatlens
Group=threatlens
WorkingDirectory=/opt/threatlens
Environment=PATH=/opt/threatlens/venv/bin
ExecStart=/opt/threatlens/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

5. **Start Service**:
```bash
sudo systemctl enable threatlens-backend
sudo systemctl start threatlens-backend
```

### Frontend Deployment

1. **Build Frontend**:
```bash
cd frontend
npm install
npm run build
```

2. **Configure nginx**:
```bash
sudo cp nginx-prod.conf /etc/nginx/sites-available/threatlens
sudo ln -s /etc/nginx/sites-available/threatlens /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## ☁️ Cloud Deployment

### AWS Deployment

#### Using ECS (Elastic Container Service)

1. **Build and Push Images**:
```bash
# Build images
docker build -f Dockerfile.backend -t threatlens-backend .
docker build -f Dockerfile.frontend -t threatlens-frontend .

# Tag for ECR
docker tag threatlens-backend:latest <account-id>.dkr.ecr.<region>.amazonaws.com/threatlens-backend:latest
docker tag threatlens-frontend:latest <account-id>.dkr.ecr.<region>.amazonaws.com/threatlens-frontend:latest

# Push to ECR
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/threatlens-backend:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/threatlens-frontend:latest
```

2. **Create ECS Task Definition**:
```json
{
  "family": "threatlens",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::<account-id>:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "<account-id>.dkr.ecr.<region>.amazonaws.com/threatlens-backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "GROQ_API_KEY",
          "value": "your-api-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/threatlens",
          "awslogs-region": "<region>",
          "awslogs-stream-prefix": "backend"
        }
      }
    },
    {
      "name": "frontend",
      "image": "<account-id>.dkr.ecr.<region>.amazonaws.com/threatlens-frontend:latest",
      "portMappings": [
        {
          "containerPort": 80,
          "protocol": "tcp"
        }
      ],
      "dependsOn": [
        {
          "containerName": "backend",
          "condition": "HEALTHY"
        }
      ]
    }
  ]
}
```

#### Using EC2

1. **Launch EC2 Instance**:
   - Use Amazon Linux 2 or Ubuntu 20.04+
   - Configure security groups for ports 80, 443, 8000
   - Attach IAM role with necessary permissions

2. **Install Docker**:
```bash
sudo yum update -y
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -a -G docker ec2-user

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

3. **Deploy Application**:
```bash
git clone <repository-url>
cd threatlens
cp .env.production .env
# Edit .env with production values
./scripts/deploy.sh production
```

### Google Cloud Platform

#### Using Cloud Run

1. **Build and Deploy**:
```bash
# Backend
gcloud builds submit --tag gcr.io/<project-id>/threatlens-backend -f Dockerfile.backend
gcloud run deploy threatlens-backend --image gcr.io/<project-id>/threatlens-backend --platform managed --region us-central1

# Frontend
gcloud builds submit --tag gcr.io/<project-id>/threatlens-frontend -f Dockerfile.frontend
gcloud run deploy threatlens-frontend --image gcr.io/<project-id>/threatlens-frontend --platform managed --region us-central1
```

### Azure

#### Using Container Instances

1. **Create Resource Group**:
```bash
az group create --name threatlens-rg --location eastus
```

2. **Deploy Containers**:
```bash
az container create \
  --resource-group threatlens-rg \
  --name threatlens-backend \
  --image <registry>/threatlens-backend:latest \
  --ports 8000 \
  --environment-variables GROQ_API_KEY=<your-key>

az container create \
  --resource-group threatlens-rg \
  --name threatlens-frontend \
  --image <registry>/threatlens-frontend:latest \
  --ports 80
```

## 🔒 Security Considerations

### SSL/TLS Configuration

1. **Obtain SSL Certificate**:
```bash
# Using Let's Encrypt
sudo certbot --nginx -d your-domain.com
```

2. **Configure nginx for HTTPS**:
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # Include SSL security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
}
```

### Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# iptables
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -j DROP
```

### Environment Security

1. **Secure Environment Variables**:
```bash
# Use secrets management
export GROQ_API_KEY=$(aws secretsmanager get-secret-value --secret-id groq-api-key --query SecretString --output text)
```

2. **File Permissions**:
```bash
chmod 600 .env
chown threatlens:threatlens .env
```

## 📊 Monitoring and Logging

### Application Monitoring

1. **Health Checks**:
```bash
# Add to crontab for monitoring
*/5 * * * * curl -f http://localhost:8000/health || echo "ThreatLens backend down" | mail -s "Alert" admin@company.com
```

2. **Log Aggregation**:
```yaml
# docker-compose.prod.yml addition
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### System Monitoring

1. **Resource Monitoring**:
```bash
# Install monitoring tools
sudo apt install htop iotop nethogs

# Monitor Docker containers
docker stats
```

2. **Log Rotation**:
```bash
# /etc/logrotate.d/threatlens
/opt/threatlens/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 threatlens threatlens
}
```

## 🔄 Backup and Recovery

### Automated Backups

1. **Database Backup**:
```bash
# Add to crontab
0 2 * * * /opt/threatlens/scripts/backup.sh
```

2. **Full System Backup**:
```bash
#!/bin/bash
# /opt/threatlens/scripts/full-backup.sh
tar -czf /backup/threatlens-$(date +%Y%m%d).tar.gz \
  /opt/threatlens/data \
  /opt/threatlens/.env \
  /etc/nginx/sites-available/threatlens
```

### Disaster Recovery

1. **Recovery Procedure**:
```bash
# Restore from backup
tar -xzf /backup/threatlens-20240101.tar.gz -C /
systemctl restart threatlens-backend
systemctl reload nginx
```

## 🚀 Performance Optimization

### Database Optimization

1. **Enable WAL Mode**:
```python
# In database.py
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 20},
    pool_pre_ping=True,
    echo=False
)

# Enable WAL mode
with engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL"))
```

### Caching

1. **nginx Caching**:
```nginx
# Add to nginx configuration
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m max_size=1g inactive=60m;

location /api/events {
    proxy_cache api_cache;
    proxy_cache_valid 200 5m;
    proxy_cache_key "$scheme$request_method$host$request_uri";
}
```

### Load Balancing

1. **Multiple Backend Instances**:
```yaml
# docker-compose.prod.yml
services:
  backend:
    deploy:
      replicas: 3
    
  nginx:
    depends_on:
      - backend
```

## 🔧 Troubleshooting

### Common Issues

1. **Container Won't Start**:
```bash
# Check logs
docker-compose logs backend
docker-compose logs frontend

# Check resource usage
docker stats
```

2. **Database Connection Issues**:
```bash
# Check database file permissions
ls -la data/threatlens.db

# Test database connection
python -c "from app.database import engine; print(engine.execute('SELECT 1').scalar())"
```

3. **High Memory Usage**:
```bash
# Monitor memory usage
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Restart containers if needed
docker-compose restart
```

### Performance Issues

1. **Slow API Responses**:
```bash
# Check database query performance
# Enable SQL logging in development
export LOG_LEVEL=DEBUG

# Monitor nginx access logs
tail -f /var/log/nginx/access.log
```

2. **High CPU Usage**:
```bash
# Check AI API rate limits
# Monitor Groq API usage in dashboard

# Scale backend instances
docker-compose up --scale backend=3
```

## 📞 Support

For deployment issues:
1. Check the troubleshooting section above
2. Review application logs
3. Verify environment configuration
4. Check system resources
5. Consult the main README for additional help