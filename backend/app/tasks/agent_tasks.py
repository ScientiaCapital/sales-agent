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
