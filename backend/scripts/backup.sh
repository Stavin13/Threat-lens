#!/bin/bash

# ThreatLens Backup Script
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR="backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="threatlens_backup_$TIMESTAMP"

echo -e "${GREEN}💾 Creating ThreatLens backup...${NC}"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create backup archive
echo -e "${GREEN}📦 Creating backup archive...${NC}"
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" \
    --exclude='venv' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='logs/*.log' \
    data/ \
    .env \
    docker-compose*.yml \
    requirements.txt \
    frontend/package*.json

# Backup database separately
if [ -f "data/threatlens.db" ]; then
    echo -e "${GREEN}🗄️  Backing up database...${NC}"
    cp data/threatlens.db "$BACKUP_DIR/threatlens_db_$TIMESTAMP.db"
fi

# Clean old backups (keep last 7 days)
echo -e "${GREEN}🧹 Cleaning old backups...${NC}"
find $BACKUP_DIR -name "threatlens_backup_*.tar.gz" -mtime +7 -delete
find $BACKUP_DIR -name "threatlens_db_*.db" -mtime +7 -delete

echo -e "${GREEN}✅ Backup completed: $BACKUP_DIR/$BACKUP_NAME.tar.gz${NC}"
echo -e "${YELLOW}💡 To restore: tar -xzf $BACKUP_DIR/$BACKUP_NAME.tar.gz${NC}"