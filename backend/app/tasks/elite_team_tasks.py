"""
Celery tasks for the Trifecta Hunter Elite Squad

Wraps the Elite Team agents (Signal Scout, Deep Hunter, Intake Commander)
as Celery tasks for scheduled and on-demand execution.

Elite Squad Mission:
- Signal Scout: Detect emerging market opportunities (hourly at :15)
- Deep Hunter: Hunt contractors based on scraping orders (event-driven)
- Intake Commander: Dedup, score with Trifecta, route to BDR (every 60s)
"""

import os
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_TRACING", "false")

import logging
logging.getLogger("langsmith.client").setLevel(logging.ERROR)
logging.getLogger("langsmith.utils").setLevel(logging.ERROR)

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ========== SIGNAL SCOUT TASK ==========

@celery_app.task(
    name="run_signal_scout",
    bind=True,
    max_retries=2,
    soft_time_limit=300,  # 5 minutes max
    time_limit=360  # Hard limit 6 minutes
)
def run_signal_scout(self) -> Dict[str, Any]:
    """
    Run Signal Scout to detect emerging market opportunities.

    Scans Close CRM and Supabase for patterns like:
    - 3+ leads from a new vertical
    - Win rate spikes in specific categories
    - Geographic clusters (5+ leads same state)
    - Trifecta patterns (multi-service companies)

    Emits scraping orders for Deep Hunter when signals detected.

    Returns:
        Dict with signals detected and scraping orders generated
    """
    try:
        import asyncio
        from app.services.langgraph.agents.elite_team.signal_scout_agent import (
            SignalScoutAgent
        )
        from app.services.langgraph.agents.elite_team.elite_team_hub import (
            get_elite_hub, EliteAgentStatus
        )

        hub = get_elite_hub()
        hub.update_agent_status(
            "signal_scout",
            EliteAgentStatus.WATCHING,
            "Scanning for market signals"
        )

        logger.info("[Signal Scout] Starting market signal scan")

        # Run the agent
        agent = SignalScoutAgent()
        result = asyncio.run(agent.run())

        # Record run
        hub.record_agent_run(
            "signal_scout",
            success=True,
            items_processed=result.get("signals_detected", 0)
        )

        logger.info(f"[Signal Scout] Complete: {result.get('signals_detected', 0)} signals, {result.get('orders_generated', 0)} orders")

        # Emit scraping orders for Deep Hunter
        orders = result.get("scraping_orders", [])
        for order in orders:
            # Queue Deep Hunter task for each order
            process_scraping_order.delay(order)

        return {
            "status": "success",
            "signals_detected": result.get("signals_detected", 0),
            "orders_generated": len(orders),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except SoftTimeLimitExceeded:
        logger.error("[Signal Scout] Task timeout")
        return {"status": "error", "error": "Task timeout"}

    except Exception as e:
        logger.error(f"[Signal Scout] Task failed: {e}")
        try:
            hub = get_elite_hub()
            hub.record_agent_run("signal_scout", success=False, error_message=str(e))
        except Exception:
            pass
        return {"status": "error", "error": str(e)}


# ========== DEEP HUNTER TASK ==========

@celery_app.task(
    name="process_scraping_order",
    bind=True,
    max_retries=2,
    soft_time_limit=1800,  # 30 minutes max (scraping takes time)
    time_limit=2100  # Hard limit 35 minutes
)
def process_scraping_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a scraping order from Signal Scout.

    Deep Hunter orchestrates dealer-scraper-mvp's ScraperFactory
    to hunt contractors based on the order parameters.

    Args:
        order: Scraping order with vertical, states, OEMs to scrape

    Returns:
        Dict with hunt results
    """
    try:
        import asyncio
        from app.services.langgraph.agents.elite_team.deep_hunter_agent import (
            DeepHunterAgent
        )
        from app.services.langgraph.agents.elite_team.elite_team_hub import (
            get_elite_hub, EliteAgentStatus
        )

        hub = get_elite_hub()
        hub.update_agent_status(
            "deep_hunter",
            EliteAgentStatus.HUNTING,
            f"Hunting {order.get('vertical', 'unknown')} in {len(order.get('states', []))} states"
        )

        logger.info(f"[Deep Hunter] Processing order: {order.get('vertical')}")

        # Run the agent
        agent = DeepHunterAgent()
        result = asyncio.run(agent.run(order))

        # Record run
        hub.record_agent_run(
            "deep_hunter",
            success=True,
            items_processed=result.get("contractors_found", 0)
        )

        logger.info(f"[Deep Hunter] Hunt complete: {result.get('contractors_found', 0)} found")

        return {
            "status": "success",
            "contractors_found": result.get("contractors_found", 0),
            "multi_oem_count": result.get("multi_oem_count", 0),
            "order_id": order.get("order_id"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except SoftTimeLimitExceeded:
        logger.error("[Deep Hunter] Task timeout")
        return {"status": "error", "error": "Task timeout"}

    except Exception as e:
        logger.error(f"[Deep Hunter] Task failed: {e}")
        try:
            hub = get_elite_hub()
            hub.record_agent_run("deep_hunter", success=False, error_message=str(e))
        except Exception:
            pass
        return {"status": "error", "error": str(e)}


@celery_app.task(
    name="run_deep_hunter",
    bind=True,
    max_retries=2
)
def run_deep_hunter(
    self,
    vertical: str,
    states: List[str],
    oems: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Manually trigger Deep Hunter for a specific vertical/state combo.

    Args:
        vertical: Vertical to hunt (e.g., "solar", "generator", "trifecta")
        states: List of state codes to scrape
        oems: Optional list of OEM brands to target

    Returns:
        Dict with hunt results
    """
    order = {
        "order_id": f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "vertical": vertical,
        "states": states,
        "oems": oems or [],
        "priority": "MEDIUM",
        "reason": "Manual trigger"
    }

    return process_scraping_order(order)


# ========== INTAKE COMMANDER TASK ==========

@celery_app.task(
    name="run_intake_commander",
    bind=True,
    max_retries=2,
    soft_time_limit=120,  # 2 minutes max
    time_limit=180  # Hard limit 3 minutes
)
def run_intake_commander(self, batch_size: int = 100) -> Dict[str, Any]:
    """
    Run Intake Commander to process incoming leads.

    Quality gate that:
    1. Loads incoming leads from Deep Hunter exports
    2. Checks for duplicates (Close CRM + Supabase)
    3. Applies 3-layer garbage contact filtering
    4. Calculates Trifecta scores
    5. Routes leads (UNICORN→BDR, PARTIAL→enrichment, etc.)

    Args:
        batch_size: Max items to process per cycle

    Returns:
        Dict with processing results
    """
    try:
        import asyncio
        from app.services.langgraph.agents.elite_team.intake_commander_agent import (
            IntakeCommanderAgent
        )
        from app.services.langgraph.agents.elite_team.elite_team_hub import (
            get_elite_hub, EliteAgentStatus
        )

        hub = get_elite_hub()

        # Check if there's work to do
        queue_size = hub.get_intake_queue_size()
        if queue_size == 0:
            logger.debug("[Intake Commander] No items in queue, skipping")
            return {
                "status": "success",
                "processed": 0,
                "message": "No items in queue"
            }

        hub.update_agent_status(
            "intake_commander",
            EliteAgentStatus.PROCESSING,
            f"Processing {min(queue_size, batch_size)} leads"
        )

        logger.info(f"[Intake Commander] Processing batch: {min(queue_size, batch_size)} items")

        # Run the agent
        agent = IntakeCommanderAgent()
        result = asyncio.run(agent.run(batch_size=batch_size))

        # Record run
        hub.record_agent_run(
            "intake_commander",
            success=True,
            items_processed=result.get("total_processed", 0)
        )

        # Update hub stats
        if result.get("unicorns_found", 0) > 0:
            for _ in range(result["unicorns_found"]):
                hub.record_unicorn_found("Unknown")  # Company names not tracked here

        if result.get("hot_leads_routed", 0) > 0:
            hub.record_bdr_routing(result["hot_leads_routed"])

        if result.get("duplicates_blocked", 0) > 0:
            hub.record_duplicates_blocked(result["duplicates_blocked"])

        logger.info(
            f"[Intake Commander] Complete: {result.get('total_processed', 0)} processed, "
            f"{result.get('unicorns_found', 0)} unicorns, "
            f"{result.get('hot_leads_routed', 0)} to BDR"
        )

        return {
            "status": "success",
            "total_processed": result.get("total_processed", 0),
            "new_leads": result.get("new_leads", 0),
            "duplicates_blocked": result.get("duplicates_blocked", 0),
            "unicorns_found": result.get("unicorns_found", 0),
            "hot_leads_routed": result.get("hot_leads_routed", 0),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except SoftTimeLimitExceeded:
        logger.error("[Intake Commander] Task timeout")
        return {"status": "error", "error": "Task timeout"}

    except Exception as e:
        logger.error(f"[Intake Commander] Task failed: {e}")
        try:
            hub = get_elite_hub()
            hub.record_agent_run("intake_commander", success=False, error_message=str(e))
        except Exception:
            pass
        return {"status": "error", "error": str(e)}


# ========== EXPORTS ==========

__all__ = [
    "run_signal_scout",
    "run_deep_hunter",
    "process_scraping_order",
    "run_intake_commander",
]
