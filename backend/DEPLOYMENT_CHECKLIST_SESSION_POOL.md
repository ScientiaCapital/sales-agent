# Browserbase Session Pool - Deployment Checklist

## Pre-Deployment Checklist

### 1. Environment Setup
- [ ] Add `BROWSERBASE_API_KEY` to `.env`
- [ ] Add `BROWSERBASE_PROJECT_ID` to `.env`
- [ ] Verify credentials work: `curl -H "x-bb-api-key: $BROWSERBASE_API_KEY" https://api.browserbase.com/v1/sessions`
- [ ] Optional: Add `LINKEDIN_COMPANY_MAX_SESSIONS` (default: 25)
- [ ] Optional: Add `LINKEDIN_SESSION_TIMEOUT_SEC` (default: 7200)
- [ ] Optional: Add `LINKEDIN_SESSION_MAX_USES` (default: 15)

### 2. Dependencies
- [ ] Install `playwright`: `pip install playwright`
- [ ] Install `httpx`: `pip install httpx` (likely already installed)
- [ ] Install `python-dotenv`: `pip install python-dotenv` (likely already installed)
- [ ] Install Playwright browsers: `playwright install chromium`

### 3. File Verification
- [ ] Core implementation exists: `/backend/app/services/browserbase_session_pool.py`
- [ ] Test suite exists: `/backend/test_session_pool.py`
- [ ] Example script exists: `/backend/example_linkedin_scrape_with_pool.py`

### 4. Testing
- [ ] Run syntax check: `python3 -m py_compile app/services/browserbase_session_pool.py`
- [ ] Run test suite: `python test_session_pool.py`
- [ ] Run example script: `python example_linkedin_scrape_with_pool.py`
- [ ] Test with 1 real company (manual verification)
- [ ] Test with 10 real companies (concurrent verification)

---

## Integration Checklist

### 5. Update Existing Scrapers

#### Option A: Update `browserbase_team_scraper.py`
- [ ] Add import: `from app.services.browserbase_session_pool import get_session_pool`
- [ ] Replace `_create_session()` with `pool.checkout()`
- [ ] Replace `_close_session()` with `pool.checkin()`
- [ ] Add try/finally blocks for checkin
- [ ] Test updated scraper

#### Option B: Update `deep_scrape_companies.py`
- [ ] Add import: `from app.services.browserbase_session_pool import get_session_pool, close_session_pool`
- [ ] Add pool initialization at start of `main()`
- [ ] Add pool warm-up: `await pool.warm_up(5)`
- [ ] Update `scrape_linkedin_via_google()` to use pool
- [ ] Add pool cleanup at end: `await close_session_pool()`
- [ ] Test updated script

### 6. Update Server Startup/Shutdown

#### Update `/backend/start_server.py`
- [ ] Add import: `from app.services.browserbase_session_pool import get_session_pool, close_session_pool`
- [ ] Add to `startup_event()`:
  ```python
  try:
      pool = await get_session_pool()
      await pool.warm_up(count=5)
      logger.info("✓ Browserbase session pool warmed up")
  except Exception as e:
      logger.warning(f"Failed to warm up session pool: {e}")
  ```
- [ ] Add to `shutdown_event()`:
  ```python
  await close_session_pool()
  logger.info("✓ Browserbase session pool closed")
  ```
- [ ] Test server startup/shutdown

### 7. Add Monitoring (Optional but Recommended)

#### Option A: Health Check Endpoint
- [ ] Add to FastAPI router:
  ```python
  @router.get("/api/health/browserbase")
  async def browserbase_health():
      pool = await get_session_pool()
      stats = await pool.get_pool_stats()
      return {"status": "healthy", "pool_stats": stats}
  ```
- [ ] Test endpoint: `curl http://localhost:8001/api/health/browserbase`

#### Option B: Logging
- [ ] Add periodic stats logging:
  ```python
  async def log_pool_stats():
      while True:
          stats = await pool.get_pool_stats()
          logger.info(f"Pool stats: {stats}")
          await asyncio.sleep(300)  # Every 5 minutes
  ```

---

## Production Deployment

### 8. Deploy to Environment

#### Development
- [ ] Deploy code with session pool
- [ ] Verify `.env` variables loaded
- [ ] Check logs for pool initialization: `✓ Browserbase session pool warmed up`
- [ ] Test with 5 companies
- [ ] Monitor pool stats for 1 hour

#### Staging
- [ ] Deploy code with session pool
- [ ] Verify `.env` variables loaded
- [ ] Run integration tests
- [ ] Test with 50 companies
- [ ] Monitor pool stats for 24 hours
- [ ] Check for session leaks (active sessions should return to 0)

#### Production
- [ ] Deploy code with session pool
- [ ] Verify `.env` variables loaded
- [ ] Monitor pool stats for first 1 hour
- [ ] Check for errors in logs
- [ ] Verify session rotation (check `usage_count` in logs)
- [ ] Monitor costs (Browserbase dashboard)

### 9. Performance Tuning

#### If Pool Utilization > 80%
- [ ] Increase `LINKEDIN_COMPANY_MAX_SESSIONS` (e.g., 50)
- [ ] Check Browserbase plan limits

#### If Session Rotation Too Frequent
- [ ] Increase `LINKEDIN_SESSION_MAX_USES` (e.g., 25)
- [ ] Increase `LINKEDIN_SESSION_TIMEOUT_SEC` (e.g., 14400)

#### If LinkedIn Rate Limiting
- [ ] Decrease `LINKEDIN_SESSION_MAX_USES` (e.g., 10)
- [ ] Add delays between scrapes: `await asyncio.sleep(2)`
- [ ] Reduce concurrent sessions

---

## Post-Deployment Verification

### 10. Metrics to Monitor

#### Day 1
- [ ] Pool initialization success rate: 100%
- [ ] Session creation success rate: >95%
- [ ] Pool utilization: <80%
- [ ] Active sessions return to 0: Yes
- [ ] Errors in logs: 0

#### Week 1
- [ ] Average scrape time: ~3 seconds (after first)
- [ ] Session rotation rate: ~1 per 15 companies
- [ ] Total sessions created: <10% of companies scraped
- [ ] Browserbase costs: 85% reduction vs no pool
- [ ] LinkedIn rate limiting: 0 incidents

### 11. Alerts to Set Up

- [ ] Alert if pool utilization > 90% for 5 minutes
- [ ] Alert if session creation fails 3+ times in 1 hour
- [ ] Alert if active sessions don't return to 0 after 2 hours
- [ ] Alert if pool initialization fails on startup
- [ ] Alert if Browserbase costs spike >20% in 1 day

---

## Rollback Plan

### If Critical Issues Occur

1. **Immediate Rollback**
   - [ ] Deploy previous version (without session pool)
   - [ ] Verify old scraper works
   - [ ] Document issue in incident log

2. **Root Cause Analysis**
   - [ ] Check logs for error messages
   - [ ] Check pool stats at time of incident
   - [ ] Check Browserbase API status
   - [ ] Check environment variables

3. **Fix and Redeploy**
   - [ ] Fix identified issue
   - [ ] Test fix in development
   - [ ] Test fix in staging
   - [ ] Redeploy to production with fix

---

## Common Issues and Solutions

### Issue 1: Pool initialization fails
**Error**: `ValueError: Browserbase credentials required`

**Solution**:
- [ ] Verify `.env` file exists
- [ ] Verify `BROWSERBASE_API_KEY` and `BROWSERBASE_PROJECT_ID` are set
- [ ] Check environment variables loaded: `echo $BROWSERBASE_API_KEY`
- [ ] Test credentials manually: `curl -H "x-bb-api-key: $BROWSERBASE_API_KEY" https://api.browserbase.com/v1/sessions`

### Issue 2: Session creation fails
**Error**: `Failed to create Browserbase session after 3 attempts`

**Solution**:
- [ ] Check Browserbase plan limits (concurrent sessions, API rate)
- [ ] Check Browserbase API status: https://status.browserbase.com
- [ ] Check network connectivity
- [ ] Review Browserbase logs in dashboard

### Issue 3: Sessions leak (don't return to pool)
**Symptom**: Pool utilization stays at 100%, new requests hang

**Solution**:
- [ ] Audit code for missing `checkin()` calls
- [ ] Check for exceptions preventing `finally` block
- [ ] Add timeout to checkout: `asyncio.wait_for(pool.checkout(), timeout=30)`
- [ ] Restart server to clear leaked sessions

### Issue 4: LinkedIn rate limiting
**Symptom**: LinkedIn blocks requests, returns 429 errors

**Solution**:
- [ ] Verify stealth mode enabled (check logs)
- [ ] Add delays between scrapes: `await asyncio.sleep(2)`
- [ ] Decrease `LINKEDIN_SESSION_MAX_USES` to rotate more frequently
- [ ] Use Google proxy search instead of direct LinkedIn access

---

## Success Criteria

### Technical Metrics
- ✅ Pool initialization: 100% success rate
- ✅ Session creation: >95% success rate
- ✅ Average scrape time: <5 seconds (after first)
- ✅ Pool utilization: <80% average
- ✅ Session leaks: 0 per day
- ✅ LinkedIn rate limiting: 0 incidents per week

### Business Metrics
- ✅ Scraping speed: 3x faster vs no pool
- ✅ Browserbase costs: 80%+ reduction vs no pool
- ✅ Data quality: Same or better vs no pool
- ✅ Uptime: 99.9%+

---

## Team Handoff

### Documentation Shared
- [ ] `SESSION_POOL_SUMMARY.md` - Overview + benchmarks
- [ ] `BROWSERBASE_SESSION_POOL.md` - Full API reference
- [ ] `INTEGRATION_GUIDE_SESSION_POOL.md` - Step-by-step integration
- [ ] `QUICK_REFERENCE_SESSION_POOL.md` - Quick reference card
- [ ] `DEPLOYMENT_CHECKLIST_SESSION_POOL.md` - This file

### Training Completed
- [ ] Team knows how to use `checkout()`/`checkin()`
- [ ] Team knows how to check pool stats
- [ ] Team knows how to monitor pool health
- [ ] Team knows how to troubleshoot common issues
- [ ] Team knows where to find documentation

### Knowledge Transfer
- [ ] Code walkthrough completed
- [ ] Q&A session completed
- [ ] Team tested session pool in development
- [ ] Team knows rollback procedure

---

## Sign-Off

### Development
- [ ] Code reviewed: _______________
- [ ] Tests passing: _______________
- [ ] Documentation complete: _______________
- [ ] Date: _______________

### Staging
- [ ] Integration tests passing: _______________
- [ ] Performance verified: _______________
- [ ] Monitoring configured: _______________
- [ ] Date: _______________

### Production
- [ ] Deployed successfully: _______________
- [ ] Metrics green for 24h: _______________
- [ ] Team trained: _______________
- [ ] Date: _______________

---

## Next Steps After Deployment

### Immediate (Day 1-7)
1. Monitor pool stats hourly
2. Check for errors in logs
3. Verify session rotation working
4. Track Browserbase costs

### Short-term (Week 2-4)
1. Tune max_uses/timeout based on metrics
2. Set up automated alerts
3. Create dashboard for pool metrics
4. Document any issues encountered

### Long-term (Month 2+)
1. Consider additional optimizations (e.g., regional pools)
2. Evaluate Browserbase plan upgrade if needed
3. Share learnings with team
4. Consider open-sourcing (if applicable)

---

## Contact

For questions or issues:
- **Documentation**: `/backend/BROWSERBASE_SESSION_POOL.md`
- **Examples**: `/backend/example_linkedin_scrape_with_pool.py`
- **Tests**: `/backend/test_session_pool.py`
- **Browserbase Support**: https://docs.browserbase.com

---

**Deployment Status**: ⬜ Not Started | 🟡 In Progress | ✅ Complete

**Last Updated**: 2025-12-01
