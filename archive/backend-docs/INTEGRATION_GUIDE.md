# Dealer Scraper → Sales Agent Integration Guide

Quick reference for integrating **dealer-scraper-mvp** with **sales-agent** API.

---

## Quick Start

### 1. Start sales-agent API

```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent
source venv/bin/activate
cd backend
python start_server.py  # Runs on port 8001
```

**API Base URL**: `http://localhost:8001/api/v1/scraper`

**Swagger Docs**: http://localhost:8001/api/v1/docs#/dealer-scraper

---

## 2. Push Data from dealer-scraper-mvp

### Option A: Celery Task (Recommended)

In `dealer-scraper-mvp/tasks.py`:

```python
import httpx
from celery import shared_task
from datetime import datetime

SALES_AGENT_API = "http://localhost:8001/api/v1/scraper"

@shared_task(name="push_to_sales_agent")
def push_to_sales_agent(contractors: list, contacts: list, source_scraper: str):
    """
    Push scraped data to sales-agent API.

    Args:
        contractors: List of contractor dicts
        contacts: List of contact dicts
        source_scraper: Source identifier (e.g., 'carrier', 'generac')
    """
    batch_id = f"{source_scraper}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Push contractors first
    if contractors:
        contractor_payload = {
            "contractors": contractors,
            "batch_id": batch_id,
            "source_scraper": source_scraper
        }

        try:
            response = httpx.post(
                f"{SALES_AGENT_API}/contractors",
                json=contractor_payload,
                timeout=120.0  # 2 minutes for large batches
            )
            response.raise_for_status()

            result = response.json()
            print(f"✅ Contractors: {result['inserted']} new, {result['updated']} updated")

        except Exception as e:
            print(f"❌ Contractor sync failed: {e}")
            raise

    # Push contacts second (requires companies to exist)
    if contacts:
        contact_payload = {
            "contacts": contacts,
            "batch_id": f"{batch_id}_contacts",
            "source_scraper": source_scraper
        }

        try:
            response = httpx.post(
                f"{SALES_AGENT_API}/contacts",
                json=contact_payload,
                timeout=120.0
            )
            response.raise_for_status()

            result = response.json()
            print(f"✅ Contacts: {result['inserted']} new, {result['updated']} updated")

        except Exception as e:
            print(f"❌ Contact sync failed: {e}")
            raise

    return {"status": "success", "batch_id": batch_id}
```

### Option B: Direct HTTP Call (Testing)

```python
import httpx

SALES_AGENT_API = "http://localhost:8001/api/v1/scraper"

contractors = [
    {
        "company_name": "ABC HVAC",
        "normalized_name": "abc hvac",
        "phone": "5551234567",
        "domain": "abchvac.com",
        "state": "tx",
        "oem_brands": ["Carrier", "Trane"],
        "source_scraper": "carrier"
    }
]

# Push contractors
response = httpx.post(
    f"{SALES_AGENT_API}/contractors",
    json={
        "contractors": contractors,
        "batch_id": "test_001",
        "source_scraper": "carrier"
    }
)

print(response.json())
# Output:
# {
#   "status": "success",
#   "inserted": 1,
#   "updated": 0,
#   "skipped": 0,
#   "errors": []
# }
```

---

## 3. Data Format Requirements

### Contractor Format

```python
contractor = {
    # REQUIRED
    "company_name": "ABC HVAC & Plumbing",
    "normalized_name": "abc hvac plumbing",  # lowercase, no punctuation
    "state": "tx",  # lowercase 2-letter code
    "source_scraper": "carrier",  # lowercase source identifier

    # OPTIONAL (but highly recommended)
    "phone": "5551234567",  # 10 digits preferred
    "email": "info@abchvac.com",
    "domain": "abchvac.com",
    "city": "Austin",
    "address": "123 Main St, Austin, TX 78701",
    "zip_code": "78701",

    # OPTIONAL (arrays)
    "oem_brands": ["Carrier", "Trane", "Lennox"],
    "certifications": ["NATE", "EPA Certified"],
    "service_areas": ["Austin", "Round Rock", "Cedar Park"]
}
```

### Contact Format

```python
contact = {
    # REQUIRED
    "company_name": "ABC HVAC & Plumbing",  # Must match contractor.company_name
    "normalized_company_name": "abc hvac plumbing",  # Must match contractor.normalized_name
    "full_name": "John Smith",
    "source_scraper": "carrier",

    # OPTIONAL (but highly recommended)
    "email": "john@abchvac.com",
    "phone": "5551234568",
    "title": "Owner",
    "is_decision_maker": True  # ATL flag
}
```

---

## 4. Batch Processing Best Practices

### Batch Size Recommendations

| Batch Size | Processing Time | Recommendation |
|------------|-----------------|----------------|
| 1-100 | < 5 seconds | Optimal |
| 100-500 | 5-20 seconds | Good |
| 500-1000 | 20-40 seconds | Acceptable |
| 1000+ | 40+ seconds | Split into smaller batches |

### Example: Process Large Scrape in Batches

```python
from celery import group

def process_scrape_results(all_contractors: list, source_scraper: str):
    """Process large scrape in batches of 100."""

    BATCH_SIZE = 100

    # Split into batches
    batches = [
        all_contractors[i:i + BATCH_SIZE]
        for i in range(0, len(all_contractors), BATCH_SIZE)
    ]

    # Create Celery group for parallel processing
    job = group(
        push_to_sales_agent.s(batch, [], source_scraper)
        for batch in batches
    )

    # Execute
    result = job.apply_async()

    print(f"Queued {len(batches)} batches for processing")

    return result
```

---

## 5. Error Handling

### Partial Success Response

When some records fail, the API returns `"status": "partial_success"`:

```json
{
  "status": "partial_success",
  "total_received": 10,
  "inserted": 8,
  "updated": 1,
  "skipped": 1,
  "errors": [
    {
      "company_name": "Bad Company",
      "error": "Missing required field: state"
    }
  ]
}
```

### Retry Strategy

```python
from celery import shared_task

@shared_task(bind=True, max_retries=3)
def push_to_sales_agent_with_retry(self, contractors, contacts, source_scraper):
    """Push with automatic retry on failure."""

    try:
        return push_to_sales_agent(contractors, contacts, source_scraper)

    except httpx.HTTPError as e:
        # Retry on HTTP errors (5xx, timeouts)
        raise self.retry(exc=e, countdown=60)  # Retry after 60 seconds

    except Exception as e:
        # Don't retry on validation errors (4xx)
        print(f"Permanent failure: {e}")
        raise
```

---

## 6. Monitoring

### Check Sync Status

```bash
curl http://localhost:8001/api/v1/scraper/status
```

Response:
```json
{
  "last_sync_at": "2025-12-08T10:35:00Z",
  "total_contractors_synced": 1234,
  "total_contacts_synced": 567,
  "last_batch_id": "carrier_20251208_103500",
  "last_source_scraper": "carrier"
}
```

### View Audit Log (Supabase)

```sql
-- Check recent imports
SELECT
  company_name,
  event_type,
  decision_data->>'source_scraper' as scraper,
  created_at
FROM lead_audit_log
WHERE created_by = 'dealer_scraper_api'
ORDER BY created_at DESC
LIMIT 50;
```

### View Synced Companies (Supabase)

```sql
-- Count by scraper source
SELECT
  source_scraper,
  COUNT(*) as total,
  COUNT(DISTINCT domain) as with_domains
FROM dim_companies
WHERE source = 'dealer_scraper'
GROUP BY source_scraper
ORDER BY total DESC;
```

---

## 7. Deduplication Logic

### How Companies Are Matched

```python
# Priority order:
1. normalized_name → UPDATE (highest priority)
2. phone → UPDATE
3. domain → UPDATE
4. No match → INSERT (new company)
```

### How Contacts Are Matched

```python
# Must first find matching company
company_id = find_company_by_normalized_name(contact.normalized_company_name)

if company_id:
    # Then match contact
    1. (company_id, email) → UPDATE
    2. (company_id, phone) → UPDATE
    3. No match → INSERT (new contact)
else:
    # SKIP contact (no company found)
```

---

## 8. Example: Full Integration

### dealer-scraper-mvp/scrapers/carrier_scraper.py

```python
from tasks import push_to_sales_agent

def scrape_carrier_dealers():
    """Scrape Carrier dealer locator and push to sales-agent."""

    contractors = []
    contacts = []

    # Scrape dealers
    for dealer in scrape_dealers_from_carrier():
        contractors.append({
            "company_name": dealer["name"],
            "normalized_name": normalize(dealer["name"]),
            "phone": dealer.get("phone"),
            "domain": extract_domain(dealer.get("website")),
            "state": dealer["state"].lower(),
            "city": dealer.get("city"),
            "oem_brands": ["Carrier"],
            "source_scraper": "carrier"
        })

        # Extract contacts if available
        if dealer.get("contacts"):
            for contact in dealer["contacts"]:
                contacts.append({
                    "company_name": dealer["name"],
                    "normalized_company_name": normalize(dealer["name"]),
                    "full_name": contact["name"],
                    "email": contact.get("email"),
                    "phone": contact.get("phone"),
                    "title": contact.get("title"),
                    "is_decision_maker": is_decision_maker(contact.get("title")),
                    "source_scraper": "carrier"
                })

    # Push to sales-agent (async via Celery)
    push_to_sales_agent.delay(contractors, contacts, "carrier")

    print(f"Queued {len(contractors)} contractors, {len(contacts)} contacts")
```

---

## 9. Testing

### Test Single Contractor

```bash
curl -X POST http://localhost:8001/api/v1/scraper/contractors \
  -H "Content-Type: application/json" \
  -d '{
    "contractors": [{
      "company_name": "Test HVAC",
      "normalized_name": "test hvac",
      "domain": "testhvac.com",
      "state": "tx",
      "oem_brands": ["Carrier"],
      "source_scraper": "test"
    }],
    "batch_id": "test_001",
    "source_scraper": "test"
  }'
```

### Test Contact Import

```bash
curl -X POST http://localhost:8001/api/v1/scraper/contacts \
  -H "Content-Type: application/json" \
  -d '{
    "contacts": [{
      "company_name": "Test HVAC",
      "normalized_company_name": "test hvac",
      "full_name": "John Tester",
      "email": "john@testhvac.com",
      "title": "Owner",
      "is_decision_maker": true,
      "source_scraper": "test"
    }],
    "batch_id": "test_contacts_001",
    "source_scraper": "test"
  }'
```

---

## 10. Troubleshooting

### Issue: Contacts Skipped (No Matching Company)

**Symptom**: `"skipped": 10, "errors": [{"error": "No matching company found"}]`

**Solution**: Ensure contacts are pushed AFTER contractors:
```python
# 1. Push contractors first
push_contractors(contractors)

# 2. Wait for completion (or use synchronous call)
time.sleep(2)

# 3. Then push contacts
push_contacts(contacts)
```

### Issue: Duplicates Created

**Symptom**: Same company appears multiple times in Supabase

**Solution**: Ensure `normalized_name` is consistent:
```python
# Bad
normalized_name = "ABC HVAC & Plumbing"  # Not normalized!

# Good
normalized_name = "abc hvac plumbing"  # lowercase, no punctuation
```

### Issue: HTTP Timeout

**Symptom**: `httpx.ReadTimeout` after 30 seconds

**Solution**: Increase timeout for large batches:
```python
response = httpx.post(
    url,
    json=payload,
    timeout=120.0  # 2 minutes instead of default 30s
)
```

---

## 11. Production Deployment

### Environment Variables (sales-agent)

```env
# .env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_key

# Optional: Sentry for error tracking
SENTRY_DSN=https://your-sentry-dsn
```

### Vercel Deployment

```bash
# Deploy to Vercel (if using serverless)
vercel --prod

# Or use Docker (recommended for background tasks)
docker-compose up -d
```

### NGINX Reverse Proxy

```nginx
# /etc/nginx/sites-available/sales-agent
server {
    listen 80;
    server_name api.sales-agent.com;

    location /api/v1/scraper/ {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
```

---

## Support

**API Docs**: http://localhost:8001/api/v1/docs#/dealer-scraper

**Full Documentation**: `/Users/tmkipper/Desktop/tk_projects/sales-agent/backend/DEALER_SCRAPER_API.md`

**Tests**: `pytest tests/test_sync_from_scraper.py -v`
