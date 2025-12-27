"""
Default Workflow Rules

Pre-configured workflow rules that ship with the system.
These rules demonstrate the workflow automation capabilities and provide
useful out-of-the-box automation for common sales scenarios.

Part of Phase 4: Workflow Automation for the Close CRM Enhancements project.

Usage:
    # Seed default rules on app startup
    from app.services.workflow.default_rules import seed_default_rules
    await seed_default_rules(db_session)

    # Or manually via API endpoint
    POST /api/v1/workflow-rules/seed-defaults
"""

from typing import List, Dict, Any
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from app.models.workflow import WorkflowRule, TriggerType, ActionType

logger = logging.getLogger(__name__)


# ============================================================================
# DEFAULT WORKFLOW RULES
# ============================================================================

DEFAULT_RULES: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # Rule 1: Won Deal Celebration
    # Sends a Slack notification when a deal is won
    # -------------------------------------------------------------------------
    {
        "name": "Won Deal Celebration",
        "description": "Send Slack celebration message when a deal is won",
        "trigger_type": TriggerType.OPPORTUNITY_WON.value,
        "trigger_conditions": {},  # Matches all won deals
        "action_type": ActionType.SEND_SLACK.value,
        "action_config": {
            "message": "Deal Won! {opportunity_name} for ${amount} :tada:"
        },
        "priority": 10,
        "is_active": True,
    },

    # -------------------------------------------------------------------------
    # Rule 2: Lost Deal Review Task
    # Creates a follow-up task for large deals that were lost
    # -------------------------------------------------------------------------
    {
        "name": "Lost Deal Review Task",
        "description": "Create review task for lost deals over $10,000",
        "trigger_type": TriggerType.OPPORTUNITY_LOST.value,
        "trigger_conditions": {
            "amount": {"gte": 10000}  # Only for deals >= $10,000
        },
        "action_type": ActionType.CREATE_TASK.value,
        "action_config": {
            "task_text": "Review lost deal: {opportunity_name} (${amount}) - Analyze what went wrong",
            "due_days": 2,
            "task_type": "follow-up"
        },
        "priority": 20,
        "is_active": True,
    },

    # -------------------------------------------------------------------------
    # Rule 3: Platinum Lead Alert
    # Sends an alert when a PLATINUM tier lead advances to meeting stage
    # -------------------------------------------------------------------------
    {
        "name": "Platinum Lead Meeting Alert",
        "description": "High-priority alert when PLATINUM lead books a meeting",
        "trigger_type": TriggerType.STAGE_CHANGE.value,
        "trigger_conditions": {
            "icp_tier": "PLATINUM",
            "to_stage": ["meeting_booked", "Meeting Booked", "Meeting"]
        },
        "action_type": ActionType.SEND_ALERT.value,
        "action_config": {
            "title": "PLATINUM Lead Meeting Booked!",
            "message": "{company_name} is now in meeting stage - high value opportunity",
            "severity": "high",
            "alert_type": "hot_lead"
        },
        "priority": 5,  # High priority - process first
        "is_active": True,
    },

    # -------------------------------------------------------------------------
    # Rule 4: Stale Opportunity Alert
    # Alerts when an opportunity has been in proposal stage for too long
    # -------------------------------------------------------------------------
    {
        "name": "Stale Proposal Alert",
        "description": "Alert when opportunity is stuck in proposal stage for 14+ days",
        "trigger_type": TriggerType.DAYS_IN_STAGE.value,
        "trigger_conditions": {
            "days": {"gte": 14},
            "stage": ["proposal", "Proposal", "Proposal Sent"]
        },
        "action_type": ActionType.SEND_ALERT.value,
        "action_config": {
            "title": "Stale Opportunity",
            "message": "{opportunity_name} has been in proposal stage for {days} days - needs attention",
            "severity": "medium",
            "alert_type": "workflow"
        },
        "priority": 50,
        "is_active": True,
    },

    # -------------------------------------------------------------------------
    # Rule 5: New Lead Welcome Task
    # Creates an initial outreach task when a new lead is created
    # -------------------------------------------------------------------------
    {
        "name": "New Lead Outreach Task",
        "description": "Create initial outreach task for new leads",
        "trigger_type": TriggerType.LEAD_CREATED.value,
        "trigger_conditions": {},  # All new leads
        "action_type": ActionType.CREATE_TASK.value,
        "action_config": {
            "task_text": "Initial outreach for new lead: {company_name}",
            "due_days": 1,
            "task_type": "follow-up"
        },
        "priority": 30,
        "is_active": True,
    },

    # -------------------------------------------------------------------------
    # Rule 6: High-Value Stage Change Alert
    # Alerts when a high-value opportunity changes stage
    # -------------------------------------------------------------------------
    {
        "name": "High-Value Stage Change",
        "description": "Alert when deals over $50,000 change stage",
        "trigger_type": TriggerType.STAGE_CHANGE.value,
        "trigger_conditions": {
            "amount": {"gte": 50000}
        },
        "action_type": ActionType.SEND_ALERT.value,
        "action_config": {
            "title": "High-Value Deal Movement",
            "message": "${amount} deal '{opportunity_name}' moved from {from_stage} to {to_stage}",
            "severity": "high",
            "alert_type": "workflow"
        },
        "priority": 15,
        "is_active": True,
    },

    # -------------------------------------------------------------------------
    # Rule 7: ICP Tier Upgrade Notification
    # Sends Slack notification when a lead's ICP tier upgrades
    # -------------------------------------------------------------------------
    {
        "name": "ICP Tier Upgrade Notification",
        "description": "Notify on Slack when lead upgrades to GOLD or PLATINUM",
        "trigger_type": TriggerType.ICP_TIER_CHANGE.value,
        "trigger_conditions": {
            "new_tier": ["GOLD", "PLATINUM"]
        },
        "action_type": ActionType.SEND_SLACK.value,
        "action_config": {
            "message": "ICP Upgrade: {company_name} is now {new_tier} tier (score: {icp_score})"
        },
        "priority": 25,
        "is_active": True,
    },
]


# ============================================================================
# SEEDING FUNCTIONS
# ============================================================================

async def seed_default_rules(db: Session) -> Dict[str, Any]:
    """
    Seed default workflow rules if they don't already exist.

    This function checks for existing rules by name and only creates
    rules that don't already exist. Safe to call multiple times.

    Args:
        db: SQLAlchemy database session

    Returns:
        Dict with seeding results:
        - created: Number of rules created
        - skipped: Number of rules that already existed
        - rules: List of created rule names

    Example:
        >>> db = SessionLocal()
        >>> result = await seed_default_rules(db)
        >>> print(result)
        {"created": 4, "skipped": 3, "rules": ["Won Deal Celebration", ...]}
    """
    created = 0
    skipped = 0
    created_rules = []

    for rule_data in DEFAULT_RULES:
        try:
            # Check if rule already exists by name
            existing = db.query(WorkflowRule).filter(
                WorkflowRule.name == rule_data["name"]
            ).first()

            if existing:
                logger.debug(f"Rule already exists: {rule_data['name']}")
                skipped += 1
                continue

            # Create new rule
            new_rule = WorkflowRule(
                name=rule_data["name"],
                description=rule_data.get("description"),
                trigger_type=rule_data["trigger_type"],
                trigger_conditions=rule_data.get("trigger_conditions", {}),
                action_type=rule_data["action_type"],
                action_config=rule_data.get("action_config", {}),
                priority=rule_data.get("priority", 100),
                is_active=rule_data.get("is_active", True),
                created_by="system",
            )

            db.add(new_rule)
            db.commit()
            db.refresh(new_rule)

            created += 1
            created_rules.append(rule_data["name"])
            logger.info(f"Created default rule: {rule_data['name']} (ID: {new_rule.id})")

        except Exception as e:
            logger.error(f"Failed to create rule '{rule_data['name']}': {e}")
            db.rollback()

    result = {
        "status": "success",
        "created": created,
        "skipped": skipped,
        "total_default_rules": len(DEFAULT_RULES),
        "rules_created": created_rules,
    }

    if created > 0:
        logger.info(f"Seeded {created} default workflow rules ({skipped} already existed)")
    else:
        logger.info(f"All {skipped} default workflow rules already exist")

    return result


def seed_default_rules_sync(db: Session) -> Dict[str, Any]:
    """
    Synchronous version of seed_default_rules for use during app startup.

    This wrapper allows calling from synchronous code like FastAPI lifespan events.

    Args:
        db: SQLAlchemy database session

    Returns:
        Dict with seeding results
    """
    import asyncio

    # Check if we're already in an async context
    try:
        loop = asyncio.get_running_loop()
        # We're in an async context, run directly
        return asyncio.run_coroutine_threadsafe(
            seed_default_rules(db), loop
        ).result(timeout=30)
    except RuntimeError:
        # No running loop, create one
        return asyncio.run(seed_default_rules(db))


# ============================================================================
# RULE MANAGEMENT UTILITIES
# ============================================================================

def get_default_rule_names() -> List[str]:
    """
    Get list of default rule names.

    Useful for identifying which rules are system defaults vs. user-created.

    Returns:
        List of default rule names
    """
    return [rule["name"] for rule in DEFAULT_RULES]


def is_default_rule(rule_name: str) -> bool:
    """
    Check if a rule name is a default system rule.

    Args:
        rule_name: Name of the rule to check

    Returns:
        True if the rule is a system default
    """
    return rule_name in get_default_rule_names()


async def reset_default_rules(db: Session) -> Dict[str, Any]:
    """
    Reset default rules to their original configuration.

    Deletes existing default rules and re-creates them.
    User-created rules are not affected.

    WARNING: This will delete any modifications made to default rules.

    Args:
        db: SQLAlchemy database session

    Returns:
        Dict with reset results
    """
    deleted = 0
    default_names = get_default_rule_names()

    # Delete existing default rules
    for name in default_names:
        try:
            existing = db.query(WorkflowRule).filter(
                WorkflowRule.name == name
            ).first()

            if existing:
                db.delete(existing)
                deleted += 1

        except Exception as e:
            logger.error(f"Failed to delete rule '{name}': {e}")
            db.rollback()

    db.commit()
    logger.info(f"Deleted {deleted} default rules for reset")

    # Re-create default rules
    seed_result = await seed_default_rules(db)

    return {
        "status": "success",
        "deleted": deleted,
        "created": seed_result["created"],
        "rules_reset": seed_result["rules_created"],
    }


__all__ = [
    "DEFAULT_RULES",
    "seed_default_rules",
    "seed_default_rules_sync",
    "get_default_rule_names",
    "is_default_rule",
    "reset_default_rules",
]
