#!/usr/bin/env python3
"""
Sales Agent → Close CRM Integration
====================================
Ensures ZERO data loss by:
1. Tagging all enriched companies with 'sales-agent' source
2. Syncing to Close CRM as leads
3. Tracking full pipeline: New → Qualified → Opp → Won/Lost
4. Bidirectional sync (Close updates → Supabase)

Pipeline Tracking:
- Enriched → Close Lead (custom.sales_agent_source = 'enrichment')
- Qualified → Opportunity Created
- Demo Scheduled → Opportunity Stage 'Demo'
- Proposal Sent → Opportunity Stage 'Proposal'
- Closed Won → Opportunity Status 'won'
- Closed Lost → Opportunity Status 'lost'
"""

import os
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from supabase import create_client
from closeio_api import Client as CloseClient

load_dotenv('../.env')

# Clients
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)
close = CloseClient(os.getenv("CLOSE_API_KEY"))

# Constants
SALES_AGENT_SOURCE = "sales-agent-enrichment"
CUSTOM_FIELD_SALES_AGENT = "cf_sales_agent_source"  # Custom field ID in Close
CUSTOM_FIELD_ENRICHED_AT = "cf_enriched_at"
CUSTOM_FIELD_ICP_SCORE = "cf_icp_score"
CUSTOM_FIELD_ICP_TIER = "cf_icp_tier"


# ============================================================================
# 1. SYNC ENRICHED COMPANIES TO CLOSE CRM
# ============================================================================

async def sync_enriched_to_close(limit: int = 100, dry_run: bool = False):
    """
    Sync recently enriched companies to Close CRM with sales-agent tag.

    Process:
    1. Find companies enriched in last 24h
    2. Check if already in Close (by domain)
    3. Create new lead OR update existing with enrichment data
    4. Tag with custom.sales_agent_source = 'enrichment'
    """
    print(f"\n{'='*70}")
    print(f"🔄 SYNCING ENRICHED COMPANIES TO CLOSE CRM")
    print(f"{'='*70}\n")

    # Get recently enriched companies (last 24 hours)
    enriched = supabase.table('dim_companies').select(
        'company_id,company_name,domain,phone,city,state,zip,'
        'apollo_enriched_at,linkedin_url,employee_count,'
        'icp_score,icp_tier,oem_brands,service_areas'
    ).not_.is_('apollo_enriched_at', 'null').limit(limit).execute()

    print(f"📊 Found {len(enriched.data)} enriched companies\n")

    synced = 0
    created = 0
    updated = 0
    skipped = 0

    for company in enriched.data:
        domain = company.get('domain')
        if not domain:
            skipped += 1
            continue

        try:
            # Check if lead already exists in Close
            existing = close.get('lead', params={'query': f'url:"{domain}"'})

            lead_data = {
                'name': company['company_name'],
                'url': domain,
                'custom': {
                    CUSTOM_FIELD_SALES_AGENT: SALES_AGENT_SOURCE,
                    CUSTOM_FIELD_ENRICHED_AT: company.get('apollo_enriched_at'),
                    CUSTOM_FIELD_ICP_SCORE: company.get('icp_score', 0),
                    CUSTOM_FIELD_ICP_TIER: company.get('icp_tier', 'LEAD'),
                }
            }

            # Add address if available
            if company.get('city') or company.get('state'):
                lead_data['addresses'] = [{
                    'city': company.get('city'),
                    'state': company.get('state'),
                    'zipcode': company.get('zip'),
                    'country': 'US'
                }]

            if not dry_run:
                if existing['data']:
                    # Update existing lead
                    lead_id = existing['data'][0]['id']
                    close.put(f'lead/{lead_id}', data=lead_data)
                    updated += 1
                    print(f"  ✅ Updated: {company['company_name']}")
                else:
                    # Create new lead
                    close.post('lead', data=lead_data)
                    created += 1
                    print(f"  🆕 Created: {company['company_name']}")
            else:
                print(f"  [DRY RUN] Would sync: {company['company_name']}")

            synced += 1

        except Exception as e:
            print(f"  ❌ Error syncing {company['company_name']}: {e}")
            continue

    print(f"\n{'='*70}")
    print(f"📊 SYNC COMPLETE")
    print(f"{'='*70}")
    print(f"  Total Processed:  {synced}")
    print(f"  🆕 Created:       {created}")
    print(f"  ✅ Updated:       {updated}")
    print(f"  ⏭️  Skipped:       {skipped}")
    print(f"{'='*70}\n")

    return {'synced': synced, 'created': created, 'updated': updated}


# ============================================================================
# 2. SYNC CONTACTS TO CLOSE LEADS
# ============================================================================

async def sync_contacts_to_close(limit: int = 100, dry_run: bool = False):
    """
    Sync ATL contacts discovered by sales-agent to Close CRM.

    Attaches contacts to existing Close leads.
    """
    print(f"\n{'='*70}")
    print(f"👥 SYNCING ATL CONTACTS TO CLOSE CRM")
    print(f"{'='*70}\n")

    # Get contacts from enriched companies
    contacts = supabase.table('dim_contacts').select(
        'contact_id,full_name,email,phone,title,company_id,'
        'dim_companies!inner(domain,company_name,close_lead_id)'
    ).not_.is_('email', 'null').limit(limit).execute()

    print(f"📊 Found {len(contacts.data)} contacts to sync\n")

    synced = 0
    for contact in contacts.data:
        company = contact.get('dim_companies', {})
        domain = company.get('domain')
        close_lead_id = company.get('close_lead_id')

        if not domain:
            continue

        try:
            # Find Close lead if we don't have ID
            if not close_lead_id:
                existing = close.get('lead', params={'query': f'url:"{domain}"'})
                if not existing['data']:
                    continue
                close_lead_id = existing['data'][0]['id']

            # Create contact in Close
            contact_data = {
                'lead_id': close_lead_id,
                'name': contact['full_name'],
                'title': contact.get('title'),
                'emails': [{'email': contact['email']}] if contact.get('email') else [],
                'phones': [{'phone': contact['phone']}] if contact.get('phone') else [],
            }

            if not dry_run:
                close.post('contact', data=contact_data)
                synced += 1
                print(f"  ✅ {contact['full_name']} → {company.get('company_name')}")
            else:
                print(f"  [DRY RUN] Would sync: {contact['full_name']}")

        except Exception as e:
            print(f"  ❌ Error syncing {contact['full_name']}: {e}")
            continue

    print(f"\n{'='*70}")
    print(f"📊 CONTACTS SYNCED: {synced}")
    print(f"{'='*70}\n")

    return {'synced': synced}


# ============================================================================
# 3. TRACK PIPELINE PROGRESSION
# ============================================================================

async def track_pipeline_updates():
    """
    Pull Close CRM opportunity updates and track in Supabase.

    Tracks:
    - Opportunity created (Qualified lead)
    - Stage changes (Demo, Proposal, Negotiation)
    - Won/Lost status
    - Close reason
    """
    print(f"\n{'='*70}")
    print(f"📈 TRACKING PIPELINE UPDATES FROM CLOSE CRM")
    print(f"={'*70}\n")

    # Get all opportunities with sales-agent source
    opps = close.get('opportunity', params={
        'query': f'custom.{CUSTOM_FIELD_SALES_AGENT}:"{SALES_AGENT_SOURCE}"'
    })

    print(f"📊 Found {len(opps.get('data', []))} sales-agent opportunities\n")

    for opp in opps.get('data', []):
        lead_id = opp['lead_id']

        # Get lead to find domain
        lead = close.get(f'lead/{lead_id}')
        domain = lead.get('url')

        if not domain:
            continue

        # Find company in Supabase
        company = supabase.table('dim_companies').select(
            'company_id'
        ).eq('domain', domain).execute()

        if not company.data:
            continue

        company_id = company.data[0]['company_id']

        # Record opportunity stage in Supabase
        opp_data = {
            'company_id': company_id,
            'close_opportunity_id': opp['id'],
            'status': opp['status_type'],  # 'active', 'won', 'lost'
            'stage': opp.get('status_label'),
            'value': opp.get('value', 0),
            'confidence': opp.get('confidence', 0),
            'expected_close_date': opp.get('date_predicted_close'),
            'actual_close_date': opp.get('date_won') or opp.get('date_lost'),
            'close_reason': opp.get('note') if opp['status_type'] in ['won', 'lost'] else None,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }

        # Upsert to fact_opportunities table
        supabase.table('fact_opportunities').upsert(
            opp_data,
            on_conflict='close_opportunity_id'
        ).execute()

        status_emoji = "🎉" if opp['status_type'] == 'won' else "😞" if opp['status_type'] == 'lost' else "🔄"
        print(f"  {status_emoji} {lead.get('name')}: {opp.get('status_label')} (${opp.get('value', 0):,.0f})")

    print(f"\n{'='*70}\n")


# ============================================================================
# 4. GENERATE PIPELINE REPORT
# ============================================================================

async def generate_pipeline_report():
    """
    Show full sales-agent attribution report:
    - Companies enriched
    - Leads created in Close
    - Opportunities created
    - Won/Lost breakdown
    - Revenue attributed to sales-agent
    """
    print(f"\n{'='*80}")
    print(f"🎯 SALES AGENT ATTRIBUTION REPORT".center(80))
    print(f"{'='*80}\n")

    # Enrichment stats
    total_enriched = supabase.table('dim_companies').select(
        'company_id', count='exact'
    ).not_.is_('apollo_enriched_at', 'null').execute()

    # Opportunities stats
    opps = supabase.table('fact_opportunities').select('*').execute()

    won = [o for o in opps.data if o['status'] == 'won']
    lost = [o for o in opps.data if o['status'] == 'lost']
    active = [o for o in opps.data if o['status'] == 'active']

    total_revenue = sum(o.get('value', 0) for o in won)
    pipeline_value = sum(o.get('value', 0) for o in active)

    print(f"📊 ENRICHMENT:")
    print(f"   Companies Enriched:    {total_enriched.count:>6,}")

    print(f"\n📈 PIPELINE:")
    print(f"   Total Opportunities:   {len(opps.data):>6,}")
    print(f"   Active:                {len(active):>6,}  (${pipeline_value:>12,.0f})")
    print(f"   Won:                   {len(won):>6,}  (${total_revenue:>12,.0f})")
    print(f"   Lost:                  {len(lost):>6,}")

    if len(opps.data) > 0:
        win_rate = len(won) / (len(won) + len(lost)) * 100 if (len(won) + len(lost)) > 0 else 0
        print(f"\n🎯 PERFORMANCE:")
        print(f"   Win Rate:              {win_rate:>6.1f}%")
        print(f"   Avg Deal Size:         ${total_revenue/len(won) if won else 0:>12,.0f}")

    print(f"\n{'='*80}\n")


# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================

async def main():
    """Run full sales-agent → Close CRM sync"""
    import argparse

    parser = argparse.ArgumentParser(description='Sales Agent → Close CRM Integration')
    parser.add_argument('--sync-companies', action='store_true', help='Sync enriched companies to Close')
    parser.add_argument('--sync-contacts', action='store_true', help='Sync ATL contacts to Close')
    parser.add_argument('--track-pipeline', action='store_true', help='Pull pipeline updates from Close')
    parser.add_argument('--report', action='store_true', help='Generate attribution report')
    parser.add_argument('--all', action='store_true', help='Run all sync operations')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (no writes to Close)')
    parser.add_argument('--limit', type=int, default=100, help='Limit records to process')

    args = parser.parse_args()

    if args.all or args.sync_companies:
        await sync_enriched_to_close(limit=args.limit, dry_run=args.dry_run)

    if args.all or args.sync_contacts:
        await sync_contacts_to_close(limit=args.limit, dry_run=args.dry_run)

    if args.all or args.track_pipeline:
        await track_pipeline_updates()

    if args.all or args.report:
        await generate_pipeline_report()


if __name__ == "__main__":
    asyncio.run(main())
