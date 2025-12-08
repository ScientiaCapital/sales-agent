# WebsiteScraper Class Design

**Date:** 2025-12-08
**Status:** Approved
**Purpose:** Enable automated website enrichment via Celery task

---

## Summary

Extract the working scraping logic from `run_enrichment.py` into a reusable `WebsiteScraper` class that can be called by the Celery enrichment task.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Session management | Persistent pool (2-3 sessions) | Cost-efficient, faster than per-domain |
| Error handling | Exponential backoff (3 retries) | Thorough, handles transient failures |
| Concurrency | Sequential (one domain at a time) | Simple, debuggable, predictable |
| Architecture | Monolithic class (~400 lines) | Matches existing code, easy to maintain |

---

## Class Structure

```python
# app/services/scrapers/website_scraper.py

class WebsiteScraper:
    """
    Browserbase-powered website scraper for contractor enrichment.

    Features:
    - Persistent session pool (2-3 warm Browserbase sessions)
    - Exponential backoff retry (3 attempts)
    - Sequential scraping (one domain at a time)
    - 3-layer garbage contact filtering
    - ATL/BTL contact extraction
    - OEM brand detection
    - Service area extraction
    """

    def __init__(self, pool_size: int = 2):
        self.pool_size = pool_size
        self._sessions: List[str] = []
        self._playwright = None
        self._browser = None

    # Session Management
    async def initialize(self) -> None
    async def close(self) -> None
    async def _create_session(self) -> Tuple[str, str]
    async def _close_session(self, session_id: str) -> None

    # Core Scraping
    async def scrape_domain(self, domain: str) -> Dict[str, Any]
    async def _scrape_page(self, page: Page, url: str) -> str
    async def _with_retry(self, func, *args, max_retries: int = 3) -> Any

    # Data Extraction (static methods)
    @staticmethod
    def extract_phones(content: str) -> List[str]
    @staticmethod
    def extract_emails(content: str) -> List[str]
    @staticmethod
    def extract_contacts(content: str) -> List[Dict]
    @staticmethod
    def extract_oem_brands(content: str) -> List[str]
    @staticmethod
    def is_garbage_contact(name: str, title: str = '') -> bool
```

---

## Return Structure

```python
# Success:
{
    "success": True,
    "domain": "example-hvac.com",
    "pages_scraped": ["/", "/about", "/contact"],
    "contacts": [
        {"name": "John Smith", "title": "Owner", "is_atl": True, "email": "...", "phone": "..."},
    ],
    "oem_brands": ["Carrier", "Trane", "Lennox"],
    "service_areas": ["Dallas", "Fort Worth"],
    "has_maintenance_plan": True,
    "company_story": "Founded in 1985...",
    "scrape_time_ms": 4500,
    "retry_count": 0,
    "error": None
}

# Failure:
{
    "success": False,
    "domain": "example-hvac.com",
    "error": "Timeout after 30s",
    "retry_count": 3
}
```

---

## Integration

The Celery task (`enrichment_tasks.py`) will use the scraper:

```python
from app.services.scrapers.website_scraper import WebsiteScraper

@celery_app.task(name="run_website_enrichment_batch")
async def run_website_enrichment_batch(batch_size: int = 5):
    scraper = WebsiteScraper(pool_size=2)
    await scraper.initialize()

    try:
        for company in companies:
            result = await scraper.scrape_domain(company['domain'])
            if result['success']:
                # Update Supabase...
    finally:
        await scraper.close()
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `app/services/scrapers/__init__.py` | Create (new package) |
| `app/services/scrapers/website_scraper.py` | Create (~400 lines) |
| `app/tasks/enrichment_tasks.py` | Modify (wire up scraper) |
| `data/contact_blocklist.txt` | Already exists (used by scraper) |

---

## Source Code Reference

Extract from `run_enrichment.py`:
- Lines 52-80: Config and blocklist loading
- Lines 82-149: `is_garbage_contact()` function
- Lines 170-206: Phone/email extraction
- Lines 217-249: ATL/BTL title lists
- Lines 174-194: Browserbase session management
- Team page paths and scraping logic

---

## Schedule

After implementation, the Celery task runs every 30 minutes (per user preference).
