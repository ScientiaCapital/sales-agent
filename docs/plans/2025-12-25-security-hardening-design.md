# Security Hardening Design - Dec 25, 2025

**Status**: Ready for implementation
**Driver**: Security audit findings
**Approach**: Incremental hardening (fix by priority, test each)

---

## Vulnerability Summary

| Priority | Vulnerability | Risk | Status |
|----------|--------------|------|--------|
| **P0** | `/test-error` endpoint exposed | High | Pending |
| **P1** | CSP `unsafe-inline/unsafe-eval` | High | Pending |
| **P2** | No rate limiting | Medium | Pending |
| **P3** | Bare exceptions (3 files) | Low | Pending |
| **P4** | CORS review | Low | Deferred |

---

## P0: Remove Test Error Endpoint

**File**: `backend/app/api/health.py`
**Lines**: 68-76

**Current**:
```python
@router.get("/test-error")
async def test_error():
    """Test endpoint to trigger a Sentry error report."""
    raise RuntimeError("Test error for Sentry monitoring - this is intentional")
```

**Action**: Delete endpoint entirely.

**Verification**:
- `curl /health/test-error` returns 404
- `/health` and `/health/ready` still return 200

**Alternative Sentry Testing**:
- Use Sentry dashboard "Send Test Event" button
- Local: `sentry_sdk.capture_message("test")`

---

## P1: CSP Header Hardening

**File**: `backend/app/main.py`
**Lines**: 121-128

**Current**:
```python
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' https://*.supabase.co wss://*.supabase.co"
)
```

**Fixed**:
```python
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' https://*.supabase.co wss://*.supabase.co; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)
```

**Changes**:
- Remove `'unsafe-inline'` from script-src
- Remove `'unsafe-eval'` from script-src
- Remove `'unsafe-inline'` from style-src
- Add `frame-ancestors 'none'` (clickjacking protection)
- Add `base-uri 'self'` (base tag injection protection)

**Verification**:
- Response headers contain updated CSP
- No `unsafe-` directives in CSP header

---

## P2: Rate Limiting with SlowAPI

### New File: `backend/app/core/rate_limit.py`

```python
"""
API Rate Limiting with SlowAPI

Protects endpoints from abuse with configurable per-route limits.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings


def get_rate_limit_key(request: Request) -> str:
    """Get rate limit key from request (IP or API key)."""
    # Check for API key first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"api_key:{api_key[:8]}"  # Use prefix only

    # Fall back to IP address
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_rate_limit_key,
    enabled=settings.RATE_LIMIT_ENABLED,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": f"Rate limit exceeded: {exc.detail}",
            "retry_after": exc.detail.split(" per ")[1] if " per " in str(exc.detail) else "60 seconds"
        },
        headers={"Retry-After": "60"}
    )
```

### Config Addition: `backend/app/core/config.py`

```python
# Rate Limiting
RATE_LIMIT_ENABLED: bool = True
RATE_LIMIT_DEFAULT: str = "100/minute"
RATE_LIMIT_AUTH: str = "5/minute"
RATE_LIMIT_ENRICH: str = "30/minute"
RATE_LIMIT_CLOSE: str = "60/minute"
RATE_LIMIT_HEALTH: str = "120/minute"
```

### Main.py Integration

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limit import limiter

# Add to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### Route Decorators (examples)

```python
# In auth routes
@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, ...):
    ...

# In enrich routes
@router.post("/enrich")
@limiter.limit("30/minute")
async def enrich(request: Request, ...):
    ...
```

### Rate Limit Tiers

| Endpoint Pattern | Limit | Reason |
|------------------|-------|--------|
| `/api/v1/auth/*` | 5/min | Prevent brute force |
| `/api/v1/enrich/*` | 30/min | Expensive LLM calls |
| `/api/v1/close/*` | 60/min | CRM API has own limits |
| `/health/*` | 120/min | Monitoring headroom |
| Default | 100/min | General protection |

### Dependency

Add to `requirements.txt`:
```
slowapi>=0.1.9
```

---

## P3: Bare Exceptions Fix

**Pattern**:
```python
# Before
except:
    pass

# After
except Exception as e:
    logger.warning(f"Non-critical error in {context}: {e}")
```

### File 1: `backend/app/services/browserbase_team_scraper.py`
**Line**: 549

### File 2: `backend/app/tasks/agent_tasks.py`
**Line**: 1120

### File 3: `backend/app/api/claude_chat.py`
**Line**: 92

---

## Implementation Order

```
Phase 1 (Immediate - High Risk):
├── P0: Remove /test-error endpoint
└── P1: Fix CSP headers

Phase 2 (Same Day - Medium Risk):
└── P2: Add rate limiting (slowapi)

Phase 3 (Cleanup):
└── P3: Fix bare exceptions
```

---

## Verification Checklist

### P0 Verification
- [ ] `GET /health/test-error` returns 404
- [ ] `GET /health` returns 200
- [ ] `GET /health/ready` returns 200

### P1 Verification
- [ ] CSP header contains no `unsafe-inline`
- [ ] CSP header contains no `unsafe-eval`
- [ ] CSP header contains `frame-ancestors 'none'`

### P2 Verification
- [ ] 6th request to `/api/v1/auth/login` within 1 min returns 429
- [ ] Response includes `Retry-After` header
- [ ] Rate limits logged for monitoring

### P3 Verification
- [ ] `grep -r "except:" backend/app/` returns empty (excluding comments)
- [ ] All exception handlers log with context

---

## Rollback Plan

Each fix is independent. If issues arise:

1. **CSP breaks frontend**: Revert CSP line, add specific hashes for required inline scripts
2. **Rate limiting too aggressive**: Adjust limits in config, or set `RATE_LIMIT_ENABLED=false`
3. **Bare exception fix causes noise**: Reduce log level to DEBUG

---

## Success Criteria

- [ ] All P0-P3 vulnerabilities addressed
- [ ] Zero regressions in existing tests
- [ ] Security headers verified via `curl -I`
- [ ] Rate limiting tested with load tool (e.g., `ab -n 200 -c 10`)
