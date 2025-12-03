# Retry Failed Enrichments

Retry companies that failed in previous batches.

**Usage**: `/enrich-retry-failed [--budget 2.00]`

---

## Quick Start

```bash
cd backend && source ../venv/bin/activate

# Check how many failed
python -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv('../.env')
sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
r = sb.table('dim_companies').select('*', count='exact').eq('enrichment_status', 'failed').execute()
print(f'{r.count} companies failed enrichment')
"

# Reset and retry
python -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv('../.env')
sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
r = sb.table('dim_companies').update({
    'enrichment_status': None,
    'enrichment_error': None
}).eq('enrichment_status', 'failed').execute()
print(f'Reset {len(r.data)} failed companies')
"

# Re-run enrichment
python run_enrichment.py --limit 50
```

---

## When to Use

- After fixing network issues
- After API rate limits reset
- After fixing extraction bugs
