"""
Pytest fixtures and configuration for social intelligence tests
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient


# ==================== Pytest Configuration ====================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== FastAPI Test Client ====================

@pytest.fixture
def client():
    """FastAPI test client."""
    from app.main import app
    return TestClient(app)


# ==================== Database Fixtures ====================

@pytest.fixture
def mock_database_url():
    """Mock Supabase database URL."""
    return "postgresql://test_user:test_pass@localhost:5432/test_db"


@pytest.fixture
def mock_db_connection():
    """Mock async database connection."""
    conn = AsyncMock()
    cursor = AsyncMock()

    # Mock cursor methods
    cursor.execute = AsyncMock()
    cursor.fetchone = AsyncMock(return_value={'count': 0})
    cursor.fetchall = AsyncMock(return_value=[])

    # Mock connection context manager
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock()
    conn.cursor = MagicMock(return_value=cursor)
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock()

    return conn


# ==================== API Key Fixtures ====================

@pytest.fixture
def mock_api_keys():
    """Mock API keys for all services."""
    return {
        'runpod': 'test_runpod_key',
        'supabase': 'postgresql://test:test@localhost:5432/test',
        'close': 'test_close_key',
        'anthropic': 'test_anthropic_key',
        'deepseek': 'test_deepseek_key',
        'twitter': 'test_twitter_bearer_token'
    }


# ==================== Sample Data Fixtures ====================

@pytest.fixture
def sample_linkedin_posts():
    """Sample LinkedIn posts for testing."""
    return [
        {
            'contact_id': 'https://linkedin.com/in/test-user',
            'platform': 'linkedin',
            'post_text': 'Just launched our new AI product!',
            'post_url': 'https://linkedin.com/posts/test-123',
            'posted_at': datetime.now() - timedelta(days=2),
            'scraped_at': datetime.now()
        }
    ]
