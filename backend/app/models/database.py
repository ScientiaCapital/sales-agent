"""
Database configuration and base models

Supports both sync and async sessions:
- Sync: `get_db()` for existing FastAPI dependencies
- Async: `get_async_db()` for new async services like LeadAuditService
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.exc import OperationalError, DBAPIError
from sqlalchemy.pool import SingletonThreadPool
import os
import logging
from app.core.exceptions import DatabaseConnectionError

logger = logging.getLogger(__name__)

# Get database URL from environment
# Use postgresql+psycopg driver (psycopg3) instead of default psycopg2
# For tests, fall back to in-memory SQLite if DATABASE_URL not set
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    import sys
    # Check if running in pytest - pytest is in sys.modules during collection
    is_testing = (
        "pytest" in sys.modules
        or os.getenv("PYTEST_CURRENT_TEST")
        or "pytest" in os.getenv("_", "")
    )
    if is_testing:
        DATABASE_URL = "sqlite:///:memory:"
        logger.warning("DATABASE_URL not set, using in-memory SQLite for tests")
    else:
        raise ValueError(
            "DATABASE_URL environment variable is required. "
            "Please set it in your .env file. "
            "Example: DATABASE_URL=postgresql+psycopg://user:password@host:port/database"
        )

# Check if this is SQLite (for testing) vs PostgreSQL (production)
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# Convert postgresql:// to postgresql+psycopg:// for psycopg3 compatibility
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Build engine kwargs conditionally based on database type
# SQLite uses SingletonThreadPool which doesn't support pool_size/max_overflow/pool_timeout
if IS_SQLITE:
    engine_kwargs = {
        "echo": os.getenv("DATABASE_ECHO", "false").lower() == "true",
        # SQLite-specific: use check_same_thread=False for multi-threaded tests
        "connect_args": {"check_same_thread": False},
        # Force SingletonThreadPool for SQLite (recommended for in-memory/file-based DBs)
        "poolclass": SingletonThreadPool,
    }
else:
    # PostgreSQL with full connection pooling
    engine_kwargs = {
        "echo": os.getenv("DATABASE_ECHO", "false").lower() == "true",
        # Connection Pool Configuration (QueuePool only)
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        # Connection Resilience
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
        # Query Configuration (PostgreSQL-specific)
        "connect_args": {
            "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
            "options": "-c statement_timeout=30000",
        },
    }

# Create SQLAlchemy engine with connection resilience
engine = create_engine(DATABASE_URL, **engine_kwargs)

# Create sessionmaker (sync)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()

# =========================================================================
# Async Database Support (for LeadAuditService and future async services)
# =========================================================================

# Only create async engine for PostgreSQL (not SQLite)
if not IS_SQLITE:
    # Convert to async URL (postgresql+psycopg_async for async psycopg3)
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql+psycopg://")

    # Create async engine with PostgreSQL pool settings
    async_engine = create_async_engine(
        ASYNC_DATABASE_URL,
        echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        pool_pre_ping=True,
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
    )
else:
    # SQLite async not typically used, but create a minimal engine for imports
    async_engine = None

# Create async sessionmaker (only for PostgreSQL)
if async_engine is not None:
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
else:
    # SQLite fallback - async not supported
    AsyncSessionLocal = None


async def get_async_db():
    """
    Async dependency function for FastAPI to get async database sessions.

    Used by:
    - LeadAuditService
    - Other async services

    Example:
        @router.get("/audit")
        async def get_audit(db: AsyncSession = Depends(get_async_db)):
            ...

    Note: Only available for PostgreSQL. SQLite does not support async.
    """
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "Async database sessions are not available. "
            "Async is only supported with PostgreSQL, not SQLite."
        )
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Import all models to ensure they are registered with SQLAlchemy

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
            except Exception as e:
                db.close()
                logger.error(f"Database connection test failed: {e}")
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


# Alias for backward compatibility with call_analysis_tasks.py
async_session_maker = AsyncSessionLocal
