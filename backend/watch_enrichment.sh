#!/bin/bash
# Real-time enrichment dashboard
# Run this to watch companies and ATLs grow LIVE

source ../venv/bin/activate

while true; do
  clear
  python3 << 'EOF'
from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv('../.env')
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

total = supabase.table('dim_companies').select('company_id', count='exact').execute()
apollo = supabase.table('dim_companies').select('company_id', count='exact').not_.is_('apollo_enriched_at', 'null').execute()
atl = supabase.table('dim_contacts').select('contact_id', count='exact').execute()

print("="*70)
print("🚀 LIVE ENRICHMENT DASHBOARD".center(70))
print("="*70)
print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}\n")
print(f"📊 COMPANIES:")
print(f"   Total:           {total.count:>8,}")
print(f"   ✅ Enriched:     {apollo.count:>8,}  ({apollo.count/total.count*100:>5.1f}%)")
print(f"   ⏳ Remaining:    {total.count - apollo.count:>8,}")
print(f"\n👥 ATL CONTACTS:   {atl.count:>8,}")
print("\n" + "="*70)
print("Refreshing every 3 seconds... (Ctrl+C to stop)")
EOF

  sleep 3
done
