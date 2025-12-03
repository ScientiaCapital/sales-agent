"""Budget Tracker - Per-Batch Cost Limits."""

from typing import Dict
from redis.asyncio import Redis


class BudgetTracker:
    """Tracks and enforces per-batch budget limits.

    Uses Redis hash to track:
    - spent_usd: Current spend (atomic HINCRBYFLOAT)
    - limit_usd: Budget limit
    - total_companies: Batch size
    - processed: Companies processed
    - stop_reason: Why batch stopped (if any)
    """

    def __init__(self, redis: Redis, batch_id: str, limit_usd: float):
        """Initialize budget tracker.

        Args:
            redis: Async Redis client
            batch_id: Unique batch identifier
            limit_usd: Maximum spend allowed for batch
        """
        self.redis = redis
        self.batch_id = batch_id
        self.limit_usd = limit_usd

    def _key(self) -> str:
        """Redis hash key for this batch."""
        return f"budget:{self.batch_id}"

    async def init_batch(self, total_companies: int) -> None:
        """Initialize batch budget tracking.

        Args:
            total_companies: Total number of companies in batch
        """
        key = self._key()
        await self.redis.hset(
            key,
            mapping={
                "spent_usd": "0.0",
                "limit_usd": str(self.limit_usd),
                "total_companies": str(total_companies),
                "processed": "0",
                "stop_reason": "",
            }
        )
        # Expire after 7 days to prevent Redis bloat
        await self.redis.expire(key, 7 * 24 * 60 * 60)

    async def add_cost(self, cost_usd: float) -> float:
        """Atomically add cost to batch total.

        Uses HINCRBYFLOAT for atomic increment - fixes race condition
        from read-modify-write pattern.

        Args:
            cost_usd: Cost to add (e.g., 0.05 for one API call)

        Returns:
            New total spent
        """
        key = self._key()
        new_total = await self.redis.hincrbyfloat(key, "spent_usd", cost_usd)
        return float(new_total)

    async def increment_processed(self) -> int:
        """Atomically increment processed count.

        Returns:
            New processed count
        """
        key = self._key()
        new_count = await self.redis.hincrby(key, "processed", 1)
        return int(new_count)

    async def can_proceed(self) -> bool:
        """Check if batch can continue processing.

        Returns:
            True if under budget, False if over budget
        """
        key = self._key()
        spent_bytes = await self.redis.hget(key, "spent_usd")

        if spent_bytes is None:
            # Batch not initialized - assume can proceed
            return True

        spent = float(spent_bytes)
        return spent < self.limit_usd

    async def get_status(self) -> Dict:
        """Get current batch budget status.

        Returns:
            Dict with spent_usd, limit_usd, processed, total_companies, stop_reason
        """
        key = self._key()
        data = await self.redis.hgetall(key)

        if not data:
            return {
                "spent_usd": 0.0,
                "limit_usd": self.limit_usd,
                "processed": 0,
                "total_companies": 0,
                "stop_reason": "not_initialized",
            }

        return {
            "spent_usd": float(data.get(b"spent_usd", b"0.0")),
            "limit_usd": float(data.get(b"limit_usd", str(self.limit_usd).encode())),
            "processed": int(data.get(b"processed", b"0")),
            "total_companies": int(data.get(b"total_companies", b"0")),
            "stop_reason": data.get(b"stop_reason", b"").decode(),
        }

    async def set_stop_reason(self, reason: str) -> None:
        """Set reason for batch stopping.

        Args:
            reason: Human-readable stop reason (e.g., "budget_exceeded", "user_paused")
        """
        key = self._key()
        await self.redis.hset(key, "stop_reason", reason)
