"""
Schema Validator Utility

GTME Rule: Validate before you migrate.
Prevents runtime errors from missing columns or invalid data.
"""

from typing import Optional, Set
from supabase import Client
import logging

logger = logging.getLogger(__name__)

# Known schema definitions
SCHEMA = {
    "dim_companies": {
        "required": [
            "company_id", "company_name", "normalized_name", "domain",
            "created_at", "updated_at"
        ],
        "optional": [
            "phone", "website", "street", "city", "state", "zip",
            "icp_score", "icp_tier", "is_service_based", "is_multi_location", "is_srec_state",
            "close_lead_id", "close_pushed_at", "funnel_stage", "disposition", "current_stage",
            "enrichment_status", "last_enriched_at", "total_enrichment_cost_usd", "team_page_url",
            "ai_enriched_at", "ai_personal_hooks", "ai_company_story", "ai_pain_points",
            "ai_buying_signals", "ai_confidence",
            "original_source", "source_type", "first_seen_at",
            "oem_brands", "oem_count", "license_types", "trade_count",
            "email_opens", "total_activities", "flagged_for_reenrich", "needs_attention",
            "first_contact_at", "last_activity_at", "deal_value_usd", "closed_at"
        ],
        "constraints": {
            "icp_tier": ["GOLD", "SILVER", "BRONZE"],
            "funnel_stage": [
                "new", "contacted", "engaged", "qualified", "demo",
                "proposal", "negotiation", "closed_won", "closed_lost", "nurture"
            ]
        }
    },
    "dim_contacts": {
        "required": [
            "contact_id", "company_id", "created_at", "updated_at"
        ],
        "optional": [
            "first_name", "last_name", "full_name", "title", "email", "phone",
            "department", "seniority", "is_atl", "linkedin_url", "twitter_handle",
            "source", "confidence", "validated",
            "close_contact_id", "close_pushed_at", "sequence_name", "sequence_subscribed_at",
            "contact_status", "emails_sent", "emails_opened", "emails_clicked",
            "emails_replied", "calls_made", "last_contacted_at"
        ],
        "constraints": {}
    },
    "lead_events": {
        "required": [
            "event_id", "event_type", "event_source", "created_at"
        ],
        "optional": [
            "company_id", "contact_id", "origination_source", "origination_list",
            "close_lead_id", "close_contact_id", "close_sequence_id", "close_sequence_name",
            "funnel_stage", "disposition", "cost_usd", "revenue_usd",
            "metadata", "notes", "created_by"
        ],
        "constraints": {
            "event_type": [
                "scraped", "enriched_hunter", "enriched_apollo", "pushed_to_crm",
                "sequence_subscribed", "email_sent", "email_opened", "email_clicked",
                "replied", "called", "voicemail", "qualified", "demo_scheduled",
                "proposal_sent", "closed_won", "closed_lost", "nurture_cold", "nurture_hot"
            ]
        }
    }
}


def get_table_columns(supabase: Client, table: str) -> Set[str]:
    """
    Get actual columns from a table by querying a sample row.

    Args:
        supabase: Supabase client
        table: Table name

    Returns:
        Set of column names
    """
    try:
        result = supabase.table(table).select("*").limit(1).execute()
        if result.data:
            return set(result.data[0].keys())
        return set()
    except Exception as e:
        logger.error(f"Failed to get columns for {table}: {e}")
        return set()


def validate_columns_exist(
    supabase: Client,
    table: str,
    columns: list[str],
    raise_on_missing: bool = True
) -> tuple[bool, list[str]]:
    """
    GTME Rule: Validate before you migrate.

    Validates that specified columns exist in the table.

    Args:
        supabase: Supabase client
        table: Table name
        columns: List of columns to check
        raise_on_missing: If True, raise ValueError on missing columns

    Returns:
        Tuple of (all_exist: bool, missing_columns: list)

    Raises:
        ValueError: If raise_on_missing=True and columns are missing
    """
    existing = get_table_columns(supabase, table)
    missing = [col for col in columns if col not in existing]

    if missing and raise_on_missing:
        raise ValueError(f"Missing columns in {table}: {missing}")

    return len(missing) == 0, missing


def validate_constraint_value(table: str, column: str, value: str) -> bool:
    """
    Validate that a value matches the constraint for a column.

    Args:
        table: Table name
        column: Column name
        value: Value to validate

    Returns:
        True if valid, False otherwise
    """
    if table not in SCHEMA:
        return True  # Unknown table, assume valid

    constraints = SCHEMA[table].get("constraints", {})
    if column not in constraints:
        return True  # No constraint, assume valid

    valid_values = constraints[column]
    return value in valid_values


def get_valid_values(table: str, column: str) -> Optional[list[str]]:
    """
    Get valid values for a constrained column.

    Args:
        table: Table name
        column: Column name

    Returns:
        List of valid values, or None if no constraint
    """
    if table not in SCHEMA:
        return None

    return SCHEMA[table].get("constraints", {}).get(column)


def safe_update(
    supabase: Client,
    table: str,
    data: dict,
    company_id: str
) -> dict:
    """
    Safely update a record, validating constraints first.

    Args:
        supabase: Supabase client
        table: Table name
        data: Update data dict
        company_id: Record ID

    Returns:
        Update result or error dict
    """
    # Validate constraints
    for column, value in data.items():
        if value is not None and not validate_constraint_value(table, column, str(value)):
            valid = get_valid_values(table, column)
            return {
                "success": False,
                "error": f"Invalid value '{value}' for {column}. Valid: {valid}"
            }

    # Validate columns exist
    try:
        validate_columns_exist(supabase, table, list(data.keys()))
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # Perform update
    try:
        result = supabase.table(table).update(data).eq("company_id", company_id).execute()
        return {"success": True, "data": result.data}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ICP-specific validators
def validate_icp_tier(tier: str) -> bool:
    """Validate ICP tier value."""
    return tier in ["GOLD", "SILVER", "BRONZE"]


def validate_icp_score(score: int) -> bool:
    """Validate ICP score is in range."""
    return 0 <= score <= 100


def score_to_tier(score: int) -> str:
    """Convert ICP score to tier."""
    if score >= 85:
        return "GOLD"
    elif score >= 70:
        return "SILVER"
    return "BRONZE"
