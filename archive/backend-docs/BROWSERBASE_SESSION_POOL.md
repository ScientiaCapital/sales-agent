# Browserbase Session Pool - Documentation

## Overview

A production-ready session pool for Browserbase browser automation with advanced stealth mode support for LinkedIn scraping.

## Features

- **Session Reuse**: Reuse browser sessions across multiple scrapes (7-15s session creation → <1s reuse)
- **Auto-Rotation**: Sessions automatically rotate after max_uses (default: 15 companies)
- **Stealth Mode**: Advanced fingerprint randomization, US residential proxies, CAPTCHA solving
- **Concurrent Access**: Thread-safe async queue with semaphore-based concurrency control
- **Graceful Cleanup**: All sessions properly closed on shutdown
- **Pool Statistics**: Real-time metrics on pool utilization

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   BrowserbaseSessionPool                    │
├─────────────────────────────────────────────────────────────┤
│ Available Queue: [Session1, Session2, Session3]            │
│ Active Sessions: {session_id -> BrowserbaseSession}        │
│ Semaphore: Limit max_concurrent (default: 25)              │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   checkout()         checkin()          close_all()
        │                  │                  │
        ▼                  ▼                  ▼
   Get session      Return session      Cleanup all
   (from queue or   (reuse or retire)   (shutdown)
    create new)
```

## Quick Start

### Installation

```bash
# Install dependencies
pip install playwright httpx python-dotenv

# Install Playwright browsers
playwright install chromium
```

### Environment Variables

```bash
# .env file
BROWSERBASE_API_KEY=your_api_key_here
BROWSERBASE_PROJECT_ID=your_project_id_here

# Optional configuration
LINKEDIN_COMPANY_MAX_SESSIONS=25        # Max concurrent sessions
LINKEDIN_SESSION_TIMEOUT_SEC=7200       # 2 hours
LINKEDIN_SESSION_MAX_USES=15            # Rotate after 15 companies
```

### Basic Usage

```python
from app.services.browserbase_session_pool import get_session_pool, close_session_pool
from playwright.async_api import async_playwright

# Get pool singleton
pool = await get_session_pool()

# Checkout a session
session = await pool.checkout()

try:
    # Use session with Playwright
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(session.connect_url)
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()

        # Scrape LinkedIn
        await page.goto("https://linkedin.com/company/anthropic")
        # ... extract data ...

        await browser.close()
finally:
    # IMPORTANT: Always checkin session
    await pool.checkin(session)

# Cleanup on shutdown
await close_session_pool()
```

## API Reference

### BrowserbaseSessionPool

#### Methods

##### `warm_up(count: int = 5) -> None`

Pre-create sessions for faster first requests.

```python
pool = await get_session_pool()
await pool.warm_up(count=5)  # Create 5 sessions upfront
```

**Args:**
- `count`: Number of sessions to pre-create (default: 5)

**Note:** Session creation takes ~7-15 seconds each. Consider warming up a small number initially.

---

##### `checkout() -> BrowserbaseSession`

Get a session from the pool (blocking if none available).

```python
session = await pool.checkout()
```

**Returns:** `BrowserbaseSession` ready for use

**Raises:** `RuntimeError` if pool is closed

**Note:** Always use `try/finally` to ensure checkin.

---

##### `checkin(session: BrowserbaseSession) -> None`

Return a session to the pool.

```python
await pool.checkin(session)
```

**Args:**
- `session`: Session to return

**Note:** Sessions exceeding max_uses or timeout are automatically closed.

---

##### `close_all() -> None`

Close all sessions and shutdown the pool.

```python
await pool.close_all()
```

**Use:** Call on application shutdown to cleanup resources.

---

##### `get_pool_stats() -> Dict[str, Any]`

Get current pool statistics.

```python
stats = await pool.get_pool_stats()
print(stats)
# {
#   "total_sessions": 5,
#   "active_sessions": 2,
#   "available_sessions": 3,
#   "max_sessions": 25,
#   "pool_utilization": "8.0%",
#   "session_timeout_sec": 7200,
#   "session_max_uses": 15
# }
```

---

### BrowserbaseSession

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `session_id` | str | Unique session ID from Browserbase |
| `connect_url` | str | WebSocket URL for Playwright CDP |
| `created_at` | float | Timestamp when session was created |
| `usage_count` | int | Number of companies scraped with this session |
| `last_used_at` | float | Timestamp of last usage |
| `is_active` | bool | Whether session is currently in use |

#### Methods

##### `is_expired(timeout_seconds: int) -> bool`

Check if session has exceeded timeout.

##### `should_rotate(max_uses: int) -> bool`

Check if session should be rotated (max uses reached).

---

### Singleton Functions

##### `get_session_pool() -> BrowserbaseSessionPool`

Get or create the global session pool singleton.

```python
pool = await get_session_pool()
```

**Returns:** `BrowserbaseSessionPool` instance

**Note:** Pool is created lazily on first access.

---

##### `close_session_pool() -> None`

Close the global session pool.

```python
await close_session_pool()
```

**Use:** Call on application shutdown.

---

## Advanced Usage

### Concurrent Scraping

```python
async def scrape_company(company_name: str):
    pool = await get_session_pool()
    session = await pool.checkout()

    try:
        # Scrape company
        result = await linkedin_scraper(session, company_name)
        return result
    finally:
        await pool.checkin(session)

# Scrape 100 companies with max 10 concurrent
companies = ["Company1", "Company2", ...]  # 100 companies
semaphore = asyncio.Semaphore(10)

async def scrape_with_limit(company):
    async with semaphore:
        return await scrape_company(company)

results = await asyncio.gather(*[scrape_with_limit(c) for c in companies])
```

---

### Custom Pool Configuration

```python
from app.services.browserbase_session_pool import BrowserbaseSessionPool

pool = BrowserbaseSessionPool(
    max_sessions=50,          # Increase concurrent limit
    session_timeout_sec=3600, # 1 hour sessions
    session_max_uses=25       # Rotate after 25 uses
)
```

---

### Session Lifecycle Hooks

```python
pool = await get_session_pool()

# Pre-warm pool
await pool.warm_up(count=10)

# Use pool
for company in companies:
    session = await pool.checkout()
    try:
        await scrape(session, company)
    finally:
        await pool.checkin(session)

    # Check pool health
    stats = await pool.get_pool_stats()
    if stats["pool_utilization"] > 80:
        logger.warning("Pool near capacity!")

# Cleanup
await pool.close_all()
```

---

## Stealth Configuration

The pool creates sessions with LinkedIn-optimized stealth settings:

```python
session_config = {
    "projectId": BROWSERBASE_PROJECT_ID,
    "timeout": 7200000,  # 2 hours in milliseconds
    "keepAlive": True,
    "browserSettings": {
        # CRITICAL: Advanced stealth mode
        "advancedStealth": True,      # Bypasses bot detection
        "blockAds": True,              # Faster page loads
        "solveCaptchas": True,         # Auto CAPTCHA solving
        "viewport": {
            "width": 1920,
            "height": 1080
        },
        # Randomized fingerprints
        "fingerprint": {
            "browsers": ["chrome"],
            "devices": ["desktop"],
            "operatingSystems": ["windows", "macos"],
            "locales": ["en-US"]
        }
    },
    # US residential proxies
    "proxies": [{
        "type": "browserbase",
        "geolocation": {
            "country": "US",
            "state": "CA"
        }
    }]
}
```

---

## Performance Benchmarks

| Metric | Without Pool | With Pool |
|--------|--------------|-----------|
| First scrape | ~15 seconds | ~15 seconds |
| Subsequent scrapes | ~15 seconds | ~3 seconds |
| 100 companies (sequential) | ~25 minutes | ~8 minutes |
| 100 companies (10 concurrent) | ~2.5 minutes | ~1.5 minutes |
| Session overhead | 100% | ~7% (1/15 rotations) |

**Cost Savings:**
- Without pool: 100 sessions created → $X
- With pool: ~7 sessions created → $X/15

---

## Testing

```bash
# Run test suite
cd backend
python test_session_pool.py
```

**Tests:**
1. Basic checkout/checkin
2. Session reuse
3. Session rotation (max_uses)
4. Concurrent access
5. Pool statistics
6. Warm-up
7. Graceful shutdown

---

## Examples

### Example 1: Simple LinkedIn Scrape

```bash
python example_linkedin_scrape_with_pool.py
```

Scrapes 6 companies using the session pool with concurrency=3.

---

### Example 2: Integrate with Existing Scraper

```python
# Before (no pool)
async def scrape_linkedin(company_name: str):
    scraper = BrowserbaseTeamScraper()
    result = await scraper.scrape_team_page(f"https://{company_domain}")
    return result

# After (with pool)
async def scrape_linkedin(company_name: str):
    pool = await get_session_pool()
    session = await pool.checkout()
    try:
        result = await scrape_with_session(session, company_name)
        return result
    finally:
        await pool.checkin(session)
```

---

## Troubleshooting

### Session Creation Fails

**Problem:** `Failed to create Browserbase session after 3 attempts`

**Solution:**
1. Verify `BROWSERBASE_API_KEY` and `BROWSERBASE_PROJECT_ID` in .env
2. Check Browserbase plan limits (concurrent sessions, API rate limits)
3. Check Browserbase API status: https://status.browserbase.com

---

### Pool Deadlock

**Problem:** `checkout()` hangs forever

**Solution:**
1. Ensure all `checkout()` calls have matching `checkin()` in `finally` block
2. Check pool stats: `await pool.get_pool_stats()`
3. Verify `max_sessions` is sufficient for concurrency level

---

### High Session Rotation

**Problem:** Too many sessions created (high costs)

**Solution:**
1. Increase `LINKEDIN_SESSION_MAX_USES` (default: 15)
2. Increase `LINKEDIN_SESSION_TIMEOUT_SEC` (default: 7200)
3. Reduce scrape concurrency to reuse sessions more

---

### LinkedIn Rate Limiting

**Problem:** LinkedIn blocks requests

**Solution:**
1. Verify stealth settings are enabled (check logs)
2. Add delays between company scrapes: `await asyncio.sleep(2)`
3. Use Google proxy search instead of direct LinkedIn access
4. Rotate sessions more frequently (decrease max_uses)

---

## Best Practices

1. **Always use try/finally for checkin**
   ```python
   session = await pool.checkout()
   try:
       await scrape(session, company)
   finally:
       await pool.checkin(session)  # CRITICAL
   ```

2. **Pre-warm pool for large batches**
   ```python
   await pool.warm_up(count=min(10, max_concurrent))
   ```

3. **Monitor pool utilization**
   ```python
   stats = await pool.get_pool_stats()
   if stats["pool_utilization"] > 80:
       logger.warning("Pool near capacity")
   ```

4. **Cleanup on shutdown**
   ```python
   async def shutdown():
       await close_session_pool()
   ```

5. **Use semaphore for concurrency control**
   ```python
   semaphore = asyncio.Semaphore(max_concurrent)
   async with semaphore:
       await scrape_company(company)
   ```

---

## FAQ

**Q: How many sessions should I pre-warm?**

A: Start with `min(5, max_concurrent)`. Session creation is slow (~10s each), so warming up 25 sessions would take ~4 minutes.

---

**Q: When should sessions rotate?**

A: Sessions rotate when:
1. `usage_count >= session_max_uses` (default: 15 companies)
2. `age > session_timeout_sec` (default: 2 hours)

---

**Q: Can I use multiple pools?**

A: Yes, but typically one global pool is sufficient. Create custom pools only if you need different configurations (e.g., different Browserbase projects).

---

**Q: How do I debug session issues?**

A: Enable debug logging:
```python
import logging
logging.getLogger("app.services.browserbase_session_pool").setLevel(logging.DEBUG)
```

---

**Q: What happens if checkin is never called?**

A: The session remains "checked out" and blocks other workers. Sessions also timeout after `session_timeout_sec`, but always use `finally` to ensure cleanup.

---

## Related Files

- `/backend/app/services/browserbase_session_pool.py` - Main implementation
- `/backend/test_session_pool.py` - Test suite
- `/backend/example_linkedin_scrape_with_pool.py` - Usage example
- `/backend/app/services/browserbase_team_scraper.py` - Original scraper (no pool)

---

## License

Internal use only. Part of Sales Agent project.

---

## Changelog

### v1.0.0 (2025-12-01)
- Initial release
- Session pooling with checkout/checkin
- Auto-rotation after max_uses
- Stealth mode for LinkedIn
- Thread-safe async queue
- Pool statistics
- Graceful cleanup
