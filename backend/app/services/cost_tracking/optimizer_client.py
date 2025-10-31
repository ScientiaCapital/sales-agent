"""
Cost Optimizer Client - Integration with ai-cost-optimizer Service

Provides async HTTP client for logging agent execution costs to ai-cost-optimizer
for real-time cost tracking, optimization recommendations, and dashboards.

The ai-cost-optimizer service:
- Tracks all LLM API calls with token counts and costs
- Provides provider recommendations based on complexity
- Maintains cost statistics and trends
- Offers caching for duplicate prompts
- Generates cost insights and optimization suggestions

Usage:
    ```python
    from app.services.cost_tracking import get_cost_optimizer

    # Get singleton client
    optimizer = await get_cost_optimizer()

    # Log LLM call
    await optimizer.log_llm_call(
        provider="cerebras",
        model="llama3.1-8b",
        prompt="Qualify this lead...",
        response="Hot lead, score: 95...",
        tokens_in=50,
        tokens_out=30,
        cost_usd=0.000006,
        agent_name="qualification",
        metadata={"lead_id": 123}
    )

    # Get real-time stats
    stats = await optimizer.get_stats()
    print(f"Total cost today: ${stats['overall']['total_cost']}")
    ```

Features:
- Async HTTP client (non-blocking)
- Automatic batching for high throughput
- Singleton pattern for connection pooling
- Cache hit/miss tracking
- Real-time cost statistics
- Provider recommendations
"""

import os
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from dataclasses import dataclass, field

import httpx
from pydantic import BaseModel

from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ========== Models ==========

class LLMCallLog(BaseModel):
    """Model for logging LLM API calls."""
    provider: str  # cerebras, claude, deepseek, ollama
    model: str  # llama3.1-8b, claude-3-5-haiku, deepseek-chat
    prompt: str
    response: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    agent_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CacheHitLog(BaseModel):
    """Model for logging cache hits."""
    cache_type: str  # linkedin, qualification
    cache_key: str
    savings_usd: float
    latency_saved_ms: int
    agent_name: Optional[str] = None


class AgentExecutionLog(BaseModel):
    """Model for logging complete agent executions."""
    agent_name: str
    agent_type: str  # qualification, enrichment, growth, marketing
    latency_ms: int
    cost_usd: float
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ========== Cost Optimizer Client ==========

class CostOptimizerClient:
    """
    Async HTTP client for ai-cost-optimizer service.

    Provides methods for:
    - Logging LLM calls with costs
    - Tracking cache hits and savings
    - Retrieving real-time statistics
    - Getting provider recommendations
    - Batching requests for performance

    Singleton pattern ensures connection pooling and efficient resource usage.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
        enable_batching: bool = True,
        batch_size: int = 10,
        batch_interval_seconds: float = 1.0
    ):
        """
        Initialize Cost Optimizer Client.

        Args:
            base_url: URL of ai-cost-optimizer service (default: from env or localhost:8000)
            timeout: HTTP request timeout in seconds
            enable_batching: Enable request batching for performance
            batch_size: Max requests per batch
            batch_interval_seconds: Max time to wait before flushing batch
        """
        self.base_url = base_url or os.getenv("AI_COST_OPTIMIZER_URL", "http://localhost:8000")
        self.timeout = timeout
        self.enable_batching = enable_batching
        self.batch_size = batch_size
        self.batch_interval_seconds = batch_interval_seconds

        # HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )

        # Batching queue
        self._batch_queue: List[Dict[str, Any]] = []
        self._batch_lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None

        # Statistics
        self.total_calls = 0
        self.total_cost_logged = 0.0
        self.total_cache_savings = 0.0
        self.failed_requests = 0

        logger.info(f"Cost Optimizer Client initialized: {self.base_url}")

    async def close(self):
        """Close HTTP client and flush pending batches."""
        if self.enable_batching:
            await self._flush_batch()
        await self.client.aclose()

    # ========== Core Logging Methods ==========

    async def log_llm_call(
        self,
        provider: str,
        model: str,
        prompt: str,
        response: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        agent_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Log LLM API call to ai-cost-optimizer.

        Args:
            provider: LLM provider (cerebras, claude, deepseek, ollama)
            model: Model ID
            prompt: Input prompt
            response: Model response
            tokens_in: Input token count
            tokens_out: Output token count
            cost_usd: Cost in USD
            agent_name: Name of agent making the call
            metadata: Additional metadata

        Returns:
            Response from optimizer or None if batched
        """
        try:
            # Track statistics
            self.total_calls += 1
            self.total_cost_logged += cost_usd

            # Prepare payload
            payload = {
                "prompt": prompt,
                "max_tokens": tokens_out,  # Approximate
                "provider": provider,
                "model": model,
                "response": response,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost": cost_usd,
                "agent_name": agent_name,
                "metadata": metadata or {}
            }

            if self.enable_batching:
                # Add to batch queue
                async with self._batch_lock:
                    self._batch_queue.append(("llm_call", payload))
                    if len(self._batch_queue) >= self.batch_size:
                        await self._flush_batch()
                return None
            else:
                # Send immediately (not actually used by ai-cost-optimizer /complete,
                # but we'll use it for logging purposes)
                response = await self.client.post("/complete", json=payload)
                response.raise_for_status()
                return response.json()

        except Exception as e:
            self.failed_requests += 1
            logger.error(f"Failed to log LLM call to optimizer: {e}")
            return None

    async def log_cache_hit(
        self,
        cache_type: str,
        cache_key: str,
        savings_usd: float,
        latency_saved_ms: int,
        agent_name: Optional[str] = None
    ) -> bool:
        """
        Log cache hit and cost savings.

        Args:
            cache_type: Type of cache (linkedin, qualification)
            cache_key: Cache key that was hit
            savings_usd: Money saved by cache hit
            latency_saved_ms: Time saved in milliseconds
            agent_name: Name of agent

        Returns:
            True if logged successfully
        """
        try:
            self.total_cache_savings += savings_usd

            # Log as metadata (ai-cost-optimizer doesn't have dedicated cache endpoint)
            logger.info(
                f"💾 Cache Hit Logged: {cache_type}:{cache_key[:50]} "
                f"(saved ${savings_usd}, {latency_saved_ms}ms, agent={agent_name})"
            )

            # Could POST to custom endpoint if we add one to ai-cost-optimizer
            return True

        except Exception as e:
            logger.error(f"Failed to log cache hit: {e}")
            return False

    async def log_agent_execution(
        self,
        agent_name: str,
        agent_type: str,
        latency_ms: int,
        cost_usd: float,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log complete agent execution.

        Args:
            agent_name: Agent name (e.g., "qualification_agent_1")
            agent_type: Agent type (qualification, enrichment, growth, marketing)
            latency_ms: Execution time in milliseconds
            cost_usd: Total cost of execution
            success: Whether execution succeeded
            error_message: Error message if failed
            metadata: Additional context

        Returns:
            True if logged successfully
        """
        try:
            self.total_cost_logged += cost_usd

            logger.info(
                f"📊 Agent Execution Logged: {agent_name} "
                f"(type={agent_type}, latency={latency_ms}ms, cost=${cost_usd:.6f}, success={success})"
            )

            # Could store in local database or send to custom endpoint
            return True

        except Exception as e:
            logger.error(f"Failed to log agent execution: {e}")
            return False

    # ========== Statistics Methods ==========

    async def get_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get overall statistics from ai-cost-optimizer.

        Returns:
            Dict with overall stats, by_provider, by_complexity, recent_requests
        """
        try:
            response = await self.client.get("/stats")
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get stats from optimizer: {e}")
            return None

    async def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get cache statistics from ai-cost-optimizer.

        Returns:
            Dict with cache hit/miss rates and savings
        """
        try:
            response = await self.client.get("/cache/stats")
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return None

    async def get_providers(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get available providers from ai-cost-optimizer.

        Returns:
            List of provider configs with pricing
        """
        try:
            response = await self.client.get("/providers")
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get providers: {e}")
            return None

    async def get_insights(self) -> Optional[Dict[str, Any]]:
        """
        Get cost insights and optimization recommendations.

        Returns:
            Dict with insights, recommendations, cost trends
        """
        try:
            response = await self.client.get("/insights")
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get insights: {e}")
            return None

    async def get_recommendation(
        self,
        prompt: str,
        max_tokens: int = 1000
    ) -> Optional[Dict[str, Any]]:
        """
        Get provider recommendation for a prompt.

        Args:
            prompt: The prompt to analyze
            max_tokens: Expected max tokens

        Returns:
            Dict with recommended provider, model, estimated_cost
        """
        try:
            response = await self.client.get(
                "/recommendation",
                params={"prompt": prompt, "max_tokens": max_tokens}
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get recommendation: {e}")
            return None

    # ========== Batching Methods ==========

    async def _flush_batch(self):
        """Flush pending batch requests."""
        if not self._batch_queue:
            return

        async with self._batch_lock:
            batch = self._batch_queue.copy()
            self._batch_queue.clear()

        logger.debug(f"Flushing batch of {len(batch)} requests")

        # Process batch (simplified - could batch actual HTTP requests)
        for request_type, payload in batch:
            try:
                if request_type == "llm_call":
                    await self.client.post("/complete", json=payload)
            except Exception as e:
                logger.error(f"Batch request failed: {e}")
                self.failed_requests += 1

    async def _start_batch_timer(self):
        """Background task to flush batch periodically."""
        while True:
            await asyncio.sleep(self.batch_interval_seconds)
            await self._flush_batch()

    # ========== Health Check ==========

    async def health_check(self) -> bool:
        """
        Check if ai-cost-optimizer service is healthy.

        Returns:
            True if service is reachable and healthy
        """
        try:
            response = await self.client.get("/health", timeout=2.0)
            return response.status_code == 200

        except Exception as e:
            logger.warning(f"Cost optimizer health check failed: {e}")
            return False

    def get_local_stats(self) -> Dict[str, Any]:
        """
        Get local client statistics.

        Returns:
            Dict with client-side metrics
        """
        return {
            "total_calls_logged": self.total_calls,
            "total_cost_logged_usd": round(self.total_cost_logged, 6),
            "total_cache_savings_usd": round(self.total_cache_savings, 6),
            "failed_requests": self.failed_requests,
            "batching_enabled": self.enable_batching,
            "batch_queue_size": len(self._batch_queue),
        }


# ========== Singleton Instance ==========

_cost_optimizer_client: Optional[CostOptimizerClient] = None


async def get_cost_optimizer(
    base_url: Optional[str] = None,
    enable_batching: bool = True
) -> CostOptimizerClient:
    """
    Get or create singleton CostOptimizerClient.

    Args:
        base_url: Override base URL (default: env or localhost:8000)
        enable_batching: Enable request batching

    Returns:
        CostOptimizerClient instance
    """
    global _cost_optimizer_client

    if _cost_optimizer_client is None:
        _cost_optimizer_client = CostOptimizerClient(
            base_url=base_url,
            enable_batching=enable_batching
        )

        # Check health
        healthy = await _cost_optimizer_client.health_check()
        if healthy:
            logger.info("✅ Connected to ai-cost-optimizer service")
        else:
            logger.warning(
                "⚠️ ai-cost-optimizer service not reachable. "
                "Cost logging will continue but stats unavailable."
            )

    return _cost_optimizer_client
