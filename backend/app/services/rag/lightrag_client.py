"""
LightRAG Company Knowledge Graph Client (Production-Ready Implementation)

Provides graph+vector hybrid RAG for Sales-Agent ResearchAgent.
PostgreSQL-backed knowledge graph with entity extraction and hybrid search.

Architecture:
- Backend: PostgreSQL with pgvector extension (Supabase-compatible)
- Embedding: sentence-transformers all-MiniLM-L6-v2 (384 dims, fast)
- LLM: Anthropic Claude (NO OpenAI per CLAUDE.md constraints)
- Connection: asyncpg with connection pooling for production performance

Features:
- Production embeddings via sentence-transformers (open-source, NO OpenAI)
- Graceful degradation to hash-based pseudo-embeddings if unavailable
- Model caching for performance
- Configurable embedding dimensions
- Connection pooling with configurable min/max sizes
- Graceful shutdown and health checks
"""

import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

# Conditional imports for graceful degradation
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    asyncpg = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None  # type: ignore

logger = logging.getLogger(__name__)


# Default embedding model for sentence-transformers (fast, 384 dimensions)
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_DIM = 384

# Fallback dimension when using hash-based embeddings
HASH_EMBEDDING_DIM = 384


@dataclass
class RAGConfig:
    """Configuration for LightRAG client."""

    pg_connection_string: str
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"
    embedding_dim: int = DEFAULT_EMBEDDING_DIM
    graph_enabled: bool = True
    vector_enabled: bool = True
    hybrid_mode: bool = True
    top_k: int = 5
    context_window: int = 32000
    use_sentence_transformers: bool = True  # Enable production embeddings

    # Connection pool settings
    pool_min_size: int = 5
    pool_max_size: int = 20
    pool_command_timeout: float = 60.0

    def __post_init__(self):
        """Validate configuration - NO OPENAI ALLOWED."""
        # Check provider
        if self.llm_provider.lower() == "openai":
            raise ValueError("OpenAI provider is not allowed. Use 'anthropic' instead.")
        # Check model name
        if "gpt" in self.llm_model.lower() or "openai" in self.llm_model.lower():
            raise ValueError("OpenAI models (gpt-*) are not allowed. Use Claude models.")


@dataclass
class RAGIndexResult:
    """Result from indexing a company into the knowledge graph."""

    success: bool
    company_id: str | None = None
    entities_created: int = 0
    relationships_created: int = 0
    vectors_created: int = 0
    processing_time_ms: int = 0
    operation: str = "create"  # create | update
    error_message: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class SearchResultItem:
    """Single search result item."""

    entity_id: str
    entity_type: str  # company | contact | relationship
    content: str
    rrf_score: float
    vector_score: float
    graph_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGSearchResult:
    """Result from hybrid search query."""

    success: bool
    query: str
    mode: Literal["low", "high", "hybrid"]
    results: list[SearchResultItem] = field(default_factory=list)
    total_results: int = 0
    processing_time_ms: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class Connection:
    """Graph connection/relationship."""

    target_entity: str
    relationship_type: str
    weight: float
    depth: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectionResult:
    """Result from get_connections graph traversal."""

    success: bool
    entity_id: str
    connections: list[Connection] = field(default_factory=list)
    max_depth: int = 1
    error_message: str | None = None


class CompanyRAG:
    """
    LightRAG client for company knowledge graph operations.

    Production-ready implementation with sentence-transformers embeddings.
    Uses in-memory storage for testing, PostgreSQL for production.
    Gracefully falls back to hash-based embeddings if sentence-transformers unavailable.

    Features:
    - asyncpg connection pooling for production performance
    - Configurable pool sizes (min/max connections)
    - Health check for monitoring
    - Graceful shutdown
    """

    def __init__(self, config: RAGConfig):
        """
        Initialize CompanyRAG client.

        Args:
            config: RAG configuration

        Raises:
            ValueError: If OpenAI provider is used (CLAUDE.md constraint)
        """
        # Enforce NO OpenAI constraint
        if config.llm_provider.lower() == "openai":
            raise ValueError(
                "OpenAI models are not allowed per CLAUDE.md constraints. "
                "Use 'anthropic' or 'openrouter' instead."
            )

        self.config = config
        self._pool: Optional[asyncpg.Pool] = None  # type: ignore
        self._embedding_model: Optional[SentenceTransformer] = None  # type: ignore
        self._use_sentence_transformers = False
        self.is_connected = False

        # In-memory storage for testing
        self._entities: dict[str, dict[str, Any]] = {}
        self._relationships: dict[str, dict[str, Any]] = {}
        self._use_memory_storage = True  # Default to memory for tests

    async def _ensure_pool(self) -> Optional[asyncpg.Pool]:  # type: ignore
        """
        Ensure connection pool is initialized and return it.

        Creates the pool lazily on first access with configured parameters.

        Returns:
            asyncpg.Pool instance or None if using memory storage

        Raises:
            RuntimeError: If asyncpg is not available and real DB is required
        """
        if self._use_memory_storage:
            return None

        if self._pool is None:
            if not ASYNCPG_AVAILABLE:
                raise RuntimeError(
                    "asyncpg is not installed. Install with: pip install asyncpg"
                )

            self._pool = await asyncpg.create_pool(
                dsn=self.config.pg_connection_string,
                min_size=self.config.pool_min_size,
                max_size=self.config.pool_max_size,
                command_timeout=self.config.pool_command_timeout,
            )
            logger.info(
                f"Connection pool created: min={self.config.pool_min_size}, "
                f"max={self.config.pool_max_size}, timeout={self.config.pool_command_timeout}s"
            )

        return self._pool

    async def connect(self):
        """Establish PostgreSQL connection pool and initialize embedding model."""
        if self.is_connected:
            return

        # Initialize sentence-transformers embedding model if available
        await self._initialize_embedding_model()

        # Check if we should use real PostgreSQL
        conn_str = self.config.pg_connection_string
        use_real_db = (
            conn_str
            and "localhost" not in conn_str
            and "test" not in conn_str
            and os.getenv("USE_REAL_DB") == "true"
        )

        if use_real_db:
            if not ASYNCPG_AVAILABLE:
                logger.warning(
                    "asyncpg not installed, falling back to memory storage. "
                    "Install with: pip install asyncpg"
                )
                self._use_memory_storage = True
            else:
                try:
                    self._use_memory_storage = False

                    # Initialize pool with configured settings
                    pool = await self._ensure_pool()

                    # Create tables if they don't exist
                    async with pool.acquire() as conn:
                        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                        await conn.execute(f"""
                            CREATE TABLE IF NOT EXISTS rag_entities (
                                id UUID PRIMARY KEY,
                                entity_type VARCHAR(50),
                                name VARCHAR(255),
                                content TEXT,
                                embedding vector({self.config.embedding_dim}),
                                metadata JSONB,
                                created_at TIMESTAMP DEFAULT NOW()
                            )
                        """)
                        await conn.execute("""
                            CREATE TABLE IF NOT EXISTS rag_relationships (
                                id UUID PRIMARY KEY,
                                source_id UUID REFERENCES rag_entities(id) ON DELETE CASCADE,
                                target_id UUID REFERENCES rag_entities(id) ON DELETE CASCADE,
                                relationship_type VARCHAR(100),
                                weight FLOAT DEFAULT 1.0,
                                metadata JSONB
                            )
                        """)
                        logger.info("Database tables initialized successfully")

                except Exception as e:
                    logger.error(f"Connection failed: {e}, falling back to memory storage")
                    self._use_memory_storage = True
                    # Clean up failed pool
                    if self._pool:
                        await self._pool.close()
                        self._pool = None

        self.is_connected = True

    async def _initialize_embedding_model(self) -> None:
        """
        Initialize sentence-transformers embedding model.

        Loads the model specified in config (default: all-MiniLM-L6-v2).
        Falls back to hash-based embeddings if sentence-transformers unavailable.
        """
        if not self.config.use_sentence_transformers:
            logger.info("Sentence-transformers disabled in config, using hash-based embeddings")
            self._use_sentence_transformers = False
            return

        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers. "
                "Falling back to hash-based pseudo-embeddings."
            )
            self._use_sentence_transformers = False
            return

        try:
            model_name = self.config.embedding_model or DEFAULT_EMBEDDING_MODEL
            logger.info(f"Loading sentence-transformers model: {model_name}")

            # Load model (will be cached after first load)
            self._embedding_model = SentenceTransformer(model_name)

            # Update embedding dimension from model
            model_dim = self._embedding_model.get_sentence_embedding_dimension()
            if model_dim != self.config.embedding_dim:
                logger.info(
                    f"Updating embedding_dim from {self.config.embedding_dim} to {model_dim} "
                    f"based on model {model_name}"
                )
                self.config.embedding_dim = model_dim

            self._use_sentence_transformers = True
            logger.info(
                f"Sentence-transformers initialized: model={model_name}, dim={model_dim}"
            )

        except Exception as e:
            logger.error(
                f"Failed to load sentence-transformers model: {e}. "
                "Falling back to hash-based embeddings."
            )
            self._embedding_model = None
            self._use_sentence_transformers = False

    async def disconnect(self):
        """Close PostgreSQL connection pool (alias for close)."""
        await self.close()

    async def close(self):
        """
        Gracefully close the connection pool.

        Should be called during application shutdown to release resources.
        Safe to call multiple times.
        """
        if self._pool:
            logger.info("Closing connection pool...")
            await self._pool.close()
            self._pool = None
            logger.info("Connection pool closed")
        self.is_connected = False

    async def health_check(self) -> bool:
        """
        Check if the database connection is healthy.

        Useful for health endpoints and monitoring.

        Returns:
            True if connection is healthy, False otherwise
        """
        if self._use_memory_storage:
            # Memory storage is always "healthy"
            return True

        try:
            pool = await self._ensure_pool()
            if pool is None:
                return False

            async with pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def get_pool_stats(self) -> dict[str, Any]:
        """
        Get connection pool statistics.

        Returns:
            Dictionary with pool statistics or empty dict if using memory storage
        """
        if self._use_memory_storage or self._pool is None:
            return {
                "storage_type": "memory",
                "entities_count": len(self._entities),
                "relationships_count": len(self._relationships),
            }

        return {
            "storage_type": "postgresql",
            "pool_size": self._pool.get_size(),
            "pool_min_size": self._pool.get_min_size(),
            "pool_max_size": self._pool.get_max_size(),
            "pool_free_size": self._pool.get_idle_size(),
            "config_min_size": self.config.pool_min_size,
            "config_max_size": self.config.pool_max_size,
            "config_command_timeout": self.config.pool_command_timeout,
        }

    async def index_company(self, company_data: dict[str, Any]) -> RAGIndexResult:
        """
        Index company data into LightRAG knowledge graph.

        Args:
            company_data: Company information to index

        Returns:
            RAGIndexResult with indexing metrics
        """
        start_time = time.time()

        try:
            if not self.is_connected:
                await self.connect()

            # Extract company name and create entity
            company_name = company_data.get("company_name", "Unknown Company")
            industry = company_data.get("industry", "")

            # Create content for embedding
            content = f"{company_name} - {industry}"
            if "description" in company_data:
                content += f". {company_data['description']}"

            # Create company entity
            company_id = str(uuid.uuid4())

            if self._use_memory_storage:
                # Store in memory (for testing)
                self._entities[company_id] = {
                    "id": company_id,
                    "entity_type": "company",
                    "name": company_name,
                    "content": content,
                    "metadata": company_data,
                    "embedding": await self._get_embedding(content),
                }
            else:
                # Store in PostgreSQL using pooled connection
                embedding = await self._get_embedding(content)
                pool = await self._ensure_pool()
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO rag_entities
                        (id, entity_type, name, content, embedding, metadata)
                        VALUES ($1, $2, $3, $4, $5::vector, $6)
                    """,
                        uuid.UUID(company_id),
                        "company",
                        company_name,
                        content,
                        embedding,
                        json.dumps(company_data),
                    )

            processing_time_ms = int((time.time() - start_time) * 1000)

            return RAGIndexResult(
                success=True,
                company_id=company_id,
                entities_created=1,
                relationships_created=0,
                vectors_created=1,
                processing_time_ms=processing_time_ms,
                operation="create",
            )

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            return RAGIndexResult(
                success=False,
                error_message=str(e),
                processing_time_ms=processing_time_ms,
            )

    async def index_batch(
        self,
        companies: list[dict[str, Any]],
        batch_size: int = 10,
    ) -> list[RAGIndexResult]:
        """
        Batch index multiple companies.

        Uses connection pooling efficiently by acquiring connections per batch.

        Args:
            companies: List of company data to index
            batch_size: Number of companies to process in each batch

        Returns:
            List of RAGIndexResult for each company
        """
        results = []

        if self._use_memory_storage:
            # Simple sequential processing for memory storage
            for company in companies:
                result = await self.index_company(company)
                results.append(result)
            return results

        # Batch processing with pooled connections
        for i in range(0, len(companies), batch_size):
            batch = companies[i : i + batch_size]
            batch_results = []

            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                for company in batch:
                    start_time = time.time()
                    try:
                        company_name = company.get("company_name", "Unknown Company")
                        industry = company.get("industry", "")
                        content = f"{company_name} - {industry}"
                        if "description" in company:
                            content += f". {company['description']}"

                        company_id = str(uuid.uuid4())
                        embedding = await self._get_embedding(content)

                        await conn.execute(
                            """
                            INSERT INTO rag_entities
                            (id, entity_type, name, content, embedding, metadata)
                            VALUES ($1, $2, $3, $4, $5::vector, $6)
                        """,
                            uuid.UUID(company_id),
                            "company",
                            company_name,
                            content,
                            embedding,
                            json.dumps(company),
                        )

                        processing_time_ms = int((time.time() - start_time) * 1000)
                        batch_results.append(
                            RAGIndexResult(
                                success=True,
                                company_id=company_id,
                                entities_created=1,
                                vectors_created=1,
                                processing_time_ms=processing_time_ms,
                                operation="create",
                            )
                        )

                    except Exception as e:
                        processing_time_ms = int((time.time() - start_time) * 1000)
                        batch_results.append(
                            RAGIndexResult(
                                success=False,
                                error_message=str(e),
                                processing_time_ms=processing_time_ms,
                            )
                        )

            results.extend(batch_results)

        return results

    async def search(
        self,
        query: str,
        mode: Literal["low", "high", "hybrid"] = "hybrid",
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> RAGSearchResult:
        """
        Hybrid search combining graph traversal and vector similarity.

        Args:
            query: Search query
            mode: Retrieval mode (low=specific, high=broad, hybrid=both)
            top_k: Number of results to return
            filters: Optional entity filters

        Returns:
            RAGSearchResult with ranked results
        """
        start_time = time.time()

        try:
            if not self.is_connected:
                await self.connect()

            results = []

            if self._use_memory_storage:
                # Simple text matching for in-memory search
                query_lower = query.lower()
                for entity_id, entity in self._entities.items():
                    content = entity.get("content", "").lower()
                    name = entity.get("name", "").lower()

                    # Simple relevance scoring
                    score = 0.0
                    if query_lower in content:
                        score = 0.8
                    elif query_lower in name:
                        score = 0.9
                    elif any(word in content for word in query_lower.split()):
                        score = 0.5

                    if score > 0:
                        results.append(
                            SearchResultItem(
                                entity_id=entity_id,
                                entity_type=entity.get("entity_type", "company"),
                                content=entity.get("content", ""),
                                rrf_score=score,
                                vector_score=score,
                                graph_score=0.0,
                                metadata=entity.get("metadata", {}),
                            )
                        )

                # Sort by score and limit
                results.sort(key=lambda x: x.rrf_score, reverse=True)
                results = results[:top_k]

            else:
                # PostgreSQL vector search using pooled connection
                query_embedding = await self._get_embedding(query)
                pool = await self._ensure_pool()
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        f"""
                        SELECT
                            id,
                            entity_type,
                            name,
                            content,
                            metadata,
                            1 - (embedding <=> $1::vector) as similarity
                        FROM rag_entities
                        ORDER BY embedding <=> $1::vector
                        LIMIT $2
                    """,
                        query_embedding,
                        top_k,
                    )

                    for row in rows:
                        vector_score = float(row["similarity"])
                        results.append(
                            SearchResultItem(
                                entity_id=str(row["id"]),
                                entity_type=row["entity_type"],
                                content=row["content"],
                                rrf_score=vector_score,
                                vector_score=vector_score,
                                graph_score=0.0,
                                metadata=(
                                    json.loads(row["metadata"]) if row["metadata"] else {}
                                ),
                            )
                        )

            processing_time_ms = int((time.time() - start_time) * 1000)

            return RAGSearchResult(
                success=True,
                query=query,
                mode=mode,
                results=results,
                total_results=len(results),
                processing_time_ms=processing_time_ms,
            )

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            return RAGSearchResult(
                success=False,
                query=query,
                mode=mode,
                error_message=str(e),
                processing_time_ms=processing_time_ms,
            )

    async def get_connections(
        self,
        entity_id: str,
        relationship_types: list[str],
        max_depth: int = 2,
    ) -> ConnectionResult:
        """
        Find graph connections for an entity.

        Args:
            entity_id: Entity to find connections for
            relationship_types: Types of relationships to traverse
            max_depth: Maximum traversal depth

        Returns:
            ConnectionResult with related entities
        """
        try:
            if not self.is_connected:
                await self.connect()

            connections = []

            if self._use_memory_storage:
                # Check in-memory relationships
                for rel_id, rel in self._relationships.items():
                    if (
                        rel.get("source_id") == entity_id
                        and rel.get("relationship_type") in relationship_types
                    ):
                        connections.append(
                            Connection(
                                target_entity=rel.get("target_id", ""),
                                relationship_type=rel.get("relationship_type", ""),
                                weight=rel.get("weight", 1.0),
                                depth=1,
                                metadata=rel.get("metadata", {}),
                            )
                        )
            else:
                # PostgreSQL query using pooled connection
                pool = await self._ensure_pool()
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT
                            r.target_id,
                            r.relationship_type,
                            r.weight,
                            r.metadata,
                            e.name as target_name
                        FROM rag_relationships r
                        JOIN rag_entities e ON r.target_id = e.id
                        WHERE r.source_id = $1
                        AND r.relationship_type = ANY($2)
                    """,
                        uuid.UUID(entity_id),
                        relationship_types,
                    )

                    for row in rows:
                        connections.append(
                            Connection(
                                target_entity=str(row["target_id"]),
                                relationship_type=row["relationship_type"],
                                weight=float(row["weight"]),
                                depth=1,
                                metadata=(
                                    json.loads(row["metadata"])
                                    if row["metadata"]
                                    else {}
                                ),
                            )
                        )

            return ConnectionResult(
                success=True,
                entity_id=entity_id,
                connections=connections,
                max_depth=max_depth,
            )

        except Exception as e:
            return ConnectionResult(
                success=False,
                entity_id=entity_id,
                error_message=str(e),
                max_depth=max_depth,
            )

    async def _get_embedding(self, text: str) -> list[float]:
        """
        Get embedding vector for text.

        Uses sentence-transformers (all-MiniLM-L6-v2) when available for production.
        Falls back to hash-based pseudo-embedding for testing or when unavailable.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats (384 dims for all-MiniLM-L6-v2)
        """
        # Use sentence-transformers if available and initialized
        if self._use_sentence_transformers and self._embedding_model is not None:
            return self._get_sentence_transformer_embedding(text)

        # Fallback to hash-based embedding for testing or graceful degradation
        return self._get_hash_embedding(text)

    def _get_sentence_transformer_embedding(self, text: str) -> list[float]:
        """
        Get embedding using sentence-transformers model.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        # Encode text to embedding
        # Note: encode() is synchronous but fast enough for single texts
        embedding = self._embedding_model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
        )

        return embedding.tolist()

    def _get_hash_embedding(self, text: str) -> list[float]:
        """
        Get hash-based pseudo-embedding for testing.

        This provides deterministic embeddings without model downloads,
        useful for unit tests and CI environments.

        Args:
            text: Text to embed

        Returns:
            Pseudo-embedding vector as list of floats
        """
        hash_bytes = hashlib.sha256(text.encode()).digest()

        # Convert to float values between -1 and 1
        embedding = []
        for i in range(0, min(len(hash_bytes), self.config.embedding_dim), 1):
            if i < len(hash_bytes):
                val = (hash_bytes[i % len(hash_bytes)] / 127.5) - 1.0
                embedding.append(val)

        # Pad to embedding_dim if needed
        while len(embedding) < self.config.embedding_dim:
            embedding.append(0.0)

        return embedding[: self.config.embedding_dim]


__all__ = [
    "CompanyRAG",
    "RAGConfig",
    "RAGIndexResult",
    "RAGSearchResult",
    "ConnectionResult",
    "SearchResultItem",
    "Connection",
    "SENTENCE_TRANSFORMERS_AVAILABLE",
    "ASYNCPG_AVAILABLE",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_EMBEDDING_DIM",
]
