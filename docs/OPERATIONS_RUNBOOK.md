# Sales-Agent Operations Runbook

**Version**: 1.0.0
**Last Updated**: 2025-12-27
**On-Call Escalation**: See [Escalation Matrix](#escalation-matrix)

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Health Checks](#health-checks)
3. [Common Incidents](#common-incidents)
4. [Database Operations](#database-operations)
5. [Security Incidents](#security-incidents)
6. [Performance Issues](#performance-issues)
7. [Escalation Matrix](#escalation-matrix)

---

## Quick Reference

### Critical Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `GET /api/v1/health` | Liveness probe | `{"status": "healthy"}` |
| `GET /api/v1/health/ready` | Readiness probe | `{"status": "ready", ...}` |
| `GET /metrics` | Prometheus metrics | Requires `X-Metrics-Key` header |

### Environment Variables (Required)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://...
SUPABASE_URL=https://...
SUPABASE_SERVICE_KEY=...

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
CLOSE_WEBHOOK_SECRET=...        # Close CRM webhook verification
METRICS_API_KEY=...             # Prometheus metrics access
JWT_SECRET_KEY=...              # JWT token signing

# Monitoring
SENTRY_DSN=...                  # Error tracking
LANGSMITH_API_KEY=...           # LLM observability
```

### Service Ports

| Service | Port | Protocol |
|---------|------|----------|
| FastAPI Backend | 8000 | HTTP |
| Celery Worker | - | N/A |
| Celery Flower | 5555 | HTTP |
| Redis | 6379 | TCP |
| PostgreSQL | 5432 | TCP |

---

## Health Checks

### Backend Health Check

```bash
# Basic liveness check
curl -s http://localhost:8000/api/v1/health | jq .

# Full readiness check (includes DB, Redis, cache)
curl -s http://localhost:8000/api/v1/health/ready | jq .
```

**Expected Response**:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "cache_hit_rate": 0.85
}
```

### Celery Worker Health

```bash
# Check worker status
celery -A app.celery_app inspect ping

# Check active tasks
celery -A app.celery_app inspect active

# Check scheduled tasks
celery -A app.celery_app inspect scheduled
```

### Database Connection Test

```bash
# Test Supabase connection
python -c "
from supabase import create_client
import os
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
print('Connected:', client.table('leads').select('id').limit(1).execute())
"
```

---

## Common Incidents

### INC-001: API Response Times > 500ms

**Symptoms**: Slow API responses, user complaints, monitoring alerts

**Diagnosis**:
```bash
# Check current request latencies
curl -s http://localhost:8000/metrics | grep http_request_duration

# Check database query times
curl -s http://localhost:8000/api/v1/metrics/summary | jq .database

# Check Redis latency
redis-cli --latency-history
```

**Resolution Steps**:
1. Check for N+1 queries in slow endpoints (Sentry traces)
2. Verify database indexes are present
3. Check Redis cache hit rate (should be > 80%)
4. Review recent deployments for performance regressions

### INC-002: Rate Limit Exceeded Errors

**Symptoms**: Users receiving 429 errors, "Rate limit exceeded" messages

**Diagnosis**:
```bash
# Check rate limit logs
grep "Rate limit exceeded" /var/log/sales-agent/api.log | tail -20

# Check SlowAPI state
redis-cli keys "slowapi:*" | head -20
```

**Resolution Steps**:
1. Identify if legitimate traffic or attack
2. For legitimate users: Temporarily increase limits in `app/core/rate_limit.py`
3. For attacks: Block IP at nginx level
4. Clear rate limit counters if needed:
   ```bash
   redis-cli keys "slowapi:*" | xargs redis-cli del
   ```

### INC-003: Webhook Verification Failures

**Symptoms**: CRM webhooks returning 401/403, missing data updates

**Diagnosis**:
```bash
# Check webhook logs
grep "webhook.*signature" /var/log/sales-agent/api.log | tail -50

# Verify webhook secret is set
echo $CLOSE_WEBHOOK_SECRET | head -c 8
```

**Resolution Steps**:
1. Verify `CLOSE_WEBHOOK_SECRET` environment variable is set
2. Check if CRM webhook secret was rotated
3. Compare signature algorithm (should be HMAC-SHA256)
4. Test webhook manually:
   ```bash
   curl -X POST http://localhost:8000/api/v1/webhooks/close/... \
     -H "X-Close-Signature: sha256=..." \
     -d '{"test": true}'
   ```

### INC-004: Celery Tasks Stuck

**Symptoms**: Background jobs not processing, queue growing

**Diagnosis**:
```bash
# Check queue lengths
celery -A app.celery_app inspect reserved

# Check for zombie workers
celery -A app.celery_app inspect active_queues

# Check task failures
celery -A app.celery_app events --dump
```

**Resolution Steps**:
1. Restart Celery workers: `supervisorctl restart celery-worker`
2. Clear stuck tasks if needed:
   ```bash
   celery -A app.celery_app purge
   ```
3. Check Redis memory usage
4. Review task logs for exceptions

---

## Database Operations

### Emergency Database Rollback

```bash
# Check current migration version
cd backend && alembic current

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade 017_cold_reach_tables
```

### Database Connection Pool Issues

**Symptoms**: "too many connections" errors, connection timeouts

**Diagnosis**:
```sql
-- Check active connections (run in Supabase SQL Editor)
SELECT count(*) FROM pg_stat_activity;

-- Check connection details
SELECT usename, application_name, client_addr, state, query_start
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;
```

**Resolution**:
1. Restart API servers to reset connection pools
2. Check for connection leaks in code
3. Increase pool size if legitimate load:
   ```python
   # In app/models/database.py
   engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=10)
   ```

### RLS Policy Issues

**Symptoms**: "permission denied" errors, empty query results

**Diagnosis**:
```sql
-- Check RLS status on tables
SELECT schemaname, tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public' AND rowsecurity = true;

-- Check policies
SELECT * FROM pg_policies WHERE schemaname = 'public';
```

**Resolution**:
1. Verify service role key is being used
2. Check if user has correct role assigned
3. Temporarily disable RLS for debugging:
   ```sql
   ALTER TABLE table_name DISABLE ROW LEVEL SECURITY;
   ```

---

## Security Incidents

### SEC-001: Suspected Brute Force Attack

**Symptoms**: High rate of 401/403 on auth endpoints, same IP

**Immediate Actions**:
1. Block IP at nginx:
   ```bash
   echo "deny 1.2.3.4;" >> /etc/nginx/conf.d/blocklist.conf
   nginx -s reload
   ```
2. Check affected accounts:
   ```bash
   grep "login.*failed" /var/log/sales-agent/api.log | grep "1.2.3.4"
   ```
3. Force password reset for affected users

### SEC-002: Suspicious Webhook Activity

**Symptoms**: Webhook signature failures from unexpected IPs

**Immediate Actions**:
1. Rotate webhook secret immediately
2. Check for successful unauthorized requests
3. Audit data changes in last 24 hours
4. Report to security team

### SEC-003: Exposed Credentials

**Symptoms**: Secrets found in logs, version control, or public

**Immediate Actions**:
1. Rotate ALL affected credentials immediately
2. Search for usage of compromised credentials:
   ```bash
   grep -r "OLD_SECRET" /var/log/ --include="*.log"
   ```
3. Force re-authentication for all users
4. Review audit logs for unauthorized access

---

## Performance Issues

### High Memory Usage

**Diagnosis**:
```bash
# Check process memory
ps aux --sort=-%mem | head -10

# Check Python memory leaks
# Add to code temporarily:
import tracemalloc
tracemalloc.start()
# ... later ...
snapshot = tracemalloc.take_snapshot()
```

**Resolution**:
1. Restart affected workers
2. Check for large in-memory caches
3. Review recent code changes for memory leaks
4. Consider increasing instance size

### High CPU Usage

**Diagnosis**:
```bash
# Check process CPU
top -bn1 | head -20

# Profile specific endpoint
py-spy record -o profile.svg --pid $(pgrep -f uvicorn)
```

**Resolution**:
1. Identify hot paths using profiler
2. Check for infinite loops or recursive calls
3. Optimize database queries
4. Scale horizontally if needed

---

## Escalation Matrix

| Severity | Response Time | Escalation Path |
|----------|---------------|-----------------|
| P1 (Critical) | 15 min | On-call → Team Lead → CTO |
| P2 (High) | 1 hour | On-call → Team Lead |
| P3 (Medium) | 4 hours | On-call → Daily standup |
| P4 (Low) | 24 hours | Ticket queue |

### P1 Criteria
- Complete service outage
- Data breach or security incident
- Customer-facing errors > 10%
- Payment/billing system down

### Contact Information

| Role | Contact | Backup |
|------|---------|--------|
| On-call Engineer | (via PagerDuty) | Slack #oncall |
| Team Lead | @team-lead | @backup-lead |
| Security | @security-team | security@company.com |
| Database Admin | @dba | (via PagerDuty) |

---

## Appendix: Useful Commands

```bash
# View recent logs
tail -f /var/log/sales-agent/api.log | jq .

# Check system resources
htop

# Test database connection
pg_isready -h localhost -p 5432

# Redis CLI
redis-cli info memory
redis-cli info clients

# Nginx status
nginx -t
systemctl status nginx

# Celery status
celery -A app.celery_app status
```
