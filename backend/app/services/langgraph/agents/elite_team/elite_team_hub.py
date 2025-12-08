"""
Elite Team Hub - Inter-Agent Coordination

Coordinates communication between the 3 Elite Squad agents:
- Signal Scout → emits scraping orders → Deep Hunter
- Deep Hunter → exports contractors → Intake Commander
- Intake Commander → routes to BDR queue

Also provides status tracking for dashboard display.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from enum import Enum
from pydantic import BaseModel, Field
import redis

logger = logging.getLogger(__name__)


class EliteAgentStatus(str, Enum):
    """Status states for Elite Team agents"""
    IDLE = "idle"
    WATCHING = "watching"
    HUNTING = "hunting"
    PROCESSING = "processing"
    ERROR = "error"
    SLEEPING = "sleeping"


class AgentMetrics(BaseModel):
    """Metrics for a single Elite agent"""
    agent_name: str
    status: EliteAgentStatus = EliteAgentStatus.IDLE
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    runs_today: int = 0
    success_count: int = 0
    error_count: int = 0
    items_processed: int = 0
    last_error: Optional[str] = None
    current_task: Optional[str] = None
    extra_data: Dict[str, Any] = Field(default_factory=dict)


class ScrapingOrder(BaseModel):
    """Order from Signal Scout to Deep Hunter"""
    order_id: str
    vertical: str
    states: List[str]
    oems: List[str]
    priority: str  # HIGH, MEDIUM, LOW
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""
    sample_companies: List[str] = Field(default_factory=list)


class IntakeItem(BaseModel):
    """Item from Deep Hunter to Intake Commander"""
    company_name: str
    normalized_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    domain: Optional[str] = None
    state: str
    oem_brands: List[str] = Field(default_factory=list)
    source_scraper: str
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EliteTeamState(BaseModel):
    """Global state for the Elite Team"""
    signal_scout: AgentMetrics = Field(
        default_factory=lambda: AgentMetrics(agent_name="signal_scout")
    )
    deep_hunter: AgentMetrics = Field(
        default_factory=lambda: AgentMetrics(agent_name="deep_hunter")
    )
    intake_commander: AgentMetrics = Field(
        default_factory=lambda: AgentMetrics(agent_name="intake_commander")
    )

    # Queues
    pending_scraping_orders: List[ScrapingOrder] = Field(default_factory=list)
    pending_intake_items: int = 0

    # Daily stats
    signals_detected_today: int = 0
    contractors_scraped_today: int = 0
    unicorns_found_today: int = 0
    leads_routed_to_bdr: int = 0
    duplicates_blocked_today: int = 0

    # Last updated
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EliteTeamHub:
    """
    Coordination hub for the Trifecta Hunter Elite Squad.

    Handles:
    - Inter-agent messaging via Redis pub/sub
    - State persistence and retrieval
    - Status reporting for dashboard
    - Scraping order queue management
    """

    REDIS_KEY_PREFIX = "elite_team:"
    STATE_KEY = "elite_team:state"
    ORDERS_KEY = "elite_team:scraping_orders"
    INTAKE_QUEUE_KEY = "elite_team:intake_queue"

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize the Elite Team Hub."""
        import os
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis: Optional[redis.Redis] = None

    @property
    def redis_client(self) -> redis.Redis:
        """Lazy Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    # ========== State Management ==========

    def get_state(self) -> EliteTeamState:
        """Get current Elite Team state."""
        try:
            state_json = self.redis_client.get(self.STATE_KEY)
            if state_json:
                return EliteTeamState.model_validate_json(state_json)
            return EliteTeamState()
        except Exception as e:
            logger.error(f"[EliteHub] Error getting state: {e}")
            return EliteTeamState()

    def save_state(self, state: EliteTeamState) -> None:
        """Save Elite Team state to Redis."""
        try:
            state.updated_at = datetime.now(timezone.utc)
            self.redis_client.set(
                self.STATE_KEY,
                state.model_dump_json(),
                ex=86400  # 24 hour expiry
            )
        except Exception as e:
            logger.error(f"[EliteHub] Error saving state: {e}")

    def update_agent_status(
        self,
        agent_name: str,
        status: EliteAgentStatus,
        current_task: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update status for a specific agent."""
        state = self.get_state()

        agent_metrics = getattr(state, agent_name, None)
        if agent_metrics:
            agent_metrics.status = status
            agent_metrics.current_task = current_task
            agent_metrics.last_run = datetime.now(timezone.utc)
            if extra_data:
                agent_metrics.extra_data.update(extra_data)

            self.save_state(state)
            logger.info(f"[EliteHub] {agent_name} status: {status} - {current_task}")

    def record_agent_run(
        self,
        agent_name: str,
        success: bool,
        items_processed: int = 0,
        error_message: Optional[str] = None
    ) -> None:
        """Record completion of an agent run."""
        state = self.get_state()

        agent_metrics = getattr(state, agent_name, None)
        if agent_metrics:
            agent_metrics.runs_today += 1
            agent_metrics.items_processed += items_processed

            if success:
                agent_metrics.success_count += 1
                agent_metrics.status = EliteAgentStatus.IDLE
            else:
                agent_metrics.error_count += 1
                agent_metrics.last_error = error_message
                agent_metrics.status = EliteAgentStatus.ERROR

            self.save_state(state)

    # ========== Scraping Order Queue ==========

    def emit_scraping_order(self, order: ScrapingOrder) -> None:
        """
        Signal Scout emits a scraping order for Deep Hunter.
        """
        try:
            # Add to Redis list
            self.redis_client.lpush(
                self.ORDERS_KEY,
                order.model_dump_json()
            )

            # Update state
            state = self.get_state()
            state.pending_scraping_orders.append(order)
            state.signals_detected_today += 1
            self.save_state(state)

            # Publish event for listeners
            self.redis_client.publish(
                "elite_team:events",
                json.dumps({
                    "event": "scraping_order_created",
                    "order_id": order.order_id,
                    "vertical": order.vertical,
                    "priority": order.priority
                })
            )

            logger.info(
                f"[EliteHub] Scraping order emitted: {order.vertical} "
                f"({len(order.states)} states, {len(order.oems)} OEMs)"
            )

        except Exception as e:
            logger.error(f"[EliteHub] Error emitting scraping order: {e}")

    def get_next_scraping_order(self) -> Optional[ScrapingOrder]:
        """
        Deep Hunter retrieves the next scraping order.
        """
        try:
            order_json = self.redis_client.rpop(self.ORDERS_KEY)
            if order_json:
                return ScrapingOrder.model_validate_json(order_json)
            return None
        except Exception as e:
            logger.error(f"[EliteHub] Error getting scraping order: {e}")
            return None

    def get_pending_order_count(self) -> int:
        """Get count of pending scraping orders."""
        try:
            return self.redis_client.llen(self.ORDERS_KEY)
        except Exception:
            return 0

    # ========== Intake Queue ==========

    def queue_for_intake(self, items: List[IntakeItem]) -> int:
        """
        Deep Hunter queues items for Intake Commander.
        """
        try:
            pipeline = self.redis_client.pipeline()
            for item in items:
                pipeline.lpush(self.INTAKE_QUEUE_KEY, item.model_dump_json())
            pipeline.execute()

            # Update state
            state = self.get_state()
            state.pending_intake_items += len(items)
            state.contractors_scraped_today += len(items)
            self.save_state(state)

            logger.info(f"[EliteHub] Queued {len(items)} items for intake")
            return len(items)

        except Exception as e:
            logger.error(f"[EliteHub] Error queueing for intake: {e}")
            return 0

    def get_intake_batch(self, batch_size: int = 100) -> List[IntakeItem]:
        """
        Intake Commander retrieves a batch of items to process.
        """
        try:
            items = []
            for _ in range(batch_size):
                item_json = self.redis_client.rpop(self.INTAKE_QUEUE_KEY)
                if item_json:
                    items.append(IntakeItem.model_validate_json(item_json))
                else:
                    break
            return items
        except Exception as e:
            logger.error(f"[EliteHub] Error getting intake batch: {e}")
            return []

    def get_intake_queue_size(self) -> int:
        """Get size of intake queue."""
        try:
            return self.redis_client.llen(self.INTAKE_QUEUE_KEY)
        except Exception:
            return 0

    # ========== Stats Updates ==========

    def record_unicorn_found(self, company_name: str) -> None:
        """Record discovery of a UNICORN (full trifecta) contractor."""
        state = self.get_state()
        state.unicorns_found_today += 1
        self.save_state(state)

        # Publish event
        self.redis_client.publish(
            "elite_team:events",
            json.dumps({
                "event": "unicorn_found",
                "company_name": company_name,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        )

        logger.info(f"[EliteHub] UNICORN FOUND: {company_name}")

    def record_bdr_routing(self, count: int) -> None:
        """Record leads routed to BDR queue."""
        state = self.get_state()
        state.leads_routed_to_bdr += count
        self.save_state(state)

    def record_duplicates_blocked(self, count: int) -> None:
        """Record duplicates blocked by Intake Commander."""
        state = self.get_state()
        state.duplicates_blocked_today += count
        self.save_state(state)

    # ========== Dashboard API ==========

    def get_dashboard_status(self) -> Dict[str, Any]:
        """
        Get Elite Team status for dashboard display.

        Returns formatted data for EliteTeamPanel.tsx
        """
        state = self.get_state()

        return {
            "signal_scout": {
                "name": "Signal Scout",
                "icon": "telescope",
                "status": state.signal_scout.status.value,
                "last_run": state.signal_scout.last_run.isoformat() if state.signal_scout.last_run else None,
                "current_task": state.signal_scout.current_task,
                "signals_detected": state.signals_detected_today,
                "extra": state.signal_scout.extra_data
            },
            "deep_hunter": {
                "name": "Deep Hunter",
                "icon": "search",
                "status": state.deep_hunter.status.value,
                "last_run": state.deep_hunter.last_run.isoformat() if state.deep_hunter.last_run else None,
                "current_task": state.deep_hunter.current_task,
                "scraped_today": state.contractors_scraped_today,
                "extra": state.deep_hunter.extra_data
            },
            "intake_commander": {
                "name": "Intake Commander",
                "icon": "shield-check",
                "status": state.intake_commander.status.value,
                "last_run": state.intake_commander.last_run.isoformat() if state.intake_commander.last_run else None,
                "current_task": state.intake_commander.current_task,
                "queue_size": self.get_intake_queue_size(),
                "unicorns_found": state.unicorns_found_today,
                "duplicates_blocked": state.duplicates_blocked_today,
                "routed_to_bdr": state.leads_routed_to_bdr,
                "extra": state.intake_commander.extra_data
            },
            "summary": {
                "signals_today": state.signals_detected_today,
                "scraped_today": state.contractors_scraped_today,
                "unicorns_today": state.unicorns_found_today,
                "bdr_routed_today": state.leads_routed_to_bdr,
                "duplicates_blocked": state.duplicates_blocked_today,
                "pending_orders": self.get_pending_order_count(),
                "intake_queue": self.get_intake_queue_size(),
            },
            "updated_at": state.updated_at.isoformat()
        }

    def reset_daily_stats(self) -> None:
        """Reset daily statistics (call at midnight)."""
        state = self.get_state()
        state.signals_detected_today = 0
        state.contractors_scraped_today = 0
        state.unicorns_found_today = 0
        state.leads_routed_to_bdr = 0
        state.duplicates_blocked_today = 0

        # Reset agent run counts
        state.signal_scout.runs_today = 0
        state.deep_hunter.runs_today = 0
        state.intake_commander.runs_today = 0

        self.save_state(state)
        logger.info("[EliteHub] Daily stats reset")


# Singleton instance
_hub_instance: Optional[EliteTeamHub] = None


def get_elite_hub() -> EliteTeamHub:
    """Get the singleton Elite Team Hub instance."""
    global _hub_instance
    if _hub_instance is None:
        _hub_instance = EliteTeamHub()
    return _hub_instance


# ========== Exports ==========

__all__ = [
    "EliteTeamHub",
    "EliteTeamState",
    "EliteAgentStatus",
    "AgentMetrics",
    "ScrapingOrder",
    "IntakeItem",
    "get_elite_hub",
]
