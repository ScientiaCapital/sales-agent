# Browserbase Session Pool - Integration Guide

## Quick Integration Steps

### Step 1: Update Environment Variables

Add to `/backend/.env`:

```bash
# Browserbase Session Pool Configuration
BROWSERBASE_API_KEY=your_api_key_here
BROWSERBASE_PROJECT_ID=your_project_id_here

# Optional: Tune for your workload
LINKEDIN_COMPANY_MAX_SESSIONS=25        # Max concurrent sessions (default: 25)
LINKEDIN_SESSION_TIMEOUT_SEC=7200       # 2 hours (default: 7200)
LINKEDIN_SESSION_MAX_USES=15            # Rotate after N companies (default: 15)
```

---

### Step 2: Update Existing Scraper to Use Pool

#### Before (browserbase_team_scraper.py)

```python
async def scrape_team_page(self, website_url: str) -> List[Dict[str, str]]:
    # Create new session (7-15 seconds)
    session_id, connect_url = await self._create_session()

    # Scrape
    team_contacts = await self._scrape_with_session(session_id, website_url, connect_url)

    # Close session
    await self._close_session(session_id)

    return team_contacts
```

#### After (with session pool)

```python
from app.services.browserbase_session_pool import get_session_pool

async def scrape_team_page(self, website_url: str) -> List[Dict[str, str]]:
    pool = await get_session_pool()

    # Checkout session from pool (<1 second after warm-up)
    session = await pool.checkout()

    try:
        # Scrape using pooled session
        team_contacts = await self._scrape_with_session(
            session.session_id,
            website_url,
            session.connect_url
        )
        return team_contacts
    finally:
        # CRITICAL: Return session to pool
        await pool.checkin(session)
```

---

### Step 3: Add Pool Initialization to Startup

Update `/backend/start_server.py`:

```python
from app.services.browserbase_session_pool import get_session_pool, close_session_pool

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up FastAPI application...")

    # Warm up Browserbase session pool
    try:
        pool = await get_session_pool()
        await pool.warm_up(count=5)  # Pre-create 5 sessions
        logger.info("✓ Browserbase session pool warmed up")
    except Exception as e:
        logger.warning(f"Failed to warm up session pool: {e}")

    # ... other startup tasks ...

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down FastAPI application...")

    # Close all Browserbase sessions
    await close_session_pool()
    logger.info("✓ Browserbase session pool closed")

    # ... other shutdown tasks ...
```

---

### Step 4: Update Deep Scraper Script

Update `/backend/deep_scrape_companies.py`:

```python
from app.services.browserbase_session_pool import get_session_pool, close_session_pool

async def scrape_linkedin_via_google(company_name: str, company_domain: str) -> Dict[str, Any]:
    """Scrape LinkedIn via Google using session pool."""
    pool = await get_session_pool()
    session = await pool.checkout()

    try:
        result = await _scrape_with_session(session, company_name, company_domain)
        return result
    finally:
        await pool.checkin(session)

async def main():
    # Warm up pool at start
    pool = await get_session_pool()
    await pool.warm_up(count=5)

    # Process companies
    for company in companies:
        result = await scrape_linkedin_via_google(company["name"], company["domain"])
        # ... save result ...

    # Cleanup at end
    await close_session_pool()
```

---

### Step 5: Test Integration

```bash
# Run test suite
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
source ../venv/bin/activate
python test_session_pool.py
```

Expected output:
```
✓ TEST PASSED: Basic checkout/checkin working
✓ TEST PASSED: Session reuse working
✓ TEST PASSED: Session rotation working
✓ TEST PASSED: Concurrent access working
✓ TEST PASSED: Pool statistics working
✓ TEST PASSED: Pool warm-up working
✓ TEST PASSED: Graceful shutdown completed
✅ ALL TESTS PASSED
```

---

### Step 6: Run Example Script

```bash
python example_linkedin_scrape_with_pool.py
```

This will scrape 6 example companies using the session pool.

---

## Common Integration Patterns

### Pattern 1: Concurrent Batch Processing

```python
from app.services.browserbase_session_pool import get_session_pool

async def process_batch(companies: List[str], max_concurrent: int = 10):
    pool = await get_session_pool()

    # Pre-warm for concurrent workload
    await pool.warm_up(count=min(5, max_concurrent))

    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_one(company):
        async with semaphore:
            session = await pool.checkout()
            try:
                return await scrape_linkedin(session, company)
            finally:
                await pool.checkin(session)

    results = await asyncio.gather(*[process_one(c) for c in companies])
    return results
```

---

### Pattern 2: Long-Running Worker

```python
async def linkedin_worker(queue: asyncio.Queue):
    pool = await get_session_pool()

    while True:
        company = await queue.get()
        if company is None:  # Poison pill
            break

        session = await pool.checkout()
        try:
            result = await scrape_linkedin(session, company)
            # ... process result ...
        finally:
            await pool.checkin(session)

        queue.task_done()
```

---

### Pattern 3: API Endpoint Integration

```python
from fastapi import APIRouter
from app.services.browserbase_session_pool import get_session_pool

router = APIRouter()

@router.post("/api/linkedin/enrich")
async def enrich_company(company_name: str):
    pool = await get_session_pool()
    session = await pool.checkout()

    try:
        result = await scrape_linkedin(session, company_name)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        await pool.checkin(session)
```

---

## Performance Tuning

### Tune Session Rotation

```bash
# For high-volume scraping (reduce session creation overhead)
LINKEDIN_SESSION_MAX_USES=25            # Rotate after 25 companies (instead of 15)

# For stealth (rotate frequently to avoid detection)
LINKEDIN_SESSION_MAX_USES=10            # Rotate after 10 companies
```

---

### Tune Concurrency

```bash
# For high-throughput (Browserbase Startup plan)
LINKEDIN_COMPANY_MAX_SESSIONS=50        # 50 concurrent sessions

# For cost optimization (Browserbase Developer plan)
LINKEDIN_COMPANY_MAX_SESSIONS=10        # 10 concurrent sessions
```

---

### Tune Session Timeout

```bash
# For long-running batches (overnight scraping)
LINKEDIN_SESSION_TIMEOUT_SEC=14400      # 4 hours

# For short-burst scraping (quick API calls)
LINKEDIN_SESSION_TIMEOUT_SEC=3600       # 1 hour
```

---

## Monitoring

### Add Pool Health Check

```python
from fastapi import APIRouter
from app.services.browserbase_session_pool import get_session_pool

@router.get("/api/health/browserbase")
async def browserbase_health():
    try:
        pool = await get_session_pool()
        stats = await pool.get_pool_stats()
        return {
            "status": "healthy",
            "pool_stats": stats
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
```

---

### Add Prometheus Metrics

```python
from prometheus_client import Gauge

# Define metrics
browserbase_sessions_total = Gauge("browserbase_sessions_total", "Total sessions in pool")
browserbase_sessions_active = Gauge("browserbase_sessions_active", "Active sessions")
browserbase_sessions_available = Gauge("browserbase_sessions_available", "Available sessions")

# Update metrics
async def update_pool_metrics():
    pool = await get_session_pool()
    stats = await pool.get_pool_stats()

    browserbase_sessions_total.set(stats["total_sessions"])
    browserbase_sessions_active.set(stats["active_sessions"])
    browserbase_sessions_available.set(stats["available_sessions"])
```

---

## Troubleshooting Integration

### Issue: Import Error

**Error:**
```python
ModuleNotFoundError: No module named 'app.services.browserbase_session_pool'
```

**Solution:**
```bash
# Verify file exists
ls -la /Users/tmkipper/Desktop/tk_projects/sales-agent/backend/app/services/browserbase_session_pool.py

# Check Python path
export PYTHONPATH=/Users/tmkipper/Desktop/tk_projects/sales-agent/backend:$PYTHONPATH
```

---

### Issue: Missing Environment Variables

**Error:**
```python
ValueError: Browserbase credentials required. Set BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID
```

**Solution:**
```bash
# Verify .env file
cat /Users/tmkipper/Desktop/tk_projects/sales-agent/backend/.env | grep BROWSERBASE

# Load .env manually
source /Users/tmkipper/Desktop/tk_projects/sales-agent/backend/.env
```

---

### Issue: Session Deadlock

**Error:**
```python
# checkout() hangs forever
session = await pool.checkout()  # ← Hangs here
```

**Solution:**
```python
# Add timeout to checkout
try:
    session = await asyncio.wait_for(pool.checkout(), timeout=30.0)
except asyncio.TimeoutError:
    logger.error("Pool checkout timeout - possible deadlock")
    # Debug: Check pool stats
    stats = await pool.get_pool_stats()
    logger.error(f"Pool stats: {stats}")
```

**Root Cause:** Missing `checkin()` in previous calls

**Fix:** Audit code for `checkout()` without matching `checkin()`:
```bash
grep -r "pool.checkout()" --include="*.py" | wc -l
grep -r "pool.checkin()" --include="*.py" | wc -l
# These counts should match!
```

---

## Migration Checklist

- [ ] Add environment variables to `.env`
- [ ] Update scraper to use `get_session_pool()`
- [ ] Replace `_create_session()` with `pool.checkout()`
- [ ] Replace `_close_session()` with `pool.checkin()`
- [ ] Add `try/finally` blocks for checkin
- [ ] Add pool warm-up to startup
- [ ] Add pool cleanup to shutdown
- [ ] Run test suite (`test_session_pool.py`)
- [ ] Run example script (`example_linkedin_scrape_with_pool.py`)
- [ ] Test with real LinkedIn scraping
- [ ] Monitor pool stats in production
- [ ] Set up alerts for pool health

---

## Next Steps

1. **Test locally**: Run test suite and example script
2. **Update scrapers**: Migrate existing Browserbase code to use pool
3. **Deploy**: Push to production with warm-up on startup
4. **Monitor**: Track pool utilization and session rotation
5. **Optimize**: Tune max_uses, timeout, and concurrency based on metrics

---

## Support

- **Documentation**: `/backend/BROWSERBASE_SESSION_POOL.md`
- **Examples**: `/backend/example_linkedin_scrape_with_pool.py`
- **Tests**: `/backend/test_session_pool.py`
- **Browserbase Docs**: https://docs.browserbase.com

For questions, check the FAQ in `BROWSERBASE_SESSION_POOL.md`.
