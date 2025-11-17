"""
Test Single Lead with Raw Status

Creates ONE test lead to verify:
1. Status = "Raw" (not custom status)
2. Custom fields populated (is_atl, qualification_score, priority_label)
3. Description contains priority label
4. Lead appears in Close CRM
"""
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

sys.path.insert(0, '/Users/tmkipper/Desktop/tk_projects/sales-agent/backend')

from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.schemas.pipeline import PipelineTestRequest, PipelineTestOptions


async def test_raw_status():
    """Test ONE lead with Raw status"""
    print("\n" + "="*80)
    print("TESTING: Single Lead with RAW Status")
    print("="*80)

    # Use a REAL company with working website and Hunter.io data
    lead = {
        'name': 'Atlanta Air Specialists',
        'company_name': 'Atlanta Air Specialists',
        'industry': 'HVAC Services',
        'website': 'https://atlantaairspecialists.com',
        'phone': '',
        'company_size': '10-50',
        'contact_name': 'Unknown',
        'contact_title': 'Owner',
    }

    print(f"\nLead: {lead['company_name']}")
    print(f"Website: {lead['website']}")
    print(f"Industry: {lead['industry']}")

    # First: DRY RUN to show what WILL happen
    print("\n" + "-"*80)
    print("STEP 1: DRY RUN (showing what WILL happen)")
    print("-"*80)

    orchestrator = PipelineOrchestrator(db=None)

    request_dry = PipelineTestRequest(
        lead=lead,
        options=PipelineTestOptions(
            skip_enrichment=False,
            create_in_crm=False,  # Don't create yet
            stop_on_duplicate=False,
            dry_run=True
        )
    )

    result_dry = await orchestrator.execute(request_dry)

    print(f"\n📋 DRY RUN RESULTS:")
    print(f"Success: {result_dry.success}")
    print(f"Total Latency: {result_dry.total_latency_ms}ms")

    # Show qualification results
    if result_dry.stages.get('qualification'):
        qual = result_dry.stages['qualification']
        if qual.output:
            print(f"\n  QUALIFICATION:")
            print(f"    Score: {qual.output.get('qualification_score', 'N/A')}")
            print(f"    Tier: {qual.output.get('tier', 'N/A')}")
            print(f"    Is ATL: {qual.output.get('is_atl', 'N/A')}")

    # Show CRM check results
    if result_dry.stages.get('crm_check'):
        crm = result_dry.stages['crm_check']
        if crm.output:
            print(f"\n  CRM CHECK:")
            print(f"    Recommendation: {crm.output.get('recommendation', 'N/A')}")
            print(f"    Company Exists: {crm.output.get('company_exists', 'N/A')}")
            print(f"    Matched Lead ID: {crm.output.get('matched_lead_id', 'N/A')}")

    # Show enrichment results (Hunter.io contacts)
    if result_dry.stages.get('enrichment'):
        enrich = result_dry.stages['enrichment']
        if enrich.output and isinstance(enrich.output, dict):
            contacts = enrich.output.get('contacts', [])
            print(f"\n  ENRICHMENT:")
            print(f"    Contacts Found: {len(contacts)}")
            if contacts:
                for i, contact in enumerate(contacts[:3], 1):  # Show first 3
                    print(f"      {i}. {contact.get('name')} ({contact.get('title')})")
                    print(f"         Email: {contact.get('email')}")
                    print(f"         ATL: {contact.get('is_atl', False)}")

    # Now ask user if they want to proceed
    print("\n" + "-"*80)
    print("STEP 2: CREATE REAL LEAD with dry_run=FALSE?")
    print("-"*80)
    print("\n⚠️  This will CREATE a real lead in Close CRM with:")
    print("  - Status: 'Raw' (status_id = stat_4qxeqdfEDGNFmh93pFmXz4l8bw78DuQtTlATratY2Qb)")
    print("  - Custom Fields: is_atl, qualification_score, priority_label")
    print("  - Description: Priority label + qualification score")

    proceed = input("\nProceed with REAL lead creation? (yes/no): ").lower().strip()

    if proceed != 'yes':
        print("\n❌ Cancelled. No lead created.")
        return

    # Create REAL lead
    print("\n" + "-"*80)
    print("Creating REAL lead in Close CRM...")
    print("-"*80)

    request_real = PipelineTestRequest(
        lead=lead,
        options=PipelineTestOptions(
            skip_enrichment=False,
            create_in_crm=True,  # CREATE FOR REAL
            stop_on_duplicate=False,
            dry_run=False  # NOT a dry run
        )
    )

    result_real = await orchestrator.execute(request_real)

    print(f"\n✅ REAL LEAD CREATED!")
    print(f"Success: {result_real.success}")
    print(f"Total Latency: {result_real.total_latency_ms}ms")

    # Show Close CRM results
    if result_real.stages.get('close_crm'):
        close = result_real.stages['close_crm']
        if close.output:
            print(f"\n  CLOSE CRM RESULT:")
            print(f"    Lead ID: {close.output.get('lead_id', 'N/A')}")
            print(f"    Status: {close.output.get('status', 'N/A')}")
            print(f"    Contacts Created: {close.output.get('contacts_created', 'N/A')}")
            print(f"    URL: https://app.close.com/lead/{close.output.get('lead_id', '')}/")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nNext Steps:")
    print("1. Check Close CRM: https://app.close.com")
    print("2. Verify lead has status='Raw'")
    print("3. Check custom fields: is_atl, qualification_score, priority_label")
    print("4. Verify description contains priority label")
    print("5. Run this script AGAIN to test deduplication (should recommend 'skip_duplicate')")
    print()


if __name__ == '__main__':
    asyncio.run(test_raw_status())
