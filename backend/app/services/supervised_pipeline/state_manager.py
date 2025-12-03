"""State Manager - Redis + Supabase State Tracking."""

import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone


class StateManager:
    """Manages enrichment state in Redis and Supabase.

    State tracking:
    - Redis: Real-time status per company (stages, retries)
    - Supabase: Persistent completion flags + cost tracking

    Redis Hash Structure per company:
    {
        "stage": "current_stage_name",
        "apollo_free": "done|running|failed|pending",
        "linkedin": "done|running|failed|pending",
        "hunter_email": "done|running|failed|pending",
        "apollo_paid": "done|running|failed|pending",
        "manual_call": "done|running|failed|pending",
        "total_cost_usd": "0.00",
        "last_updated": "2025-12-02T10:30:00Z",
        "error": "error message if failed"
    }
    """

    def __init__(self, redis, supabase):
        """Initialize StateManager.

        Args:
            redis: Redis async client
            supabase: Supabase client
        """
        self.redis = redis
        self.supabase = supabase

    def _key(self, company_id: str) -> str:
        """Generate Redis key for company state.

        Args:
            company_id: Company UUID

        Returns:
            Redis key string
        """
        return f"enrichment:state:{company_id}"

    async def init_company(self, company_id: str) -> None:
        """Initialize state tracking for a company.

        Args:
            company_id: Company UUID
        """
        key = self._key(company_id)
        await self.redis.hset(
            key,
            mapping={
                "stage": "apollo_free",
                "apollo_free": "pending",
                "linkedin": "pending",
                "hunter_email": "pending",
                "apollo_paid": "pending",
                "manual_call": "pending",
                "total_cost_usd": "0.00",
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def update_stage_status(
        self,
        company_id: str,
        stage: str,
        status: str,
        cost_usd: float = 0.0
    ) -> None:
        """Update stage status in Redis.

        Args:
            company_id: Company UUID
            stage: Stage name (apollo_free, linkedin, etc.)
            status: Status (done, running, failed, pending)
            cost_usd: Cost incurred for this stage
        """
        key = self._key(company_id)

        # Get current total cost
        current_cost = await self.redis.hget(key, "total_cost_usd")
        if current_cost:
            total_cost = float(current_cost) + cost_usd
        else:
            total_cost = cost_usd

        # Update stage status and metadata
        await self.redis.hset(
            key,
            mapping={
                stage: status,
                "total_cost_usd": str(total_cost),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        )

        # If stage is now running, update current stage
        if status == "running":
            await self.redis.hset(key, "stage", stage)

    async def get_company_status(self, company_id: str) -> Dict[str, str]:
        """Get company enrichment status from Redis.

        Args:
            company_id: Company UUID

        Returns:
            Dictionary with stage statuses
        """
        key = self._key(company_id)
        status_bytes = await self.redis.hgetall(key)

        # Convert bytes to strings
        status = {}
        for k, v in status_bytes.items():
            key_str = k.decode('utf-8') if isinstance(k, bytes) else k
            val_str = v.decode('utf-8') if isinstance(v, bytes) else v
            status[key_str] = val_str

        return status

    async def sync_to_supabase(
        self,
        company_id: str,
        stage: str,
        cost_usd: float = 0.0
    ) -> None:
        """Sync completion status to Supabase.

        Updates dim_companies with:
        - enrichment_{stage}_completed = True
        - enrichment_{stage}_cost_usd = cost
        - enrichment_last_updated = now

        Args:
            company_id: Company UUID
            stage: Stage name
            cost_usd: Cost for this stage
        """
        update_data = {
            f"enrichment_{stage}_completed": True,
            f"enrichment_{stage}_cost_usd": cost_usd,
            "enrichment_last_updated": datetime.now(timezone.utc).isoformat(),
        }

        self.supabase.table("dim_companies").update(update_data).eq(
            "id", company_id
        ).execute()

    async def mark_complete(self, company_id: str) -> None:
        """Mark entire enrichment pipeline as complete.

        Args:
            company_id: Company UUID
        """
        # Get final cost
        status = await self.get_company_status(company_id)
        total_cost = float(status.get("total_cost_usd", 0.0))

        # Update Supabase
        self.supabase.table("dim_companies").update({
            "enrichment_pipeline_completed": True,
            "enrichment_total_cost_usd": total_cost,
            "enrichment_completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", company_id).execute()

        # Update Redis
        key = self._key(company_id)
        await self.redis.hset(
            key,
            mapping={
                "stage": "complete",
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def mark_failed(self, company_id: str, error: str) -> None:
        """Mark pipeline as failed with error.

        Args:
            company_id: Company UUID
            error: Error message
        """
        key = self._key(company_id)
        await self.redis.hset(
            key,
            mapping={
                "stage": "failed",
                "error": error,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Optionally sync to Supabase
        self.supabase.table("dim_companies").update({
            "enrichment_pipeline_failed": True,
            "enrichment_error": error,
            "enrichment_last_updated": datetime.now(timezone.utc).isoformat(),
        }).eq("id", company_id).execute()

    async def cleanup(self, company_id: str) -> None:
        """Remove Redis state after completion.

        Args:
            company_id: Company UUID
        """
        key = self._key(company_id)
        await self.redis.delete(key)

    async def get_current_stage(self, company_id: str) -> Optional[str]:
        """Get the current stage for a company.

        Args:
            company_id: Company UUID

        Returns:
            Current stage name or None
        """
        key = self._key(company_id)
        stage = await self.redis.hget(key, "stage")
        if stage:
            return stage.decode('utf-8') if isinstance(stage, bytes) else stage
        return None

    async def get_total_cost(self, company_id: str) -> float:
        """Get total enrichment cost for a company.

        Args:
            company_id: Company UUID

        Returns:
            Total cost in USD
        """
        key = self._key(company_id)
        cost = await self.redis.hget(key, "total_cost_usd")
        if cost:
            cost_str = cost.decode('utf-8') if isinstance(cost, bytes) else cost
            return float(cost_str)
        return 0.0
