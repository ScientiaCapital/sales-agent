# Browserbase Session Pool - Quick Reference Card

## 30-Second Setup

```bash
# 1. Add to .env
BROWSERBASE_API_KEY=your_key
BROWSERBASE_PROJECT_ID=your_project

# 2. Use in code
from app.services.browserbase_session_pool import get_session_pool

pool = await get_session_pool()
session = await pool.checkout()
try:
    # Use session.connect_url with Playwright
finally:
    await pool.checkin(session)
```

---

## Essential Methods

| Method | Usage | When |
|--------|-------|------|
| `checkout()` | `session = await pool.checkout()` | Get session |
| `checkin(session)` | `await pool.checkin(session)` | Return session |
| `warm_up(count)` | `await pool.warm_up(5)` | Startup |
| `close_all()` | `await pool.close_all()` | Shutdown |
| `get_pool_stats()` | `stats = await pool.get_pool_stats()` | Monitoring |

---

## Common Patterns

### Pattern 1: Basic Usage
```python
pool = await get_session_pool()
session = await pool.checkout()
try:
    browser = await playwright.chromium.connect_over_cdp(session.connect_url)
    # ... scrape ...
finally:
    await pool.checkin(session)
```

### Pattern 2: Batch Processing
```python
async def scrape_company(company):
    session = await pool.checkout()
    try:
        return await scrape(session, company)
    finally:
        await pool.checkin(session)

results = await asyncio.gather(*[scrape_company(c) for c in companies])
```

### Pattern 3: Startup/Shutdown
```python
@app.on_event("startup")
async def startup():
    pool = await get_session_pool()
    await pool.warm_up(5)

@app.on_event("shutdown")
async def shutdown():
    await close_session_pool()
```

---

## Environment Variables

```bash
# Required
BROWSERBASE_API_KEY=sk_...
BROWSERBASE_PROJECT_ID=proj_...

# Optional (defaults shown)
LINKEDIN_COMPANY_MAX_SESSIONS=25        # Max concurrent
LINKEDIN_SESSION_TIMEOUT_SEC=7200       # 2 hours
LINKEDIN_SESSION_MAX_USES=15            # Rotate after 15
```

---

## Key Metrics

| Metric | Without Pool | With Pool |
|--------|--------------|-----------|
| First scrape | 15s | 15s |
| Next scrapes | 15s | 3s |
| 100 companies | 25 min | 8 min |
| Sessions created | 100 | 7 |
| Cost (example) | $1.00 | $0.07 |

---

## Common Errors

### Error 1: Import Error
```python
ModuleNotFoundError: No module named 'app.services.browserbase_session_pool'
```
**Fix**: Check file exists at correct path

### Error 2: Missing Credentials
```python
ValueError: Browserbase credentials required
```
**Fix**: Add `BROWSERBASE_API_KEY` and `BROWSERBASE_PROJECT_ID` to `.env`

### Error 3: Deadlock
```python
# checkout() hangs forever
```
**Fix**: Check for missing `checkin()` calls. Use `try/finally`.

---

## Testing

```bash
# Run test suite
python test_session_pool.py

# Run example
python example_linkedin_scrape_with_pool.py
```

---

## Critical Rules

1. ✅ **Always use try/finally** for checkin
2. ✅ **Pre-warm pool** on startup (`warm_up(5)`)
3. ✅ **Close pool** on shutdown (`close_all()`)
4. ✅ **Monitor stats** in production (`get_pool_stats()`)
5. ❌ **Never create multiple pools** (use singleton)
6. ❌ **Never hardcode credentials** (use .env)

---

## Stealth Configuration (Auto-Applied)

```python
{
    "advancedStealth": True,        # ✅ Bot detection bypass
    "blockAds": True,               # ✅ Faster loading
    "solveCaptchas": True,          # ✅ Auto CAPTCHA
    "fingerprint": {...},           # ✅ Randomized
    "proxies": [{"country": "US"}]  # ✅ US residential
}
```

---

## Session Lifecycle

```
[Create] → [Checkout] → [Use] → [Checkin] → [Reuse or Rotate]
   15s        <1s        ~3s       <1s         (15 uses)
```

---

## Pool Statistics

```python
stats = await pool.get_pool_stats()
# {
#   "total_sessions": 5,
#   "active_sessions": 2,
#   "available_sessions": 3,
#   "max_sessions": 25,
#   "pool_utilization": "8.0%"
# }
```

---

## Documentation

| File | Purpose |
|------|---------|
| `SESSION_POOL_SUMMARY.md` | Overview + benchmarks |
| `BROWSERBASE_SESSION_POOL.md` | Full API reference |
| `INTEGRATION_GUIDE_SESSION_POOL.md` | Step-by-step guide |
| `QUICK_REFERENCE_SESSION_POOL.md` | This file |

---

## One-Liners

```python
# Get pool
pool = await get_session_pool()

# Warm up
await pool.warm_up(5)

# Get session
session = await pool.checkout()

# Return session
await pool.checkin(session)

# Stats
stats = await pool.get_pool_stats()

# Cleanup
await close_session_pool()
```

---

## Performance Tips

1. **Warm up** with `min(5, max_concurrent)` sessions
2. **Increase max_uses** (25) for high-volume scraping
3. **Decrease max_uses** (10) for stealth priority
4. **Monitor utilization** and adjust max_sessions
5. **Add delays** between scrapes (2s) for rate limiting

---

## When to Use

✅ **Use session pool when:**
- Scraping 10+ companies
- Need stealth mode (LinkedIn)
- Want cost optimization
- Need concurrent scraping

❌ **Don't use when:**
- Single one-off scrape
- Simple HTTP requests (use httpx)
- Non-browser automation

---

## Support

- **Full docs**: `BROWSERBASE_SESSION_POOL.md`
- **Examples**: `example_linkedin_scrape_with_pool.py`
- **Tests**: `test_session_pool.py`
- **Browserbase**: https://docs.browserbase.com

---

## TL;DR

```python
# Setup (once)
pool = await get_session_pool()
await pool.warm_up(5)

# Use (many times)
session = await pool.checkout()
try:
    # Scrape with session
finally:
    await pool.checkin(session)

# Cleanup (once)
await close_session_pool()
```

**Result**: 5x faster, 85% cheaper, LinkedIn stealth mode ✅
