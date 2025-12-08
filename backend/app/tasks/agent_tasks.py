"""
Celery tasks for multi-agent workflow execution

This module defines async tasks for agent-based lead processing, including:
- Individual agent execution (qualifier, enricher, researcher)
- Multi-agent workflow orchestration
- Batch lead processing
- Background enrichment tasks
"""
# LangSmith tracing is configured centrally in celery_app.py
# Do NOT override here - let the central config control tracing
import os
import logging

# Suppress LangSmith warning logs when tracing is disabled
logging.getLogger("langsmith.client").setLevel(logging.ERROR)
logging.getLogger("langsmith.utils").setLevel(logging.ERROR)

from typing import Dict, List, Any
from celery import group, chain
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.models import Lead, CerebrasAPICall, get_db
from app.services import CerebrasService
from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ============================================================================
# UTILITY TASKS
# ============================================================================

@celery_app.task(name="ping", bind=True)
def ping_task(self):
    """Simple ping task for testing Celery connectivity"""
    logger.info("Ping task executed successfully")
    return {"status": "pong", "task_id": self.request.id}


# ============================================================================
# LEAD PROCESSING TASKS
# ============================================================================

@celery_app.task(name="qualify_lead_async", bind=True, max_retries=3)
def qualify_lead_async(
    self,
    lead_id: int,
    company_name: str,
    company_website: str = None,
    company_size: str = None,
    industry: str = None,
    contact_name: str = None,
    contact_title: str = None,
    notes: str = None
):
    """
    Async task to qualify a lead using Cerebras AI
    
    This task:
    1. Calls CerebrasService for lead qualification
    2. Updates Lead record with score and reasoning
    3. Tracks API call metrics
    4. Handles retries with exponential backoff
    
    Args:
        lead_id: Database ID of the lead to qualify
        company_name: Company name
        company_website: Company website URL
        company_size: Company size category
        industry: Industry sector
        contact_name: Contact person name
        contact_title: Contact person job title
        notes: Additional context
        
    Returns:
        Dict with qualification results
    """
    try:
        logger.info(f"Starting async qualification for lead_id={lead_id}")
        
        # Initialize Cerebras service
        cerebras_service = CerebrasService()
        
        # Call qualification service
        score, reasoning, latency_ms = cerebras_service.qualify_lead(
            company_name=company_name,
            company_website=company_website,
            company_size=company_size,
            industry=industry,
            contact_name=contact_name,
            contact_title=contact_title,
            notes=notes
        )
        
        # Update database
        db: Session = next(get_db())
        try:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if lead:
                lead.qualification_score = score
                lead.qualification_reasoning = reasoning
                lead.qualification_model = cerebras_service.default_model
                lead.qualification_latency_ms = latency_ms
                lead.status = "qualified" if score >= 70 else "pending"
                
                # Track API call
                prompt_est = len(company_name) // 4
                completion_est = len(reasoning) // 4
                cost_info = cerebras_service.calculate_cost(prompt_est, completion_est)
                
                api_call = CerebrasAPICall(
                    endpoint="/chat/completions",
                    model=cerebras_service.default_model,
                    prompt_tokens=prompt_est,
                    completion_tokens=completion_est,
                    total_tokens=prompt_est + completion_est,
                    latency_ms=latency_ms,
                    cache_hit=False,
                    cost_usd=cost_info["total_cost_usd"],
                    operation_type="async_lead_qualification",
                    success=True
                )
                db.add(api_call)
                db.commit()
                
                logger.info(f"Lead {lead_id} qualified: score={score}, latency={latency_ms}ms")
                
                return {
                    "lead_id": lead_id,
                    "score": score,
                    "reasoning": reasoning,
                    "latency_ms": latency_ms,
                    "status": "qualified" if score >= 70 else "pending"
                }
            else:
                logger.error(f"Lead {lead_id} not found in database")
                return {"error": f"Lead {lead_id} not found"}
                
        finally:
            db.close()
            
    except SoftTimeLimitExceeded:
        logger.warning(f"Soft time limit exceeded for lead {lead_id}")
        raise
        
    except Exception as exc:
        # Exponential backoff retry
        logger.error(f"Error qualifying lead {lead_id}: {exc}")
        countdown = 2 ** self.request.retries  # 1s, 2s, 4s
        raise self.retry(exc=exc, countdown=countdown, max_retries=3)


# ============================================================================
# AGENT EXECUTION TASKS  
# ============================================================================

@celery_app.task(name="execute_agent", bind=True, max_retries=3)
def execute_agent_task(
    self,
    agent_type: str,
    lead_id: int,
    input_data: Dict[str, Any]
):
    """
    Execute individual agent as async Celery task
    
    This is a generic agent execution wrapper that routes to specific
    agent implementations based on agent_type.
    
    Args:
        agent_type: Type of agent (qualifier, enricher, researcher)
        lead_id: Lead database ID
        input_data: Agent-specific input parameters
        
    Returns:
        Dict with agent execution results
    """
    try:
        logger.info(f"Executing {agent_type} agent for lead_id={lead_id}")
        
        # Route to specific agent implementation
        if agent_type == "qualifier":
            return qualify_lead_async.apply_async(
                args=[lead_id],
                kwargs=input_data
            ).get()
            
        elif agent_type == "enricher":
            return enrich_lead_async.apply_async(
                args=[lead_id],
                kwargs=input_data
            ).get()
            
        elif agent_type == "researcher":
            # Placeholder for future research agent
            logger.info(f"Research agent not yet implemented for lead {lead_id}")
            return {"status": "not_implemented", "agent": "researcher"}
            
        else:
            logger.error(f"Unknown agent type: {agent_type}")
            return {"error": f"Unknown agent type: {agent_type}"}
            
    except Exception as exc:
        logger.error(f"Error executing {agent_type} agent: {exc}")
        countdown = 2 ** self.request.retries
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(name="enrich_lead_async", bind=True, max_retries=3)
def enrich_lead_async(
    self,
    lead_id: int,
    enrichment_data: Dict[str, Any] = None
):
    """
    Async task to enrich lead data with additional information
    
    This is a placeholder for future lead enrichment functionality
    (e.g., company data APIs, contact lookup services, etc.)
    
    Args:
        lead_id: Database ID of lead to enrich
        enrichment_data: Additional data to merge into lead record
        
    Returns:
        Dict with enrichment results
    """
    try:
        logger.info(f"Enriching lead_id={lead_id}")
        
        db: Session = next(get_db())
        try:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if lead:
                # Placeholder: Update lead with enrichment data
                if enrichment_data:
                    for key, value in enrichment_data.items():
                        if hasattr(lead, key):
                            setattr(lead, key, value)
                    db.commit()
                
                logger.info(f"Lead {lead_id} enriched successfully")
                return {
                    "lead_id": lead_id,
                    "status": "enriched",
                    "fields_updated": list(enrichment_data.keys()) if enrichment_data else []
                }
            else:
                logger.error(f"Lead {lead_id} not found")
                return {"error": f"Lead {lead_id} not found"}
                
        finally:
            db.close()
            
    except Exception as exc:
        logger.error(f"Error enriching lead {lead_id}: {exc}")
        countdown = 2 ** self.request.retries
        raise self.retry(exc=exc, countdown=countdown)


# ============================================================================
# AI REPORT GENERATION TASKS
# ============================================================================

@celery_app.task(name="generate_report_async", bind=True, max_retries=3)
def generate_report_async(
    self,
    lead_id: int,
    force_refresh: bool = False
):
    """
    Async task to generate AI-powered company research report
    
    This task orchestrates the 3-agent pipeline:
    1. SearchAgent - Company research (6 parallel searches)
    2. AnalysisAgent - Strategic insights and opportunities
    3. SynthesisAgent - Professional report generation
    
    Args:
        lead_id: Database ID of lead to generate report for
        force_refresh: Skip cache and force new research
        
    Returns:
        Dict with report generation results
    """
    try:
        logger.info(f"Starting async report generation for lead_id={lead_id}")
        
        # Import here to avoid circular dependencies
        from app.services.report_generator import ReportGenerator
        from app.models import Lead
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from app.core.config import settings
        import asyncio
        
        # Create async session
        engine = create_async_engine(settings.ASYNC_DATABASE_URL, echo=False)
        async_session_factory = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async def _generate():
            async with async_session_factory() as session:
                # Get lead
                lead = await session.get(Lead, lead_id)
                if not lead:
                    logger.error(f"Lead {lead_id} not found")
                    return {"error": f"Lead {lead_id} not found"}
                
                # Generate report
                report_gen = ReportGenerator()
                report = await report_gen.generate_report(lead, session, force_refresh=force_refresh)
                
                return {
                    "lead_id": lead_id,
                    "report_id": report.id,
                    "status": report.status,
                    "title": report.title,
                    "confidence_score": report.confidence_score,
                    "generation_time_ms": report.generation_time_ms,
                    "error_message": report.error_message
                }
        
        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_generate())
            logger.info(f"Report generated for lead {lead_id}: {result}")
            return result
        finally:
            loop.close()
            
    except SoftTimeLimitExceeded:
        logger.warning(f"Soft time limit exceeded for report generation (lead {lead_id})")
        raise
        
    except Exception as exc:
        logger.error(f"Error generating report for lead {lead_id}: {exc}")
        countdown = 2 ** self.request.retries  # Exponential backoff
        raise self.retry(exc=exc, countdown=countdown, max_retries=3)


@celery_app.task(name="batch_generate_reports", bind=True)
def batch_generate_reports_task(self, lead_ids: List[int], force_refresh: bool = False):
    """
    Generate reports for multiple leads in parallel
    
    Uses Celery group to execute report generation for multiple leads concurrently.
    
    Args:
        lead_ids: List of lead database IDs
        force_refresh: Skip cache for all reports
        
    Returns:
        Dict with batch generation results
    """
    try:
        logger.info(f"Batch generating reports for {len(lead_ids)} leads")
        
        # Create group of report generation tasks
        job = group([
            generate_report_async.s(lead_id, force_refresh)
            for lead_id in lead_ids
        ])
        
        # Execute in parallel
        results = job.apply_async().get()
        
        return {
            "batch_size": len(lead_ids),
            "results": results,
            "force_refresh": force_refresh
        }
        
    except Exception as exc:
        logger.error(f"Error in batch report generation: {exc}")
        raise


# ============================================================================
# CRM SYNC TASKS (Placeholder for Task 5)
# ============================================================================

@celery_app.task(name="sync_crm_contacts", bind=True, max_retries=3)
def sync_crm_contacts_task(
    self,
    crm_platform: str,
    operation: str = "import",
    filters: Dict[str, Any] = None
):
    """
    Sync contacts with CRM platform (Close, Apollo, LinkedIn)

    Task 5.5: Full implementation with CRMSyncService.
    Handles:
    - Close CRM: Full bidirectional sync (create, update, delete)
    - Apollo: One-way enrichment (import only)
    - LinkedIn: Profile scraping enrichment (import only)

    Args:
        crm_platform: Platform to sync with (close, apollo, linkedin)
        operation: Sync direction (import, export, bidirectional)
        filters: Optional platform-specific filters
            - Close: query, created_date_gte, updated_date_gte
            - Apollo: emails (required list)
            - LinkedIn: profile_urls (required list)

    Returns:
        Dict with sync results
    """
    try:
        logger.info(f"Starting CRM sync: platform={crm_platform}, operation={operation}")

        # Initialize database session
        db: Session = next(get_db())

        try:
            # Import asyncio for running async function
            import asyncio
            from app.services.crm_sync_service import CRMSyncService

            # Get Redis client if available
            redis_client = None
            try:
                from redis import Redis
                import os
                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                redis_client = Redis.from_url(redis_url)
                redis_client.ping()  # Test connection
            except Exception as e:
                logger.warning(f"Redis not available for CRM sync: {e}")

            # Initialize sync service
            sync_service = CRMSyncService(
                db=db,
                redis_client=redis_client
            )

            # Run async sync operation
            result = asyncio.run(
                sync_service.sync_platform(
                    platform=crm_platform,
                    direction=operation,
                    filters=filters
                )
            )

            # Convert SyncResult to dict for Celery serialization
            result_dict = {
                "status": "success",
                "platform": result.platform,
                "operation": result.operation,
                "contacts_processed": result.contacts_processed,
                "contacts_created": result.contacts_created,
                "contacts_updated": result.contacts_updated,
                "contacts_failed": result.contacts_failed,
                "errors": result.errors,
                "started_at": result.started_at.isoformat() if result.started_at else None,
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "duration_seconds": result.duration_seconds
            }

            logger.info(
                f"CRM sync completed: {result.platform} - "
                f"{result.contacts_created} created, {result.contacts_updated} updated, "
                f"{result.contacts_failed} failed"
            )

            return result_dict

        finally:
            db.close()

    except Exception as exc:
        logger.error(f"Error in CRM sync ({crm_platform}): {exc}", exc_info=True)
        countdown = 2 ** self.request.retries
        raise self.retry(exc=exc, countdown=countdown)


# ============================================================================
# WORKFLOW ORCHESTRATION TASKS
# ============================================================================

@celery_app.task(name="execute_workflow", bind=True)
def execute_workflow_task(self, workflow_id: str, lead_id: int, workflow_config: Dict = None):
    """
    Execute complete multi-agent workflow
    
    Orchestrates multiple agents in sequence or parallel using Celery canvas.
    
    Workflow types:
    - "qualify": Single qualification agent
    - "full_process": Qualifier → Enricher → Researcher (sequence)
    - "parallel_process": Qualifier + Enricher + Researcher (parallel)
    
    Args:
        workflow_id: Workflow identifier (qualify, full_process, parallel_process)
        lead_id: Lead database ID
        workflow_config: Optional workflow configuration
        
    Returns:
        Dict with workflow execution results
    """
    try:
        logger.info(f"Starting workflow {workflow_id} for lead_id={lead_id}")
        
        if workflow_id == "qualify":
            # Simple single-agent workflow
            result = execute_agent_task.apply_async(
                args=["qualifier", lead_id, workflow_config or {}]
            ).get()
            return {"workflow": workflow_id, "lead_id": lead_id, "result": result}
            
        elif workflow_id == "parallel_process":
            # Parallel execution with group
            job = group([
                execute_agent_task.s("qualifier", lead_id, {}),
                execute_agent_task.s("enricher", lead_id, {}),
            ])
            results = job.apply_async().get()
            return {"workflow": workflow_id, "lead_id": lead_id, "results": results}
            
        elif workflow_id == "full_process":
            # Sequential execution with chain
            job = chain(
                execute_agent_task.s("qualifier", lead_id, {}),
                execute_agent_task.s("enricher", lead_id, {}),
            )
            result = job.apply_async().get()
            return {"workflow": workflow_id, "lead_id": lead_id, "result": result}
            
        else:
            logger.error(f"Unknown workflow: {workflow_id}")
            return {"error": f"Unknown workflow: {workflow_id}"}
            
    except Exception as exc:
        logger.error(f"Error executing workflow {workflow_id}: {exc}")
        raise


@celery_app.task(name="batch_process_leads", bind=True)
def batch_process_leads_task(self, lead_ids: List[int], workflow_id: str = "qualify"):
    """
    Process multiple leads in parallel

    Uses Celery group to execute workflows for multiple leads concurrently.

    Args:
        lead_ids: List of lead database IDs
        workflow_id: Workflow to execute for each lead

    Returns:
        Dict with batch processing results
    """
    try:
        logger.info(f"Batch processing {len(lead_ids)} leads with workflow {workflow_id}")

        # Create group of workflow tasks
        job = group([
            execute_workflow_task.s(workflow_id, lead_id)
            for lead_id in lead_ids
        ])

        # Execute in parallel
        results = job.apply_async().get()

        return {
            "batch_size": len(lead_ids),
            "workflow": workflow_id,
            "results": results
        }

    except Exception as exc:
        logger.error(f"Error in batch processing: {exc}")
        raise


# ============================================================================
# LEAD SCOUT TASKS (Autonomous Discovery)
# ============================================================================

@celery_app.task(name="run_lead_scout", bind=True, max_retries=2, soft_time_limit=600)
def run_lead_scout_task(
    self,
    limit: int = 10,
    require_domain: bool = True,
    icp_tier: str = None
):
    """
    Autonomous lead discovery task (runs via Celery Beat every 30 minutes)

    This task:
    1. Queries Supabase for unenriched companies
    2. Scrapes websites for signals (brands, certifications, contacts)
    3. Scores with QualificationAgent
    4. Generates "WHY call" recommendations
    5. Saves back to Supabase

    Designed for Tim's calling list - prioritizes HOT leads with reasoning.

    Args:
        limit: Number of leads to scout per run (default: 10)
        require_domain: Only scout companies with domains (default: True)
        icp_tier: Filter by ICP tier (PLATINUM, GOLD, SILVER, BRONZE)

    Returns:
        Dict with scout results and stats
    """
    try:
        logger.info(f"Starting Lead Scout task: limit={limit}, require_domain={require_domain}")

        # Import and run async scout
        import asyncio
        from app.services.langgraph.agents.lead_scout_agent import LeadScoutAgent

        async def _scout():
            scout = LeadScoutAgent(provider='cerebras')
            return await scout.scout(
                limit=limit,
                require_domain=require_domain,
                icp_tier=icp_tier
            )

        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_scout())
        finally:
            loop.close()

        # Convert result to serializable dict
        result_dict = {
            "status": "success",
            "total_scouted": result.total_scouted,
            "hot_leads": result.hot_leads,
            "warm_leads": result.warm_leads,
            "cold_leads": result.cold_leads,
            "errors": result.errors,
            "duration_ms": result.duration_ms,
            "results": [
                {
                    "company_id": r.company_id,
                    "company_name": r.company_name,
                    "domain": r.domain,
                    "icp_score": r.icp_score,
                    "priority": r.priority,
                    "why_call": r.why_call[:200],  # Truncate for log readability
                    "scouted_at": r.scouted_at
                }
                for r in result.results
            ]
        }

        logger.info(
            f"Lead Scout completed: {result.total_scouted} scouted, "
            f"{result.hot_leads} HOT, {result.warm_leads} WARM, {result.cold_leads} COLD, "
            f"{len(result.errors)} errors in {result.duration_ms}ms"
        )

        return result_dict

    except SoftTimeLimitExceeded:
        logger.warning("Lead Scout soft time limit exceeded (10 minutes)")
        raise

    except Exception as exc:
        logger.error(f"Error in Lead Scout task: {exc}", exc_info=True)
        countdown = 60 * (2 ** self.request.retries)  # 1 min, 2 min backoff
        raise self.retry(exc=exc, countdown=countdown)


# ============================================================================
# MORNING REPORT TASKS (Daily Summary with Outreach Drafts)
# ============================================================================

@celery_app.task(name="generate_morning_report", bind=True, max_retries=2, soft_time_limit=900)
def generate_morning_report_task(
    self,
    hours_back: int = 24,
    top_n: int = 10,
    save_to_file: bool = True
):
    """
    Generate morning report summarizing overnight lead scouting (runs at 9 AM EST / 14:00 UTC)

    This task:
    1. Queries leads scouted in the last N hours
    2. Generates summary with HOT/WARM/COLD counts
    3. Creates personalized outreach drafts for top leads:
       - Email draft (150-200 words)
       - SMS draft (under 160 chars)
       - Call opener (2-3 sentences)
    4. Optionally saves report to markdown file

    Args:
        hours_back: Hours to look back for scouted leads (default: 24)
        top_n: Number of top leads to include with outreach drafts (default: 10)
        save_to_file: Save report to data/reports/ (default: True)

    Returns:
        Dict with report summary and file path
    """
    try:
        logger.info(f"Starting Morning Report: hours_back={hours_back}, top_n={top_n}")

        # Import and run async report generation
        import asyncio
        from app.services.langgraph.agents.morning_report_agent import MorningReportAgent

        async def _generate():
            agent = MorningReportAgent(provider='cerebras')
            report = await agent.generate_report(
                hours_back=hours_back,
                top_n=top_n
            )

            file_path = None
            if save_to_file:
                file_path = await agent.save_report_to_file(report)

            return report, file_path

        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report, file_path = loop.run_until_complete(_generate())
        finally:
            loop.close()

        # Convert result to serializable dict
        result_dict = {
            "status": "success",
            "generated_at": report.generated_at,
            "report_date": report.report_date,
            "total_scouted": report.total_scouted,
            "hot_leads": report.hot_leads,
            "warm_leads": report.warm_leads,
            "cold_leads": report.cold_leads,
            "top_leads_count": len(report.top_leads),
            "signals_summary": report.signals_summary,
            "summary_preview": report.summary[:500] if report.summary else None,
            "file_path": file_path
        }

        logger.info(
            f"Morning Report generated: {report.total_scouted} leads, "
            f"{report.hot_leads} HOT, {report.warm_leads} WARM, {report.cold_leads} COLD, "
            f"{len(report.top_leads)} with outreach drafts"
        )

        return result_dict

    except SoftTimeLimitExceeded:
        logger.warning("Morning Report soft time limit exceeded (15 minutes)")
        raise

    except Exception as exc:
        logger.error(f"Error in Morning Report task: {exc}", exc_info=True)
        countdown = 120 * (2 ** self.request.retries)  # 2 min, 4 min backoff
        raise self.retry(exc=exc, countdown=countdown)


# ============================================================================
# SALES INTEL TASKS (Personal Hook Extraction)
# ============================================================================

@celery_app.task(name="run_sales_intel_batch", bind=True, max_retries=2, soft_time_limit=600)
def run_sales_intel_batch_task(self, limit: int = 10):
    """
    Run SalesIntelAgent on leads that have been scouted but lack personal hooks.

    This task:
    1. Queries leads with ai_company_story but no ai_personal_hooks
    2. For each lead, extracts personal hooks (hobbies, family, pets)
    3. Generates personalized email/SMS/voice openers
    4. Saves results back to Supabase

    Args:
        limit: Number of leads to process per run (default: 10)

    Returns:
        Dict with processed count and results
    """
    try:
        logger.info(f"Starting Sales Intel batch: limit={limit}")

        import asyncio
        from app.services.langgraph.agents.sales_intel_agent import SalesIntelAgent
        from app.services.langgraph.tools.supabase_tools import (
            query_leads_for_sales_intel,
            save_sales_intel,
            get_lead_details
        )

        # Query leads needing personal hook extraction
        leads = query_leads_for_sales_intel(limit=limit)

        if not leads:
            logger.info("No leads found for sales intel analysis")
            return {"status": "no_leads", "processed": 0}

        results = []
        errors = []

        async def process_lead(lead):
            """Process a single lead with SalesIntelAgent."""
            agent = SalesIntelAgent()

            # Get full lead details including contacts
            lead_details = get_lead_details.invoke({
                'company_id': lead['company_id'],
                'include_contacts': True
            })

            # Find best contact
            contacts = lead_details.get('contacts', [])
            best_contact = None
            for contact in contacts:
                if contact.get('contact_type') == 'ATL':
                    best_contact = contact
                    break
            if not best_contact and contacts:
                best_contact = contacts[0]

            contact_name = best_contact.get('name', 'Owner') if best_contact else 'Owner'
            contact_title = best_contact.get('title', 'Owner') if best_contact else 'Owner'

            # Run analysis
            result = await agent.analyze(
                company_name=lead['company_name'],
                contact_name=contact_name,
                contact_title=contact_title,
                scraped_content=lead.get('ai_company_story', ''),
                services=lead.get('service_areas', '').split(',') if lead.get('service_areas') else None,
                brands=lead.get('oem_brands', '').split(',') if lead.get('oem_brands') else None,
                location=f"{lead.get('city', '')}, {lead.get('state', '')}"
            )

            # Save to Supabase
            save_sales_intel.invoke({
                'company_id': lead['company_id'],
                'personal_hooks': [
                    {"category": h.category, "detail": h.detail, "opener": h.conversation_opener}
                    for h in result.personal_hooks
                ],
                'company_story': result.company_story,
                'pain_points': result.pain_points,
                'email_draft': result.email_body,
                'sms_draft': result.sms_draft,
                'voice_opener': result.voice_opener
            })

            return {
                "company_id": lead['company_id'],
                "company_name": lead['company_name'],
                "hooks_found": len(result.personal_hooks),
                "confidence": result.confidence,
                "processing_time_ms": result.processing_time_ms
            }

        # Process each lead
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            for lead in leads:
                try:
                    result = loop.run_until_complete(process_lead(lead))
                    results.append(result)
                except Exception as e:
                    error_msg = f"Failed to process {lead['company_name']}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
        finally:
            loop.close()

        logger.info(
            f"Sales Intel batch completed: {len(results)} processed, "
            f"{len(errors)} errors"
        )

        return {
            "status": "success",
            "processed": len(results),
            "errors": errors,
            "results": results
        }

    except SoftTimeLimitExceeded:
        logger.warning("Sales Intel batch soft time limit exceeded")
        raise

    except Exception as exc:
        logger.error(f"Error in Sales Intel batch: {exc}", exc_info=True)
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


# ============================================================================
# GROWTH CAMPAIGN TASKS (Multi-Touch Optimization)
# ============================================================================

@celery_app.task(name="run_growth_campaigns", bind=True, max_retries=2, soft_time_limit=900)
def run_growth_campaigns_task(self, goal: str = "book_meeting", max_leads: int = 5):
    """
    Run GrowthAgent campaigns for HOT leads.

    This task:
    1. Queries HOT leads with ICP score >= 75
    2. For each lead, runs a 5-cycle campaign optimization
    3. Goal: book_meeting, get_reply, or engagement
    4. Logs results and learnings

    Args:
        goal: Campaign goal (book_meeting, get_reply, engagement)
        max_leads: Maximum leads to process per run (default: 5)

    Returns:
        Dict with campaign results
    """
    try:
        logger.info(f"Starting Growth Campaigns: goal={goal}, max_leads={max_leads}")

        import asyncio
        from app.services.langgraph.agents.growth_agent import GrowthAgent
        from app.services.langgraph.tools.supabase_tools import query_hot_leads

        # Query HOT leads
        leads = query_hot_leads(limit=max_leads)

        if not leads:
            logger.info("No HOT leads found for growth campaigns")
            return {"status": "no_leads", "campaigns_run": 0}

        results = []
        errors = []

        async def run_campaign(lead):
            """Run a single growth campaign."""
            agent = GrowthAgent(provider='cerebras')
            result = await agent.run_campaign(
                lead_id=lead['company_id'],
                goal=goal,
                max_cycles=5
            )
            return result

        # Process each lead
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            for lead in leads:
                try:
                    result = loop.run_until_complete(run_campaign(lead))
                    results.append({
                        "company_id": lead['company_id'],
                        "company_name": lead['company_name'],
                        "goal": goal,
                        "goal_met": result.goal_met,
                        "cycle_count": result.cycle_count,
                        "response_rate": result.response_rate,
                        "engagement_score": result.engagement_score,
                        "learnings": result.learnings[:3] if result.learnings else [],
                        "latency_ms": result.latency_ms
                    })
                    logger.info(
                        f"Growth campaign for {lead['company_name']}: "
                        f"goal_met={result.goal_met}, cycles={result.cycle_count}"
                    )
                except Exception as e:
                    error_msg = f"Campaign failed for {lead['company_name']}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
        finally:
            loop.close()

        logger.info(
            f"Growth Campaigns completed: {len(results)} run, "
            f"{sum(1 for r in results if r.get('goal_met'))} goals met, "
            f"{len(errors)} errors"
        )

        return {
            "status": "success",
            "campaigns_run": len(results),
            "goals_met": sum(1 for r in results if r.get('goal_met')),
            "errors": errors,
            "results": results
        }

    except SoftTimeLimitExceeded:
        logger.warning("Growth Campaigns soft time limit exceeded")
        raise

    except Exception as exc:
        logger.error(f"Error in Growth Campaigns: {exc}", exc_info=True)
        countdown = 120 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


# ============================================================================
# BDR AGENT TASKS - Human-in-Loop Outreach with Slack Approval
# ============================================================================

@celery_app.task(name="run_bdr_outreach", bind=True, max_retries=2, soft_time_limit=300)
def run_bdr_outreach_task(self, company_id: str):
    """
    Start BDR outreach workflow for a single company.

    This task:
    1. Fetches lead details from Supabase
    2. Runs BDRAgent to research and draft email
    3. Saves draft to dim_ai_drafts table
    4. Sends Slack notification with Approve/Reject buttons
    5. PAUSES until human responds via Slack webhook

    The agent uses LangGraph's interrupt() to pause at the draft review step.
    When the user clicks Approve/Reject in Slack, resume_bdr_outreach_task is triggered.

    Args:
        company_id: UUID of the company in dim_companies

    Returns:
        Dict with draft_id and status
    """
    try:
        import asyncio
        from app.services.langgraph.agents.bdr_agent import BDRAgent
        from app.services.langgraph.tools.supabase_tools import get_supabase
        from app.services.slack_notifier import get_slack_notifier
        import uuid

        logger.info(f"Starting BDR outreach for company_id={company_id}")

        # Get lead details from Supabase
        supabase = get_supabase()
        result = supabase.table('dim_companies').select(
            'company_id, company_name, domain, phone, city, state, '
            'icp_tier, icp_score, current_stage, '
            'ai_company_story, ai_personal_hooks, ai_pain_points'
        ).eq('company_id', company_id).execute()

        if not result.data:
            raise ValueError(f"Company not found: {company_id}")

        lead = result.data[0]

        # Get best contact for this company
        contacts_result = supabase.table('dim_contacts').select(
            'contact_id, first_name, last_name, title, email'
        ).eq('company_id', company_id).eq('is_atl', True).limit(1).execute()

        contact = contacts_result.data[0] if contacts_result.data else {}
        contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or "Owner"
        contact_title = contact.get('title', 'Owner')
        contact_email = contact.get('email')

        # Run BDRAgent
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            agent = BDRAgent(provider='cerebras')

            async def run_agent():
                return await agent.start_outreach(
                    lead_id=company_id,
                    company_name=lead['company_name'],
                    contact_name=contact_name,
                    contact_title=contact_title
                )

            bdr_result = loop.run_until_complete(run_agent())

            # Extract draft from result
            # BDRAgent returns interrupt data with draft
            if "__interrupt__" in bdr_result:
                interrupt_data = bdr_result["__interrupt__"][0].get("value", {})
            else:
                interrupt_data = bdr_result

            draft_subject = interrupt_data.get("draft_subject", f"Quick question for {lead['company_name']}")
            draft_body = interrupt_data.get("draft_body", "")
            research_summary = interrupt_data.get("research_summary", "")

            # Generate draft ID
            draft_id = str(uuid.uuid4())

            # Save draft to dim_ai_drafts
            draft_data = {
                "draft_id": draft_id,
                "company_id": company_id,
                "contact_email": contact_email,
                "draft_type": "email",
                "subject": draft_subject,
                "body": draft_body,
                "research_summary": research_summary,
                "status": "pending_approval",
                "created_at": "now()"
            }

            supabase.table('dim_ai_drafts').insert(draft_data).execute()

            logger.info(f"BDR draft saved: {draft_id} for {lead['company_name']}")

            # Send Slack notification
            async def send_notification():
                notifier = get_slack_notifier()
                personal_hooks = None
                if lead.get('ai_personal_hooks'):
                    import json
                    try:
                        personal_hooks = json.loads(lead['ai_personal_hooks'])
                    except:
                        pass

                await notifier.send_bdr_approval_request(
                    draft_id=draft_id,
                    company_name=lead['company_name'],
                    contact_name=contact_name,
                    contact_title=contact_title,
                    subject=draft_subject,
                    body_preview=draft_body,
                    research_summary=research_summary,
                    personal_hooks=personal_hooks
                )

            loop.run_until_complete(send_notification())

        finally:
            loop.close()

        logger.info(f"BDR outreach initiated for {lead['company_name']}, awaiting approval")

        return {
            "status": "awaiting_approval",
            "draft_id": draft_id,
            "company_id": company_id,
            "company_name": lead['company_name']
        }

    except SoftTimeLimitExceeded:
        logger.warning(f"BDR outreach soft time limit exceeded for {company_id}")
        raise

    except Exception as exc:
        logger.error(f"Error in BDR outreach for {company_id}: {exc}", exc_info=True)
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(name="resume_bdr_outreach", bind=True, max_retries=1)
def resume_bdr_outreach_task(
    self,
    draft_id: str,
    action: str,
    feedback: str = None,
    approved_by: str = None
):
    """
    Resume BDR workflow after Slack approval/rejection.

    This task is triggered by the Slack webhook handler when a user
    clicks Approve, Reject, or Edit on a BDR draft notification.

    Actions:
    - approve: Mark draft as approved, "send" the email (or queue for sending)
    - reject: Mark draft as rejected, archive it
    - revise: Re-run BDRAgent with feedback, create new draft

    Args:
        draft_id: UUID of the draft in dim_ai_drafts
        action: Action type (approve, reject, revise)
        feedback: Optional feedback for revision
        approved_by: Slack username who took the action

    Returns:
        Dict with updated status
    """
    try:
        import asyncio
        from app.services.langgraph.tools.supabase_tools import get_supabase
        from app.services.slack_notifier import get_slack_notifier

        logger.info(f"Resuming BDR for draft_id={draft_id}, action={action}")

        supabase = get_supabase()

        # Get draft details
        draft_result = supabase.table('dim_ai_drafts').select('*').eq('draft_id', draft_id).execute()

        if not draft_result.data:
            raise ValueError(f"Draft not found: {draft_id}")

        draft = draft_result.data[0]
        company_id = draft['company_id']

        # Get company name for notifications
        company_result = supabase.table('dim_companies').select('company_name').eq('company_id', company_id).execute()
        company_name = company_result.data[0]['company_name'] if company_result.data else "Unknown"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            if action == "approve":
                # Mark as approved and "sent"
                # In a real system, this would trigger actual email sending via SendGrid/etc
                supabase.table('dim_ai_drafts').update({
                    "status": "sent",
                    "approved_by": approved_by,
                    "sent_at": "now()"
                }).eq('draft_id', draft_id).execute()

                # Update company stage
                supabase.table('dim_companies').update({
                    "current_stage": "CONTACTED"
                }).eq('company_id', company_id).execute()

                logger.info(f"BDR draft approved and sent: {draft_id}")

                # Send confirmation to Slack
                async def send_confirmation():
                    notifier = get_slack_notifier()
                    await notifier.send_status_update(
                        draft_id=draft_id,
                        company_name=company_name,
                        status="sent",
                        message=f"Email sent to {draft.get('contact_email', 'contact')} by {approved_by}"
                    )

                loop.run_until_complete(send_confirmation())

                return {
                    "status": "sent",
                    "draft_id": draft_id,
                    "approved_by": approved_by
                }

            elif action == "reject":
                # Mark as rejected
                supabase.table('dim_ai_drafts').update({
                    "status": "rejected",
                    "rejected_by": approved_by
                }).eq('draft_id', draft_id).execute()

                logger.info(f"BDR draft rejected: {draft_id}")

                return {
                    "status": "rejected",
                    "draft_id": draft_id,
                    "rejected_by": approved_by
                }

            elif action == "revise":
                # Mark current draft as revised
                supabase.table('dim_ai_drafts').update({
                    "status": "revised",
                    "revision_feedback": feedback
                }).eq('draft_id', draft_id).execute()

                # TODO: Pass feedback to BDRAgent for context-aware revision
                # Currently creates a fresh draft without revision context.
                # To improve: Modify BDRAgent.start_outreach() to accept previous_feedback param
                # and use it in the prompt for generating improved drafts.
                run_bdr_outreach_task.delay(company_id)

                logger.info(f"BDR draft revision requested: {draft_id}")

                return {
                    "status": "revision_requested",
                    "draft_id": draft_id,
                    "feedback": feedback
                }

            else:
                raise ValueError(f"Unknown action: {action}")

        finally:
            loop.close()

    except Exception as exc:
        logger.error(f"Error resuming BDR for {draft_id}: {exc}", exc_info=True)
        raise


@celery_app.task(name="run_bdr_batch", bind=True, max_retries=2, soft_time_limit=900)
def run_bdr_batch_task(self, limit: int = 3):
    """
    Run BDR outreach for a batch of HOT leads.

    Queries HOT leads that haven't been contacted and initiates
    BDR outreach for each, sending Slack notifications for approval.

    Scheduled to run every hour via Celery Beat.

    Args:
        limit: Maximum number of leads to process per batch

    Returns:
        Dict with batch results
    """
    try:
        from app.services.langgraph.tools.supabase_tools import get_supabase

        logger.info(f"Starting BDR batch for {limit} leads")

        supabase = get_supabase()

        # Get HOT leads that haven't been contacted
        # Exclude leads that already have pending or sent drafts
        result = supabase.table('dim_companies').select(
            'company_id, company_name'
        ).eq(
            'current_stage', 'HOT'
        ).gte(
            'icp_score', 70
        ).not_.is_(
            'ai_company_story', 'null'  # Must have been scouted
        ).limit(limit).execute()

        leads = result.data or []

        if not leads:
            logger.info("No HOT leads available for BDR batch")
            return {
                "status": "success",
                "leads_queued": 0,
                "message": "No HOT leads available"
            }

        # Check which leads already have pending drafts
        company_ids = [lead['company_id'] for lead in leads]
        drafts_result = supabase.table('dim_ai_drafts').select(
            'company_id'
        ).in_('company_id', company_ids).in_(
            'status', ['pending_approval', 'sent']
        ).execute()

        already_drafted = {d['company_id'] for d in (drafts_result.data or [])}

        # Queue BDR outreach for leads without pending drafts
        queued = []
        skipped = []

        for lead in leads:
            if lead['company_id'] in already_drafted:
                skipped.append(lead['company_name'])
                continue

            # Queue the BDR outreach task
            run_bdr_outreach_task.delay(lead['company_id'])
            queued.append(lead['company_name'])

        logger.info(
            f"BDR batch: {len(queued)} queued, {len(skipped)} skipped (already have drafts)"
        )

        # Send batch summary to Slack if any were queued
        if queued:
            import asyncio
            from app.services.slack_notifier import get_slack_notifier

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                async def send_summary():
                    notifier = get_slack_notifier()
                    await notifier.send_batch_summary(
                        drafts_created=len(queued),
                        companies=queued,
                        errors=0
                    )
                loop.run_until_complete(send_summary())
            finally:
                loop.close()

        return {
            "status": "success",
            "leads_queued": len(queued),
            "leads_skipped": len(skipped),
            "companies": queued
        }

    except SoftTimeLimitExceeded:
        logger.warning("BDR batch soft time limit exceeded")
        raise

    except Exception as exc:
        logger.error(f"Error in BDR batch: {exc}", exc_info=True)
        countdown = 120 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
