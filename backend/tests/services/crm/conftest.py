"""
Minimal conftest for CRM service tests.

This conftest provides only the essentials needed for CRM tests
without importing the full FastAPI application.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables BEFORE importing app modules
env_path = Path(__file__).parent.parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models.database import Base

# Test database URL - uses actual PostgreSQL for integration tests
TEST_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://sales_agent:dev_password_change_in_production@localhost:5433/sales_agent_db")

# Create test engine
test_engine = create_engine(TEST_DATABASE_URL)

# Create test session maker
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Create a fresh database session for each test.

    Creates only CRM-related tables to avoid pgvector dependency.
    """
    from app.models.crm import CRMContact, CRMCredential, CRMSyncLog, CRMWebhook

    # Create session
    session = TestingSessionLocal()

    # Create only CRM tables (not all Base tables)
    CRMContact.__table__.create(bind=test_engine, checkfirst=True)
    CRMCredential.__table__.create(bind=test_engine, checkfirst=True)
    CRMSyncLog.__table__.create(bind=test_engine, checkfirst=True)
    CRMWebhook.__table__.create(bind=test_engine, checkfirst=True)

    try:
        yield session
    finally:
        session.close()
        # Drop CRM tables after test
        CRMWebhook.__table__.drop(bind=test_engine, checkfirst=True)
        CRMSyncLog.__table__.drop(bind=test_engine, checkfirst=True)
        CRMCredential.__table__.drop(bind=test_engine, checkfirst=True)
        CRMContact.__table__.drop(bind=test_engine, checkfirst=True)
