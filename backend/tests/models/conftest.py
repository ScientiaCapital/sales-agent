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

    # Import model after Base is loaded
    from app.models.pipeline_models import PipelineTestExecution

    # Create only pipeline_test_executions table (avoid pgvector dependency)
    PipelineTestExecution.__table__.create(bind=engine, checkfirst=True)

    # Create session
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.rollback()
    session.close()
    PipelineTestExecution.__table__.drop(bind=engine, checkfirst=True)
