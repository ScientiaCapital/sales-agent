"""
Customer service for multi-tenant platform management

Handles customer registration, authentication, agent deployment, and quota enforcement
"""
import secrets
import hashlib
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models import Customer, CustomerAgent, CustomerQuota
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from app.core.logging import setup_logging

logger = setup_logging(__name__)

# Initialize password hasher with bcrypt (explicitly using bcrypt from requirements.txt)
password_hash = PasswordHash((BcryptHasher(),))


class CustomerService:
    """
    Service for customer management in multi-tenant platform

    Features:
    - Customer registration with secure password hashing
    - API key generation and management
    - Agent deployment and orchestration
    - Quota enforcement and usage tracking
    """

    def __init__(self):
        """Initialize Customer service"""
        logger.info("Initialized Customer service")
    
    def register_customer(
        self,
        email: str,
        password: str,
        company_name: str,
        contact_name: Optional[str] = None,
        subscription_tier: str = "free",
        db: Session = None
    ) -> Dict:
        """
        Register a new customer with secure password hashing and generate API key

        Args:
            email: Customer email
            password: Customer password
            company_name: Company name
            contact_name: Contact person name
            subscription_tier: Subscription level (free, starter, pro, enterprise)
            db: Database session

        Returns:
            Dictionary with customer data and API key
        """
        try:
            # Hash password securely
            password_hashed = password_hash.hash(password)

            # Generate API key
            api_key = self._generate_api_key()
            api_key_hash = self._hash_api_key(api_key)

            # Create customer record
            customer = Customer(
                company_name=company_name,
                email=email,
                api_key=api_key,  # Store plain key (will be shown once)
                api_key_hash=api_key_hash,
                subscription_tier=subscription_tier,
                contact_name=contact_name,
                status="active"
            )

            db.add(customer)
            db.flush()  # Get customer ID

            # Create default quotas based on subscription tier
            quotas = self._create_default_quotas(customer.id, subscription_tier)
            db.add(quotas)

            db.commit()
            db.refresh(customer)

            logger.info(f"Registered customer: {customer.id} ({company_name})")

            return {
                'customer_id': customer.id,
                'email': email,
                'company_name': company_name,
                'api_key': api_key,  # Only shown once
                'subscription_tier': subscription_tier,
                'status': 'active',
                'created_at': customer.created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to register customer {email}: {e}", exc_info=True)
            db.rollback()
            raise
    
    def _generate_api_key(self) -> str:
        """Generate a secure API key"""
        # Format: sa_<32 random hex characters>
        random_bytes = secrets.token_bytes(16)
        return f"sa_{random_bytes.hex()}"
    
    def _hash_api_key(self, api_key: str) -> str:
        """Hash API key for secure storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def _create_default_quotas(self, customer_id: int, subscription_tier: str) -> CustomerQuota:
        """Create default quotas based on subscription tier"""
        quota_tiers = {
            'free': {
                'max_api_calls_per_day': 100,
                'max_api_calls_per_month': 3000,
                'max_agents': 2,
                'max_concurrent_agents': 1,
                'max_leads_per_month': 100,
                'max_storage_mb': 100,
                'max_documents': 10,
                'max_cost_per_month_usd': 10.0,
                'rate_limit_per_second': 5,
                'rate_limit_per_minute': 50
            },
            'starter': {
                'max_api_calls_per_day': 1000,
                'max_api_calls_per_month': 30000,
                'max_agents': 5,
                'max_concurrent_agents': 3,
                'max_leads_per_month': 1000,
                'max_storage_mb': 1000,
                'max_documents': 100,
                'max_cost_per_month_usd': 100.0,
                'rate_limit_per_second': 10,
                'rate_limit_per_minute': 100
            },
            'pro': {
                'max_api_calls_per_day': 10000,
                'max_api_calls_per_month': 300000,
                'max_agents': 20,
                'max_concurrent_agents': 10,
                'max_leads_per_month': 10000,
                'max_storage_mb': 10000,
                'max_documents': 1000,
                'max_cost_per_month_usd': 1000.0,
                'rate_limit_per_second': 50,
                'rate_limit_per_minute': 500
            },
            'enterprise': {
                'max_api_calls_per_day': 100000,
                'max_api_calls_per_month': 3000000,
                'max_agents': 100,
                'max_concurrent_agents': 50,
                'max_leads_per_month': 100000,
                'max_storage_mb': 100000,
                'max_documents': 10000,
                'max_cost_per_month_usd': 10000.0,
                'rate_limit_per_second': 100,
                'rate_limit_per_minute': 1000
            }
        }
        
        tier_quotas = quota_tiers.get(subscription_tier, quota_tiers['free'])
        
        return CustomerQuota(
            customer_id=customer_id,
            **tier_quotas
        )
    
    def deploy_agent(
        self,
        customer_id: int,
        agent_name: str,
        agent_type: str,
        agent_role: Optional[str] = None,
        config: Optional[Dict] = None,
        model: Optional[str] = None,
        db: Session = None
    ) -> Dict:
        """
        Deploy an agent for a customer
        
        Args:
            customer_id: Customer ID
            agent_name: Agent name
            agent_type: Agent type (lead_qualifier, outreach, researcher, etc.)
            agent_role: Specific role in multi-agent team
            config: Agent configuration
            model: AI model to use
            db: Database session
        
        Returns:
            Agent deployment details
        """
        try:
            # Check customer quotas
            quotas = db.query(CustomerQuota).filter(
                CustomerQuota.customer_id == customer_id
            ).first()
            
            if not quotas:
                raise ValueError(f"Quotas not found for customer {customer_id}")
            
            # Check agent limits
            active_agents = db.query(CustomerAgent).filter(
                CustomerAgent.customer_id == customer_id,
                CustomerAgent.status == "deployed"
            ).count()
            
            if active_agents >= quotas.max_concurrent_agents:
                raise ValueError(
                    f"Agent limit reached ({active_agents}/{quotas.max_concurrent_agents}). "
                    "Please upgrade your plan or terminate existing agents."
                )
            
            # Generate unique deployment ID
            deployment_id = f"agent_{customer_id}_{secrets.token_hex(8)}"
            
            # Create agent record
            agent = CustomerAgent(
                customer_id=customer_id,
                agent_name=agent_name,
                agent_type=agent_type,
                agent_role=agent_role,
                deployment_id=deployment_id,
                status="deployed",
                config=config or {},
                model=model or "llama3.1-8b",
                total_tasks=0,
                completed_tasks=0,
                failed_tasks=0,
                total_api_calls=0,
                total_cost_usd=0.0,
                last_active_at=datetime.now()
            )
            
            db.add(agent)
            
            # Update quotas
            quotas.active_agents_count = active_agents + 1
            
            db.commit()
            db.refresh(agent)
            
            logger.info(f"Deployed agent {deployment_id} for customer {customer_id}")
            
            return {
                'agent_id': agent.id,
                'deployment_id': deployment_id,
                'agent_name': agent_name,
                'agent_type': agent_type,
                'agent_role': agent_role,
                'status': 'deployed',
                'model': agent.model,
                'deployed_at': agent.deployed_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to deploy agent for customer {customer_id}: {e}", exc_info=True)
            db.rollback()
            raise
    
    def get_agent_status(
        self,
        customer_id: int,
        db: Session
    ) -> List[Dict]:
        """
        Get status of all agents for a customer
        
        Args:
            customer_id: Customer ID
            db: Database session
        
        Returns:
            List of agent status details
        """
        try:
            agents = db.query(CustomerAgent).filter(
                CustomerAgent.customer_id == customer_id
            ).all()
            
            agent_statuses = []
            for agent in agents:
                agent_statuses.append({
                    'agent_id': agent.id,
                    'deployment_id': agent.deployment_id,
                    'agent_name': agent.agent_name,
                    'agent_type': agent.agent_type,
                    'agent_role': agent.agent_role,
                    'status': agent.status,
                    'model': agent.model,
                    'performance': {
                        'total_tasks': agent.total_tasks,
                        'completed_tasks': agent.completed_tasks,
                        'failed_tasks': agent.failed_tasks,
                        'success_rate': (
                            (agent.completed_tasks / agent.total_tasks * 100)
                            if agent.total_tasks > 0 else 0
                        ),
                        'average_latency_ms': agent.average_latency_ms
                    },
                    'resource_usage': {
                        'total_api_calls': agent.total_api_calls,
                        'total_cost_usd': agent.total_cost_usd
                    },
                    'deployed_at': agent.deployed_at.isoformat(),
                    'last_active_at': agent.last_active_at.isoformat() if agent.last_active_at else None,
                    'terminated_at': agent.terminated_at.isoformat() if agent.terminated_at else None
                })
            
            logger.info(f"Retrieved status for {len(agents)} agents (customer {customer_id})")
            return agent_statuses
            
        except Exception as e:
            logger.error(f"Failed to get agent status for customer {customer_id}: {e}")
            raise
    
    def terminate_agent(
        self,
        customer_id: int,
        deployment_id: str,
        db: Session
    ):
        """
        Terminate a deployed agent
        
        Args:
            customer_id: Customer ID (for authorization)
            deployment_id: Agent deployment ID
            db: Database session
        """
        try:
            agent = db.query(CustomerAgent).filter(
                CustomerAgent.deployment_id == deployment_id,
                CustomerAgent.customer_id == customer_id
            ).first()
            
            if not agent:
                raise ValueError(f"Agent {deployment_id} not found for customer {customer_id}")
            
            # Update agent status
            agent.status = "terminated"
            agent.terminated_at = datetime.now()
            
            # Update quotas
            quotas = db.query(CustomerQuota).filter(
                CustomerQuota.customer_id == customer_id
            ).first()
            
            if quotas:
                quotas.active_agents_count = max(0, quotas.active_agents_count - 1)
            
            db.commit()
            
            logger.info(f"Terminated agent {deployment_id} for customer {customer_id}")
            
        except Exception as e:
            logger.error(f"Failed to terminate agent {deployment_id}: {e}")
            db.rollback()
            raise
    
    def check_quota(
        self,
        customer_id: int,
        quota_type: str,
        db: Session
    ) -> bool:
        """
        Check if customer has remaining quota
        
        Args:
            customer_id: Customer ID
            quota_type: Type of quota to check (api_calls, agents, leads, storage, cost)
            db: Database session
        
        Returns:
            True if quota available, False otherwise
        """
        try:
            quotas = db.query(CustomerQuota).filter(
                CustomerQuota.customer_id == customer_id
            ).first()
            
            if not quotas:
                return False
            
            if quota_type == 'api_calls_daily':
                return quotas.api_calls_today < quotas.max_api_calls_per_day
            
            elif quota_type == 'api_calls_monthly':
                return quotas.api_calls_this_month < quotas.max_api_calls_per_month
            
            elif quota_type == 'agents':
                return quotas.active_agents_count < quotas.max_agents
            
            elif quota_type == 'leads':
                return quotas.leads_this_month < quotas.max_leads_per_month
            
            elif quota_type == 'storage':
                return quotas.storage_used_mb < quotas.max_storage_mb
            
            elif quota_type == 'documents':
                return quotas.documents_count < quotas.max_documents
            
            elif quota_type == 'cost':
                return quotas.cost_this_month_usd < quotas.max_cost_per_month_usd
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check quota for customer {customer_id}: {e}")
            return False
    
    def increment_usage(
        self,
        customer_id: int,
        usage_type: str,
        amount: float = 1.0,
        db: Session = None
    ):
        """
        Increment usage counters for quota tracking
        
        Args:
            customer_id: Customer ID
            usage_type: Type of usage (api_calls, leads, storage, cost)
            amount: Amount to increment
            db: Database session
        """
        try:
            quotas = db.query(CustomerQuota).filter(
                CustomerQuota.customer_id == customer_id
            ).first()
            
            if not quotas:
                logger.warning(f"Quotas not found for customer {customer_id}")
                return
            
            if usage_type == 'api_calls':
                quotas.api_calls_today += int(amount)
                quotas.api_calls_this_month += int(amount)
            
            elif usage_type == 'leads':
                quotas.leads_this_month += int(amount)
            
            elif usage_type == 'storage':
                quotas.storage_used_mb += amount
            
            elif usage_type == 'documents':
                quotas.documents_count += int(amount)
            
            elif usage_type == 'cost':
                quotas.cost_this_month_usd += amount
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to increment usage for customer {customer_id}: {e}")
            db.rollback()
