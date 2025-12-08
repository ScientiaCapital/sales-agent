"""
Celery tasks for DropInAgent enrichment

Handles background enrichment from any source:
- Terminal CLI
- Slack commands
- Claude Code sessions
- Close CRM webhooks
- API calls

All routes through unified DropInAgent with dedup-first pipeline.
"""

# LangSmith tracing is configured centrally in celery_app.py
# Do NOT override here - let the central config control tracing
import os
import logging

# Suppress LangSmith warning logs when tracing is disabled
logging.getLogger("langsmith.client").setLevel(logging.ERROR)
logging.getLogger("langsmith.utils").setLevel(logging.ERROR)

from typing import Literal, Optional, List, Dict, Any
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.core.logging import setup_logging
from app.services.langgraph.agents.dropin_agent import DropInAgent, DropInResult

logger = setup_logging(__name__)


# ========== Celery Tasks ==========

@celery_app.task(
    name="run_dropin_enrichment",
    bind=True,
    max_retries=2,
    soft_time_limit=300  # 5 minutes max
)
def run_dropin_enrichment(
    self,
    input: str,
    input_type: Literal["auto", "url", "company_name", "close_id", "person"] = "auto",
    stage_channels: Optional[List[str]] = None,
    auto_trigger: bool = False,
    source: str = "manual"
) -> Dict[str, Any]:
    """
    Run DropInAgent enrichment as background task.

    Args:
        input: Any input (URL, company name, Close ID, person)
        input_type: Input type hint (auto-detects if "auto")
        stage_channels: Channels to stage for outreach (email, sms, linkedin, call)
        auto_trigger: Auto-send outreach if HOT (default: False)
        source: Source of request (manual, slack, claude_code, webhook)

    Returns:
        Dict with enrichment results or error

    Example:
        # Manual enrichment
        result = run_dropin_enrichment.delay(
            input="https://acme-hvac.com",
            input_type="auto",
            source="manual"
        )

        # From Slack with staging
        result = run_dropin_enrichment.delay(
            input="https://acme-hvac.com",
            stage_channels=["email", "sms"],
            source="slack"
        )

        # Auto-trigger outreach
        result = run_dropin_enrichment.delay(
            input="lead_abc123",
            input_type="close_id",
            stage_channels=["email"],
            auto_trigger=True,
            source="webhook"
        )
    """
    try:
        logger.info(
            f"[DropIn] Starting enrichment: input={input}, type={input_type}, "
            f"source={source}, channels={stage_channels}, auto={auto_trigger}"
        )

        # Initialize DropInAgent
        agent = DropInAgent(
            close_api_key=os.getenv("CLOSE_API_KEY"),
            provider="cerebras"  # Fast and cheap
        )

        # Run enrichment (async function - need to await)
        import asyncio
        result: DropInResult = asyncio.run(
            agent.drop_in(
                input=input,
                input_type=input_type,
                stage_channels=stage_channels,
                auto_trigger=auto_trigger
            )
        )

        # Convert to dict for Celery
        result_dict = result.model_dump()

        # Log result
        if result.exists_in_close:
            logger.info(
                f"[DropIn] ⚠️  Already exists: {result.existing_lead.company_name} "
                f"(confidence: {result.existing_lead.confidence:.1f}%)"
            )
        elif result.status == "enriched":
            logger.info(
                f"[DropIn] ✅ Enriched: {result.company_name}, "
                f"score={result.icp_score}, tier={result.icp_tier}, "
                f"priority={result.priority}, {result.duration_ms}ms"
            )
        else:
            logger.error(f"[DropIn] ❌ Failed: {result.error}")

        return {
            "status": "success",
            "result": result_dict,
            "source": source
        }

    except SoftTimeLimitExceeded:
        logger.error(f"[DropIn] Task timeout: {input}")
        return {
            "status": "error",
            "error": "Task timeout after 5 minutes",
            "input": input,
            "source": source
        }

    except Exception as e:
        logger.error(f"[DropIn] Task failed: {e}")

        # Retry on transient errors
        if "network" in str(e).lower() or "timeout" in str(e).lower():
            logger.info(f"[DropIn] Retrying due to transient error: {e}")
            raise self.retry(exc=e, countdown=30)  # Retry after 30 seconds

        return {
            "status": "error",
            "error": str(e),
            "input": input,
            "source": source
        }


@celery_app.task(
    name="run_dropin_batch",
    bind=True,
    max_retries=1
)
def run_dropin_batch(
    self,
    inputs: List[str],
    input_type: Literal["auto", "url", "company_name", "close_id", "person"] = "auto",
    stage_channels: Optional[List[str]] = None,
    auto_trigger: bool = False,
    source: str = "batch"
) -> Dict[str, Any]:
    """
    Run DropInAgent enrichment on a batch of inputs.

    Args:
        inputs: List of inputs (URLs, company names, etc.)
        input_type: Input type hint
        stage_channels: Channels to stage for outreach
        auto_trigger: Auto-send outreach if HOT
        source: Source of request

    Returns:
        Dict with batch results

    Example:
        result = run_dropin_batch.delay(
            inputs=["https://acme.com", "https://beta.com", "Gamma Corp"],
            stage_channels=["email"],
            source="csv_import"
        )
    """
    try:
        logger.info(f"[DropIn Batch] Starting: {len(inputs)} inputs, source={source}")

        results = []
        errors = []

        for input_str in inputs:
            # Spawn individual task for each input
            task = run_dropin_enrichment.delay(
                input=input_str,
                input_type=input_type,
                stage_channels=stage_channels,
                auto_trigger=auto_trigger,
                source=f"{source}_batch"
            )
            results.append({
                "input": input_str,
                "task_id": task.id
            })

        logger.info(f"[DropIn Batch] Spawned {len(results)} tasks")

        return {
            "status": "success",
            "total": len(inputs),
            "tasks_spawned": len(results),
            "results": results,
            "source": source
        }

    except Exception as e:
        logger.error(f"[DropIn Batch] Failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "total": len(inputs),
            "source": source
        }


# ========== Exports ==========

__all__ = [
    "run_dropin_enrichment",
    "run_dropin_batch"
]
