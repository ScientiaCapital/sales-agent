"""
Celery tasks for IntakeCommanderAgent.

Runs every 60 seconds to process incoming leads from Deep Hunter,
apply quality filters, calculate Trifecta scores, and route to BDR queue.

Schedule: Every 60 seconds (continuous intake processing)
"""

from celery import shared_task
from app.core.logging import setup_logging
from app.services.langgraph.agents.elite_team import (
    IntakeCommanderAgent,
    IntakeResult,
)

logger = setup_logging(__name__)


@shared_task(
    name="intake_commander.process_intake",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def process_intake_cycle(self):
    """
    Process incoming leads through Intake Commander.

    This task:
    1. Loads leads from Supabase intake queue
    2. Checks for duplicates in Close CRM + Supabase
    3. Applies 3-layer garbage contact filtering
    4. Calculates Trifecta scores
    5. Routes leads based on score (UNICORN→BDR, etc.)

    Runs every 60 seconds via Celery Beat.

    Returns:
        dict: Processing summary with counts
    """
    try:
        logger.info("Starting Intake Commander cycle...")

        # Initialize agent
        agent = IntakeCommanderAgent(provider="cerebras")

        # Run processing (async, so we need to handle event loop)
        import asyncio
        loop = asyncio.get_event_loop()
        result: IntakeResult = loop.run_until_complete(agent.process_intake())

        # Log results
        logger.info(
            f"Intake cycle complete: {result.total_processed} processed, "
            f"{result.unicorns_found} unicorns, {result.routed_to_bdr} to BDR, "
            f"{result.duration_ms}ms"
        )

        # Return summary for monitoring
        return {
            "status": "success",
            "total_processed": result.total_processed,
            "new_leads": result.new_leads,
            "duplicates_blocked": result.duplicates_blocked,
            "garbage_contacts_filtered": result.garbage_contacts_filtered,
            "routed_to_bdr": result.routed_to_bdr,
            "routed_to_enrichment": result.routed_to_enrichment,
            "routed_to_nurture": result.routed_to_nurture,
            "unicorns_found": result.unicorns_found,
            "duration_ms": result.duration_ms,
            "errors": result.errors
        }

    except Exception as e:
        logger.error(f"Intake Commander cycle failed: {e}", exc_info=True)

        # Retry with exponential backoff
        raise self.retry(exc=e)


@shared_task(name="intake_commander.process_file")
def process_intake_file(file_path: str):
    """
    Process a specific intake file (CSV or JSON).

    Useful for manual imports or batch processing.

    Args:
        file_path: Path to CSV or JSON file with leads

    Returns:
        dict: Processing summary
    """
    try:
        logger.info(f"Processing intake file: {file_path}")

        # Initialize agent with file path
        agent = IntakeCommanderAgent(
            provider="cerebras",
            intake_path=file_path
        )

        # Run processing
        import asyncio
        loop = asyncio.get_event_loop()
        result: IntakeResult = loop.run_until_complete(agent.process_intake())

        logger.info(f"File processing complete: {result.total_processed} leads")

        return {
            "status": "success",
            "file_path": file_path,
            "total_processed": result.total_processed,
            "unicorns_found": result.unicorns_found,
            "duration_ms": result.duration_ms,
            "errors": result.errors
        }

    except Exception as e:
        logger.error(f"File processing failed: {e}", exc_info=True)
        return {
            "status": "error",
            "file_path": file_path,
            "error": str(e)
        }


@shared_task(name="intake_commander.calculate_trifecta_score")
def calculate_company_trifecta_score(company_data: dict):
    """
    Calculate Trifecta score for a single company.

    Useful for on-demand scoring or API endpoints.

    Args:
        company_data: Company data dict with OEMs, trades, contacts, etc.

    Returns:
        dict: TrifectaScore as dict
    """
    from app.services.langgraph.agents.elite_team import calculate_trifecta_score

    try:
        score = calculate_trifecta_score(company_data)
        return score.model_dump()
    except Exception as e:
        logger.error(f"Trifecta scoring failed: {e}")
        return {"error": str(e)}
