# VLM Cache + Parallel Integration Design

**Date:** 2025-12-25
**Status:** Approved
**Goal:** Integrate VLMCache and parallel processing into production VLM enrichment pipeline

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    vlm_batch_5.py                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Parallel Company Processing (3 concurrent)          │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  Per Company: Parallel Screenshots (3 conc) │    │   │
│  │  │  ┌─────────────────────────────────────┐   │    │   │
│  │  │  │  VLMContactExtractor                 │   │    │   │
│  │  │  │  ├─ Check VLMCache (Redis)          │   │    │   │
│  │  │  │  ├─ If miss: Call OpenRouter API    │   │    │   │
│  │  │  │  └─ Store result in cache (24h TTL) │   │    │   │
│  │  │  └─────────────────────────────────────┘   │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| Cache backend | Redis | User confirmed available |
| Cache TTL | 24 hours | Balance freshness vs savings |
| Concurrent companies | 3 | Conservative, avoid rate limits |
| Concurrent screenshots | 3 | Conservative, avoid rate limits |

## Files to Modify

### 1. vlm_contact_extractor.py - Cache Integration

```python
class VLMContactExtractor:
    def __init__(
        self,
        api_key: str,
        # NEW: Cache parameters
        enable_cache: bool = True,
        redis_url: str = None,  # Auto-detect from env if None
        cache_ttl: int = 86400,  # 24 hours
    ):
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self._cache = None  # Lazy-loaded
        self._redis_url = redis_url or os.getenv("REDIS_URL")

    async def _get_cache(self) -> Optional[VLMCache]:
        """Lazy-load cache connection."""
        if not self.enable_cache or not self._redis_url:
            return None
        if self._cache is None:
            client = redis.from_url(self._redis_url)
            self._cache = VLMCache(client, self.cache_ttl)
        return self._cache

    async def extract_contacts(self, screenshot_path, ...):
        # 1. Check cache first
        cache = await self._get_cache()
        if cache:
            cached = await cache.get(screenshot_path)
            if cached:
                logger.info(f"Cache HIT: {screenshot_path}")
                return cached

        # 2. Call VLM API (existing code)
        result = await self._call_vlm_api(...)

        # 3. Store in cache
        if cache and result.get("contacts"):
            await cache.set(screenshot_path, result)

        return result
```

### 2. vlm_batch_5.py - Parallel Processing

```python
# Constants at top
CONCURRENT_COMPANIES = 3      # Max companies at once
CONCURRENT_SCREENSHOTS = 3    # Max screenshots per company

async def process_screenshots_parallel(pages, extractor):
    """Process screenshots in parallel batches of 3."""
    tasks = []
    page_map = {}

    for page in pages:
        if not page.screenshot_path:
            continue
        task = extractor.extract_contacts(
            screenshot_path=Path(page.screenshot_path),
            page_url=page.url,
            page_text=page.text[:1000] if page.text else ""
        )
        tasks.append(task)
        page_map[len(tasks) - 1] = page

    # Process in batches of 3
    all_results = []
    for i in range(0, len(tasks), CONCURRENT_SCREENSHOTS):
        batch = tasks[i:i + CONCURRENT_SCREENSHOTS]
        results = await asyncio.gather(*batch, return_exceptions=True)
        all_results.extend(zip(range(i, i + len(batch)), results))

    return all_results, page_map

async def run_batch(companies, crawler, extractor, dry_run):
    """Process companies in parallel with semaphore."""
    semaphore = asyncio.Semaphore(CONCURRENT_COMPANIES)

    async def process_with_limit(company):
        async with semaphore:
            return await process_company(company, crawler, extractor, dry_run)

    tasks = [process_with_limit(c) for c in companies]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

## Error Handling

```python
# Screenshot-level errors
for idx, result in all_results:
    page = page_map[idx]
    if isinstance(result, Exception):
        logger.error(f"Screenshot failed: {page.url}", error=str(result))
        continue  # Don't block other screenshots

# Company-level errors
for i, result in enumerate(results):
    if isinstance(result, Exception):
        logger.error(f"Company failed: {companies[i]['company_name']}")
        results[i] = {"status": "failed", "error": str(result)}
```

## Rollback

- `enable_cache=False` disables caching
- `CONCURRENT_COMPANIES=1` for sequential company processing
- `CONCURRENT_SCREENSHOTS=1` for sequential screenshot processing

## Expected Improvements

| Metric | Before | After |
|--------|--------|-------|
| Cache hits on re-run | 0% | ~30% |
| Batch processing speed | 1x | ~3x |
| API cost savings | 0% | ~30% on re-runs |

## Testing Strategy

1. Unit tests exist for VLMCache and parallel patterns
2. Add integration test: cache + parallel together
3. Run on 5 test companies before full batch
