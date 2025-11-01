"""
Minimal conftest for model tests
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

from app.models.database import Base


@pytest.fixture(scope="function")
def db_session():
    """Create test database session"""
    # Use test database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    engine = create_engine(database_url)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Import models after Base is loaded
    from app.models.pipeline_models import PipelineTestExecution
    from app.models.ai_cost_tracking import AICostTracking
    from app.models.lead import Lead

    # Create tables (avoid pgvector dependency)
    Lead.__table__.create(bind=engine, checkfirst=True)
    PipelineTestExecution.__table__.create(bind=engine, checkfirst=True)
    AICostTracking.__table__.create(bind=engine, checkfirst=True)

    # Create session
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.rollback()
    session.close()
    AICostTracking.__table__.drop(bind=engine, checkfirst=True)
    PipelineTestExecution.__table__.drop(bind=engine, checkfirst=True)
    Lead.__table__.drop(bind=engine, checkfirst=True)
