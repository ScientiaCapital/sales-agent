# Enrichment Status

Check current enrichment progress.

**Usage**: `/enrich-status`

---

## Quick Check

```bash
cd backend && source ../venv/bin/activate
python -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv('../.env')

sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

# Total companies
total = sb.table('dim_companies').select('*', count='exact').execute()

# With domains (can enrich)
with_domains = sb.table('dim_companies').select('*', count='exact').not_.is_('website', 'null').execute()

# Already enriched
enriched = sb.table('dim_companies').select('*', count='exact').not_.is_('last_enriched_at', 'null').execute()

# Contacts found
contacts = sb.table('dim_contacts').select('*', count='exact').execute()

print(f'''
Enrichment Status
─────────────────
Total Companies: {total.count:,}
With Domains:    {with_domains.count:,}
Enriched:        {enriched.count:,}
Remaining:       {with_domains.count - enriched.count:,}
Contacts Found:  {contacts.count:,}
''')
"
```

---

## ICP Tier Breakdown

```bash
python -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv('../.env')
sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
for tier in ['PLATINUM', 'GOLD', 'SILVER', 'BRONZE']:
    r = sb.table('dim_companies').select('*', count='exact').eq('icp_tier', tier).execute()
    print(f'{tier}: {r.count}')
"
```
