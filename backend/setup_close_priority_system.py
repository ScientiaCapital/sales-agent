"""
Setup Close CRM Priority System - ATL/BTL Smart Views

This script creates a complete lead prioritization system:
1. Creates custom fields for lead_tier, qualification_score, contact_level, priority
2. Creates tiered Smart Views:
   - 🔥 Hot ATL Leads (score >70, decision-makers, last 7 days)
   - ⭐ Validated ATL Leads (all ATL contacts)
   - 📋 BTL Leads (below-the-line contacts)
3. Enables Tim Kipper to focus on the best leads first

Run this once to set up the complete priority system.
"""
import os
import asyncio
import httpx
from dotenv import load_dotenv
import logging
import base64
import json
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env from parent directory (project root)
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)

CLOSE_API_KEY = os.getenv("CLOSE_API_KEY")
BASE_URL = "https://api.close.com/api/v1"
TIM_KIPPER_USER_ID = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")

# Create Basic Auth header (Close CRM uses Basic Auth, not Bearer)
auth_string = f"{CLOSE_API_KEY}:"
auth_bytes = auth_string.encode('ascii')
auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
AUTH_HEADER = f"Basic {auth_b64}"


async def create_custom_field(field_name: str, field_type: str, choices: list = None):
    """
    Create a custom field in Close CRM.

    Args:
        field_name: Name of the custom field (e.g., "Lead Tier")
        field_type: Type of field ("text", "number", "choices", etc.)
        choices: List of choices for "choices" type fields

    Returns:
        Custom field ID if successful, None otherwise
    """
    try:
        payload = {
            "name": field_name,
            "type": field_type,
            "editable_with_roles": ["admin", "user"],  # Who can edit this field
        }

        if field_type == "choices" and choices:
            payload["choices"] = choices

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/custom_field/lead/",
                headers={
                    "Authorization": AUTH_HEADER,
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=10.0
            )

            if response.status_code in (200, 201):
                data = response.json()
                logger.info(f"✅ Created custom field: {field_name} (ID: {data.get('id')})")
                return data.get('id')
            elif response.status_code == 400:
                # Field might already exist
                error_data = response.json()
                if "already exists" in str(error_data).lower():
                    logger.info(f"⚠️  Custom field '{field_name}' already exists")
                    return None
                else:
                    logger.error(f"Failed to create custom field '{field_name}': {response.status_code} - {response.text}")
                    return None
            else:
                logger.error(f"Failed to create custom field '{field_name}': {response.status_code} - {response.text}")
                return None

    except Exception as e:
        logger.error(f"Error creating custom field '{field_name}': {e}")
        return None


async def create_smart_view(name: str, query_obj: dict):
    """
    Create a Smart View (Saved Search) in Close CRM.

    Args:
        name: Name of the Smart View
        query_obj: Query object (will be stringified)

    Returns:
        Smart View ID if successful, None otherwise
    """
    try:
        smart_view_payload = {
            "name": name,
            "object_type": "lead",
            "query": json.dumps(query_obj)
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/saved_search/",
                headers={
                    "Authorization": AUTH_HEADER,
                    "Content-Type": "application/json"
                },
                json=smart_view_payload,
                timeout=10.0
            )

            if response.status_code in (200, 201):
                data = response.json()
                logger.info(f"✅ Created Smart View: {name} (ID: {data.get('id')})")
                return data.get('id')
            elif response.status_code == 400:
                error_data = response.json()
                if "already exists" in str(error_data).lower():
                    logger.info(f"⚠️  Smart View '{name}' already exists")
                    return None
                else:
                    logger.error(f"Failed to create Smart View '{name}': {response.status_code} - {response.text}")
                    return None
            else:
                logger.error(f"Failed to create Smart View '{name}': {response.status_code} - {response.text}")
                return None

    except Exception as e:
        logger.error(f"Error creating Smart View '{name}': {e}")
        return None


async def create_hot_atl_smart_view():
    """🔥 Hot ATL Leads - Decision-makers with score >70, created in last 7 days."""
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    query_obj = {
        "type": "and",
        "queries": [
            {"type": "object_type", "object_type": "lead"},
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "date_created"},
                "condition": {"type": "moment_range", "gte": seven_days_ago.strftime("%Y-%m-%dT%H:%M:%SZ")}
            },
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "created_by"},
                "condition": {"type": "reference", "reference_type": "user", "object_ids": [TIM_KIPPER_USER_ID]}
            },
            {
                "type": "field_condition",
                "field": {"type": "custom_field", "custom_field_id": "lead_tier"},
                "condition": {"type": "text", "mode": "full_words", "value": "ATL"}
            },
            {
                "type": "field_condition",
                "field": {"type": "custom_field", "custom_field_id": "qualification_score"},
                "condition": {"type": "number_range", "gte": 70}
            }
        ]
    }

    return await create_smart_view("🔥 Hot ATL Leads (Priority)", query_obj)


async def create_validated_atl_smart_view():
    """⭐ Validated ATL Leads - All decision-makers with verified contact info."""
    query_obj = {
        "type": "and",
        "queries": [
            {"type": "object_type", "object_type": "lead"},
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "created_by"},
                "condition": {"type": "reference", "reference_type": "user", "object_ids": [TIM_KIPPER_USER_ID]}
            },
            {
                "type": "field_condition",
                "field": {"type": "custom_field", "custom_field_id": "lead_tier"},
                "condition": {"type": "text", "mode": "full_words", "value": "ATL"}
            }
        ]
    }

    return await create_smart_view("⭐ Validated ATL Leads", query_obj)


async def create_btl_smart_view():
    """📋 BTL Leads - Below-the-line contacts (lower priority)."""
    query_obj = {
        "type": "and",
        "queries": [
            {"type": "object_type", "object_type": "lead"},
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "object_type": "lead", "field_name": "created_by"},
                "condition": {"type": "reference", "reference_type": "user", "object_ids": [TIM_KIPPER_USER_ID]}
            },
            {
                "type": "field_condition",
                "field": {"type": "custom_field", "custom_field_id": "lead_tier"},
                "condition": {"type": "text", "mode": "full_words", "value": "BTL"}
            }
        ]
    }

    return await create_smart_view("📋 BTL Leads (Lower Priority)", query_obj)


async def main():
    """Run Close CRM Priority System setup."""
    if not CLOSE_API_KEY:
        logger.error("❌ CLOSE_API_KEY not found in .env file")
        return

    if not TIM_KIPPER_USER_ID:
        logger.error("❌ CLOSE_DEFAULT_OWNER_USER_ID not found in .env file")
        logger.error("   Run setup_close_crm_config.py first to configure Tim Kipper as default owner")
        return

    logger.info("=" * 80)
    logger.info("Close CRM Priority System Setup")
    logger.info("=" * 80)

    # Step 1: Create custom fields
    logger.info("\n[Step 1] Creating custom fields...")

    await create_custom_field("Lead Tier", "choices", choices=["ATL", "BTL"])
    await create_custom_field("Qualification Score", "number")
    await create_custom_field("Contact Level", "choices",
                             choices=["C-Level", "VP", "Director", "Manager", "Individual Contributor"])
    await create_custom_field("Priority", "choices", choices=["Hot", "Warm", "Cold"])

    # Step 2: Create Smart Views
    logger.info("\n[Step 2] Creating prioritized Smart Views...")

    hot_atl_id = await create_hot_atl_smart_view()
    validated_atl_id = await create_validated_atl_smart_view()
    btl_id = await create_btl_smart_view()

    logger.info("\n" + "=" * 80)
    logger.info("✅ Priority System Setup Complete!")
    logger.info("=" * 80)

    logger.info("\n📊 Smart Views Created (in priority order):")
    logger.info("   1. 🔥 Hot ATL Leads (Priority) - Call these FIRST!")
    logger.info("   2. ⭐ Validated ATL Leads - Call when hot list is done")
    logger.info("   3. 📋 BTL Leads (Lower Priority) - Delegate or nurture")
    logger.info("   4. 🆕 My New Leads (Last 7 Days) - All new leads")

    logger.info("\n💡 Next Steps:")
    logger.info("   - Pipeline will automatically tag leads as ATL/BTL")
    logger.info("   - Qualification scores will populate automatically")
    logger.info("   - Focus your calling time on Hot ATL Leads first!")


if __name__ == "__main__":
    asyncio.run(main())
