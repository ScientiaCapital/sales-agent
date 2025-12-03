# Retry Failed Enrichments

Retry all companies that failed in previous enrichment batches.

## Usage
```
/enrich-retry-failed [--budget 2.00]
```

## What This Does

1. Find failed companies in Supabase
2. Reset their enrichment_status to NULL
3. Re-run through supervised pipeline

## Execution

```bash
cd backend
source ../venv/bin/activate

# Reset failed companies
python -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv('../.env')

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
result = supabase.table('dim_companies').update({
    'enrichment_status': None,
    'enrichment_error': None
}).eq('enrichment_status', 'failed').execute()
print(f'Reset {len(result.data)} failed companies')
"

# Re-run enrichment
python run_supervised_enrichment.py --budget ${BUDGET:-2.0}
```

## When to Use

- After fixing network/API issues
- After increasing rate limits
- To retry transient failures
