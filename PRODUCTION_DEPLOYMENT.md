# 🚀 Production Deployment Guide - Sales Agent

Complete guide to deploying Sales Agent to production with Claude SDK and DeepSeek integration.

---

## 📋 Pre-Deployment Checklist

### 1. Infrastructure Requirements

**Minimum Server Specs:**
- **CPU**: 4 cores (8 cores recommended)
- **RAM**: 8GB (16GB recommended)
- **Storage**: 50GB SSD
- **OS**: Ubuntu 22.04 LTS or later
- **Network**: Public IP with ports 80, 443 open

**Required Services:**
- Docker 24+ with Docker Compose
- SSL certificate (Let's Encrypt recommended)
- Domain name pointed to server IP

### 2. API Keys Required

```bash
# AI Providers
ANTHROPIC_API_KEY=sk-ant-api03-...     # Get from: https://console.anthropic.com/
DEEPSEEK_API_KEY=sk-...                # Get from: https://platform.deepseek.com/
CEREBRAS_API_KEY=csk-...               # Get from: https://cloud.cerebras.ai/
OLLAMA_API_KEY=ollama                  # Local (no key needed)

# CRM Integrations
CLOSE_API_KEY=...                      # Get from: https://app.close.com/settings/api/
APOLLO_API_KEY=...                     # Get from: https://app.apollo.io/settings/integrations
HUNTER_API_KEY=...                     # Get from: https://hunter.io/api_keys

# Voice/TTS
CARTESIA_API_KEY=...                   # Get from: https://cartesia.ai/

# Monitoring (Optional)
LANGCHAIN_API_KEY=...                  # Get from: https://smith.langchain.com/
SENTRY_DSN=...                         # Get from: https://sentry.io/
```

---

## 🏗️ Step 1: Server Setup

### Install Docker

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin

# Verify installation
docker --version
docker compose version

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### Clone Repository

```bash
# Clone the repository
git clone https://github.com/ScientiaCapital/sales-agent.git
cd sales-agent

# Checkout main branch
git checkout main
```

---

## 🔐 Step 2: Environment Configuration

### Create Production .env File

```bash
# Copy example
cp .env.example .env.production

# Edit with your values
nano .env.production
```

**Production .env Template:**

```bash
# ========== AI Providers ==========
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
DEEPSEEK_API_KEY=sk-your-key-here
CEREBRAS_API_KEY=csk-your-key-here
OLLAMA_API_KEY=ollama

# ========== Database ==========
POSTGRES_USER=sales_agent_prod
POSTGRES_PASSWORD=CHANGE_ME_TO_STRONG_PASSWORD
POSTGRES_DB=sales_agent_prod
DATABASE_URL=postgresql+psycopg://sales_agent_prod:CHANGE_ME_TO_STRONG_PASSWORD@postgres:5432/sales_agent_prod

# ========== Redis ==========
REDIS_URL=redis://redis:6379/0

# ========== CRM ==========
CLOSE_API_KEY=your-close-key
APOLLO_API_KEY=your-apollo-key
HUNTER_API_KEY=your-hunter-key

# ========== Voice ==========
CARTESIA_API_KEY=your-cartesia-key

# ========== LangChain/LangSmith ==========
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=sales-agent-production

# ========== Monitoring ==========
SENTRY_DSN=your-sentry-dsn
DATADOG_ENABLED=false
ENVIRONMENT=production

# ========== Application ==========
DATABASE_ECHO=false
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
TESTING=false
```

### Secure the Environment File

```bash
# Set proper permissions
chmod 600 .env.production

# Never commit to git
echo ".env.production" >> .gitignore
```

---

## 🔒 Step 3: SSL Certificate Setup

### Option A: Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt install certbot

# Get certificate (replace with your domain)
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Certificates will be in:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem

# Copy to project
sudo mkdir -p ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/
sudo chown -R $USER:$USER ssl/
chmod 600 ssl/*
```

### Option B: Self-Signed (Development Only)

```bash
mkdir -p ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/privkey.pem \
  -out ssl/fullchain.pem \
  -subj "/CN=localhost"
```

---

## 🚢 Step 4: Build and Deploy

### Build Docker Images

```bash
# Load environment variables
export $(cat .env.production | grep -v '^#' | xargs)

# Build images
docker compose -f docker-compose.production.yml build

# Verify images
docker images | grep sales-agent
```

### Initialize Database

```bash
# Start database first
docker compose -f docker-compose.production.yml up -d postgres redis

# Wait for database to be ready
sleep 10

# Run migrations
docker compose -f docker-compose.production.yml run --rm backend alembic upgrade head
```

### Start All Services

```bash
# Start all services
docker compose -f docker-compose.production.yml up -d

# Check status
docker compose -f docker-compose.production.yml ps

# View logs
docker compose -f docker-compose.production.yml logs -f
```

---

## ✅ Step 5: Verification

### Health Checks

```bash
# Backend API health
curl http://localhost:8001/api/health

# Expected response:
# {"status":"healthy","timestamp":"2025-11-01T..."}

# Database connection
curl http://localhost:8001/api/health/db

# Redis connection
curl http://localhost:8001/api/health/redis

# AI providers health
curl http://localhost:8001/api/costs/ai/health
```

### Test Unified Claude SDK

```bash
# Get AI cost stats
curl http://localhost:8001/api/costs/ai

# Expected response:
# {
#   "total_requests": 0,
#   "total_cost_usd": 0.0,
#   "provider_breakdown": {...}
# }
```

### Test Frontend

```bash
# Open in browser
open http://localhost

# Or curl
curl -I http://localhost
```

---

## 📊 Step 6: Monitoring Setup

### Enable Logging

```bash
# View real-time logs
docker compose -f docker-compose.production.yml logs -f backend

# View specific service
docker compose -f docker-compose.production.yml logs -f celery

# Export logs
docker compose -f docker-compose.production.yml logs --no-color > deployment.log
```

### Set Up Alerts

```bash
# Install monitoring tools
pip install datadog sentry-sdk

# Configure in .env.production
SENTRY_DSN=your-sentry-dsn
DATADOG_ENABLED=true
DATADOG_API_KEY=your-datadog-key
```

---

## 🔄 Step 7: CI/CD Integration

### GitHub Actions Setup

1. **Add Repository Secrets:**
   - Go to: Settings → Secrets and variables → Actions
   - Add secrets:
     ```
     DOCKER_REGISTRY=your-registry
     DOCKER_USERNAME=your-username
     DOCKER_PASSWORD=your-password
     PRODUCTION_HOST=your-server-ip
     PRODUCTION_USER=your-ssh-user
     PRODUCTION_SSH_KEY=your-private-key
     ```

2. **Trigger Deployment:**
   ```bash
   # Tag a new release
   git tag v1.0.0
   git push origin v1.0.0

   # GitHub Actions will automatically deploy
   ```

### Manual Deployment

```bash
# SSH to production server
ssh user@your-server

# Navigate to project
cd /opt/sales-agent

# Pull latest code
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.production.yml up -d --build

# Run migrations
docker compose -f docker-compose.production.yml run --rm backend alembic upgrade head

# Health check
curl http://localhost:8001/api/health
```

---

## 📈 Step 8: Performance Optimization

### Database Optimization

```bash
# Connect to PostgreSQL
docker exec -it sales-agent-postgres-prod psql -U sales_agent_prod -d sales_agent_prod

# Create indexes
CREATE INDEX idx_leads_created_at ON leads(created_at DESC);
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_agent_executions_agent_type ON agent_executions(agent_type);

# Analyze query performance
EXPLAIN ANALYZE SELECT * FROM leads WHERE status = 'hot';
```

### Redis Optimization

```bash
# Connect to Redis
docker exec -it sales-agent-redis-prod redis-cli

# Check memory usage
INFO memory

# Check key statistics
INFO keyspace

# Set eviction policy (already set in docker-compose)
CONFIG SET maxmemory-policy allkeys-lru
```

### Application Tuning

Edit `docker-compose.production.yml`:

```yaml
backend:
  deploy:
    resources:
      limits:
        cpus: '4'
        memory: 4G
    replicas: 4  # Increase for higher load
```

---

## 🔧 Step 9: Backup Strategy

### Database Backups

```bash
# Create backup directory
mkdir -p /opt/backups

# Automated daily backup script
cat > /opt/backups/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/opt/backups
DATE=$(date +%Y%m%d_%H%M%S)
docker exec sales-agent-postgres-prod pg_dump -U sales_agent_prod sales_agent_prod | gzip > $BACKUP_DIR/backup_$DATE.sql.gz
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete
EOF

chmod +x /opt/backups/backup.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/backups/backup.sh") | crontab -
```

### Restore from Backup

```bash
# Stop services
docker compose -f docker-compose.production.yml stop backend celery

# Restore database
gunzip < backup_YYYYMMDD_HHMMSS.sql.gz | docker exec -i sales-agent-postgres-prod psql -U sales_agent_prod sales_agent_prod

# Restart services
docker compose -f docker-compose.production.yml start backend celery
```

---

## 🚨 Troubleshooting

### Common Issues

**Issue: Backend not starting**
```bash
# Check logs
docker compose -f docker-compose.production.yml logs backend

# Common fixes:
# 1. Database not ready - wait 30 seconds
# 2. Missing API keys - check .env.production
# 3. Port conflict - check if 8001 is available
```

**Issue: Database connection failed**
```bash
# Check PostgreSQL status
docker compose -f docker-compose.production.yml ps postgres

# Restart database
docker compose -f docker-compose.production.yml restart postgres

# Check credentials
docker compose -f docker-compose.production.yml exec backend env | grep DATABASE_URL
```

**Issue: High CPU usage**
```bash
# Check resource usage
docker stats

# Scale down replicas temporarily
docker compose -f docker-compose.production.yml scale backend=2 celery=1

# Check for runaway processes
docker compose -f docker-compose.production.yml top
```

---

## 📞 Support

### Logs Location
- **Backend**: `docker compose logs backend`
- **Celery**: `docker compose logs celery`
- **Database**: `docker compose logs postgres`
- **All**: `docker compose logs --tail=100 -f`

### Useful Commands

```bash
# Restart all services
docker compose -f docker-compose.production.yml restart

# Stop all services
docker compose -f docker-compose.production.yml down

# Remove all data (DANGEROUS!)
docker compose -f docker-compose.production.yml down -v

# Update to latest version
git pull origin main
docker compose -f docker-compose.production.yml up -d --build

# Scale services
docker compose -f docker-compose.production.yml scale backend=4 celery=2

# Check resource usage
docker stats --no-stream
```

---

## ✅ Post-Deployment Checklist

- [ ] All health checks passing
- [ ] SSL certificate valid
- [ ] Database migrations completed
- [ ] API keys configured correctly
- [ ] Monitoring/logging enabled
- [ ] Backup script running
- [ ] CI/CD pipeline configured
- [ ] Domain DNS pointed correctly
- [ ] Firewall configured (80, 443 open)
- [ ] Load testing completed
- [ ] Documentation updated
- [ ] Team notified of deployment

---

## 🎯 Success Metrics

Monitor these metrics post-deployment:

| Metric | Target | Command |
|--------|--------|---------|
| API Response Time | <500ms | `curl -w "%{time_total}\n" http://localhost:8001/api/health` |
| CPU Usage | <70% | `docker stats --no-stream` |
| Memory Usage | <80% | `docker stats --no-stream` |
| Error Rate | <1% | Check logs and Sentry |
| Uptime | 99.9% | Monitor endpoint |
| AI Cost per Lead | <$0.0005 | `curl http://localhost:8001/api/costs/ai` |

---

## 🚀 You're Live!

Your Sales Agent is now running in production with:
- ✅ Unified Claude SDK with DeepSeek (11x cost savings)
- ✅ Full CRM integration (Close, Apollo, LinkedIn)
- ✅ Multi-agent system (6 LangGraph agents)
- ✅ Voice capabilities (Cartesia TTS)
- ✅ Production-grade infrastructure
- ✅ Automated CI/CD pipeline
- ✅ Comprehensive monitoring

**Next Steps:**
1. Start sending production leads
2. Monitor cost dashboard
3. Verify savings vs Claude-only
4. Scale as needed

**Questions?** Check logs first, then consult troubleshooting section above.
