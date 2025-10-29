# CSV Import Step-by-Step Guide

## Quick Start

This guide walks you through importing your CSV file of 200 companies into the Sales Agent platform.

## Prerequisites

### 1. Start Docker Services (PostgreSQL + Redis)

```bash
docker-compose up -d
```

Verify services are running:
```bash
docker-compose ps
```

Expected output:
```
NAME                   STATUS
sales-agent-postgres   Up (healthy)
sales-agent-redis      Up (healthy)
```

### 2. Start FastAPI Server

Open a **new terminal window** and run:

```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent
python3 start_server.py
```

Server will start at `http://localhost:8001`

**Keep this terminal window open** - the server needs to keep running.

### 3. Verify Server is Running

In another terminal, test the health endpoint:

```bash
curl http://localhost:8001/api/health
```

Expected response:
```json
{"status":"healthy","timestamp":"2025-01-28T...","services":{"database":"connected","redis":"connected"}}
```

## CSV File Format

### Required Columns
- `company_name` (required)

### Optional Columns
- `company_website`
- `company_size`
- `industry`
- `contact_name`
- `contact_email`
- `contact_phone`
- `contact_title`
- `notes`

### Example CSV Format

```csv
company_name,company_website,company_size,industry,contact_email,contact_name,contact_title
Acme Corp,https://acme.com,50-200,SaaS,john@acme.com,John Doe,CEO
TechStart,https://techstart.io,10-50,Software,jane@techstart.io,Jane Smith,CTO
```

## Import Methods

### Method 1: Using curl (Recommended)

**Basic Import:**
```bash
curl -X POST "http://localhost:8001/api/leads/import/csv" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@companies_ready_to_import.csv"
```

**Strict Mode** (fails on first validation error):
```bash
curl -X POST "http://localhost:8001/api/leads/import/csv?strict_mode=true" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@companies_ready_to_import.csv"
```

### Method 2: Using Python Script

Create `scripts/import_csv.py`:

```python
#!/usr/bin/env python3
import requests
import sys

def import_csv(file_path, strict_mode=False):
    url = "http://localhost:8001/api/leads/import/csv"
    params = {"strict_mode": strict_mode} if strict_mode else {}
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(url, files=files, params=params)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Success!")
        print(f"   Imported: {result['imported_count']}/{result['total_leads']}")
        print(f"   Failed: {result['failed_count']}")
        print(f"   Duration: {result['duration_ms']}ms")
        print(f"   Rate: {result['leads_per_second']} leads/sec")
        
        if result['errors']:
            print(f"\n⚠️  Errors ({len(result['errors'])}):")
            for error in result['errors'][:5]:  # Show first 5
                print(f"   - {error}")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "companies_ready_to_import.csv"
    strict = "--strict" in sys.argv
    import_csv(file_path, strict)
```

Run it:
```bash
python3 scripts/import_csv.py companies_ready_to_import.csv
```

## Verification

### Check Imported Leads

**View all leads:**
```bash
curl http://localhost:8001/api/leads/ | jq '.total'
```

**View first 5 leads:**
```bash
curl http://localhost:8001/api/leads/ | jq '.leads[0:5]'
```

**Check specific lead:**
```bash
curl http://localhost:8001/api/leads/1 | jq
```

### Database Query

Connect to PostgreSQL:
```bash
docker exec -it sales-agent-postgres-1 psql -U sales_agent -d sales_agent_db
```

Query leads:
```sql
-- Count total leads
SELECT COUNT(*) FROM leads;

-- View recent imports
SELECT id, company_name, contact_email, created_at 
FROM leads 
ORDER BY created_at DESC 
LIMIT 10;

-- Check companies without emails (for enrichment)
SELECT id, company_name, company_website, notes 
FROM leads 
WHERE contact_email IS NULL OR contact_email = ''
LIMIT 10;
```

## Expected Response

Successful import response:
```json
{
  "message": "Leads imported successfully",
  "filename": "companies_ready_to_import.csv",
  "total_leads": 200,
  "imported_count": 198,
  "failed_count": 2,
  "duration_ms": 4234,
  "leads_per_second": 46.73,
  "errors": [
    "Row 45: Invalid email format 'invalid-email'",
    "Row 123: Missing required field 'company_name'"
  ]
}
```

## Troubleshooting

### Error: "Connection refused" or "Server not running"

**Fix:** Start the FastAPI server:
```bash
python3 start_server.py
```

Keep the terminal window open!

### Error: "File must be a CSV file"

**Fix:** Ensure your file has `.csv` extension:
```bash
mv your_file.csv companies_ready_to_import.csv
```

### Error: "Missing required field 'company_name'"

**Fix:** Check your CSV has a header row with `company_name`:
```bash
head -1 companies_ready_to_import.csv
```

### Error: "Database connection failed"

**Fix:** Start Docker services:
```bash
docker-compose up -d
```

Wait 5 seconds, then verify:
```bash
docker-compose ps
```

### Error: "File size exceeds maximum"

**Fix:** Current limit is 10MB. For larger files, split into batches:
```bash
# Split CSV into 500-row chunks
split -l 500 companies.csv companies_chunk_
```

### Import Performance

- **Target**: 200 companies in <5 seconds
- **Typical**: ~3-4 seconds for 200 companies
- **Rate**: ~50-70 leads/second

## Next Steps

After importing, you can:

1. **Enrich contacts** using Apollo.io (see batch enrichment script)
2. **Qualify leads** using the Qualification Agent
3. **View leads** via API or database
4. **Create campaigns** for imported leads

See `TERMINAL_TESTING_GUIDE.md` for testing agents with imported leads.

