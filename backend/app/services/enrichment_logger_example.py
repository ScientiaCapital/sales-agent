"""
Example Usage of EnrichmentLogger in run_enrichment.py

This shows how to integrate the EnrichmentLogger into the existing enrichment flow.
DO NOT run this file directly - it's a reference for integration patterns.
"""

# Example 1: Logging enrichment attempts in run_enrichment.py
# ============================================================

from app.services.enrichment_logger import log_enrichment_attempt, log_stage_transition

def example_enrichment_with_logging(supabase, company_id, domain):
    """
    Example of how to add logging to an enrichment operation.
    """
    import time
    start_time = time.time()

    # Log stage transition: company entering enrichment
    log_stage_transition(
        supabase_client=supabase,
        company_id=company_id,
        from_stage='discovery',
        to_stage='enrichment'
    )

    try:
        # Perform enrichment (example: Hunter.io)
        contacts_found = 0
        emails_found = 0
        cost_usd = 0.0

        # ... actual enrichment code here ...
        # contacts = hunter_search(domain)
        # contacts_found = len(contacts)
        # emails_found = sum(1 for c in contacts if c.get('email'))
        # cost_usd = 0.05  # Hunter cost per search

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Log successful enrichment
        log_enrichment_attempt(
            supabase_client=supabase,
            company_id=company_id,
            method='hunter',
            success=True,
            contacts_found=contacts_found,
            emails_found=emails_found,
            cost_usd=cost_usd,
            latency_ms=latency_ms
        )

        # Log stage transition: enrichment complete
        log_stage_transition(
            supabase_client=supabase,
            company_id=company_id,
            from_stage='enrichment',
            to_stage='qualification'
        )

        return {'success': True, 'contacts': contacts_found}

    except Exception as e:
        # Log failed enrichment
        latency_ms = int((time.time() - start_time) * 1000)
        log_enrichment_attempt(
            supabase_client=supabase,
            company_id=company_id,
            method='hunter',
            success=False,
            contacts_found=0,
            emails_found=0,
            cost_usd=0.0,
            latency_ms=latency_ms,
            error_message=str(e)
        )

        # Log stage transition: enrichment failed
        log_stage_transition(
            supabase_client=supabase,
            company_id=company_id,
            from_stage='enrichment',
            to_stage='failed'
        )

        return {'success': False, 'error': str(e)}


# Example 2: Browserbase scraping with logging
# =============================================

def example_browserbase_scraping_with_logging(supabase, company_id, domain):
    """
    Example of logging Browserbase scraping results.
    """
    import time
    start_time = time.time()

    try:
        # Perform Browserbase scraping
        # contacts = await scrape_with_browserbase(domain)
        contacts_found = 5
        emails_found = 3
        cost_usd = 0.015  # Browserbase session cost

        latency_ms = int((time.time() - start_time) * 1000)

        # Log the enrichment
        log_enrichment_attempt(
            supabase_client=supabase,
            company_id=company_id,
            method='browserbase',
            success=True,
            contacts_found=contacts_found,
            emails_found=emails_found,
            cost_usd=cost_usd,
            latency_ms=latency_ms
        )

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        log_enrichment_attempt(
            supabase_client=supabase,
            company_id=company_id,
            method='browserbase',
            success=False,
            cost_usd=0.015,  # Still charged even if failed
            latency_ms=latency_ms,
            error_message=str(e)
        )


# Example 3: Async usage in FastAPI endpoints
# ============================================

async def example_async_enrichment_logging():
    """
    Example of using the async EnrichmentLogger class in FastAPI.
    """
    from supabase import create_client
    from app.services.enrichment_logger import EnrichmentLogger
    import os

    # Initialize Supabase client
    supabase = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_SERVICE_KEY')
    )

    # Create logger
    logger = EnrichmentLogger(supabase)

    # Log enrichment
    await logger.log_enrichment_attempt(
        company_id='uuid-here',
        method='apollo',
        success=True,
        contacts_found=7,
        emails_found=5,
        cost_usd=0.10,
        latency_ms=2300
    )

    # Log stage transition
    await logger.log_stage_transition(
        company_id='uuid-here',
        from_stage='enrichment',
        to_stage='qualification'
    )

    # Get enrichment history
    history = await logger.get_company_enrichment_history(
        company_id='uuid-here',
        limit=10
    )

    # Get stats
    stats = await logger.get_enrichment_stats(
        method='hunter',
        since_hours=24
    )
    print(f"Hunter stats last 24h: {stats}")


# Example 4: Integration points in run_enrichment.py
# ===================================================

def integration_points_in_run_enrichment():
    """
    Key locations in run_enrichment.py where logging should be added.

    1. After get_unenriched_batch() - log stage transition to 'enrichment'
    2. After successful enrichment - log enrichment attempt with results
    3. After failed enrichment - log enrichment attempt with error
    4. After batch completion - log stage transitions to 'qualified' or 'failed'

    Specific functions to modify:
    - main() - after line 2089 (supabase = get_supabase())
    - sync_to_supabase() - around line 1825 (after successful sync)
    - Before/after enrichment loops
    """
    pass


# Example 5: Cost tracking over time
# ===================================

async def example_cost_analysis():
    """
    Example of using the logger to analyze enrichment costs.
    """
    from supabase import create_client
    from app.services.enrichment_logger import EnrichmentLogger
    import os

    supabase = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_SERVICE_KEY')
    )

    logger = EnrichmentLogger(supabase)

    # Get overall stats
    all_stats = await logger.get_enrichment_stats(since_hours=168)  # 7 days
    print(f"Total cost last week: ${all_stats['total_cost_usd']:.2f}")
    print(f"Success rate: {all_stats['success_rate']*100:.1f}%")
    print(f"Average latency: {all_stats['avg_latency_ms']}ms")

    # Get method-specific stats
    hunter_stats = await logger.get_enrichment_stats(method='hunter', since_hours=24)
    browserbase_stats = await logger.get_enrichment_stats(method='browserbase', since_hours=24)

    print(f"\nHunter: ${hunter_stats['total_cost_usd']:.2f} - {hunter_stats['total_contacts']} contacts")
    print(f"Browserbase: ${browserbase_stats['total_cost_usd']:.2f} - {browserbase_stats['total_contacts']} contacts")

    # Calculate cost per contact
    if all_stats['total_contacts'] > 0:
        cost_per_contact = all_stats['total_cost_usd'] / all_stats['total_contacts']
        print(f"\nCost per contact: ${cost_per_contact:.3f}")


if __name__ == '__main__':
    print("This is an example file. See docstrings for integration patterns.")
    print("\nKey integration points:")
    print("1. Import: from app.services.enrichment_logger import log_enrichment_attempt, log_stage_transition")
    print("2. After enrichment: log_enrichment_attempt(supabase, company_id, method, ...)")
    print("3. Stage changes: log_stage_transition(supabase, company_id, to_stage, from_stage)")
    print("\nSee function docstrings for detailed examples.")
