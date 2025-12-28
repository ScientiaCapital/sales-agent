# Sales-Agent Deployment Guide

**Version**: 1.0.0
**Last Updated**: 2025-12-27

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Setup](#database-setup)
4. [Backend Deployment](#backend-deployment)
5. [Frontend Deployment](#frontend-deployment)
6. [Nginx Configuration](#nginx-configuration)
7. [Monitoring Setup](#monitoring-setup)
8. [Security Checklist](#security-checklist)
9. [Rollback Procedures](#rollback-procedures)

---

## Prerequisites

### Required Services

| Service | Version | Purpose |
|---------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| PostgreSQL | 15+ | Primary database (via Supabase) |
| Redis | 7+ | Caching, rate limiting, Celery broker |
| Nginx | 1.24+ | Reverse proxy, SSL termination |

### Required Accounts

- **Supabase**: Database and authentication
- **Sentry**: Error tracking
- **LangSmith**: LLM observability
- **Close CRM**: Webhook integration (if using)
- **Twilio**: Voice calling (if using)

---

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/sales-agent.git
cd sales-agent
git checkout main  # or your deployment branch
```

### 2. Create Environment Files

**Backend** (`backend/.env`):
```bash
# Database (Supabase)
DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@db.supabase.co:5432/postgres
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_KEY=eyJ...  # Service role key (NOT anon key)
SUPABASE_ANON_KEY=eyJ...

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
JWT_SECRET_KEY=$(openssl rand -hex 32)
CLOSE_WEBHOOK_SECRET=your_close_webhook_secret
METRICS_API_KEY=$(openssl rand -hex 32)

# AI/LLM
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...  # For fallback/embeddings
LANGSMITH_API_KEY=ls-...
LANGSMITH_PROJECT=sales-agent-prod
LANGSMITH_TRACING=true

# Monitoring
SENTRY_DSN=https://...@sentry.io/...
ENVIRONMENT=production

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=100/minute
```

**Frontend** (`frontend/.env.production`):
```bash
VITE_API_URL=https://api.yourdomain.com/api/v1
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_SENTRY_DSN=https://...@sentry.io/...
```

### 3. Install Dependencies

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm ci --production=false
```

---

## Database Setup

### 1. Run Migrations

```bash
cd backend

# Check current migration state
alembic current

# Run all pending migrations
alembic upgrade head

# Verify migration
alembic current
```

### 2. Verify RLS Policies

```sql
-- Run in Supabase SQL Editor
SELECT schemaname, tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public';

-- All tables should have rowsecurity = true
```

### 3. Create Database Indexes

Indexes are created by migrations, but verify:
```sql
SELECT indexname, tablename
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename;
```

---

## Backend Deployment

### Option A: Systemd Service

**1. Create service file** (`/etc/systemd/system/sales-agent-api.service`):
```ini
[Unit]
Description=Sales Agent API
After=network.target redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/sales-agent/backend
Environment=PATH=/opt/sales-agent/backend/venv/bin
EnvironmentFile=/opt/sales-agent/backend/.env
ExecStart=/opt/sales-agent/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**2. Create Celery worker service** (`/etc/systemd/system/sales-agent-celery.service`):
```ini
[Unit]
Description=Sales Agent Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/sales-agent/backend
Environment=PATH=/opt/sales-agent/backend/venv/bin
EnvironmentFile=/opt/sales-agent/backend/.env
ExecStart=/opt/sales-agent/backend/venv/bin/celery -A app.celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**3. Enable and start services**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable sales-agent-api sales-agent-celery
sudo systemctl start sales-agent-api sales-agent-celery
```

### Option B: Docker Deployment

**1. Build images**:
```bash
docker build -t sales-agent-api:latest -f backend/Dockerfile backend/
docker build -t sales-agent-frontend:latest -f frontend/Dockerfile frontend/
```

**2. Run with docker-compose**:
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  api:
    image: sales-agent-api:latest
    ports:
      - "8000:8000"
    env_file:
      - backend/.env
    depends_on:
      - redis
    restart: always

  celery:
    image: sales-agent-api:latest
    command: celery -A app.celery_app worker --loglevel=info
    env_file:
      - backend/.env
    depends_on:
      - redis
    restart: always

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: always

volumes:
  redis_data:
```

---

## Frontend Deployment

### 1. Build Production Assets

```bash
cd frontend
npm run build

# Output is in dist/
ls -la dist/
```

### 2. Deploy to Vercel (Recommended)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

### 3. Deploy to Static Host

```bash
# Copy dist to web server
rsync -avz dist/ user@server:/var/www/sales-agent/
```

---

## Nginx Configuration

### 1. Install SSL Certificates

```bash
# Using Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d api.yourdomain.com
```

### 2. Deploy Nginx Config

```bash
# Copy production config
sudo cp backend/nginx/nginx.prod.conf /etc/nginx/nginx.conf

# Update domain name
sudo sed -i 's/YOUR_DOMAIN/api.yourdomain.com/g' /etc/nginx/nginx.conf

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 3. Verify HTTPS

```bash
# Test SSL grade
curl -I https://api.yourdomain.com/api/v1/health

# Check SSL certificate
openssl s_client -connect api.yourdomain.com:443 -servername api.yourdomain.com
```

---

## Monitoring Setup

### 1. Prometheus Metrics

Configure Prometheus to scrape `/metrics`:
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'sales-agent'
    static_configs:
      - targets: ['localhost:8000']
    bearer_token: 'YOUR_METRICS_API_KEY'
    metrics_path: /metrics
    scheme: http
    headers:
      X-Metrics-Key: 'YOUR_METRICS_API_KEY'
```

### 2. Sentry Configuration

Sentry is auto-configured via environment variables. Verify:
```bash
# Check Sentry connection
curl -X POST https://api.yourdomain.com/api/v1/test-sentry
```

### 3. LangSmith Tracing

Verify LLM traces are appearing:
```bash
# Check LangSmith dashboard
open https://smith.langchain.com/
```

---

## Security Checklist

### Pre-Deployment

- [ ] All secrets rotated from development values
- [ ] `ENVIRONMENT=production` set
- [ ] `DEBUG=false` or not set
- [ ] SSL certificates installed and valid
- [ ] Rate limiting enabled (`RATE_LIMIT_ENABLED=true`)
- [ ] Webhook secrets configured
- [ ] Metrics endpoint protected (`METRICS_API_KEY` set)

### Post-Deployment

- [ ] Health check endpoints responding
- [ ] SSL grade A+ on SSL Labs
- [ ] No secrets in logs
- [ ] RLS policies active on all tables
- [ ] Error tracking receiving events
- [ ] Rate limiting working (test with `ab` or similar)

### Verification Commands

```bash
# Check no debug mode
curl -s https://api.yourdomain.com/api/v1/health | grep -i debug

# Verify rate limiting
for i in {1..20}; do curl -s -o /dev/null -w "%{http_code}\n" \
  https://api.yourdomain.com/api/v1/supabase-auth/login \
  -d '{"email":"test@test.com","password":"test"}'; done

# Check security headers
curl -I https://api.yourdomain.com/ | grep -E "X-|Strict-|Content-Security"

# Verify webhook protection
curl -X POST https://api.yourdomain.com/api/v1/webhooks/close/lead \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
# Should return 401 without valid signature
```

---

## Rollback Procedures

### Application Rollback

```bash
# 1. Stop services
sudo systemctl stop sales-agent-api sales-agent-celery

# 2. Checkout previous version
cd /opt/sales-agent
git checkout HEAD~1  # or specific commit

# 3. Reinstall dependencies
cd backend && pip install -r requirements.txt

# 4. Restart services
sudo systemctl start sales-agent-api sales-agent-celery
```

### Database Rollback

```bash
# 1. Check current migration
cd backend && alembic current

# 2. Rollback one migration
alembic downgrade -1

# 3. Or rollback to specific revision
alembic downgrade 017_cold_reach_tables
```

### Emergency Rollback (Blue-Green)

If using blue-green deployment:
```bash
# Switch load balancer to previous deployment
# (Implementation depends on your infrastructure)
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u sales-agent-api -n 50

# Check for port conflicts
sudo lsof -i :8000

# Verify environment
source /opt/sales-agent/backend/venv/bin/activate
python -c "from app.main import app; print('OK')"
```

### Database Connection Issues

```bash
# Test direct connection
python -c "
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    print(conn.execute(text('SELECT 1')).scalar())
"
```

### Redis Connection Issues

```bash
# Test Redis
redis-cli ping

# Check Redis logs
sudo journalctl -u redis -n 50
```

---

## Support

- **Documentation**: `/docs/` directory
- **Operations Runbook**: `docs/OPERATIONS_RUNBOOK.md`
- **Issue Tracker**: GitHub Issues
- **Emergency Contact**: See escalation matrix in runbook
