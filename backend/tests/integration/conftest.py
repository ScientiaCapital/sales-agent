"""
Conftest for integration tests.

Provides database fixtures without importing full FastAPI app
to avoid circular import issues during testing.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables BEFORE importing app modules
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base

# Test database URL (in-memory SQLite for testing)
TEST_DATABASE_URL = "sqlite:///./test_integration.db"

# Create test engine
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Create test session maker
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    # Create tables
    Base.metadata.create_all(bind=test_engine)

    # Create session
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        # Drop tables after test
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def async_session(db_session):
    """
    Provide db_session as async_session for compatibility.

    Note: This is a sync session, not truly async, but works for testing
    since our agents can handle both sync and async sessions.
    """
    return db_session
