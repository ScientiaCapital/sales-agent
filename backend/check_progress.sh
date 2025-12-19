#!/bin/bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
source ../venv/bin/activate
python3 -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()
s = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

# Enrichment status
free = s.table('dim_companies').select('company_id', count='exact').eq('enrichment_status', 'free_enriched').execute()
pending = s.table('dim_companies').select('company_id', count='exact').or_('enrichment_status.is.null,enrichment_status.eq.pending').neq('domain', None).execute()
total = free.count + pending.count

# ATL contacts found
atl = s.table('dim_contacts').select('contact_id', count='exact').eq('is_atl', True).execute()

print('=' * 50)
print('ENRICHMENT PROGRESS')
print('=' * 50)
print(f'FREE Enriched:  {free.count:,}')
print(f'Pending:        {pending.count:,}')
print(f'Progress:       {100*free.count/total:.1f}%')
print(f'ATL Contacts:   {atl.count:,}')
print('=' * 50)

# Check if process running
import subprocess
result = subprocess.run(['pgrep', '-f', 'run_enrichment'], capture_output=True, text=True)
if result.stdout.strip():
    print(f'Process running: PID {result.stdout.strip()}')
else:
    print('⚠️  Process NOT running!')
"
