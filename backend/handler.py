#!/usr/bin/env python3
"""
RunPod Serverless Handler for Social Intelligence Pipeline

Entry point for RunPod serverless execution.
Wraps social_intelligence_runner.py with RunPod's handler interface.
"""
import asyncio
import os
import sys
import traceback
from typing import Dict, Any
from datetime import datetime

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

import runpod
from social_intelligence_runner import SocialIntelligenceRunner
from check_email_engagement import EngagementChecker
from app.core.logging import setup_logging, log_performance, log_error

# Set up structured logging
logger = setup_logging(__name__)


async def run_full_pipeline(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the complete social intelligence pipeline.

    Args:
        config: Pipeline configuration
            - max_contacts: Maximum contacts to process (default: 20)
            - platforms: List of platforms to scrape (default: ["linkedin", "twitter"])

    Returns:
        Pipeline execution results
    """
    start_time = datetime.now()
    logger.info(
        "pipeline_started",
        task="full_pipeline",
        max_contacts=config.get("max_contacts", 20),
        platforms=config.get("platforms", ["linkedin", "twitter"])
    )

    try:
        runner = SocialIntelligenceRunner()
        result = await runner.run_full_pipeline()

        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        log_performance(
            logger,
            service="social_intelligence_runner",
            operation="full_pipeline",
            latency_ms=latency_ms,
            contacts_processed=result.get("contacts_processed", 0),
            posts_scraped=result.get("posts_scraped", 0),
            drafts_created=result.get("drafts_created", 0)
        )

        return {
            "success": True,
            "task": "full_pipeline",
            "result": result,
            "latency_ms": round(latency_ms, 2)
        }

    except Exception as e:
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        log_error(logger, "social_intelligence_runner", "full_pipeline", e)

        return {
            "success": False,
            "task": "full_pipeline",
            "error": str(e),
            "error_type": type(e).__name__,
            "latency_ms": round(latency_ms, 2)
        }


async def run_engagement_check() -> Dict[str, Any]:
    """
    Check email engagement and update high-intent flags.

    Returns:
        Engagement check results
    """
    start_time = datetime.now()
    logger.info("engagement_check_started", task="engagement_check")

    try:
        checker = EngagementChecker()
        result = await checker.check_all_engagement()

        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        log_performance(
            logger,
            service="engagement_checker",
            operation="check_all_engagement",
            latency_ms=latency_ms,
            high_intent_contacts=result.get("high_intent_contacts", 0)
        )

        return {
            "success": True,
            "task": "engagement_check",
            "result": result,
            "latency_ms": round(latency_ms, 2)
        }

    except Exception as e:
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        log_error(logger, "engagement_checker", "check_all_engagement", e)

        return {
            "success": False,
            "task": "engagement_check",
            "error": str(e),
            "error_type": type(e).__name__,
            "latency_ms": round(latency_ms, 2)
        }


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod serverless handler function.

    Job input format:
    {
        "input": {
            "task": "full_pipeline" | "engagement_check",
            "config": {
                "max_contacts": 20,
                "platforms": ["linkedin", "twitter"]
            }
        }
    }

    Args:
        job: RunPod job payload

    Returns:
        Job execution results
    """
    try:
        # Extract job input
        job_input = job.get("input", {})
        task = job_input.get("task", "full_pipeline")
        config = job_input.get("config", {})

        logger.info(
            "job_received",
            job_id=job.get("id"),
            task=task,
            config=config
        )

        # Route to appropriate handler
        if task == "full_pipeline":
            result = asyncio.run(run_full_pipeline(config))
        elif task == "engagement_check":
            result = asyncio.run(run_engagement_check())
        else:
            return {
                "success": False,
                "error": f"Unknown task: {task}",
                "valid_tasks": ["full_pipeline", "engagement_check"]
            }

        logger.info(
            "job_completed",
            job_id=job.get("id"),
            task=task,
            success=result.get("success"),
            latency_ms=result.get("latency_ms")
        )

        return result

    except Exception as e:
        logger.error(
            "job_failed",
            job_id=job.get("id"),
            error_type=type(e).__name__,
            error_message=str(e),
            traceback=traceback.format_exc(),
            exc_info=True
        )

        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }


if __name__ == "__main__":
    logger.info("runpod_handler_starting", version="1.0.0")

    # Start RunPod serverless handler
    runpod.serverless.start({"handler": handler})
