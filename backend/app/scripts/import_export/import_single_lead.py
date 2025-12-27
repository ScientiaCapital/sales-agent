"""
Import Single Lead from CSV to Test Raw Status

Tests complete CSV → Close CRM flow with:
1. Status = "Raw" (not custom status)
2. Custom fields populated
3. Description with priority label
"""
import asyncio
import sys
import csv
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

sys.path.insert(0, '/Users/tmkipper/Desktop/tk_projects/sales-agent/backend')

from app.services.pipeline import PipelineOrchestrator
from app.schemas.pipeline import PipelineTestRequest, PipelineTestOptions


async def import_single_lead():
    """Import one lead from CSV"""
    print("\n" + "="*80)
    print("IMPORTING SINGLE LEAD FROM CSV - Testing Raw Status")
    print("="*80)

    # Load CSV
    csv_path = Path(__file__).parent / 'test_raw_single.csv'
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        row = next(reader)

    # Map CSV to lead format
    lead = {
        'name': row['Contractor Name'],
        'company_name': row['Contractor Name'],
        'website': f"https://{row['Domain']}" if row['Domain'] and not row['Domain'].startswith('http') else row['Domain'],
        'phone': row['Phone'],
        'company_size': '50-100',
        'industry': 'HVAC Services',
        'contact_name': 'Unknown',
        'contact_title': 'Owner',
        'state': row['State'],
        'city': row['City'],
        'icp_tier': row['ICP Tier'],
        'oem_sources': row['OEM Sources'],
    }

    print(f"\nLead: {lead['name']}")
    print(f"Website: {lead['website']}")
    print(f"Location: {lead['city']}, {lead['state']}")
    print(f"ICP Tier: {lead['icp_tier']}")

    # Initialize orchestrator
    orchestrator = PipelineOrchestrator(db=None)

    # Run pipeline with create_in_crm=TRUE (real creation)
    print("\n" + "-"*80)
    print("Running Pipeline with create_in_crm=TRUE...")
    print("-"*80)

    request = PipelineTestRequest(
        lead=lead,
        options=PipelineTestOptions(
            skip_enrichment=False,  # Run enrichment (Hunter.io)
            create_in_crm=True,     # CREATE IN CLOSE CRM
            stop_on_duplicate=False,
            dry_run=False           # NOT a dry run - REAL creation
        )
    )

    result = await orchestrator.execute(request)

    # Print results
    print(f"\n{'='*80}")
    print("PIPELINE RESULT")
    print(f"{'='*80}")
    print(f"Success: {result.success}")
    print(f"Total Latency: {result.total_latency_ms}ms ({result.total_latency_ms/1000:.1f}s)")
    print(f"Total Cost: ${result.total_cost_usd:.6f}")

    # Stage details
    for stage_name, stage_result in result.stages.items():
        print(f"\n[{stage_name.upper()}]")
        print(f"  Status: {stage_result.status}")
        print(f"  Latency: {stage_result.latency_ms}ms")

        if stage_result.output:
            output = stage_result.output

            if stage_name == 'qualification':
                print(f"  Qualification Score: {output.get('qualification_score', 'N/A')}")
                print(f"  Tier: {output.get('tier', 'N/A')}")
                print(f"  Is ATL: {output.get('is_atl', False)}")
                if output.get('disqualified_reason'):
                    print(f"  ⚠️  Disqualified: {output.get('disqualified_reason')}")

            elif stage_name == 'enrichment' and isinstance(output, dict):
                contacts = output.get('contacts', [])
                print(f"  Contacts Found: {len(contacts)}")
                if contacts:
                    for i, contact in enumerate(contacts[:5], 1):
                        print(f"    {i}. {contact.get('name')} ({contact.get('title')})")
                        print(f"       Email: {contact.get('email')}")
                        print(f"       ATL: {contact.get('is_atl', False)}")

            elif stage_name == 'close_crm':
                print(f"  ✅ Lead ID: {output.get('lead_id', 'N/A')}")
                print(f"  ✅ Status: {output.get('status', 'N/A')}")
                print(f"  ✅ Contacts Created: {output.get('contacts_created', 'N/A')}")
                if output.get('lead_id'):
                    print(f"\n  🔗 Close CRM URL: https://app.close.com/lead/{output['lead_id']}/")

    if not result.success:
        print(f"\n❌ ERROR: {result.error_message}")

    print("\n" + "="*80)
    print("IMPORT COMPLETE")
    print("="*80)

    if result.success and result.stages.get('close_crm') and result.stages['close_crm'].output:
        lead_id = result.stages['close_crm'].output.get('lead_id')
        if lead_id:
            print("\n✅ SUCCESS! Lead created in Close CRM")
            print(f"\nNext Steps:")
            print(f"1. Open Close CRM: https://app.close.com/lead/{lead_id}/")
            print(f"2. Verify Status = 'Raw' (NOT a custom status)")
            print(f"3. Check custom fields:")
            print(f"   - is_atl (boolean)")
            print(f"   - qualification_score (number)")
            print(f"   - priority_label (text)")
            print(f"4. Check description contains priority label")
            print(f"5. Verify lead appears in appropriate smart view")
        else:
            print("\n⚠️  Lead was not created (likely skipped due to no contacts)")
    else:
        print("\n⚠️  Pipeline did not complete successfully")

    print()


if __name__ == '__main__':
    asyncio.run(import_single_lead())
