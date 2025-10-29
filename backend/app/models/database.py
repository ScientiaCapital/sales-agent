"""
Database configuration and base models
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, DBAPIError
import os
import logging
from app.core.exceptions import DatabaseConnectionError

logger = logging.getLogger(__name__)

# Get database URL from environment - REQUIRED, no default for security
# Use postgresql+psycopg driver (psycopg3) instead of default psycopg2
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required. "
        "Please set it in your .env file. "
        "Example: DATABASE_URL=postgresql+psycopg://user:password@host:port/database"
    )

# Convert postgresql:// to postgresql+psycopg:// for psycopg3 compatibility
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Create SQLAlchemy engine with connection resilience
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",  # Environment-controlled SQL logging
    
    # Connection Pool Configuration
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),  # Base pool size
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),  # Additional connections when pool exhausted
    
    # Connection Resilience
    pool_pre_ping=True,  # Test connection before use (prevents stale connection errors)
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),  # Recycle connections after 1 hour
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),  # Wait 30s for available connection
    
    # Query Configuration
    connect_args={
        "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),  # 10s connection timeout
        "options": "-c statement_timeout=30000"  # 30s query timeout
    }
)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()

# Import all models to ensure they are registered with SQLAlchemy
from app.models.lead import Lead
from app.models.api_call import CerebrasAPICall
from app.models.agent_models import (
    AgentExecution, AgentWorkflow, EnrichedLead, 
    MarketingCampaign, BookedMeeting
)
from app.models.campaign import Campaign, CampaignMessage
from app.models.crm import CRMCredential, CRMContact, CRMSyncLog
from app.models.langgraph_models import LangGraphExecution, LangGraphCheckpoint, LangGraphToolCall

def get_db():
    """
    Dependency function for FastAPI to get database sessions
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def check_database_health() -> dict:
    """
    Check database connectivity and health.
    
    Returns:
        dict: Health check results with status and latency
        
    Example:
        {
            "status": "healthy",
            "latency_ms": 15,
            "pool_size": 5,
            "pool_checked_out": 2
        }
    """
    import time
    from sqlalchemy.pool import NullPool
    
    start_time = time.time()
    
    try:
        # Test database connection with simple query
        db = SessionLocal()
        try:
            # Execute simple query to verify connectivity
            result = db.execute(text("SELECT 1"))
            result.fetchone()
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Get connection pool stats
            pool = engine.pool
            pool_status = {
                "status": "healthy",
                "latency_ms": latency_ms,
                "pool_size": pool.size(),
                "pool_checked_out": pool.checkedout() if hasattr(pool, 'checkedout') else 0,
            }
            
            logger.debug(f"Database health check passed in {latency_ms}ms")
            return pool_status
            
        finally:
            db.close()
            
    except (OperationalError, DBAPIError) as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Database health check failed after {latency_ms}ms: {e}")
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "error": str(e),
            "error_type": type(e).__name__
        }
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Unexpected error in database health check: {e}")
        return {
            "status": "error",
            "latency_ms": latency_ms,
            "error": str(e),
            "error_type": type(e).__name__
        }


def get_db_with_retry(max_retries: int = 3):
    """
    Get database session with automatic retry on connection failures.
    
    Args:
        max_retries: Maximum number of connection retry attempts
        
    Yields:
        Database session
        
    Note:
        Uses exponential backoff: 1s, 2s, 4s between retries
    """
    import time
    
    last_error = None
    for attempt in range(max_retries):
        try:
            db = SessionLocal()
            try:
                # Test connection with simple query
                db.execute(text("SELECT 1"))
                yield db
                return  # Success - exit retry loop
            except:
                db.close()
                raise
        except (OperationalError, DBAPIError) as e:
            last_error = e

            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s
                delay = 2 ** attempt
                logger.warning(
                    f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                logger.error(f"All {max_retries} database connection attempts failed")
                raise DatabaseConnectionError(
                    f"Failed to connect to database after {max_retries} attempts",
                    context={
                        "max_retries": max_retries,
                        "last_error": str(e),
                        "error_type": type(e).__name__
                    }
                )
        finally:
            if 'db' in locals():
                db.close()

    # Should never reach here, but for safety
    if last_error:
        raise DatabaseConnectionError(
            "Database connection failed after all retry attempts",
            context={"error": str(last_error)}
        )
