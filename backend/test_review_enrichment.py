"""
Test pipeline with review enrichment
"""
import asyncio
import sys
sys.path.insert(0, '/Users/tmkipper/Desktop/tk_projects/sales-agent/.worktrees/pipeline-testing/backend')

from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.schemas.pipeline import PipelineTestRequest, PipelineTestOptions


async def test_pipeline():
    # Test with A & A GENPRO INC.
    lead = {
        'name': 'A & A GENPRO INC.',
        'company_name': 'A & A GENPRO INC.',
        'website': 'https://www.aagenpro.com/',
        'company_size': '50-100',
        'industry': 'Construction',
        'contact_name': 'Unknown',
        'contact_title': 'Owner',
    }

    request = PipelineTestRequest(
        lead=lead,
        options=PipelineTestOptions(
            skip_enrichment=False,
            create_in_crm=False,
            stop_on_duplicate=False,
            dry_run=True
        )
    )

    orchestrator = PipelineOrchestrator(db=None)
    result = await orchestrator.execute(request)

    print('\n=== PIPELINE TEST RESULT ===')
    print(f'Success: {result.success}')
    print(f'Total Latency: {result.total_latency_ms}ms')
    print(f'Total Cost: ${result.total_cost_usd}')
    print(f'Lead: {result.lead_name}')
    print('\nStages:')
    for stage_name, stage_result in result.stages.items():
        print(f'  {stage_name}: {stage_result.status}')
        if stage_result.output and stage_name == 'enrichment':
            output = stage_result.output
            if isinstance(output, dict):
                print(f'    - Reputation Score: {output.get("reputation_score", "N/A")}')
                print(f'    - Average Rating: {output.get("average_rating", "N/A")}')
                print(f'    - Total Reviews: {output.get("total_reviews", "N/A")}')
                print(f'    - Review Quality: {output.get("review_data_quality", "N/A")}')
                platform_reviews = output.get("platform_reviews", [])
                if platform_reviews:
                    print(f'    - Platform Results:')
                    for pr in platform_reviews:
                        print(f'      * {pr["platform"]}: status={pr["status"]}, rating={pr.get("rating")}, reviews={pr.get("review_count")}')

    if not result.success:
        print(f'\nError: {result.error_message}')
        print(f'Failed at stage: {result.error_stage}')

    print('\n')


if __name__ == '__main__':
    asyncio.run(test_pipeline())
