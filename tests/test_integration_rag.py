"""
Integration Tests for CompanyRAG with PostgreSQL.

These tests require a live PostgreSQL connection.
Skip with: pytest -m "not integration"

Environment variables required:
- DATABASE_URL or SUPABASE_DB_URL: PostgreSQL connection string
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock

import sys
sys.path.insert(0, "/Users/tmkipper/Desktop/tk_projects/sales-agent/backend")

from app.services.rag.lightrag_client import (
    CompanyRAG,
    RAGConfig,
    RAGSearchResult,
    RAGIndexResult,
)


# Check if we have a real database connection
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
SKIP_INTEGRATION = DATABASE_URL is None


@pytest.fixture
def rag_config():
    """Configuration for integration tests."""
    return RAGConfig(
        pg_connection_string=DATABASE_URL or "postgresql://test:test@localhost:5432/test",
        embedding_model="all-MiniLM-L6-v2",
        llm_provider="anthropic",
        llm_model="claude-3-5-haiku-20241022",
        pool_min_size=2,
        pool_max_size=5,
        pool_command_timeout=30.0,
    )


@pytest.fixture
def company_rag(rag_config):
    """Initialize CompanyRAG for testing."""
    return CompanyRAG(config=rag_config)


class TestConnectionPooling:
    """Test asyncpg connection pooling."""

    @pytest.mark.asyncio
    async def test_health_check_memory_mode(self, company_rag):
        """Health check should work in memory mode."""
        # Memory mode always returns True
        result = await company_rag.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_pool_stats_memory_mode(self, company_rag):
        """Pool stats should work in memory mode."""
        stats = await company_rag.get_pool_stats()
        assert "storage_type" in stats
        assert stats["storage_type"] == "memory"

    @pytest.mark.asyncio
    async def test_close_idempotent(self, company_rag):
        """Close should be idempotent."""
        await company_rag.close()
        await company_rag.close()  # Should not raise
        assert company_rag.is_connected is False


class TestMemoryStorageFallback:
    """Test in-memory storage fallback."""

    @pytest.mark.asyncio
    async def test_index_and_search_memory_mode(self, company_rag):
        """Index and search should work in memory mode."""
        # Index a company
        company_data = {
            "company_name": "Test Corp",
            "industry": "Technology",
            "description": "A test company for integration testing",
        }
        index_result = await company_rag.index_company(company_data)
        assert isinstance(index_result, RAGIndexResult)
        assert index_result.success is True

        # Search for the company
        search_result = await company_rag.search(
            query="Find Test Corp",
            mode="hybrid"
        )
        assert isinstance(search_result, RAGSearchResult)
        assert search_result.success is True


@pytest.mark.skipif(SKIP_INTEGRATION, reason="No database connection available")
class TestPostgreSQLIntegration:
    """Integration tests requiring live PostgreSQL."""

    @pytest.mark.asyncio
    async def test_connect_and_health_check(self, company_rag):
        """Test real database connection."""
        await company_rag.connect()
        assert company_rag.is_connected is True

        health = await company_rag.health_check()
        assert health is True

        await company_rag.close()

    @pytest.mark.asyncio
    async def test_pool_stats_postgresql(self, company_rag):
        """Test pool statistics with real database."""
        await company_rag.connect()

        stats = await company_rag.get_pool_stats()
        assert stats["storage_type"] == "postgresql"
        assert "pool_size" in stats
        assert "idle_connections" in stats
        assert stats["min_size"] == 2
        assert stats["max_size"] == 5

        await company_rag.close()

    @pytest.mark.asyncio
    async def test_index_company_postgresql(self, company_rag):
        """Test indexing company data to PostgreSQL."""
        await company_rag.connect()

        company_data = {
            "company_name": "Integration Test Corp",
            "industry": "Construction",
            "employees": 500,
            "revenue": "50M",
            "description": "MEP contractor specializing in commercial projects",
        }

        result = await company_rag.index_company(company_data)
        assert result.success is True
        assert result.entity_id is not None

        await company_rag.close()

    @pytest.mark.asyncio
    async def test_hybrid_search_postgresql(self, company_rag):
        """Test hybrid search against PostgreSQL."""
        await company_rag.connect()

        # Index test data first
        await company_rag.index_company({
            "company_name": "Solar Solutions Inc",
            "industry": "Renewable Energy",
            "description": "Commercial solar installation and maintenance",
        })

        # Search
        result = await company_rag.search(
            query="solar installation companies",
            mode="hybrid",
            top_k=5
        )

        assert result.success is True
        # Results may be empty if just indexed, but query should succeed

        await company_rag.close()


class TestNoOpenAIEnforcement:
    """Ensure NO OpenAI models are used."""

    def test_reject_openai_provider(self):
        """Should reject OpenAI as LLM provider."""
        with pytest.raises(ValueError, match="OpenAI.*not allowed"):
            RAGConfig(
                pg_connection_string="postgresql://test@localhost/test",
                embedding_model="text-embedding-3-large",
                llm_provider="openai",
                llm_model="gpt-4",
            )

    def test_reject_openai_model(self):
        """Should reject OpenAI model names."""
        with pytest.raises(ValueError, match="OpenAI.*not allowed"):
            RAGConfig(
                pg_connection_string="postgresql://test@localhost/test",
                embedding_model="text-embedding-3-large",
                llm_provider="anthropic",
                llm_model="gpt-4-turbo",
            )

    def test_accept_anthropic(self):
        """Should accept Anthropic models."""
        config = RAGConfig(
            pg_connection_string="postgresql://test@localhost/test",
            embedding_model="all-MiniLM-L6-v2",
            llm_provider="anthropic",
            llm_model="claude-3-5-haiku-20241022",
        )
        assert config.llm_provider == "anthropic"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
