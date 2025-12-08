"""Celery tasks for LinkedIn automation."""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.celery_app import celery_app
from app.services.langgraph.agents.linkedin_agent import (
    LinkedInAgent,
    ConnectionResult,
    MessageResult,
)
from app.services.langgraph.tools.supabase_tools import get_supabase

logger = logging.getLogger(__name__)


# ============================================================================
# LinkedIn Action Queue Management
# ============================================================================


@celery_app.task(name="send_linkedin_connection", queue="linkedin")
def send_linkedin_connection(
    lead_id: str,
    profile_url: str,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Queue LinkedIn connection request.

    Args:
        lead_id: Company ID in dim_companies
        profile_url: LinkedIn profile URL
        note: Optional personalized note

    Returns:
        Connection result
    """
    import asyncio

    logger.info(f"[LinkedIn] Sending connection request: {profile_url}")

    async def _send():
        async with LinkedInAgent() as agent:
            result = await agent.send_connection_request(
                profile_url=profile_url,
                note=note,
            )

            # Save result to database
            await _save_linkedin_action(
                lead_id=lead_id,
                action_type="connect",
                profile_url=profile_url,
                payload={"note": note},
                result=result.model_dump(),
            )

            return result.model_dump()

    return asyncio.run(_send())


@celery_app.task(name="send_linkedin_message", queue="linkedin")
def send_linkedin_message(
    lead_id: str,
    profile_url: str,
    message: str,
) -> Dict[str, Any]:
    """
    Queue LinkedIn message.

    Args:
        lead_id: Company ID in dim_companies
        profile_url: LinkedIn profile URL
        message: Message content

    Returns:
        Message result
    """
    import asyncio

    logger.info(f"[LinkedIn] Sending message: {profile_url}")

    async def _send():
        async with LinkedInAgent() as agent:
            result = await agent.send_message(
                profile_url=profile_url,
                message=message,
            )

            # Save result to database
            await _save_linkedin_action(
                lead_id=lead_id,
                action_type="message",
                profile_url=profile_url,
                payload={"message": message},
                result=result.model_dump(),
            )

            return result.model_dump()

    return asyncio.run(_send())


@celery_app.task(name="react_to_linkedin_post", queue="linkedin")
def react_to_linkedin_post(
    lead_id: str,
    post_url: str,
    reaction: str = "like",
) -> Dict[str, Any]:
    """
    Queue LinkedIn post reaction.

    Args:
        lead_id: Company ID
        post_url: LinkedIn post URL
        reaction: Reaction type (like, celebrate, support, etc)

    Returns:
        Reaction result
    """
    import asyncio

    logger.info(f"[LinkedIn] Reacting to post: {post_url}")

    async def _react():
        async with LinkedInAgent() as agent:
            result = await agent.react_to_post(
                post_url=post_url,
                reaction=reaction,
            )

            # Save result
            await _save_linkedin_action(
                lead_id=lead_id,
                action_type="react",
                profile_url=post_url,
                payload={"reaction": reaction},
                result=result.model_dump(),
            )

            return result.model_dump()

    return asyncio.run(_react())


@celery_app.task(name="comment_on_linkedin_post", queue="linkedin")
def comment_on_linkedin_post(
    lead_id: str,
    post_url: str,
    comment: str,
) -> Dict[str, Any]:
    """
    Queue LinkedIn post comment.

    Args:
        lead_id: Company ID
        post_url: LinkedIn post URL
        comment: Comment text

    Returns:
        Comment result
    """
    import asyncio

    logger.info(f"[LinkedIn] Commenting on post: {post_url}")

    async def _comment():
        async with LinkedInAgent() as agent:
            result = await agent.comment_on_post(
                post_url=post_url,
                comment=comment,
            )

            # Save result
            await _save_linkedin_action(
                lead_id=lead_id,
                action_type="comment",
                profile_url=post_url,
                payload={"comment": comment},
                result=result.model_dump(),
            )

            return result.model_dump()

    return asyncio.run(_comment())


# ============================================================================
# Daily LinkedIn Actions (Scheduled Task)
# ============================================================================


@celery_app.task(name="run_linkedin_daily_actions", queue="linkedin")
def run_linkedin_daily_actions() -> Dict[str, Any]:
    """
    Process queued LinkedIn actions (max 10 connections/day).

    This runs daily and processes pending actions from the queue.

    Returns:
        Summary of actions performed
    """
    import asyncio

    logger.info("[LinkedIn] Running daily action cycle")

    async def _run():
        supabase = get_supabase()

        # Get pending LinkedIn actions
        result = supabase.table("linkedin_action_queue").select("*").eq(
            "status", "pending"
        ).order("scheduled_for", desc=False).limit(50).execute()

        if not result.data:
            logger.info("[LinkedIn] No pending actions")
            return {"actions_processed": 0}

        async with LinkedInAgent() as agent:
            remaining = agent.get_remaining_actions()
            logger.info(f"[LinkedIn] Remaining actions today: {remaining}")

            actions_processed = 0
            results = []

            for action in result.data:
                action_type = action["action_type"]
                action_id = action["id"]
                lead_id = action["lead_id"]
                payload = action["payload"]

                # Check if we can still perform this action type
                if remaining.get(action_type + "s", 0) <= 0:
                    logger.warning(
                        f"[LinkedIn] Daily limit reached for {action_type}"
                    )
                    continue

                try:
                    # Execute action
                    action_result = None

                    if action_type == "connect":
                        action_result = await agent.send_connection_request(
                            profile_url=payload["profile_url"],
                            note=payload.get("note"),
                        )
                    elif action_type == "message":
                        action_result = await agent.send_message(
                            profile_url=payload["profile_url"],
                            message=payload["message"],
                        )
                    elif action_type == "react":
                        action_result = await agent.react_to_post(
                            post_url=payload["post_url"],
                            reaction=payload.get("reaction", "like"),
                        )
                    elif action_type == "comment":
                        action_result = await agent.comment_on_post(
                            post_url=payload["post_url"],
                            comment=payload["comment"],
                        )

                    if action_result:
                        # Update action status
                        supabase.table("linkedin_action_queue").update({
                            "status": "completed" if action_result.success else "failed",
                            "executed_at": datetime.utcnow().isoformat(),
                            "result": action_result.model_dump(),
                        }).eq("id", action_id).execute()

                        actions_processed += 1
                        results.append(action_result.model_dump())

                        # Update remaining count
                        remaining[action_type + "s"] = agent.rate_limiter.get_remaining(
                            action_type + "s"
                        )

                except Exception as e:
                    logger.error(f"[LinkedIn] Action failed: {e}")
                    supabase.table("linkedin_action_queue").update({
                        "status": "failed",
                        "executed_at": datetime.utcnow().isoformat(),
                        "result": {"error": str(e)},
                    }).eq("id", action_id).execute()

            return {
                "actions_processed": actions_processed,
                "results": results,
                "remaining": remaining,
            }

    return asyncio.run(_run())


# ============================================================================
# Helper Functions
# ============================================================================


async def _save_linkedin_action(
    lead_id: str,
    action_type: str,
    profile_url: str,
    payload: Dict[str, Any],
    result: Dict[str, Any],
):
    """Save LinkedIn action to database."""
    supabase = get_supabase()

    try:
        supabase.table("linkedin_action_queue").insert({
            "lead_id": lead_id,
            "action_type": action_type,
            "payload": {
                "profile_url": profile_url,
                **payload,
            },
            "status": "completed" if result.get("success") else "failed",
            "executed_at": datetime.utcnow().isoformat(),
            "result": result,
        }).execute()

        logger.info(f"[LinkedIn] Saved {action_type} action for lead {lead_id}")

    except Exception as e:
        logger.error(f"[LinkedIn] Failed to save action: {e}")


def queue_linkedin_connection(
    lead_id: str,
    profile_url: str,
    note: Optional[str] = None,
    scheduled_for: Optional[datetime] = None,
) -> str:
    """
    Queue a LinkedIn connection request for later execution.

    Args:
        lead_id: Company ID
        profile_url: LinkedIn profile URL
        note: Optional personalized note
        scheduled_for: When to execute (default: ASAP)

    Returns:
        Action queue ID
    """
    supabase = get_supabase()

    result = supabase.table("linkedin_action_queue").insert({
        "lead_id": lead_id,
        "action_type": "connect",
        "payload": {
            "profile_url": profile_url,
            "note": note,
        },
        "status": "pending",
        "scheduled_for": (scheduled_for or datetime.utcnow()).isoformat(),
    }).execute()

    action_id = result.data[0]["id"]
    logger.info(f"[LinkedIn] Queued connection request: {action_id}")
    return action_id


def queue_linkedin_message(
    lead_id: str,
    profile_url: str,
    message: str,
    scheduled_for: Optional[datetime] = None,
) -> str:
    """
    Queue a LinkedIn message for later execution.

    Args:
        lead_id: Company ID
        profile_url: LinkedIn profile URL
        message: Message content
        scheduled_for: When to execute (default: ASAP)

    Returns:
        Action queue ID
    """
    supabase = get_supabase()

    result = supabase.table("linkedin_action_queue").insert({
        "lead_id": lead_id,
        "action_type": "message",
        "payload": {
            "profile_url": profile_url,
            "message": message,
        },
        "status": "pending",
        "scheduled_for": (scheduled_for or datetime.utcnow()).isoformat(),
    }).execute()

    action_id = result.data[0]["id"]
    logger.info(f"[LinkedIn] Queued message: {action_id}")
    return action_id
