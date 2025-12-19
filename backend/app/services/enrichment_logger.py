"""
Enrichment Logger Service - Logs enrichment events to Supabase fact tables.

Provides:
- Enrichment attempt logging to fact_enrichments
- Stage transition logging to fact_pipeline_stages
- Cost and performance tracking
- Success/failure tracking

ENRICHMENT STATUS VALUES (dim_companies.enrichment_status):
- 'pending': Needs enrichment
- 'free_enriched': After free enrichment (Hunter.io free, BeautifulSoup)
- 'paid_enriched': After paid enrichment (Apollo, Browserbase, LinkedIn)
- 'enriched': Full enrichment complete
- 'failed': Enrichment failed
- 'found_page_no_contacts': Page found but no contacts extracted

Usage:
    from app.services.enrichment_logger import EnrichmentLogger

    logger = EnrichmentLogger(supabase_client)

    # Log enrichment attempt
    await logger.log_enrichment_attempt(
        company_id="uuid",
        method="hunter",
        success=True,
        contacts_found=3,
        emails_found=2,
        cost_usd=0.05,
        latency_ms=1250
    )

    # Log stage transition
    await logger.log_stage_transition(
        company_id="uuid",
        from_stage="pending",
        to_stage="free_enriched"
    )
"""
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class EnrichmentLogger:
    """
    Service for logging enrichment events to Supabase fact tables.

    Writes to:
    - fact_enrichments: Enrichment attempts, costs, performance
    - fact_pipeline_stages: Stage transitions for funnel analysis
    """

    def __init__(self, supabase_client):
        """
        Initialize enrichment logger with Supabase client.

        Args:
            supabase_client: Supabase client instance from create_client()
        """
        self.supabase = supabase_client

    async def log_enrichment_attempt(
        self,
        company_id: str,
        method: str,
        success: bool = True,
        contacts_found: int = 0,
        atl_found: int = 0,
        emails_found: int = 0,
        cost_usd: float = 0.0,
        latency_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        source_id: Optional[str] = None
    ) -> dict:
        """
        Log an enrichment attempt to fact_enrichments table.

        Args:
            company_id: UUID of company being enriched
            method: Enrichment method ('hunter', 'apollo', 'browserbase', 'website_scrape', 'review_scrape')
            success: Whether enrichment succeeded
            contacts_found: Number of contacts discovered
            atl_found: Number of ATL (Above The Line) contacts found
            emails_found: Number of email addresses found
            cost_usd: Cost in USD for this enrichment
            latency_ms: Processing time in milliseconds
            error_message: Error message if failed
            source_id: Optional UUID reference to dim_sources

        Returns:
            Created fact_enrichments record
        """
        try:
            enrichment_data = {
                'enrichment_id': str(uuid4()),
                'company_id': company_id,
                'source_id': source_id,
                'method': method,
                'contacts_found': contacts_found,
                'atl_found': atl_found,
                'emails_found': emails_found,
                'cost_usd': cost_usd,
                'latency_ms': latency_ms,
                'success': success,
                'error_message': error_message,
                'enriched_at': datetime.utcnow().isoformat()
            }

            # Insert to Supabase
            result = self.supabase.table('fact_enrichments').insert(enrichment_data).execute()

            logger.debug(
                f"Enrichment logged: {method} for company {company_id} "
                f"({'success' if success else 'failed'}) - "
                f"{contacts_found} contacts, {emails_found} emails, ${cost_usd:.4f}"
            )

            return result.data[0] if result.data else enrichment_data

        except Exception as e:
            logger.error(f"Failed to log enrichment attempt: {e}")
            # Don't raise - logging failures shouldn't break enrichment
            return {}

    async def log_stage_transition(
        self,
        company_id: str,
        to_stage: str,
        from_stage: Optional[str] = None,
        changed_by: Optional[str] = None
    ) -> dict:
        """
        Log a pipeline stage transition to fact_pipeline_stages table.

        Args:
            company_id: UUID of company
            to_stage: New stage (e.g., 'discovery', 'enrichment', 'qualification', 'outreach')
            from_stage: Previous stage (None if first entry)
            changed_by: Optional UUID of user who triggered change

        Returns:
            Created fact_pipeline_stages record
        """
        try:
            stage_data = {
                'stage_change_id': str(uuid4()),
                'company_id': company_id,
                'changed_by': changed_by,
                'from_stage': from_stage,
                'to_stage': to_stage,
                'changed_at': datetime.utcnow().isoformat()
            }

            # Insert to Supabase
            result = self.supabase.table('fact_pipeline_stages').insert(stage_data).execute()

            logger.debug(
                f"Stage transition logged: company {company_id} "
                f"from '{from_stage or 'none'}' to '{to_stage}'"
            )

            return result.data[0] if result.data else stage_data

        except Exception as e:
            logger.error(f"Failed to log stage transition: {e}")
            # Don't raise - logging failures shouldn't break pipeline
            return {}

    async def log_batch_enrichment(
        self,
        enrichment_results: list[dict]
    ) -> int:
        """
        Log multiple enrichment attempts in a batch.

        Args:
            enrichment_results: List of enrichment result dicts with keys:
                - company_id, method, success, contacts_found, emails_found, cost_usd, latency_ms

        Returns:
            Number of records successfully logged
        """
        logged_count = 0

        for result in enrichment_results:
            await self.log_enrichment_attempt(
                company_id=result.get('company_id'),
                method=result.get('method'),
                success=result.get('success', True),
                contacts_found=result.get('contacts_found', 0),
                atl_found=result.get('atl_found', 0),
                emails_found=result.get('emails_found', 0),
                cost_usd=result.get('cost_usd', 0.0),
                latency_ms=result.get('latency_ms'),
                error_message=result.get('error_message'),
                source_id=result.get('source_id')
            )
            logged_count += 1

        logger.info(f"Batch enrichment logged: {logged_count} records")
        return logged_count

    async def get_company_enrichment_history(
        self,
        company_id: str,
        limit: int = 50
    ) -> list[dict]:
        """
        Get enrichment history for a company.

        Args:
            company_id: UUID of company
            limit: Max records to return

        Returns:
            List of enrichment records ordered by enriched_at DESC
        """
        try:
            result = self.supabase.table('fact_enrichments')\
                .select('*')\
                .eq('company_id', company_id)\
                .order('enriched_at', desc=True)\
                .limit(limit)\
                .execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Failed to get enrichment history: {e}")
            return []

    async def get_company_stage_history(
        self,
        company_id: str,
        limit: int = 50
    ) -> list[dict]:
        """
        Get stage transition history for a company.

        Args:
            company_id: UUID of company
            limit: Max records to return

        Returns:
            List of stage change records ordered by changed_at DESC
        """
        try:
            result = self.supabase.table('fact_pipeline_stages')\
                .select('*')\
                .eq('company_id', company_id)\
                .order('changed_at', desc=True)\
                .limit(limit)\
                .execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Failed to get stage history: {e}")
            return []

    async def get_enrichment_stats(
        self,
        method: Optional[str] = None,
        since_hours: int = 24
    ) -> dict:
        """
        Get enrichment statistics for monitoring and cost analysis.

        Args:
            method: Optional filter by enrichment method
            since_hours: Time window in hours (default 24)

        Returns:
            {
                "total_attempts": 150,
                "successful": 142,
                "failed": 8,
                "success_rate": 0.947,
                "total_contacts": 420,
                "total_emails": 380,
                "total_cost_usd": 7.50,
                "avg_latency_ms": 1250,
                "by_method": {"hunter": 80, "browserbase": 70}
            }
        """
        try:
            # Calculate time cutoff
            from datetime import timedelta
            cutoff = (datetime.utcnow() - timedelta(hours=since_hours)).isoformat()

            # Build query
            query = self.supabase.table('fact_enrichments')\
                .select('*')\
                .gte('enriched_at', cutoff)

            if method:
                query = query.eq('method', method)

            result = query.execute()
            records = result.data if result.data else []

            if not records:
                return {
                    "total_attempts": 0,
                    "successful": 0,
                    "failed": 0,
                    "success_rate": 0.0,
                    "total_contacts": 0,
                    "total_emails": 0,
                    "total_cost_usd": 0.0,
                    "avg_latency_ms": 0,
                    "by_method": {}
                }

            # Calculate stats
            total = len(records)
            successful = sum(1 for r in records if r.get('success'))
            failed = total - successful
            total_contacts = sum(r.get('contacts_found', 0) for r in records)
            total_emails = sum(r.get('emails_found', 0) for r in records)
            total_cost = sum(r.get('cost_usd', 0) for r in records)

            latencies = [r.get('latency_ms', 0) for r in records if r.get('latency_ms')]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0

            by_method = {}
            for r in records:
                m = r.get('method', 'unknown')
                by_method[m] = by_method.get(m, 0) + 1

            return {
                "total_attempts": total,
                "successful": successful,
                "failed": failed,
                "success_rate": successful / total if total > 0 else 0.0,
                "total_contacts": total_contacts,
                "total_emails": total_emails,
                "total_cost_usd": float(total_cost),
                "avg_latency_ms": int(avg_latency),
                "by_method": by_method
            }

        except Exception as e:
            logger.error(f"Failed to get enrichment stats: {e}")
            return {}


# Synchronous wrapper functions for use in run_enrichment.py
def log_enrichment_attempt(
    supabase_client,
    company_id: str,
    method: str,
    success: bool = True,
    contacts_found: int = 0,
    atl_found: int = 0,
    emails_found: int = 0,
    cost_usd: float = 0.0,
    latency_ms: Optional[int] = None,
    error_message: Optional[str] = None
) -> dict:
    """
    Synchronous helper to log enrichment attempt.

    For use in sync codebases like run_enrichment.py.

    Args:
        supabase_client: Supabase client instance
        company_id: UUID of company being enriched
        method: Enrichment method (e.g., 'browserbase_free', 'hunter_domain')
        success: Whether enrichment succeeded
        contacts_found: Total contacts discovered
        atl_found: ATL (Above The Line) contacts found
        emails_found: Email addresses found
        cost_usd: Cost in USD
        latency_ms: Processing time in ms
        error_message: Error message if failed
    """
    try:
        enrichment_data = {
            'enrichment_id': str(uuid4()),
            'company_id': company_id,
            'method': method,
            'contacts_found': contacts_found,
            'atl_found': atl_found,
            'emails_found': emails_found,
            'cost_usd': cost_usd,
            'latency_ms': latency_ms,
            'success': success,
            'error_message': error_message,
            'enriched_at': datetime.utcnow().isoformat()
        }

        result = supabase_client.table('fact_enrichments').insert(enrichment_data).execute()

        logger.debug(
            f"Enrichment logged: {method} for company {company_id} - "
            f"{contacts_found} contacts, {emails_found} emails"
        )

        return result.data[0] if result.data else enrichment_data

    except Exception as e:
        logger.error(f"Failed to log enrichment: {e}")
        return {}


def log_stage_transition(
    supabase_client,
    company_id: str,
    to_stage: str,
    from_stage: Optional[str] = None
) -> dict:
    """
    Synchronous helper to log stage transition.

    For use in sync codebases like run_enrichment.py.
    """
    try:
        stage_data = {
            'stage_change_id': str(uuid4()),
            'company_id': company_id,
            'from_stage': from_stage,
            'to_stage': to_stage,
            'changed_at': datetime.utcnow().isoformat()
        }

        result = supabase_client.table('fact_pipeline_stages').insert(stage_data).execute()

        logger.debug(
            f"Stage transition: company {company_id} "
            f"from '{from_stage or 'none'}' to '{to_stage}'"
        )

        return result.data[0] if result.data else stage_data

    except Exception as e:
        logger.error(f"Failed to log stage transition: {e}")
        return {}
