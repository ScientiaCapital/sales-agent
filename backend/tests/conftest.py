"""
Pytest configuration and fixtures for comprehensive testing.

This module provides shared fixtures, test configuration, and utilities
for the entire test suite.
"""

import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator, Dict, Any
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Import application components
from app.main import app
from app.models.database import Base, get_db
from app.core.config import get_settings
from app.services.routing.unified_router import UnifiedRouter
from app.services.routing.base_router import ProviderConfig, ProviderType

# Test database URL (in-memory SQLite for testing)
TEST_DATABASE_URL = "sqlite:///./test.db"

# Create test engine
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Create test session maker
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_session() -> Generator:
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
def client(db_session) -> Generator[TestClient, None, None]:
    """Create a test client with database dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def async_client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def mock_providers() -> Dict[ProviderType, ProviderConfig]:
    """Create mock provider configurations for testing."""
    return {
        ProviderType.CEREBRAS: ProviderConfig(
            provider_type=ProviderType.CEREBRAS,
            model="llama3.1-8b",
            base_url="https://api.cerebras.ai/v1",
            api_key="test-cerebras-key",
            max_tokens=512,
            temperature=0.7,
            timeout_seconds=30,
            cost_per_token=0.000006,
            circuit_breaker_config={"failure_threshold": 5, "recovery_timeout": 60},
            retry_config={"max_retries": 3, "base_delay": 1}
        ),
        ProviderType.CLAUDE: ProviderConfig(
            provider_type=ProviderType.CLAUDE,
            model="claude-3-5-sonnet-20241022",
            base_url="https://api.anthropic.com",
            api_key="test-claude-key",
            max_tokens=4096,
            temperature=0.7,
            timeout_seconds=60,
            cost_per_token=0.001743,
            circuit_breaker_config={"failure_threshold": 5, "recovery_timeout": 60},
            retry_config={"max_retries": 3, "base_delay": 1}
        ),
        ProviderType.DEEPSEEK: ProviderConfig(
            provider_type=ProviderType.DEEPSEEK,
            model="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            api_key="test-deepseek-key",
            max_tokens=2048,
            temperature=0.7,
            timeout_seconds=45,
            cost_per_token=0.00027,
            circuit_breaker_config={"failure_threshold": 5, "recovery_timeout": 60},
            retry_config={"max_retries": 3, "base_delay": 1}
        ),
        ProviderType.OLLAMA: ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            model="llama3.1:8b",
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            max_tokens=1024,
            temperature=0.7,
            timeout_seconds=30,
            cost_per_token=0.0,
            circuit_breaker_config={"failure_threshold": 5, "recovery_timeout": 60},
            retry_config={"max_retries": 3, "base_delay": 1}
        )
    }


@pytest.fixture
def mock_router(mock_providers) -> UnifiedRouter:
    """Create a mock unified router for testing."""
    return UnifiedRouter(mock_providers)


@pytest.fixture
def mock_lead_data() -> Dict[str, Any]:
    """Create mock lead data for testing."""
    return {
        "company_name": "Test Company Inc.",
        "email": "test@testcompany.com",
        "phone": "+1-555-0123",
        "website": "https://testcompany.com",
        "industry": "Technology",
        "company_size": "50-200",
        "annual_revenue": "10M-50M",
        "location": "San Francisco, CA",
        "description": "A test company for automated testing"
    }


@pytest.fixture
def mock_crm_contact() -> Dict[str, Any]:
    """Create mock CRM contact data for testing."""
    return {
        "id": "test_contact_123",
        "name": "John Doe",
        "email": "john.doe@testcompany.com",
        "phone": "+1-555-0123",
        "company": "Test Company Inc.",
        "title": "CTO",
        "custom_fields": {
            "industry": "Technology",
            "company_size": "50-200",
            "annual_revenue": "10M-50M"
        }
    }


@pytest.fixture
def mock_ai_response() -> Dict[str, Any]:
    """Create mock AI response for testing."""
    return {
        "content": "This is a test AI response for automated testing.",
        "model": "test-model",
        "tokens_used": 25,
        "cost_usd": 0.0001,
        "latency_ms": 500,
        "metadata": {
            "provider": "test",
            "timestamp": "2025-10-29T19:47:35Z"
        }
    }


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    websocket = AsyncMock()
    websocket.send_json = AsyncMock()
    websocket.receive_json = AsyncMock()
    websocket.close = AsyncMock()
    return websocket


@pytest.fixture
def mock_redis():
    """Create a mock Redis client for testing."""
    redis_mock = Mock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.exists = AsyncMock(return_value=False)
    redis_mock.incr = AsyncMock(return_value=1)
    redis_mock.expire = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture
def mock_celery():
    """Create a mock Celery task for testing."""
    task_mock = Mock()
    task_mock.delay = Mock(return_value=Mock(id="test-task-123"))
    task_mock.apply_async = Mock(return_value=Mock(id="test-task-123"))
    return task_mock


# Test utilities
class TestUtils:
    """Utility functions for testing."""
    
    @staticmethod
    def assert_response_success(response, expected_status=200):
        """Assert that a response is successful."""
        assert response.status_code == expected_status
        assert "error" not in response.json()
    
    @staticmethod
    def assert_response_error(response, expected_status=400):
        """Assert that a response contains an error."""
        assert response.status_code == expected_status
        assert "error" in response.json()
    
    @staticmethod
    def assert_ai_response_structure(response_data):
        """Assert that AI response has correct structure."""
        required_fields = ["content", "model", "tokens_used", "cost_usd", "latency_ms"]
        for field in required_fields:
            assert field in response_data, f"Missing field: {field}"
        
        assert isinstance(response_data["content"], str)
        assert isinstance(response_data["tokens_used"], int)
        assert isinstance(response_data["cost_usd"], (int, float))
        assert isinstance(response_data["latency_ms"], int)
    
    @staticmethod
    def assert_lead_structure(lead_data):
        """Assert that lead data has correct structure."""
        required_fields = ["company_name", "email", "phone", "website"]
        for field in required_fields:
            assert field in lead_data, f"Missing field: {field}"
        
        assert isinstance(lead_data["company_name"], str)
        assert "@" in lead_data["email"]
        assert lead_data["phone"].startswith("+")
        assert lead_data["website"].startswith("http")


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "ai: mark test as requiring AI services"
    )
    config.addinivalue_line(
        "markers", "database: mark test as requiring database"
    )
    config.addinivalue_line(
        "markers", "external: mark test as requiring external services"
    )


# Test discovery configuration
collect_ignore = [
    "test_legacy.py",  # Ignore legacy test files
    "test_old_*.py",   # Ignore old test files
]
