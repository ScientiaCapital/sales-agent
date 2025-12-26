"""
TDD Tests for LightRAG Company Knowledge Graph Client.

RED Phase: All tests should FAIL initially.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

import sys
sys.path.insert(0, "/Users/tmkipper/Desktop/tk_projects/sales-agent/backend")

from app.services.rag.lightrag_client import (
    CompanyRAG,
    RAGSearchResult,
    RAGIndexResult,
    ConnectionResult,
    RAGConfig,
)


@pytest.fixture
def rag_config():
    """Default RAG configuration for testing."""
    return RAGConfig(
        pg_connection_string="postgresql://test:test@localhost:5432/test_db",
        embedding_model="text-embedding-3-large",
        llm_provider="anthropic",
        llm_model="claude-3-5-haiku-20241022",
    )


@pytest.fixture
def company_rag(rag_config):
    """Initialize CompanyRAG client."""
    return CompanyRAG(config=rag_config)


class TestCompanyRAGInitialization:
    """Test CompanyRAG client initialization."""

    def test_init_with_valid_config(self, rag_config):
        """Test initialization with valid configuration."""
        client = CompanyRAG(config=rag_config)
        assert client.config.llm_provider == "anthropic"

    def test_init_fails_with_openai(self):
        """Test that initialization FAILS if OpenAI provider is used."""
        with pytest.raises(ValueError, match="OpenAI.*not allowed"):
            RAGConfig(
                pg_connection_string="postgresql://test:test@localhost:5432/test",
                embedding_model="text-embedding-3-large",
                llm_provider="openai",
                llm_model="gpt-4",
            )


class TestCompanyIndexing:
    """Test indexing company data into LightRAG."""

    @pytest.mark.asyncio
    async def test_index_company_basic(self, company_rag):
        """Test indexing basic company information."""
        company_data = {
            "company_name": "Acme Corp",
            "industry": "Construction",
        }
        result = await company_rag.index_company(company_data)
        assert isinstance(result, RAGIndexResult)
        assert result.success is True


class TestHybridSearch:
    """Test hybrid search."""

    @pytest.mark.asyncio
    async def test_search_basic_query(self, company_rag):
        """Test basic search query."""
        result = await company_rag.search("Find Acme Corp", mode="hybrid")
        assert isinstance(result, RAGSearchResult)
        assert result.success is True


class TestGraphConnections:
    """Test graph traversal."""

    @pytest.mark.asyncio
    async def test_get_connections(self, company_rag):
        """Test finding connections for an entity."""
        result = await company_rag.get_connections(
            entity_id="acme-123",
            relationship_types=["works_with"],
            max_depth=2,
        )
        assert isinstance(result, ConnectionResult)
        assert result.success is True
