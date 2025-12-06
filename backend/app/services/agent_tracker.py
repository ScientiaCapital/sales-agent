"""
Agent Execution Tracker

Tracks agent runs, status, and history in Redis for BDR Cockpit dashboards.
Provides real-time agent status monitoring and historical execution data.
"""

from typing import Optional, List
from redis import asyncio as aioredis
import json
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)

# Redis key prefixes
KEY_PREFIX_RUN = "agent:run:"          # agent:run:{agent_name}:{task_id}
KEY_PREFIX_LAST = "agent:last:"        # agent:last:{agent_name}
KEY_PREFIX_STATS = "agent:stats:"      # agent:stats:{agent_name}:{date}
KEY_PREFIX_STATUS = "agent:status:"    # agent:status:{agent_name}


class AgentTracker:
    """
    Redis-backed agent execution tracker.

    Tracks:
    - Current status (running/idle/error)
    - Last run time and result
    - Today's run count and error count
    - Recent execution history (last 100 runs per agent)
    """

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize tracker with Redis connection."""
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis: Optional[aioredis.Redis] = None
        self.history_limit = 100  # Keep last 100 runs per agent
        self.history_ttl = timedelta(days=7)  # Expire history after 7 days

    async def _get_redis(self) -> Optional[aioredis.Redis]:
        """Get Redis client with lazy initialization."""
        if self._redis is None:
            try:
                self._redis = await aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
                await self._redis.ping()
                logger.info("AgentTracker: Redis connection established")
            except Exception as e:
                logger.error(f"AgentTracker: Redis connection failed: {e}")
                return None
        return self._redis

    async def record_start(
        self,
        agent_name: str,
        task_id: str,
        args: Optional[dict] = None
    ) -> bool:
        """
        Record agent start event.

        Args:
            agent_name: Name of the agent (e.g., 'lead_scout')
            task_id: Celery task ID
            args: Task arguments

        Returns:
            True if recorded successfully
        """
        try:
            redis = await self._get_redis()
            if not redis:
                return False

            now = datetime.utcnow()
            today = now.strftime("%Y-%m-%d")

            run_data = {
                "task_id": task_id,
                "agent_name": agent_name,
                "status": "running",
                "started_at": now.isoformat(),
                "args": args or {}
            }

            # Store current run
            run_key = f"{KEY_PREFIX_RUN}{agent_name}:{task_id}"
            await redis.setex(
                run_key,
                int(self.history_ttl.total_seconds()),
                json.dumps(run_data)
            )

            # Update current status
            status_key = f"{KEY_PREFIX_STATUS}{agent_name}"
            await redis.set(status_key, json.dumps({
                "status": "running",
                "task_id": task_id,
                "started_at": now.isoformat()
            }))

            # Increment today's run count
            stats_key = f"{KEY_PREFIX_STATS}{agent_name}:{today}"
            await redis.hincrby(stats_key, "runs", 1)
            await redis.expire(stats_key, int(timedelta(days=2).total_seconds()))

            logger.info(f"AgentTracker: Recorded start for {agent_name} ({task_id})")
            return True

        except Exception as e:
            logger.error(f"AgentTracker: Failed to record start: {e}")
            return False

    async def record_completion(
        self,
        agent_name: str,
        task_id: str,
        result: Optional[dict] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Record agent completion event.

        Args:
            agent_name: Name of the agent
            task_id: Celery task ID
            result: Task result (if successful)
            error: Error message (if failed)

        Returns:
            True if recorded successfully
        """
        try:
            redis = await self._get_redis()
            if not redis:
                return False

            now = datetime.utcnow()
            today = now.strftime("%Y-%m-%d")

            # Get start time from run record
            run_key = f"{KEY_PREFIX_RUN}{agent_name}:{task_id}"
            run_data_raw = await redis.get(run_key)

            if run_data_raw:
                run_data = json.loads(run_data_raw)
                started_at = datetime.fromisoformat(run_data["started_at"])
                duration_ms = int((now - started_at).total_seconds() * 1000)
            else:
                duration_ms = None

            # Determine final status
            status = "failed" if error else "completed"

            # Update run record
            completed_data = {
                "task_id": task_id,
                "agent_name": agent_name,
                "status": status,
                "started_at": run_data.get("started_at") if run_data_raw else now.isoformat(),
                "completed_at": now.isoformat(),
                "duration_ms": duration_ms,
                "result": result,
                "error": error
            }

            await redis.setex(
                run_key,
                int(self.history_ttl.total_seconds()),
                json.dumps(completed_data)
            )

            # Update last run record
            last_key = f"{KEY_PREFIX_LAST}{agent_name}"
            await redis.set(last_key, json.dumps(completed_data))

            # Update status to idle
            status_key = f"{KEY_PREFIX_STATUS}{agent_name}"
            await redis.set(status_key, json.dumps({
                "status": "idle",
                "last_run_at": now.isoformat(),
                "last_status": status
            }))

            # Add to history list (prepend)
            history_key = f"agent:history:{agent_name}"
            await redis.lpush(history_key, json.dumps(completed_data))
            await redis.ltrim(history_key, 0, self.history_limit - 1)
            await redis.expire(history_key, int(self.history_ttl.total_seconds()))

            # Increment error count if failed
            if error:
                stats_key = f"{KEY_PREFIX_STATS}{agent_name}:{today}"
                await redis.hincrby(stats_key, "errors", 1)

            logger.info(f"AgentTracker: Recorded completion for {agent_name} ({task_id}) - {status}")
            return True

        except Exception as e:
            logger.error(f"AgentTracker: Failed to record completion: {e}")
            return False

    async def get_agent_status(self, agent_name: str) -> dict:
        """
        Get current status for an agent.

        Returns:
            Dict with status, last_run, runs_today, errors_today
        """
        try:
            redis = await self._get_redis()
            if not redis:
                return {"status": "unknown", "connected": False}

            today = datetime.utcnow().strftime("%Y-%m-%d")

            # Get current status
            status_key = f"{KEY_PREFIX_STATUS}{agent_name}"
            status_raw = await redis.get(status_key)

            if status_raw:
                status_data = json.loads(status_raw)
            else:
                status_data = {"status": "idle"}

            # Get last run
            last_key = f"{KEY_PREFIX_LAST}{agent_name}"
            last_raw = await redis.get(last_key)
            last_run = json.loads(last_raw) if last_raw else None

            # Get today's stats
            stats_key = f"{KEY_PREFIX_STATS}{agent_name}:{today}"
            stats = await redis.hgetall(stats_key)

            return {
                "status": status_data.get("status", "idle"),
                "current_task_id": status_data.get("task_id"),
                "last_run": last_run,
                "last_run_at": last_run.get("completed_at") if last_run else None,
                "runs_today": int(stats.get("runs", 0)),
                "errors_today": int(stats.get("errors", 0))
            }

        except Exception as e:
            logger.error(f"AgentTracker: Failed to get status: {e}")
            return {"status": "unknown", "error": str(e)}

    async def get_agent_history(
        self,
        agent_name: str,
        limit: int = 20
    ) -> List[dict]:
        """
        Get recent execution history for an agent.

        Args:
            agent_name: Name of the agent
            limit: Maximum number of runs to return

        Returns:
            List of run records (newest first)
        """
        try:
            redis = await self._get_redis()
            if not redis:
                return []

            history_key = f"agent:history:{agent_name}"
            raw_items = await redis.lrange(history_key, 0, limit - 1)

            return [json.loads(item) for item in raw_items]

        except Exception as e:
            logger.error(f"AgentTracker: Failed to get history: {e}")
            return []

    async def get_all_agent_statuses(self, agent_names: List[str]) -> dict:
        """
        Get statuses for multiple agents efficiently.

        Args:
            agent_names: List of agent names

        Returns:
            Dict mapping agent_name to status dict
        """
        results = {}
        for name in agent_names:
            results[name] = await self.get_agent_status(name)
        return results

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


# Global tracker instance
_tracker: Optional[AgentTracker] = None


def get_agent_tracker() -> AgentTracker:
    """Get or create global AgentTracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = AgentTracker()
    return _tracker


async def close_agent_tracker():
    """Close global tracker connection."""
    global _tracker
    if _tracker:
        await _tracker.close()
        _tracker = None
