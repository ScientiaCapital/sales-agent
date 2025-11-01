"""
Test Pipeline with 10 Sample Contractor Leads

Tests full pipeline with real contractor data:
- Website validation (ICP qualifier)
- Qualification scoring
- Review scraping (Google, Yelp, BBB, Facebook)
- Reputation scoring
"""
import asyncio
import sys
import csv
import os
from typing import List, Dict, Any
from pathlib import Path

sys.path.insert(0, '/Users/tmkipper/Desktop/tk_projects/sales-agent/.worktrees/pipeline-testing/backend')

from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.schemas.pipeline import PipelineTestRequest, PipelineTestOptions


CSV_PATH = "/Users/tmkipper/Desktop/tk_projects/gtm-engineer-journey/projects/dealer-scraper-mvp/output/gtm/executive_package_20251025/TOP_200_CONTRACTORS_with_overlap.csv"


def load_sample_leads(csv_path: str, sample_size: int = 10) -> List[Dict[str, Any]]:
    """Load sample leads from CSV"""
    leads = []

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= sample_size:
                break

            # Map CSV columns to pipeline lead format
            lead = {
                'name': row['Contractor Name'],
                'company_name': row['Contractor Name'],
                'website': f"https://{row['Domain']}" if row['Domain'] and not row['Domain'].startswith('http') else row['Domain'],
                'phone': row['Phone'],
                'company_size': '50-100',  # Default estimate
                'industry': 'Commercial HVAC/Electrical',
                'contact_name': 'Unknown',
                'contact_title': 'Owner',
                'state': row['State'],
                'city': row['City'],
                'icp_tier': row['ICP Tier'],
                'oem_sources': row['OEM Sources'],
            }
            leads.append(lead)

    return leads


async def test_single_lead(orchestrator: PipelineOrchestrator, lead: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Test pipeline on a single lead"""
    print(f"\n{'='*80}")
    print(f"TESTING LEAD {index + 1}: {lead['name']}")
    print(f"{'='*80}")
    print(f"Website: {lead['website']}")
    print(f"ICP Tier: {lead['icp_tier']}")
    print(f"OEM: {lead['oem_sources']}")

    request = PipelineTestRequest(
        lead=lead,
        options=PipelineTestOptions(
            skip_enrichment=False,
            create_in_crm=False,
            stop_on_duplicate=False,
            dry_run=True
        )
    )

    result = await orchestrator.execute(request)

    # Print results
    print(f"\n--- PIPELINE RESULT ---")
    print(f"Success: {result.success}")
    print(f"Total Latency: {result.total_latency_ms}ms ({result.total_latency_ms/1000:.1f}s)")
    print(f"Total Cost: ${result.total_cost_usd:.6f}")

    # Stage-by-stage breakdown
    for stage_name, stage_result in result.stages.items():
        print(f"\n  [{stage_name.upper()}]")
        print(f"    Status: {stage_result.status}")
        print(f"    Latency: {stage_result.latency_ms}ms")
        print(f"    Cost: ${stage_result.cost_usd:.6f}")

        if stage_result.output:
            output = stage_result.output

            if stage_name == 'qualification':
                print(f"    Qualification Score: {output.get('qualification_score', 'N/A')}")
                print(f"    Tier: {output.get('tier', 'N/A')}")
                if output.get('disqualified_reason'):
                    print(f"    ⚠️  Disqualified: {output.get('disqualified_reason')}")
                    print(f"    Website Error: {output.get('website_error', 'N/A')}")

            elif stage_name == 'enrichment' and isinstance(output, dict):
                print(f"    Company: {output.get('company', 'N/A')}")

                # Review data
                reputation_score = output.get('reputation_score')
                if reputation_score is not None:
                    print(f"\n    🌟 REPUTATION DATA:")
                    print(f"       Overall Score: {reputation_score}/100")
                    print(f"       Average Rating: {output.get('average_rating', 'N/A')}/5.0")
                    print(f"       Total Reviews: {output.get('total_reviews', 0)}")
                    print(f"       Data Quality: {output.get('review_data_quality', 'N/A')}")
                    print(f"       Negative Signals: {output.get('has_negative_signals', False)}")

                    # Platform breakdown
                    platform_reviews = output.get('platform_reviews', [])
                    if platform_reviews:
                        print(f"\n       Platform Breakdown:")
                        for pr in platform_reviews:
                            status_emoji = '✅' if pr['status'] == 'success' else '❌'
                            print(f"         {status_emoji} {pr['platform'].upper()}: "
                                  f"rating={pr.get('rating', 'N/A')}, "
                                  f"reviews={pr.get('review_count', 'N/A')}, "
                                  f"status={pr['status']}")
                else:
                    print(f"    ⚠️  No review data collected")

    if not result.success:
        print(f"\n❌ ERROR: {result.error_message}")
        print(f"Failed at stage: {result.error_stage}")

    # Return summary for aggregation
    return {
        'lead_name': lead['name'],
        'success': result.success,
        'qualification_score': result.stages['qualification'].output.get('qualification_score') if result.stages.get('qualification') and result.stages['qualification'].output else None,
        'reputation_score': result.stages['enrichment'].output.get('reputation_score') if result.stages.get('enrichment') and result.stages['enrichment'].output else None,
        'total_latency_ms': result.total_latency_ms,
        'total_cost_usd': result.total_cost_usd,
        'website_valid': result.stages['qualification'].output.get('disqualified_reason') != 'website_not_accessible' if result.stages.get('qualification') and result.stages['qualification'].output else True,
    }


async def test_sample_leads():
    """Test pipeline with sample leads"""
    print("\n" + "="*80)
    print("PIPELINE SAMPLE TEST - 10 CONTRACTOR LEADS")
    print("="*80)

    # Load sample leads
    print(f"\nLoading sample leads from: {CSV_PATH}")
    leads = load_sample_leads(CSV_PATH, sample_size=10)
    print(f"✅ Loaded {len(leads)} sample leads")

    # Initialize orchestrator
    orchestrator = PipelineOrchestrator(db=None)

    # Test each lead
    results = []
    for i, lead in enumerate(leads):
        try:
            result = await test_single_lead(orchestrator, lead, i)
            results.append(result)
        except Exception as e:
            print(f"\n❌ ERROR testing {lead['name']}: {e}")
            results.append({
                'lead_name': lead['name'],
                'success': False,
                'error': str(e)
            })

    # Aggregate statistics
    print(f"\n\n{'='*80}")
    print("AGGREGATE STATISTICS")
    print(f"{'='*80}")

    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    print(f"\nSuccess Rate: {len(successful)}/{len(results)} ({len(successful)/len(results)*100:.1f}%)")
    print(f"Failed: {len(failed)}")

    if successful:
        avg_latency = sum(r['total_latency_ms'] for r in successful) / len(successful)
        total_cost = sum(r['total_cost_usd'] for r in successful)

        print(f"\nPerformance:")
        print(f"  Average Latency: {avg_latency:.0f}ms ({avg_latency/1000:.1f}s)")
        print(f"  Total Cost: ${total_cost:.6f}")
        print(f"  Cost per Lead: ${total_cost/len(successful):.6f}")

        # Qualification scores
        qual_scores = [r['qualification_score'] for r in successful if r['qualification_score'] is not None]
        if qual_scores:
            avg_qual = sum(qual_scores) / len(qual_scores)
            print(f"\nQualification Scores:")
            print(f"  Average: {avg_qual:.1f}")
            print(f"  Range: {min(qual_scores):.1f} - {max(qual_scores):.1f}")

        # Reputation scores
        rep_scores = [r['reputation_score'] for r in successful if r['reputation_score'] is not None]
        if rep_scores:
            avg_rep = sum(rep_scores) / len(rep_scores)
            print(f"\nReputation Scores:")
            print(f"  Average: {avg_rep:.1f}/100")
            print(f"  Range: {min(rep_scores):.1f} - {max(rep_scores):.1f}")
            print(f"  Leads with Reviews: {len(rep_scores)}/{len(successful)}")

        # Website validation
        websites_valid = [r for r in successful if r.get('website_valid')]
        print(f"\nWebsite Validation:")
        print(f"  Valid Websites: {len(websites_valid)}/{len(successful)}")

    if failed:
        print(f"\n❌ Failed Leads:")
        for r in failed:
            print(f"  - {r['lead_name']}: {r.get('error', 'Unknown error')}")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    asyncio.run(test_sample_leads())
