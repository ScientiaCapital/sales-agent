# Batch Enrichment

Run parallel batch enrichment for multiple companies.

**Usage**: `/batch-enrich`

---

## Quick Start

```bash
cd backend && source ../venv/bin/activate

# Check what needs enrichment
python -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv('../.env')
sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
r = sb.table('dim_companies').select('company_id', count='exact').is_('last_enriched_at', 'null').not_.is_('website', 'null').execute()
print(f'{r.count} companies need enrichment')
"

# Run batch (100 at a time)
python run_enrichment.py --limit 100 --auto
```

---

## Options

| Flag | Description |
|------|-------------|
| `--limit N` | Process N companies (default: 5) |
| `--auto` | Auto-approve batches (no prompts) |
| `--domain X` | Enrich single domain |

---

## Pipeline Stages

```
1. Scrape website (Browserbase)
2. Extract ATL/BTL contacts
3. Find emails (Hunter.io)
4. Detect OEM brands
5. Update Supabase
```

---

## Rate Limits

| Service | Limit |
|---------|-------|
| Browserbase | 5 concurrent |
| Hunter.io | 50/month |
| Apollo | 200/hour |
