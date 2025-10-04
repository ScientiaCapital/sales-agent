"""
Customer API endpoints for multi-tenant platform
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.models import get_db
from app.schemas.customer import (
    CustomerRegistrationRequest,
    CustomerRegistrationResponse,
    AgentDeploymentRequest,
    AgentDeploymentResponse,
    AgentStatusResponse,
    CustomerQuotaResponse
)
from app.services.customer_service import CustomerService
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/api/customers", tags=["customers"])

# Initialize Customer service
customer_service = CustomerService()


@router.post("/register", response_model=CustomerRegistrationResponse, status_code=201)
async def register_customer(
    request: CustomerRegistrationRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new customer
    
    This endpoint:
    1. Creates a Firebase Authentication user
    2. Generates a unique API key
    3. Creates customer record with multi-tenant isolation
    4. Sets up default quotas based on subscription tier
    5. Configures Firebase custom claims for RBAC
    
    Returns customer details and API key (shown only once).
    
    IMPORTANT: Save the API key immediately - it won't be shown again!
    """
    try:
        logger.info(f"Registering customer: {request.email} ({request.company_name})")
        
        result = customer_service.register_customer(
            email=request.email,
            password=request.password,
            company_name=request.company_name,
            contact_name=request.contact_name,
            subscription_tier=request.subscription_tier,
            db=db
        )
        
        logger.info(f"Customer registered successfully: {result['customer_id']}")
        
        return result
        
    except ValueError as e:
        logger.warning(f"Registration validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Failed to register customer: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Customer registration failed: {str(e)}"
        )


@router.post("/{customer_id}/agents/deploy", response_model=AgentDeploymentResponse, status_code=201)
async def deploy_agent(
    customer_id: int,
    request: AgentDeploymentRequest,
    db: Session = Depends(get_db)
):
    """
    Deploy an agent for a customer
    
    This endpoint:
    1. Validates customer quotas (max agents, concurrent agents)
    2. Creates agent deployment with unique deployment ID
    3. Initializes agent with specified configuration and model
    4. Updates quota counters
    
    Agent Types:
    - lead_qualifier: Qualify leads with AI scoring
    - outreach: Automated personalized outreach
    - researcher: Market research and enrichment
    - scheduler: Meeting booking and coordination
    
    Returns agent deployment details including deployment_id for monitoring.
    """
    try:
        logger.info(f"Deploying agent for customer {customer_id}: {request.agent_name} ({request.agent_type})")
        
        result = customer_service.deploy_agent(
            customer_id=customer_id,
            agent_name=request.agent_name,
            agent_type=request.agent_type,
            agent_role=request.agent_role,
            config=request.config,
            model=request.model,
            db=db
        )
        
        logger.info(f"Agent deployed successfully: {result['deployment_id']}")
        
        return result
        
    except ValueError as e:
        logger.warning(f"Agent deployment validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Failed to deploy agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Agent deployment failed: {str(e)}"
        )


@router.get("/{customer_id}/agents/status", response_model=List[AgentStatusResponse])
async def get_agent_status(
    customer_id: int,
    db: Session = Depends(get_db)
):
    """
    Get status of all agents for a customer
    
    Returns comprehensive agent metrics:
    - Deployment status (deployed, paused, terminated)
    - Performance metrics (tasks completed, success rate, latency)
    - Resource usage (API calls, costs)
    - Activity timestamps
    
    Use this for monitoring agent health and performance optimization.
    """
    try:
        logger.info(f"Retrieving agent status for customer {customer_id}")
        
        agents = customer_service.get_agent_status(
            customer_id=customer_id,
            db=db
        )
        
        logger.info(f"Retrieved status for {len(agents)} agents")
        
        return agents
        
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve agent status: {str(e)}"
        )


@router.delete("/{customer_id}/agents/{deployment_id}", status_code=204)
async def terminate_agent(
    customer_id: int,
    deployment_id: str,
    db: Session = Depends(get_db)
):
    """
    Terminate a deployed agent
    
    This endpoint:
    1. Verifies customer ownership
    2. Stops agent execution
    3. Updates agent status to 'terminated'
    4. Decrements quota counters
    
    Returns 204 No Content on success.
    """
    try:
        logger.info(f"Terminating agent {deployment_id} for customer {customer_id}")
        
        customer_service.terminate_agent(
            customer_id=customer_id,
            deployment_id=deployment_id,
            db=db
        )
        
        logger.info(f"Agent {deployment_id} terminated successfully")
        
        return None
        
    except ValueError as e:
        logger.warning(f"Agent termination error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:
        logger.error(f"Failed to terminate agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to terminate agent: {str(e)}"
        )


@router.get("/{customer_id}/quotas", response_model=CustomerQuotaResponse)
async def get_customer_quotas(
    customer_id: int,
    db: Session = Depends(get_db)
):
    """
    Get customer quotas and usage statistics
    
    Returns:
    - API call limits and current usage (daily/monthly)
    - Agent deployment limits
    - Lead processing limits
    - Storage quotas
    - Cost caps and current spending
    - Rate limiting configuration
    
    Use this for displaying usage dashboards and enforcing limits.
    """
    try:
        from app.models import CustomerQuota
        
        logger.info(f"Retrieving quotas for customer {customer_id}")
        
        quotas = db.query(CustomerQuota).filter(
            CustomerQuota.customer_id == customer_id
        ).first()
        
        if not quotas:
            raise HTTPException(
                status_code=404,
                detail=f"Quotas not found for customer {customer_id}"
            )
        
        return quotas
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get quotas: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve quotas: {str(e)}"
        )
