# Dealer Scraper Sync API

FastAPI endpoint for receiving scraped leads from **dealer-scraper-mvp**.

## Overview

This API receives batches of contractors and contacts from Celery push tasks in dealer-scraper-mvp and syncs them to the Supabase star schema (`dim_companies`, `dim_contacts`).

**Base URL**: `http://localhost:8001/api/v1/scraper`

**Authentication**: None required (internal service)

---

## Endpoints

### 1. POST `/contractors`

Receive batch of scraped contractors.

**Request Body**:
```json
{
  "contractors": [
    {
      "company_name": "ABC HVAC & Plumbing",
      "normalized_name": "abc hvac plumbing",
      "phone": "5551234567",
      "email": "info@abchvac.com",
      "domain": "abchvac.com",
      "state": "tx",
      "city": "Austin",
      "address": "123 Main St, Austin, TX 78701",
      "zip_code": "78701",
      "oem_brands": ["Carrier", "Trane", "Lennox"],
      "source_scraper": "carrier",
      "certifications": ["NATE", "EPA Certified"],
      "service_areas": ["Austin", "Round Rock", "Cedar Park"]
    }
  ],
  "batch_id": "carrier_batch_20251208",
  "source_scraper": "carrier"
}
```

**Response**:
```json
{
  "status": "success",
  "batch_id": "carrier_batch_20251208",
  "source_scraper": "carrier",
  "total_received": 1,
  "inserted": 1,
  "updated": 0,
  "skipped": 0,
  "errors": [],
  "timestamp": "2025-12-08T10:30:00Z"
}
```

**Business Logic**:

1. **Deduplication** - Check if contractor exists by:
   - `normalized_name` (primary)
   - `phone` (secondary)
   - `domain` (tertiary)

2. **If exists**: Merge OEM brands and update fields
3. **If new**: Insert with `source='dealer_scraper'`
4. **Audit logging**: All imports logged to `lead_audit_log`

**Deduplication Strategy**:

```python
# Priority order:
1. normalized_name match → UPDATE
2. phone match → UPDATE
3. domain match → UPDATE
4. No match → INSERT
```

**OEM Brand Merging**:

```python
# Existing: ["Carrier", "Trane"]
# New: ["Trane", "Lennox"]
# Result: ["Carrier", "Trane", "Lennox"]  # Case-insensitive dedup
```

---

### 2. POST `/contacts`

Receive batch of scraped contacts.

**Request Body**:
```json
{
  "contacts": [
    {
      "company_name": "ABC HVAC & Plumbing",
      "normalized_company_name": "abc hvac plumbing",
      "full_name": "John Smith",
      "email": "john@abchvac.com",
      "phone": "5551234568",
      "title": "Owner",
      "is_decision_maker": true,
      "source_scraper": "carrier"
    }
  ],
  "batch_id": "carrier_contacts_20251208",
  "source_scraper": "carrier"
}
```

**Response**:
```json
{
  "status": "success",
  "batch_id": "carrier_contacts_20251208",
  "source_scraper": "carrier",
  "total_received": 1,
  "inserted": 1,
  "updated": 0,
  "skipped": 0,
  "errors": [],
  "timestamp": "2025-12-08T10:35:00Z"
}
```

**Business Logic**:

1. **Find matching company** by `normalized_company_name`
2. **If no company match**: Skip contact (can't orphan)
3. **If company found**: Check if contact exists by email or phone
4. **If exists**: Update title and other fields
5. **If new**: Insert linked to `company_id`

**Deduplication Strategy**:

```python
# Priority order:
1. Find company by normalized_company_name
2. If company found:
   - Match contact by (company_id, email)
   - Match contact by (company_id, phone)
   - If match → UPDATE
   - If no match → INSERT
3. If company NOT found → SKIP (error logged)
```

---

### 3. GET `/status`

Get sync status and last sync information.

**Response**:
```json
{
  "last_sync_at": "2025-12-08T10:35:00Z",
  "total_contractors_synced": 1234,
  "total_contacts_synced": 567,
  "last_batch_id": "carrier_contacts_20251208",
  "last_source_scraper": "carrier"
}
```

**Data Sources**:

- `last_sync_at` - From `lead_audit_log.created_at` (last entry)
- `total_contractors_synced` - Count from `dim_companies WHERE source='dealer_scraper'`
- `total_contacts_synced` - Count from `dim_contacts WHERE source='dealer_scraper'`
- `last_batch_id` - From `lead_audit_log.session_id`
- `last_source_scraper` - From `lead_audit_log.decision_data.source_scraper`

---

## Integration with dealer-scraper-mvp

### Celery Task Configuration

In `dealer-scraper-mvp/tasks.py`:

```python
import httpx
from celery import shared_task

SALES_AGENT_API_URL = "http://localhost:8001/api/v1/scraper"

@shared_task(name="push_contractors_to_sales_agent")
def push_contractors_to_sales_agent(contractors: list, source_scraper: str):
    """Push batch of contractors to sales-agent API."""

    payload = {
        "contractors": contractors,
        "batch_id": f"{source_scraper}_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "source_scraper": source_scraper
    }

    try:
        response = httpx.post(
            f"{SALES_AGENT_API_URL}/contractors",
            json=payload,
            timeout=60.0
        )
        response.raise_for_status()

        result = response.json()
        logger.info(
            f"Synced {result['inserted']} new, {result['updated']} updated contractors"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to push contractors: {e}")
        raise


@shared_task(name="push_contacts_to_sales_agent")
def push_contacts_to_sales_agent(contacts: list, source_scraper: str):
    """Push batch of contacts to sales-agent API."""

    payload = {
        "contacts": contacts,
        "batch_id": f"{source_scraper}_contacts_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "source_scraper": source_scraper
    }

    try:
        response = httpx.post(
            f"{SALES_AGENT_API_URL}/contacts",
            json=payload,
            timeout=60.0
        )
        response.raise_for_status()

        result = response.json()
        logger.info(
            f"Synced {result['inserted']} new, {result['updated']} updated contacts"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to push contacts: {e}")
        raise
```

---

## Error Handling

### Contractor Import Errors

**Scenario**: Individual contractor fails validation/insert

**Behavior**: Skip contractor, log to `errors` array, continue processing batch

**Response**:
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

### Contact Import Errors

**Scenario**: Contact company not found in `dim_companies`

**Behavior**: Skip contact, log to `errors` array

**Response**:
```json
{
  "status": "partial_success",
  "total_received": 5,
  "inserted": 3,
  "updated": 0,
  "skipped": 2,
  "errors": [
    {
      "contact_name": "Jane Doe",
      "company_name": "Unknown Company",
      "error": "No matching company found"
    }
  ]
}
```

---

## Data Flow

```
dealer-scraper-mvp (Celery Task)
    |
    | POST /api/v1/scraper/contractors
    ▼
sales-agent FastAPI
    |
    | Dedup + Merge OEM brands
    ▼
Supabase (dim_companies)
    |
    | Log import
    ▼
Supabase (lead_audit_log)
```

---

## Testing

### Manual Test (curl)

**Test contractor import**:
```bash
curl -X POST http://localhost:8001/api/v1/scraper/contractors \
  -H "Content-Type: application/json" \
  -d '{
    "contractors": [
      {
        "company_name": "Test HVAC Co",
        "normalized_name": "test hvac co",
        "domain": "testhvac.com",
        "state": "tx",
        "oem_brands": ["Carrier"],
        "source_scraper": "test"
      }
    ],
    "batch_id": "test_batch_001",
    "source_scraper": "test"
  }'
```

**Test contact import**:
```bash
curl -X POST http://localhost:8001/api/v1/scraper/contacts \
  -H "Content-Type: application/json" \
  -d '{
    "contacts": [
      {
        "company_name": "Test HVAC Co",
        "normalized_company_name": "test hvac co",
        "full_name": "John Tester",
        "email": "john@testhvac.com",
        "title": "Owner",
        "is_decision_maker": true,
        "source_scraper": "test"
      }
    ],
    "batch_id": "test_contacts_001",
    "source_scraper": "test"
  }'
```

**Get sync status**:
```bash
curl http://localhost:8001/api/v1/scraper/status
```

### Python Test

```python
import httpx

SALES_AGENT_URL = "http://localhost:8001/api/v1/scraper"

# Test contractor sync
contractors_payload = {
    "contractors": [
        {
            "company_name": "ABC HVAC",
            "normalized_name": "abc hvac",
            "domain": "abchvac.com",
            "state": "tx",
            "oem_brands": ["Carrier", "Trane"],
            "source_scraper": "carrier"
        }
    ],
    "batch_id": "test_001",
    "source_scraper": "carrier"
}

response = httpx.post(f"{SALES_AGENT_URL}/contractors", json=contractors_payload)
print(response.json())

# Expected:
# {
#   "status": "success",
#   "inserted": 1,
#   "updated": 0,
#   "skipped": 0
# }
```

---

## Database Schema

### dim_companies (Updated Fields)

| Column | Type | Description |
|--------|------|-------------|
| `source` | TEXT | Always 'dealer_scraper' for synced companies |
| `source_scraper` | TEXT | Scraper source (generac, enphase, carrier, etc.) |
| `oem_brands` | TEXT[] | Merged array of OEM brands |
| `service_areas` | TEXT[] | Merged array of service areas |
| `certifications` | TEXT[] | Merged array of certifications |
| `last_enriched_at` | TIMESTAMP | Set to NOW() on sync |

### dim_contacts (Updated Fields)

| Column | Type | Description |
|--------|------|-------------|
| `source` | TEXT | Always 'dealer_scraper' for synced contacts |
| `source_scraper` | TEXT | Scraper source |
| `is_decision_maker` | BOOLEAN | ATL flag |

### lead_audit_log (Audit Entries)

| Column | Value |
|--------|-------|
| `company_name` | Company name from import |
| `session_id` | Batch ID from request |
| `event_type` | 'inserted' or 'updated' |
| `stage` | 'import' |
| `created_by` | 'dealer_scraper_api' |
| `decision_data` | JSON with source_scraper, match_reason, etc. |

---

## Performance

**Batch Processing**:
- Loads all existing companies ONCE per batch
- Builds in-memory lookup maps for O(1) deduplication
- Processes contractors/contacts in single pass

**Benchmarks** (estimated):
- 100 contractors: ~2-3 seconds
- 500 contractors: ~8-10 seconds
- 1000 contractors: ~15-20 seconds

**Optimization Tips**:
- Keep batch sizes under 500 records
- Use batch_id for tracking large imports
- Run multiple small batches vs. one large batch

---

## Monitoring

### Logs

```python
logger.info(f"Processing {total_received} contractors from {request.source_scraper}")
logger.info(f"Contractor sync complete: {inserted} inserted, {updated} updated, {skipped} skipped")
logger.warning(f"No company found for contact {contact.full_name}")
logger.error(f"Error processing contractor {contractor.company_name}: {e}")
```

### Metrics to Track

- `total_received` - Total records in batch
- `inserted` - New records created
- `updated` - Existing records updated
- `skipped` - Records skipped due to errors
- `errors` - Error details array

### Health Check

```bash
curl http://localhost:8001/api/v1/scraper/status
```

Returns last sync timestamp and totals.

---

## Security

**Internal Service**: This endpoint assumes dealer-scraper-mvp is a trusted internal service.

**Future Enhancements**:
- Add API key authentication
- Add rate limiting
- Add IP whitelisting
- Add request signing

---

## Next Steps

1. **Deploy sales-agent API** - Ensure `/api/v1/scraper/*` is accessible
2. **Configure dealer-scraper-mvp** - Add Celery tasks to call this endpoint
3. **Test integration** - Run end-to-end test with real scraper data
4. **Monitor imports** - Check `lead_audit_log` and Supabase tables
5. **Scale up** - Increase batch sizes as needed

---

## Support

**API Documentation**: http://localhost:8001/api/v1/docs#/dealer-scraper

**Logs**: `backend/logs/sales-agent.log`

**Database**: Supabase `dim_companies`, `dim_contacts`, `lead_audit_log`
