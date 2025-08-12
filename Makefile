# ThreatLens Makefile

.PHONY: help install dev-setup build start stop restart logs clean test deploy backup

# Default target
help:
	@echo "ThreatLens Development Commands"
	@echo "==============================="
	@echo "install      - Install dependencies"
	@echo "dev-setup    - Setup development environment"
	@echo "build        - Build Docker images"
	@echo "start        - Start services with Docker"
	@echo "stop         - Stop services"
	@echo "restart      - Restart services"
	@echo "logs         - View service logs"
	@echo "clean        - Clean up containers and images"
	@echo "test         - Run tests"
	@echo "deploy-dev   - Deploy development environment"
	@echo "deploy-prod  - Deploy production environment"
	@echo "backup       - Create backup"

# Development setup
install:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

dev-setup:
	@echo "Setting up development environment..."
	./scripts/dev-setup.sh

# Docker operations
build:
	@echo "Building Docker images..."
	docker-compose build --no-cache

start:
	@echo "Starting services..."
	docker-compose up -d

stop:
	@echo "Stopping services..."
	docker-compose down

restart:
	@echo "Restarting services..."
	docker-compose restart

logs:
	@echo "Viewing logs..."
	docker-compose logs -f

# Cleanup
clean:
	@echo "Cleaning up containers and images..."
	docker-compose down --remove-orphans
	docker system prune -f
	docker volume prune -f

# Testing
test:
	@echo "Running backend tests..."
	pytest
	@echo "Running frontend tests..."
	cd frontend && npm test -- --run

test-coverage:
	@echo "Running tests with coverage..."
	pytest --cov=app --cov-report=html
	cd frontend && npm test -- --coverage --run

# Deployment
deploy-dev:
	@echo "Deploying development environment..."
	./scripts/deploy.sh development

deploy-prod:
	@echo "Deploying production environment..."
	./scripts/deploy.sh production

# Backup
backup:
	@echo "Creating backup..."
	./scripts/backup.sh

# Database operations
db-init:
	@echo "Initializing database..."
	python setup_env.py

db-reset:
	@echo "Resetting database..."
	rm -f data/threatlens.db*
	python setup_env.py

# Demo
demo:
	@echo "Loading demo data..."
	python demo_data_loader.py

# Health check
health:
	@echo "Checking service health..."
	curl -f http://localhost:8000/health || echo "Backend unhealthy"
	curl -f http://localhost:3000 || echo "Frontend unhealthy"

# Development server (without Docker)
dev-backend:
	@echo "Starting backend development server..."
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	@echo "Starting frontend development server..."
	cd frontend && npm start

# Linting and formatting
lint:
	@echo "Running Python linting..."
	flake8 app/ tests/
	@echo "Running frontend linting..."
	cd frontend && npm run lint

format:
	@echo "Formatting Python code..."
	black app/ tests/
	@echo "Formatting frontend code..."
	cd frontend && npm run format

# Security scan
security-scan:
	@echo "Running security scan..."
	safety check
	cd frontend && npm audit

# Performance test
perf-test:
	@echo "Running performance tests..."
	python tests/stress_test_realtime_system.py