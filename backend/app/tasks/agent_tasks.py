"""
Celery tasks for multi-agent workflow execution

This module defines async tasks for agent-based lead processing, including:
- Individual agent execution (qualifier, enricher, researcher)
- Multi-agent workflow orchestration
- Batch lead processing
- Background enrichment tasks
"""
import time
from typing import Dict, List, Any
from celery import group, chain, chord
from celery.exceptions import SoftTimeLimitExceeded, Retry
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
        from app.models import Lead, Report
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
